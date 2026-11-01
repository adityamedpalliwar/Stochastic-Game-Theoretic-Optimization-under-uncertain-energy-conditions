"""Reproducible CLI script for training the shared household demand and solar LSTM model.

Migrated from notebooks/02_demand_forecasting.ipynb.

Preserves:
- Exact 2-layer LSTM architecture: Input(24, 6) -> LSTM(32) -> Dense(16, relu) -> Dense(2, linear)
- Feature definitions: total_demand_kwh, solar_generation_kwh, hour_sin, hour_cos, dow_sin, dow_cos
- Target definitions: total_demand_kwh, solar_generation_kwh
- Chronological train (72%) / validation (8%) / test (20%) split
- Scaler fitting strictly on training data (validation and test quarantined)
- Random seed 42 and EarlyStopping(patience=5, restore_best_weights=True)
- Safe output handling: outputs to models/retrained/ by default without overwriting accepted baselines

Usage:
    python -m src.forecasting.train --output-dir models/retrained
"""

from __future__ import annotations

import argparse
from pathlib import Path
import random
import sys
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

try:
    import tensorflow as tf
except ImportError:
    tf = None

from src.data.preprocessing import create_lstm_sequences


FEATURE_COLUMNS: List[str] = [
    "total_demand_kwh",
    "solar_generation_kwh",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
]
TARGET_COLUMNS: List[str] = [
    "total_demand_kwh",
    "solar_generation_kwh",
]
DEFAULT_LOOKBACK_HOURS: int = 24
DEFAULT_TRAIN_FRACTION: float = 0.80
DEFAULT_VAL_FRACTION_OF_TRAIN: float = 0.10
DEFAULT_RANDOM_SEED: int = 42
DEFAULT_EPOCHS: int = 30
DEFAULT_BATCH_SIZE: int = 64
DEFAULT_EARLY_STOPPING_PATIENCE: int = 5


def set_reproducible_seeds(seed: int = DEFAULT_RANDOM_SEED) -> None:
    """Set random seeds across random, numpy, and TensorFlow."""
    random.seed(seed)
    np.random.seed(seed)
    if tf is not None:
        try:
            tf.keras.utils.set_random_seed(seed)
        except Exception:
            pass


def build_shared_lstm_model(
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
    num_features: int = len(FEATURE_COLUMNS),
    num_targets: int = len(TARGET_COLUMNS),
    lstm_units: int = 32,
    dense_units: int = 16,
    learning_rate: float = 0.001,
) -> Any:
    """Build and compile the authoritative multi-variable LSTM model architecture."""
    if tf is None:
        raise ImportError(
            "TensorFlow is required to build or train the LSTM model. "
            "Please install TensorFlow in a compatible Python environment (Python 3.10-3.11, see requirements-training.txt)."
        )

    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(lookback_hours, num_features)),
        tf.keras.layers.LSTM(lstm_units),
        tf.keras.layers.Dense(dense_units, activation="relu"),
        tf.keras.layers.Dense(num_targets, activation="linear"),
    ])

    optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)
    model.compile(optimizer=optimizer, loss="mse")
    return model


