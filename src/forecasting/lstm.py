
"""LSTM model construction, training, evaluation, and NumPy inference
for household demand and solar forecasting.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Dict, List, Union

import h5py
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

try:
    import tensorflow as tf
except ImportError:
    tf = None


def build_lstm_model(
    lookback_hours: int = 24,
    num_features: int = 6,
    num_outputs: int = 2,
    lstm_units: int = 32,
    dense_units: int = 16,
    learning_rate: float = 0.001,
) -> tf.keras.Model:
    """Build and compile the multi-variable LSTM model.

    TensorFlow is required only when building or training a model.
    """
    if tf is None:
        raise ImportError(
            "TensorFlow is required to build or train the LSTM model. "
            "Install a compatible TensorFlow version in your environment."
        )

    model = tf.keras.Sequential([
        tf.keras.layers.Input(
            shape=(lookback_hours, num_features)
        ),
        tf.keras.layers.LSTM(lstm_units),
        tf.keras.layers.Dense(
            dense_units,
            activation="relu",
        ),
        tf.keras.layers.Dense(
            num_outputs,
            activation="linear",
        ),
    ])

    optimizer = tf.keras.optimizers.Adam(
        learning_rate=learning_rate
    )
    model.compile(optimizer=optimizer, loss="mse")

    return model


def evaluate_forecasts(
    predictions_df: pd.DataFrame,
    baseline_predictions_df: pd.DataFrame,
) -> pd.DataFrame:
    """Evaluate LSTM and persistence forecasts using MAE and RMSE."""

    def _evaluate(
        frame: pd.DataFrame,
        model_name: str,
    ) -> List[Dict]:
        rows = []

        groups = [("overall", frame)] + list(
            frame.groupby("house_id", sort=True)
        )

        targets = [
            (
                "total_demand_kwh",
                "actual_demand_kwh",
                "predicted_demand_kwh",
            ),
            (
                "solar_generation_kwh",
                "actual_solar_generation_kwh",
                "predicted_solar_generation_kwh",
            ),
        ]

        for scope, subset in groups:
            for target_name, actual_col, pred_col in targets:
                actual_vals = subset[actual_col].to_numpy(
                    dtype=float
                )
                pred_vals = subset[pred_col].to_numpy(
                    dtype=float
                )

                rows.append({
                    "scope": scope,
                    "house_id": (
                        "ALL" if scope == "overall" else scope
                    ),
                    "model": model_name,
                    "target": target_name,
                    "n_test_hours": len(subset),
                    "mae_kwh": mean_absolute_error(
                        actual_vals,
                        pred_vals,
                    ),
                    "rmse_kwh": float(
                        np.sqrt(
                            mean_squared_error(
                                actual_vals,
                                pred_vals,
                            )
                        )
                    ),
                })

        return rows

    rows = _evaluate(
        predictions_df,
        "shared_lstm_24h",
    ) + _evaluate(
        baseline_predictions_df,
        "persistence_last_hour",
    )

    return pd.DataFrame(rows)


class LSTMWeights:
    """Encapsulates weights extracted from a saved Keras model."""

    def __init__(
        self,
        w_lstm_kernel: np.ndarray,
        w_lstm_recurrent: np.ndarray,
        w_lstm_bias: np.ndarray,
        w_dense1_kernel: np.ndarray,
        w_dense1_bias: np.ndarray,
        w_dense2_kernel: np.ndarray,
        w_dense2_bias: np.ndarray,
    ) -> None:
        self.w_lstm_kernel = w_lstm_kernel.astype(np.float32)
        self.w_lstm_recurrent = w_lstm_recurrent.astype(np.float32)
        self.w_lstm_bias = w_lstm_bias.astype(np.float32)
        self.w_dense1_kernel = w_dense1_kernel.astype(np.float32)
        self.w_dense1_bias = w_dense1_bias.astype(np.float32)
        self.w_dense2_kernel = w_dense2_kernel.astype(np.float32)
        self.w_dense2_bias = w_dense2_bias.astype(np.float32)

    @classmethod
    def from_keras_file(
        cls,
        model_path: Union[str, Path],
    ) -> LSTMWeights:
        """Extract LSTM and Dense weights from a .keras archive."""
        path = Path(model_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Model file not found: {path}"
            )

        with zipfile.ZipFile(path, "r") as archive:
            if "model.weights.h5" not in archive.namelist():
                raise ValueError(
                    "model.weights.h5 not found in .keras archive"
                )

            weights_bytes = archive.read("model.weights.h5")

        with h5py.File(io.BytesIO(weights_bytes), "r") as h5:
            w_kernel = h5["layers/lstm/cell/vars/0"][:]
            w_recurrent = h5["layers/lstm/cell/vars/1"][:]
            w_bias = h5["layers/lstm/cell/vars/2"][:]

            w_d1_k = h5["layers/dense/vars/0"][:]
            w_d1_b = h5["layers/dense/vars/1"][:]

            w_d2_k = h5["layers/dense_1/vars/0"][:]
            w_d2_b = h5["layers/dense_1/vars/1"][:]

        return cls(
            w_lstm_kernel=w_kernel,
            w_lstm_recurrent=w_recurrent,
            w_lstm_bias=w_bias,
            w_dense1_kernel=w_d1_k,
            w_dense1_bias=w_d1_b,
            w_dense2_kernel=w_d2_k,
            w_dense2_bias=w_d2_b,
        )


def _sigmoid(x: np.ndarray) -> np.ndarray:
    """Numerically stable sigmoid function."""
    result = np.empty_like(x, dtype=np.float32)
    positive = x >= 0

    result[positive] = 1.0 / (
        1.0 + np.exp(-x[positive])
    )

    exp_x = np.exp(x[~positive])
    result[~positive] = exp_x / (
        1.0 + exp_x
    )

    return result


def predict_lstm_numpy(
    sequences: np.ndarray,
    weights: LSTMWeights,
) -> np.ndarray:
    """Run LSTM inference using NumPy.

    Accepts either:
      - (24, num_features)
      - (batch_size, 24, num_features)

    The required number of input features is inferred from the
    saved LSTM kernel. For your current model, it is six.

    Returns scaled predictions with shape (2,) for a single
    sequence or (batch_size, 2) for a batch.
    """
    seq = np.asarray(sequences, dtype=np.float32)
    single_sample = False

    # Infer the expected feature count from the trained model.
    expected_features = weights.w_lstm_kernel.shape[0]

    if seq.ndim == 2:
        if seq.shape != (24, expected_features):
            raise ValueError(
                f"Expected shape (24, {expected_features}), "
                f"got {seq.shape}"
            )

        seq = seq[np.newaxis, :, :]
        single_sample = True

    elif seq.ndim == 3:
        if seq.shape[1:] != (24, expected_features):
            raise ValueError(
                f"Expected shape (*, 24, {expected_features}), "
                f"got {seq.shape}"
            )

    else:
        raise ValueError(
            f"Expected a 2D or 3D sequence array, got {seq.shape}"
        )

    batch_size, timesteps, _ = seq.shape

    hidden_units = weights.w_lstm_recurrent.shape[0]

    h = np.zeros(
        (batch_size, hidden_units),
        dtype=np.float32,
    )
    c = np.zeros(
        (batch_size, hidden_units),
        dtype=np.float32,
    )

    w_k = weights.w_lstm_kernel
    w_r = weights.w_lstm_recurrent
    w_b = weights.w_lstm_bias
    u = hidden_units

    # Forward pass through the LSTM.
    for t in range(timesteps):
        xt = seq[:, t, :]

        z = (
            np.dot(xt, w_k)
            + np.dot(h, w_r)
            + w_b
        )

        # Keras LSTM gate order: input, forget, candidate, output.
        i = _sigmoid(z[:, :u])
        f = _sigmoid(z[:, u:2 * u])
        c_candidate = np.tanh(z[:, 2 * u:3 * u])
        o = _sigmoid(z[:, 3 * u:4 * u])

        c = f * c + i * c_candidate
        h = o * np.tanh(c)

    # Dense layer with ReLU activation.
    dense1 = np.maximum(
        0.0,
        np.dot(h, weights.w_dense1_kernel)
        + weights.w_dense1_bias,
    )

    # Final linear output layer.
    out = (
        np.dot(dense1, weights.w_dense2_kernel)
        + weights.w_dense2_bias
    )

    return out[0] if single_sample else out
