"""Evaluation metrics and baseline comparisons.

Baseline metrics preserved from evaluation_metrics.csv:
- Demand: LSTM MAE 0.4953 kWh vs Persistence MAE 0.4310 kWh (Persistence is superior on demand).
- Solar:  LSTM MAE 0.0730 kWh vs Persistence MAE 0.0864 kWh (LSTM is superior on solar).

Note: The LSTM baseline is a preliminary shared model needing further tuning.
We do NOT claim that the LSTM is superior to persistence for demand.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd


def mean_absolute_error(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Compute Mean Absolute Error (MAE) in original units."""
    a = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    if len(a) != len(p):
        raise ValueError(f"Length mismatch: {len(a)} vs {len(p)}")
    return float(np.mean(np.abs(a - p)))


def root_mean_squared_error(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Compute Root Mean Squared Error (RMSE) in original units."""
    a = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    if len(a) != len(p):
        raise ValueError(f"Length mismatch: {len(a)} vs {len(p)}")
    return float(np.sqrt(np.mean((a - p) ** 2)))


def load_baseline_evaluation_metrics(
    metrics_path: Union[str, Path] = "data/processed/evaluation_metrics.csv",
) -> pd.DataFrame:
    """Load the existing evaluated metrics table."""
    path = Path(metrics_path)
    if not path.exists():
        raise FileNotFoundError(f"Evaluation metrics file not found: {path}")
    return pd.read_csv(path)


def format_evaluation_summary_table(metrics_df: pd.DataFrame) -> pd.DataFrame:
    """Format evaluation table for supervisor presentation."""
    df = metrics_df.copy()
    overall = df.loc[df["scope"] == "overall"].copy()
    overall["target_label"] = overall["target"].replace({
        "total_demand_kwh": "Total Demand (kWh)",
        "solar_generation_kwh": "Solar Generation (kWh)",
    })
    overall["model_label"] = overall["model"].replace({
        "shared_lstm_24h": "Shared LSTM (24h lookback)",
        "persistence_last_hour": "Persistence (Last Observed Hour)",
    })
    return overall[["target_label", "model_label", "n_test_hours", "mae_kwh", "rmse_kwh"]].sort_values(
        ["target_label", "model_label"]
    ).reset_index(drop=True)