def train_lstm_model(
    data_path: Path | str = "data/processed/three_house_hourly_lstm_ready.csv",
    output_dir: Path | str = "models/retrained",
    epochs: int = DEFAULT_EPOCHS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
    seed: int = DEFAULT_RANDOM_SEED,
    allow_overwrite: bool = False,
    verbose: int = 1,
) -> Dict[str, Any]:
    """Execute complete end-to-end model training workflow and save artifacts."""
    if tf is None:
        raise ImportError(
            "TensorFlow is required to train the LSTM model. "
            "Please install TensorFlow in a compatible Python environment (Python 3.10-3.11, see requirements-training.txt)."
        )

    data_path = Path(data_path)
    output_dir = Path(output_dir)

    if not data_path.exists():
        raise FileNotFoundError(f"Input hourly dataset not found: {data_path}")

    # Safety check on overwriting accepted production artifacts
    accepted_model_path = Path("data/processed/lstm_model.keras").resolve()
    target_model_path = (output_dir / "lstm_model.keras").resolve()

    if target_model_path == accepted_model_path and not allow_overwrite:
        raise PermissionError(
            f"Target output path '{target_model_path}' matches the accepted production model. "
            "Overwriting accepted baseline artifacts is prohibited by default. "
            "Use a different --output-dir (e.g. models/retrained) or explicitly pass --allow-overwrite."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    set_reproducible_seeds(seed)

    print(f"Loading hourly panel from {data_path}...")
    hourly = pd.read_csv(data_path, parse_dates=["timestamp"])

    print(f"Generating sequences (lookback={lookback_hours}h, train_frac={DEFAULT_TRAIN_FRACTION})...")
    seq, feature_scaler, target_scaler = create_lstm_sequences(
        hourly_df=hourly,
        feature_columns=FEATURE_COLUMNS,
        target_columns=TARGET_COLUMNS,
        lookback_hours=lookback_hours,
        train_fraction=DEFAULT_TRAIN_FRACTION,
        val_fraction_of_train=DEFAULT_VAL_FRACTION_OF_TRAIN,
    )

    print("Building LSTM model...")
    model = build_shared_lstm_model(
        lookback_hours=lookback_hours,
        num_features=len(FEATURE_COLUMNS),
        num_targets=len(TARGET_COLUMNS),
    )

    stop_early = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss",
        patience=DEFAULT_EARLY_STOPPING_PATIENCE,
        restore_best_weights=True,
    )

    print(f"Fitting model (epochs={epochs}, batch_size={batch_size}, shuffle=False)...")
    history = model.fit(
        seq["X_train"],
        seq["y_train"],
        validation_data=(seq["X_val"], seq["y_val"]),
        epochs=epochs,
        batch_size=batch_size,
        shuffle=False,
        callbacks=[stop_early],
        verbose=verbose,
    )

    print("Evaluating predictions on held-out test split...")
    predicted_scaled = model.predict(seq["X_test"], verbose=0)
    predicted_raw_unclipped = target_scaler.inverse_transform(predicted_scaled)
    actual_raw = seq["test_actual_raw"].astype(float)
    baseline_raw = seq["baseline_test"].astype(float)

    predicted_raw = np.maximum(0.0, predicted_raw_unclipped)

    test_predictions = pd.DataFrame({
        "house_id": seq["test_house_id"],
        "forecast_timestamp": pd.to_datetime(seq["test_target_timestamp"]),
        "actual_demand_kwh": actual_raw[:, 0],
        "predicted_demand_kwh": predicted_raw[:, 0],
        "actual_solar_generation_kwh": actual_raw[:, 1],
        "predicted_solar_generation_kwh": predicted_raw[:, 1],
    }).sort_values(["house_id", "forecast_timestamp"]).reset_index(drop=True)

    # Save artifacts
    saved_model_path = output_dir / "lstm_model.keras"
    saved_scaler_path = output_dir / "lstm_scaler.joblib"
    saved_preds_path = output_dir / "test_predictions.csv"
    saved_seq_path = output_dir / "lstm_sequences.npz"

    print(f"Saving retrained model to {saved_model_path}...")
    model.save(saved_model_path)

    print(f"Saving target scaler to {saved_scaler_path}...")
    # Wrap target_scaler with feature_scaler attribute to preserve predict.py compatibility
    setattr(target_scaler, "feature_scaler", feature_scaler)
    joblib.dump(target_scaler, saved_scaler_path)

    print(f"Saving test predictions to {saved_preds_path}...")
    test_predictions.to_csv(saved_preds_path, index=False)

    print(f"Saving sequence matrices to {saved_seq_path}...")
    np.savez_compressed(saved_seq_path, **seq)

    # Calculate summary metrics
    mae_demand = mean_absolute_error(actual_raw[:, 0], predicted_raw[:, 0])
    rmse_demand = float(np.sqrt(mean_squared_error(actual_raw[:, 0], predicted_raw[:, 0])))
    mae_solar = mean_absolute_error(actual_raw[:, 1], predicted_raw[:, 1])
    rmse_solar = float(np.sqrt(mean_squared_error(actual_raw[:, 1], predicted_raw[:, 1])))

    summary = {
        "output_dir": str(output_dir),
        "epochs_trained": len(history.history["loss"]),
        "final_train_loss": float(history.history["loss"][-1]),
        "final_val_loss": float(history.history["val_loss"][-1]),
        "test_mae_demand_kwh": float(mae_demand),
        "test_rmse_demand_kwh": float(rmse_demand),
        "test_mae_solar_kwh": float(mae_solar),
        "test_rmse_solar_kwh": float(rmse_solar),
        "model_path": str(saved_model_path),
        "scaler_path": str(saved_scaler_path),
    }

    print("\nTraining complete! Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    return summary


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Reproducible LSTM Model Training CLI Script",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data-path",
        type=Path,
        default=Path("data/processed/three_house_hourly_lstm_ready.csv"),
        help="Path to hourly LSTM-ready CSV dataset",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("models/retrained"),
        help="Output directory to save retrained model and artifacts",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=DEFAULT_EPOCHS,
        help="Maximum training epochs",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Batch size for gradient descent",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=DEFAULT_LOOKBACK_HOURS,
        help="Lookback sequence horizon in hours",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_RANDOM_SEED,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--allow-overwrite",
        action="store_true",
        help="Explicitly permit overwriting accepted baseline artifacts if output-dir is data/processed",
    )
    return parser.parse_args(args)


def main() -> None:
    """Entry point for CLI execution."""
    args = parse_args()
    if tf is None:
        print(
            "ERROR: TensorFlow is not installed in this environment.\n"
            "Model retraining requires TensorFlow (Python 3.10-3.11 recommended).\n"
            "Please install requirements from requirements-training.txt in a compatible Python environment.\n"
            "For inference and simulation, use the pre-trained accepted model (no TensorFlow required).",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        train_lstm_model(
            data_path=args.data_path,
            output_dir=args.output_dir,
            epochs=args.epochs,
            batch_size=args.batch_size,
            lookback_hours=args.lookback,
            seed=args.seed,
            allow_overwrite=args.allow_overwrite,
        )
    except Exception as e:
        print(f"ERROR: Training failed with exception: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

