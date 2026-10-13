"""LSTM model construction, training, and evaluation for household demand and solar forecasting."""

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import MinMaxScaler
import tensorflow as tf


def build_lstm_model(
    lookback_hours: int = 24,
    num_features: int = 6,
    num_outputs: int = 2,
    lstm_units: int = 32,
    dense_units: int = 16,
    learning_rate: float = 0.001,
) -> tf.keras.Model:
    """Build and compile the multi-variable LSTM model.

    Args:
        lookback_hours: Window length of past observations.
        num_features: Number of input features per time step (e.g. 6 with cyclical features).
        num_outputs: Number of target outputs (e.g. demand and solar).
        lstm_units: Number of hidden units in LSTM layer.
        dense_units: Units in intermediate dense layer.
        learning_rate: Adam optimizer learning rate.

    Returns:
        Compiled Keras Model.
    """
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(lookback_hours, num_features)),
        tf.keras.layers.LSTM(lstm_units),
        tf.keras.layers.Dense(dense_units, activation="relu"),
        tf.keras.layers.Dense(num_outputs, activation="linear"),
    ])
    optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)
    model.compile(optimizer=optimizer, loss="mse")
    return model


def evaluate_forecasts(
    predictions_df: pd.DataFrame,
    baseline_predictions_df: pd.DataFrame,
) -> pd.DataFrame:
    """Evaluate predictions against actuals and compute MAE / RMSE across overall and per-house scopes.

    Args:
        predictions_df: DataFrame with ['house_id', 'actual_demand_kwh', 'predicted_demand_kwh',
                                       'actual_solar_generation_kwh', 'predicted_solar_generation_kwh'].
        baseline_predictions_df: DataFrame with persistence predictions.

    Returns:
        DataFrame of evaluation metrics.
    """
    def _evaluate(frame: pd.DataFrame, model_name: str) -> List[Dict]:
        rows = []
        groups = [("overall", frame)] + list(frame.groupby("house_id", sort=True))
        for scope, subset in groups:
            for target_name, actual_col, pred_col in [
                ("total_demand_kwh", "actual_demand_kwh", "predicted_demand_kwh"),
                ("solar_generation_kwh", "actual_solar_generation_kwh", "predicted_solar_generation_kwh"),
            ]:
                actual_vals = subset[actual_col].to_numpy(dtype=float)
                pred_vals = subset[pred_col].to_numpy(dtype=float)
                rows.append({
                    "scope": scope,
                    "house_id": "ALL" if scope == "overall" else scope,
                    "model": model_name,
                    "target": target_name,
                    "n_test_hours": len(subset),
                    "mae_kwh": mean_absolute_error(actual_vals, pred_vals),
                    "rmse_kwh": float(np.sqrt(mean_squared_error(actual_vals, pred_vals))),
                })
        return rows

    rows = _evaluate(predictions_df, "shared_lstm_24h") + _evaluate(
        baseline_predictions_df, "persistence_last_hour"
    )
    return pd.DataFrame(rows)
