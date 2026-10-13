
"""Forecasting interface for next-hour household energy prediction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import warnings

import joblib
import numpy as np
import pandas as pd

from src.forecasting.lstm import LSTMWeights, predict_lstm_numpy


@dataclass
class ForecastResult:
    """Holds a single one-step-ahead forecast result."""

    house_id: str
    forecast_timestamp: pd.Timestamp
    predicted_demand_kwh: float
    predicted_solar_generation_kwh: float
    actual_demand_kwh: Optional[float]
    actual_solar_generation_kwh: Optional[float]
    is_held_out_period: bool

    @property
    def demand_error_kwh(self) -> Optional[float]:
        if self.actual_demand_kwh is not None:
            return self.actual_demand_kwh - self.predicted_demand_kwh
        return None

    @property
    def solar_error_kwh(self) -> Optional[float]:
        if self.actual_solar_generation_kwh is not None:
            return (
                self.actual_solar_generation_kwh
                - self.predicted_solar_generation_kwh
            )
        return None

    def to_dict(self) -> Dict[str, Union[str, float, None, bool]]:
        return {
            "house_id": self.house_id,
            "forecast_timestamp": str(self.forecast_timestamp),
            "predicted_demand_kwh": round(self.predicted_demand_kwh, 4),
            "predicted_solar_generation_kwh": round(
                self.predicted_solar_generation_kwh, 4
            ),
            "actual_demand_kwh": (
                round(self.actual_demand_kwh, 4)
                if self.actual_demand_kwh is not None else None
            ),
            "actual_solar_generation_kwh": (
                round(self.actual_solar_generation_kwh, 4)
                if self.actual_solar_generation_kwh is not None else None
            ),
            "demand_error_kwh": (
                round(self.demand_error_kwh, 4)
                if self.demand_error_kwh is not None else None
            ),
            "solar_error_kwh": (
                round(self.solar_error_kwh, 4)
                if self.solar_error_kwh is not None else None
            ),
            "is_held_out_period": self.is_held_out_period,
        }


class EnergyForecaster:
    """End-to-end interface for LSTM energy forecasting."""

    FEATURE_COLUMNS = [
        "total_demand_kwh",
        "solar_generation_kwh",
        "hour_sin",
        "hour_cos",
        "dow_sin",
        "dow_cos",
    ]
    TARGET_COLUMNS = [
        "total_demand_kwh",
        "solar_generation_kwh",
    ]
    LOOKBACK_HOURS = 24

    def __init__(
        self,
        data_path: Union[str, Path] = (
            "data/processed/three_house_hourly_lstm_ready.csv"
        ),
        model_path: Union[str, Path] = (
            "data/processed/lstm_model.keras"
        ),
        scaler_path: Union[str, Path] = (
            "data/processed/lstm_scaler.joblib"
        ),
    ) -> None:
        self.data_path = Path(data_path)
        self.model_path = Path(model_path)
        self.scaler_path = Path(scaler_path)

        for path, label in [
            (self.data_path, "Hourly dataset"),
            (self.model_path, "Model file"),
            (self.scaler_path, "Scaler file"),
        ]:
            if not path.exists():
                raise FileNotFoundError(f"{label} not found: {path}")

        self.df = pd.read_csv(
            self.data_path,
            parse_dates=["timestamp"],
        )
        self.df = self.df.sort_values(
            ["house_id", "timestamp"]
        ).reset_index(drop=True)

        missing = set(self.FEATURE_COLUMNS) - set(self.df.columns)
        if missing:
            raise ValueError(
                f"Hourly dataset is missing model features: {sorted(missing)}"
            )

        self.weights = LSTMWeights.from_keras_file(self.model_path)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            scaler_obj = joblib.load(self.scaler_path)

        self.data_min_ = np.asarray(
            scaler_obj.data_min_, dtype=np.float32
        )
        self.data_max_ = np.asarray(
            scaler_obj.data_max_, dtype=np.float32
        )
        self.scale_range_ = self.data_max_ - self.data_min_

        if len(self.data_min_) != 2:
            raise ValueError(
                "Expected a two-feature scaler for demand and solar; "
                f"found {len(self.data_min_)} features."
            )

        if np.any(self.scale_range_ <= 0):
            raise ValueError("Scaler features have zero or negative range.")

        expected_features = self.weights.w_lstm_kernel.shape[0]
        if expected_features != len(self.FEATURE_COLUMNS):
            raise ValueError(
                f"The saved LSTM expects {expected_features} features, "
                f"but this forecaster prepares {len(self.FEATURE_COLUMNS)}."
            )

        self.houses = sorted(self.df["house_id"].unique())

        first_house_times = (
            self.df.loc[
                self.df["house_id"] == self.houses[0], "timestamp"
            ]
            .reset_index(drop=True)
        )
        split_idx = int(len(first_house_times) * 0.8)
        self.test_start_timestamp = first_house_times.iloc[split_idx]

    def scale(self, values: np.ndarray) -> np.ndarray:
        """Scale demand and solar using the existing two-feature scaler."""
        values = np.asarray(values, dtype=np.float32)
        return (values - self.data_min_) / self.scale_range_

    def inverse_scale(self, scaled: np.ndarray) -> np.ndarray:
        """Convert scaled demand and solar back to physical units."""
        scaled = np.asarray(scaled, dtype=np.float32)
        return scaled * self.scale_range_ + self.data_min_

    @staticmethod
    def _time_features(timestamps: pd.DatetimeIndex) -> np.ndarray:
        """Create cyclic hour-of-day and day-of-week features."""
        hour = timestamps.hour.to_numpy(dtype=np.float32)
        dow = timestamps.dayofweek.to_numpy(dtype=np.float32)

        hour_angle = 2.0 * np.pi * hour / 24.0
        dow_angle = 2.0 * np.pi * dow / 7.0

        return np.column_stack([
            np.sin(hour_angle),
            np.cos(hour_angle),
            np.sin(dow_angle),
            np.cos(dow_angle),
        ]).astype(np.float32)

    def get_lookback_window(
        self,
        house_id: str,
        forecast_timestamp: Union[str, pd.Timestamp],
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Return the preceding 24 hours of six model features."""
        ts = pd.to_datetime(forecast_timestamp)

        house_df = (
            self.df.loc[self.df["house_id"] == house_id]
            .set_index("timestamp")
            .sort_index()
        )

        if ts not in house_df.index:
            raise KeyError(f"Timestamp {ts} not found for {house_id}")

        idx_loc = house_df.index.get_loc(ts)
        if isinstance(idx_loc, slice):
            idx_loc = idx_loc.start

        if idx_loc < self.LOOKBACK_HOURS:
            raise ValueError(
                f"Insufficient lookback history at {ts}; "
                f"need {self.LOOKBACK_HOURS} prior hours."
            )

        window_df = house_df.iloc[
            idx_loc - self.LOOKBACK_HOURS:idx_loc
        ]

        if len(window_df) != self.LOOKBACK_HOURS:
            raise ValueError(
                f"Expected {self.LOOKBACK_HOURS} lookback rows, "
                f"got {len(window_df)}."
            )

        energy_raw = window_df[self.TARGET_COLUMNS].to_numpy(
            dtype=np.float32
        )
        energy_scaled = self.scale(energy_raw)

        time_features = self._time_features(
            pd.DatetimeIndex(window_df.index)
        )

        window_scaled = np.column_stack([
            energy_scaled,
            time_features,
        ]).astype(np.float32)

        actual_row = house_df.iloc[idx_loc][
            self.TARGET_COLUMNS
        ].to_numpy(dtype=np.float32)

        return window_scaled, actual_row

    def predict_next_hour(
        self,
        house_id: str,
        forecast_timestamp: Union[str, pd.Timestamp],
    ) -> ForecastResult:
        """Forecast demand and solar generation for one household."""
        ts = pd.to_datetime(forecast_timestamp)

        window_scaled, actual_raw = self.get_lookback_window(
            house_id, ts
        )

        pred_scaled = predict_lstm_numpy(
            window_scaled, self.weights
        )

        pred_raw = self.inverse_scale(pred_scaled)
        pred_clipped = np.maximum(0.0, pred_raw)

        return ForecastResult(
            house_id=house_id,
            forecast_timestamp=ts,
            predicted_demand_kwh=float(pred_clipped[0]),
            predicted_solar_generation_kwh=float(pred_clipped[1]),
            actual_demand_kwh=(
                float(actual_raw[0]) if actual_raw is not None else None
            ),
            actual_solar_generation_kwh=(
                float(actual_raw[1]) if actual_raw is not None else None
            ),
            is_held_out_period=bool(
                ts >= self.test_start_timestamp
            ),
        )

    def predict_all_households(
        self,
        forecast_timestamp: Union[str, pd.Timestamp],
    ) -> Dict[str, ForecastResult]:
        """Forecast all households at the specified timestamp."""
        ts = pd.to_datetime(forecast_timestamp)
        return {
            house_id: self.predict_next_hour(house_id, ts)
            for house_id in self.houses
        }
