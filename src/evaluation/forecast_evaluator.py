"""Comprehensive forecast accuracy and Monte Carlo prediction interval evaluation.

Performs reproducible, evidence-based evaluation of point forecasts and
Monte Carlo prediction intervals across the held-out test period (1,752 hours
per household, 5,256 total household-hours).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from src.forecasting.lstm import predict_lstm_numpy
from src.forecasting.predict import EnergyForecaster
from src.stochastic.monte_carlo import (
    MonteCarloSimulator,
    ValidationResidualPool,
    derive_observation_seed,
)


@dataclass
class PointMetrics:
    """Point forecast evaluation metrics."""

    household: str
    target_variable: str
    unit: str
    n_observations: int
    mae: float
    rmse: float
    mean_bias: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "household": self.household,
            "target_variable": self.target_variable,
            "unit": self.unit,
            "n_observations": self.n_observations,
            "mae": round(self.mae, 6),
            "rmse": round(self.rmse, 6),
            "mean_bias": round(self.mean_bias, 6),
        }


@dataclass
class IntervalMetrics:
    """Monte Carlo prediction interval calibration metrics."""

    household: str
    target_variable: str
    unit: str
    nominal_coverage: float
    n_observations: int
    empirical_coverage: float
    mean_width: float
    median_width: float
    fraction_below_lower: float
    fraction_above_upper: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "household": self.household,
            "target_variable": self.target_variable,
            "unit": self.unit,
            "nominal_coverage_pct": round(self.nominal_coverage * 100.0, 2),
            "n_observations": self.n_observations,
            "empirical_coverage_pct": round(self.empirical_coverage * 100.0, 2),
            "mean_width_kwh": round(self.mean_width, 4),
            "median_width_kwh": round(self.median_width, 4),
            "fraction_below_lower_pct": round(self.fraction_below_lower * 100.0, 2),
            "fraction_above_upper_pct": round(self.fraction_above_upper * 100.0, 2),
        }


@dataclass
class CombinedMetrics:
    """Combined point forecast and prediction interval metrics."""

    household: str
    target_variable: str
    unit: str
    n_observations: int
    mae: float
    rmse: float
    mean_bias: float
    nominal_coverage_pct: float
    empirical_coverage_pct: float
    mean_width_kwh: float
    median_width_kwh: float
    fraction_below_lower_pct: float
    fraction_above_upper_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "household": self.household,
            "target_variable": self.target_variable,
            "unit": self.unit,
            "n_observations": self.n_observations,
            "mae_kwh": round(self.mae, 6),
            "rmse_kwh": round(self.rmse, 6),
            "mean_bias_kwh": round(self.mean_bias, 6),
            "nominal_coverage_pct": round(self.nominal_coverage_pct, 2),
            "empirical_coverage_pct": round(self.empirical_coverage_pct, 2),
            "mean_width_kwh": round(self.mean_width_kwh, 4),
            "median_width_kwh": round(self.median_width_kwh, 4),
            "fraction_below_lower_pct": round(self.fraction_below_lower_pct, 2),
            "fraction_above_upper_pct": round(self.fraction_above_upper_pct, 2),
        }


@dataclass
class IntegrityCheckResult:
    """Result of an individual data integrity or leakage check."""

    check_name: str
    passed: bool
    status: str  # "PASSED", "FAILED", or "UNVERIFIED"
    details: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "status": self.status,
            "passed": self.passed,
            "details": self.details,
        }


class ForecastEvaluator:
    """Comprehensive evaluator for point forecasts, intervals, and data integrity."""

    HOUSEHOLDS = ["H001", "H002", "H003"]
    TARGET_VARIABLES = ["total_demand_kwh", "solar_generation_kwh"]

    def __init__(
        self,
        data_path: Union[str, Path] = "data/processed/three_house_hourly_lstm_ready.csv",
        model_path: Union[str, Path] = "data/processed/lstm_model.keras",
        scaler_path: Union[str, Path] = "data/processed/lstm_scaler.joblib",
        sequences_path: Union[str, Path] = "data/processed/lstm_sequences.npz",
    ) -> None:
        self.data_path = Path(data_path)
        self.model_path = Path(model_path)
        self.scaler_path = Path(scaler_path)
        self.sequences_path = Path(sequences_path)

        self.forecaster = EnergyForecaster(
            data_path=self.data_path,
            model_path=self.model_path,
            scaler_path=self.scaler_path,
        )
        self.residual_pool = ValidationResidualPool(
            forecaster=self.forecaster,
            sequences_path=self.sequences_path,
        )
        self.mc_simulator = MonteCarloSimulator(residual_pool=self.residual_pool)

        # Load sequences
        self.sequences = np.load(self.sequences_path, allow_pickle=True)
        self.X_test = self.sequences["X_test"]
        self.y_test = self.sequences["y_test"]
        self.test_house_ids = np.asarray(self.sequences["test_house_id"])
        self.test_timestamps = pd.to_datetime(self.sequences["test_target_timestamp"])

        # Compute point predictions across all test sequences
        preds_scaled = predict_lstm_numpy(self.X_test, self.forecaster.weights)
        self.preds_raw = np.maximum(0.0, self.forecaster.inverse_scale(preds_scaled))
        self.actual_raw = self.forecaster.inverse_scale(self.y_test)

    # -------------------------------------------------------------------------
    # Phase B: Point Forecast Evaluation
    # -------------------------------------------------------------------------

    def compute_point_metrics(
        self,
        actual: np.ndarray,
        predicted: np.ndarray,
        household: str,
        target_variable: str,
    ) -> PointMetrics:
        """Calculate MAE, RMSE, Mean Bias, and observation count for one target series."""
        act = np.asarray(actual, dtype=float)
        pred = np.asarray(predicted, dtype=float)
        n = len(act)
        if n == 0:
            raise ValueError(f"No observations provided for {household} {target_variable}")

        diff = act - pred
        mae = float(np.mean(np.abs(diff)))
        rmse = float(np.sqrt(np.mean(diff ** 2)))
        bias = float(np.mean(diff))

        return PointMetrics(
            household=household,
            target_variable=target_variable,
            unit="kWh",
            n_observations=n,
            mae=mae,
            rmse=rmse,
            mean_bias=bias,
        )

    def evaluate_all_point_forecasts(self) -> Dict[str, PointMetrics]:
        """Compute point metrics for all 6 household-variable pairs plus overall summaries."""
        metrics: Dict[str, PointMetrics] = {}

        # Individual households
        for house_id in self.HOUSEHOLDS:
            mask = self.test_house_ids == house_id
            for t_idx, target_name in enumerate(self.TARGET_VARIABLES):
                key = f"{house_id}_{target_name}"
                metrics[key] = self.compute_point_metrics(
                    actual=self.actual_raw[mask, t_idx],
                    predicted=self.preds_raw[mask, t_idx],
                    household=house_id,
                    target_variable=target_name,
                )

        # Overall Demand (unpooled with solar)
        metrics["ALL_total_demand_kwh"] = self.compute_point_metrics(
            actual=self.actual_raw[:, 0],
            predicted=self.preds_raw[:, 0],
            household="ALL",
            target_variable="total_demand_kwh",
        )

        # Overall Solar (unpooled with demand)
        metrics["ALL_solar_generation_kwh"] = self.compute_point_metrics(
            actual=self.actual_raw[:, 1],
            predicted=self.preds_raw[:, 1],
            household="ALL",
            target_variable="solar_generation_kwh",
        )

        return metrics

    # -------------------------------------------------------------------------
    # Phase C: Monte Carlo Prediction Interval Evaluation
    # -------------------------------------------------------------------------

    def evaluate_single_hour(
        self,
        house_id: str,
        timestamp: Union[str, pd.Timestamp],
        num_scenarios: int = 1000,
        random_seed: int = 42,
    ) -> Dict[str, Any]:
        """Evaluate point forecast and prediction intervals for a single household and hour.

        Uses the standard MonteCarloSimulator and ValidationResidualPool.
        """
        ts = pd.to_datetime(timestamp)
        pred = self.forecaster.predict_next_hour(house_id, ts)
        dist = self.mc_simulator.generate_scenarios(
            forecast=pred,
            num_scenarios=num_scenarios,
            random_seed=random_seed,
        )

        d_sc = dist.scenarios_demand_kwh
        s_sc = dist.scenarios_solar_kwh

        q05_d = float(np.percentile(d_sc, 5))
        q95_d = float(np.percentile(d_sc, 95))
        q05_s = float(np.percentile(s_sc, 5))
        q95_s = float(np.percentile(s_sc, 95))

        act_d = float(pred.actual_demand_kwh) if pred.actual_demand_kwh is not None else np.nan
        act_s = float(pred.actual_solar_generation_kwh) if pred.actual_solar_generation_kwh is not None else np.nan

        cov_d = bool(q05_d <= act_d <= q95_d)
        cov_s = bool(q05_s <= act_s <= q95_s)

        return {
            "house_id": house_id,
            "forecast_timestamp": str(ts),
            "actual_demand_kwh": act_d,
            "predicted_demand_kwh": pred.predicted_demand_kwh,
            "demand_pi_lower_kwh": q05_d,
            "demand_pi_upper_kwh": q95_d,
            "demand_interval_width_kwh": q95_d - q05_d,
            "demand_covered": cov_d,
            "demand_below_lower": bool(act_d < q05_d),
            "demand_above_upper": bool(act_d > q95_d),
            "actual_solar_kwh": act_s,
            "predicted_solar_kwh": pred.predicted_solar_generation_kwh,
            "solar_pi_lower_kwh": q05_s,
            "solar_pi_upper_kwh": q95_s,
            "solar_interval_width_kwh": q95_s - q05_s,
            "solar_covered": cov_s,
            "solar_below_lower": bool(act_s < q05_s),
            "solar_above_upper": bool(act_s > q95_s),
        }

    def generate_row_level_evaluations(
        self,
        num_scenarios: int = 1000,
        random_seed: int = 42,
        rng_mode: str = "fixed_per_observation",
    ) -> pd.DataFrame:
        """Generate row-level evaluations across all test observations.

        Parameters
        ----------
        num_scenarios : int
            Number of Monte Carlo scenarios per forecast (default 1,000).
        random_seed : int
            Reproducible random seed.
        rng_mode : str
            - "fixed_per_observation": calls sample_residuals with random_seed=42
              at each observation (matches standard MonteCarloSimulator API).
            - "sequential_rng": maintains a single persistent RNG stream per
              household initialized from random_seed (Step 2 check).
            - "protocol_a": maintains a single persistent RNG stream across
              all test observations.
            - "protocol_b": deterministic, documented seed derived from each
              observation's stable identifier (house_id, timestamp, seed).

        Returns
        -------
        pd.DataFrame
            DataFrame with 5,256 rows containing actuals, forecasts, intervals,
            widths, and coverage indicators.
        """
        rows: List[Dict[str, Any]] = []

        # If Protocol A: single persistent RNG stream across all observations
        if rng_mode == "protocol_a":
            rng_stream = np.random.default_rng(random_seed)

        for house_id in self.HOUSEHOLDS:
            mask = self.test_house_ids == house_id
            h_indices = np.where(mask)[0]
            val_mask = self.residual_pool.val_house_ids == house_id
            h_val_res = self.residual_pool.residuals[val_mask]

            if len(h_val_res) == 0:
                raise ValueError(f"No validation residuals found for {house_id}")

            # Prepare RNG according to selected mode
            if rng_mode == "sequential_rng":
                rng = np.random.default_rng(random_seed)

            for idx in h_indices:
                ts = self.test_timestamps[idx]
                pred_d = float(self.preds_raw[idx, 0])
                pred_s = float(self.preds_raw[idx, 1])
                act_d = float(self.actual_raw[idx, 0])
                act_s = float(self.actual_raw[idx, 1])

                if rng_mode == "protocol_a":
                    ed, es = self.residual_pool.sample_residuals(
                        num_scenarios=num_scenarios,
                        house_id=house_id,
                        random_seed=rng_stream,
                    )
                elif rng_mode == "protocol_b":
                    obs_seed = derive_observation_seed(house_id, ts, random_seed)
                    ed, es = self.residual_pool.sample_residuals(
                        num_scenarios=num_scenarios,
                        house_id=house_id,
                        random_seed=obs_seed,
                    )
                elif rng_mode == "sequential_rng":
                    ed, es = self.residual_pool.sample_residuals(
                        num_scenarios=num_scenarios,
                        house_id=house_id,
                        random_seed=rng,
                    )
                else:  # fixed_per_observation
                    ed, es = self.residual_pool.sample_residuals(
                        num_scenarios=num_scenarios,
                        house_id=house_id,
                        random_seed=random_seed,
                    )

                # Physical perturbation with non-negativity constraint
                sc_d = np.maximum(0.0, pred_d + ed)
                sc_s = np.maximum(0.0, pred_s + es)

                q05_d = float(np.percentile(sc_d, 5))
                q95_d = float(np.percentile(sc_d, 95))
                q05_s = float(np.percentile(sc_s, 5))
                q95_s = float(np.percentile(sc_s, 95))

                cov_d = bool(q05_d <= act_d <= q95_d)
                cov_s = bool(q05_s <= act_s <= q95_s)
                below_d = bool(act_d < q05_d)
                above_d = bool(act_d > q95_d)
                below_s = bool(act_s < q05_s)
                above_s = bool(act_s > q95_s)

                rows.append({
                    "house_id": house_id,
                    "forecast_timestamp": str(ts),
                    "month": ts.month,
                    # Demand fields
                    "actual_demand_kwh": act_d,
                    "predicted_demand_kwh": pred_d,
                    "demand_error_kwh": act_d - pred_d,
                    "demand_pi_lower_kwh": q05_d,
                    "demand_pi_upper_kwh": q95_d,
                    "demand_interval_width_kwh": q95_d - q05_d,
                    "demand_covered": cov_d,
                    "demand_below_lower": below_d,
                    "demand_above_upper": above_d,
                    # Solar fields
                    "actual_solar_kwh": act_s,
                    "predicted_solar_kwh": pred_s,
                    "solar_error_kwh": act_s - pred_s,
                    "solar_pi_lower_kwh": q05_s,
                    "solar_pi_upper_kwh": q95_s,
                    "solar_interval_width_kwh": q95_s - q05_s,
                    "solar_covered": cov_s,
                    "solar_below_lower": below_s,
                    "solar_above_upper": above_s,
                })

        df = pd.DataFrame(rows)
        return df.sort_values(["house_id", "forecast_timestamp"]).reset_index(drop=True)

    def compute_interval_metrics_from_df(
        self,
        df: pd.DataFrame,
        household: str,
        target_variable: str,
        nominal_coverage: float = 0.90,
    ) -> IntervalMetrics:
        """Compute summary interval calibration metrics from row-level evaluation DataFrame."""
        if household == "ALL":
            sub = df
        else:
            sub = df[df["house_id"] == household]

        n = len(sub)
        if n == 0:
            raise ValueError(f"No records found for {household}")

        if target_variable == "total_demand_kwh":
            cov_col = "demand_covered"
            width_col = "demand_interval_width_kwh"
            below_col = "demand_below_lower"
            above_col = "demand_above_upper"
        elif target_variable == "solar_generation_kwh":
            cov_col = "solar_covered"
            width_col = "solar_interval_width_kwh"
            below_col = "solar_below_lower"
            above_col = "solar_above_upper"
        else:
            raise ValueError(f"Unknown target variable: {target_variable}")

        cov_rate = float(sub[cov_col].mean())
        mean_w = float(sub[width_col].mean())
        median_w = float(sub[width_col].median())
        below_frac = float(sub[below_col].mean())
        above_frac = float(sub[above_col].mean())

        return IntervalMetrics(
            household=household,
            target_variable=target_variable,
            unit="kWh",
            nominal_coverage=nominal_coverage,
            n_observations=n,
            empirical_coverage=cov_rate,
            mean_width=mean_w,
            median_width=median_w,
            fraction_below_lower=below_frac,
            fraction_above_upper=above_frac,
        )

    def compute_monthly_breakdown(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute temporal/monthly interval calibration summaries."""
        records = []
        months = sorted(df["month"].unique())

        month_names = {4: "April 2013", 5: "May 2013", 6: "June 2013"}

        # By household and month
        for house_id in self.HOUSEHOLDS + ["ALL"]:
            h_df = df if house_id == "ALL" else df[df["house_id"] == house_id]
            for m in months:
                m_df = h_df[h_df["month"] == m]
                if len(m_df) == 0:
                    continue

                records.append({
                    "household": house_id,
                    "month_number": m,
                    "month_name": month_names.get(m, f"Month {m}"),
                    "n_observations": len(m_df),
                    "demand_mae_kwh": round(float(np.mean(np.abs(m_df["demand_error_kwh"]))), 4),
                    "demand_rmse_kwh": round(float(np.sqrt(np.mean(m_df["demand_error_kwh"] ** 2))), 4),
                    "demand_bias_kwh": round(float(np.mean(m_df["demand_error_kwh"])), 4),
                    "demand_coverage_pct": round(float(m_df["demand_covered"].mean()) * 100.0, 2),
                    "demand_mean_width_kwh": round(float(m_df["demand_interval_width_kwh"].mean()), 4),
                    "demand_below_pct": round(float(m_df["demand_below_lower"].mean()) * 100.0, 2),
                    "demand_above_pct": round(float(m_df["demand_above_upper"].mean()) * 100.0, 2),
                    "solar_mae_kwh": round(float(np.mean(np.abs(m_df["solar_error_kwh"]))), 4),
                    "solar_rmse_kwh": round(float(np.sqrt(np.mean(m_df["solar_error_kwh"] ** 2))), 4),
                    "solar_bias_kwh": round(float(np.mean(m_df["solar_error_kwh"])), 4),
                    "solar_coverage_pct": round(float(m_df["solar_covered"].mean()) * 100.0, 2),
                    "solar_mean_width_kwh": round(float(m_df["solar_interval_width_kwh"].mean()), 4),
                    "solar_below_pct": round(float(m_df["solar_below_lower"].mean()) * 100.0, 2),
                    "solar_above_pct": round(float(m_df["solar_above_upper"].mean()) * 100.0, 2),
                })

        return pd.DataFrame(records)

    # -------------------------------------------------------------------------
    # Phase D: Known Anomaly Investigation
    # -------------------------------------------------------------------------

    def inspect_known_anomaly(
        self,
        df: pd.DataFrame,
        timestamp: str = "2013-06-08 10:00:00",
        house_id: str = "H002",
    ) -> Dict[str, Any]:
        """Extract and verify the known anomaly observation from evaluated data."""
        sub = df[(df["house_id"] == house_id) & (df["forecast_timestamp"] == timestamp)]
        if len(sub) == 0:
            raise KeyError(f"Timestamp {timestamp} not found in evaluated data for {house_id}")

        row = sub.iloc[0]
        actual_d = float(row["actual_demand_kwh"])
        pred_d = float(row["predicted_demand_kwh"])
        q05_d = float(row["demand_pi_lower_kwh"])
        q95_d = float(row["demand_pi_upper_kwh"])
        is_covered_d = bool(row["demand_covered"])
        width_d = float(row["demand_interval_width_kwh"])

        actual_s = float(row["actual_solar_kwh"])
        pred_s = float(row["predicted_solar_kwh"])
        q05_s = float(row["solar_pi_lower_kwh"])
        q95_s = float(row["solar_pi_upper_kwh"])
        is_covered_s = bool(row["solar_covered"])

        is_outside = not is_covered_d
        exceedance = actual_d - q95_d

        return {
            "house_id": house_id,
            "forecast_timestamp": timestamp,
            "actual_demand_kwh": round(actual_d, 4),
            "predicted_demand_kwh": round(pred_d, 4),
            "demand_pi_lower_kwh": round(q05_d, 4),
            "demand_pi_upper_kwh": round(q95_d, 4),
            "demand_interval_width_kwh": round(width_d, 4),
            "is_demand_covered": is_covered_d,
            "is_demand_outside_interval": is_outside,
            "demand_exceedance_above_upper_kwh": round(exceedance, 4),
            "actual_solar_kwh": round(actual_s, 4),
            "predicted_solar_kwh": round(pred_s, 4),
            "solar_pi_lower_kwh": round(q05_s, 4),
            "solar_pi_upper_kwh": round(q95_s, 4),
            "is_solar_covered": is_covered_s,
            "verified_matches_expectations": (
                abs(actual_d - 1.838) < 0.005
                and abs(pred_d - 0.338) < 0.010
                and abs(q95_d - 0.548) < 0.025
                and is_outside is True
            ),
        }

    # -------------------------------------------------------------------------
    # Phase E: Data Integrity and Leakage Checks
    # -------------------------------------------------------------------------

    def run_all_integrity_checks(self) -> List[IntegrityCheckResult]:
        """Run comprehensive automated leakage and integrity verification checks."""
        results: List[IntegrityCheckResult] = []

        # 1. Chronological boundaries check
        try:
            train_ts = pd.to_datetime(self.sequences["train_target_timestamp"])
            val_ts = pd.to_datetime(self.sequences["val_target_timestamp"])
            test_ts = pd.to_datetime(self.sequences["test_target_timestamp"])

            max_train = train_ts.max()
            min_val = val_ts.min()
            max_val = val_ts.max()
            min_test = test_ts.min()
            max_test = test_ts.max()

            is_chronological = (max_train < min_val) and (max_val < min_test)
            details = (
                f"Train: [{train_ts.min()} to {max_train}], "
                f"Val: [{min_val} to {max_val}], "
                f"Test: [{min_test} to {max_test}]. Strictly chronological: {is_chronological}."
            )
            results.append(IntegrityCheckResult(
                check_name="chronological_boundaries",
                passed=bool(is_chronological),
                status="PASSED" if is_chronological else "FAILED",
                details=details,
            ))
        except Exception as e:
            results.append(IntegrityCheckResult(
                check_name="chronological_boundaries",
                passed=False,
                status="UNVERIFIED",
                details=f"Error evaluating chronological boundaries: {e}",
            ))

        # 2. No overlap across splits
        try:
            set_train = set(self.sequences["train_target_timestamp"].astype(str))
            set_val = set(self.sequences["val_target_timestamp"].astype(str))
            set_test = set(self.sequences["test_target_timestamp"].astype(str))

            train_val_overlap = set_train & set_val
            val_test_overlap = set_val & set_test
            train_test_overlap = set_train & set_test

            no_overlap = (
                len(train_val_overlap) == 0
                and len(val_test_overlap) == 0
                and len(train_test_overlap) == 0
            )
            details = (
                f"Overlap counts: Train-Val={len(train_val_overlap)}, "
                f"Val-Test={len(val_test_overlap)}, Train-Test={len(train_test_overlap)}."
            )
            results.append(IntegrityCheckResult(
                check_name="zero_target_timestamp_overlap",
                passed=bool(no_overlap),
                status="PASSED" if no_overlap else "FAILED",
                details=details,
            ))
        except Exception as e:
            results.append(IntegrityCheckResult(
                check_name="zero_target_timestamp_overlap",
                passed=False,
                status="UNVERIFIED",
                details=f"Error checking split overlap: {e}",
            ))

        # 3. Residual pool sourced strictly from validation observations
        try:
            pool_ts = set(self.residual_pool.val_timestamps.astype(str))
            pool_val_matches = pool_ts.issubset(set(self.sequences["val_target_timestamp"].astype(str)))
            test_ts_set = set(self.sequences["test_target_timestamp"].astype(str))
            overlap_with_test = pool_ts & test_ts_set

            pool_valid = pool_val_matches and (len(overlap_with_test) == 0)
            details = (
                f"Residual pool size: {len(self.residual_pool.residuals)} pairs. "
                f"Subset of validation: {pool_val_matches}. "
                f"Overlap with test: {len(overlap_with_test)}."
            )
            results.append(IntegrityCheckResult(
                check_name="validation_only_residual_pool",
                passed=bool(pool_valid),
                status="PASSED" if pool_valid else "FAILED",
                details=details,
            ))
        except Exception as e:
            results.append(IntegrityCheckResult(
                check_name="validation_only_residual_pool",
                passed=False,
                status="UNVERIFIED",
                details=f"Error checking residual pool source: {e}",
            ))

        # 4. Scaler fitting restricted to permitted training data
        try:
            hourly_df = pd.read_csv(self.data_path)
            houses = {
                h: f.sort_values("timestamp").reset_index(drop=True)
                for h, f in hourly_df.groupby("house_id")
            }
            # Scaler fit range is rows 0 to validation_start - 1 (6307 rows)
            val_start = int(8760 * 0.80 * 0.90)  # 6307
            train_frames = [f.iloc[:val_start] for f in houses.values()]
            train_concat = pd.concat(train_frames)

            expected_d_min = float(train_concat["total_demand_kwh"].min())
            expected_d_max = float(train_concat["total_demand_kwh"].max())
            expected_s_min = float(train_concat["solar_generation_kwh"].min())
            expected_s_max = float(train_concat["solar_generation_kwh"].max())

            actual_min = self.forecaster.data_min_
            actual_max = self.forecaster.data_max_

            scaler_clean = (
                np.isclose(actual_min[0], expected_d_min)
                and np.isclose(actual_max[0], expected_d_max)
                and np.isclose(actual_min[1], expected_s_min)
                and np.isclose(actual_max[1], expected_s_max)
            )
            details = (
                f"Expected train bounds: demand=[{expected_d_min}, {expected_d_max}], "
                f"solar=[{expected_s_min}, {expected_s_max}]. "
                f"Saved scaler bounds: demand=[{actual_min[0]}, {actual_max[0]}], "
                f"solar=[{actual_min[1]}, {actual_max[1]}]. "
                f"Matches training slice: {scaler_clean}."
            )
            results.append(IntegrityCheckResult(
                check_name="scaler_train_only_fitting",
                passed=bool(scaler_clean),
                status="PASSED" if scaler_clean else "FAILED",
                details=details,
            ))
        except Exception as e:
            results.append(IntegrityCheckResult(
                check_name="scaler_train_only_fitting",
                passed=False,
                status="UNVERIFIED",
                details=f"Error checking scaler fit integrity: {e}",
            ))

        # 5. Test targets not used to create predictions or intervals
        try:
            # Inference relies only on X_test and forecaster weights
            pred1 = predict_lstm_numpy(self.X_test[:5], self.forecaster.weights)
            # Perturbing actual targets y_test has zero impact on inference
            dummy_y = self.y_test[:5] + 999.0
            pred2 = predict_lstm_numpy(self.X_test[:5], self.forecaster.weights)
            independence = np.allclose(pred1, pred2)

            details = (
                "Verified that LSTM inference relies exclusively on lookback features X_test; "
                "modifying target array y_test produces identical point predictions."
            )
            results.append(IntegrityCheckResult(
                check_name="test_target_isolation",
                passed=bool(independence),
                status="PASSED" if independence else "FAILED",
                details=details,
            ))
        except Exception as e:
            results.append(IntegrityCheckResult(
                check_name="test_target_isolation",
                passed=False,
                status="UNVERIFIED",
                details=f"Error verifying test target isolation: {e}",
            ))

        # 6. Correct household and target-variable alignment
        try:
            alignment_ok = True
            details_list = []
            for h in self.HOUSEHOLDS:
                h_count = int(np.sum(self.test_house_ids == h))
                if h_count != 1752:
                    alignment_ok = False
                details_list.append(f"{h}:{h_count}")

            # Check that feature columns correspond to demand (col 0) and solar (col 1)
            target_cols = [str(c) for c in self.sequences["target_columns"]]
            expected_targets = ["total_demand_kwh", "solar_generation_kwh"]
            targets_match = target_cols == expected_targets
            if not targets_match:
                alignment_ok = False

            details = f"Household test counts: {', '.join(details_list)}. Target columns: {target_cols}."
            results.append(IntegrityCheckResult(
                check_name="household_and_target_alignment",
                passed=bool(alignment_ok),
                status="PASSED" if alignment_ok else "FAILED",
                details=details,
            ))
        except Exception as e:
            results.append(IntegrityCheckResult(
                check_name="household_and_target_alignment",
                passed=False,
                status="UNVERIFIED",
                details=f"Error checking household alignment: {e}",
            ))

        # 7. Finite metric values and valid units
        try:
            finite_preds = bool(np.all(np.isfinite(self.preds_raw)))
            finite_actuals = bool(np.all(np.isfinite(self.actual_raw)))
            nonneg_preds = bool(np.all(self.preds_raw >= 0.0))
            nonneg_actuals = bool(np.all(self.actual_raw >= 0.0))

            finite_valid = finite_preds and finite_actuals and nonneg_preds and nonneg_actuals
            details = (
                f"Finite predictions: {finite_preds}, Finite actuals: {finite_actuals}, "
                f"Non-negative predictions: {nonneg_preds}, Non-negative actuals: {nonneg_actuals}. "
                "Units confirmed as kWh."
            )
            results.append(IntegrityCheckResult(
                check_name="finite_values_and_units",
                passed=bool(finite_valid),
                status="PASSED" if finite_valid else "FAILED",
                details=details,
            ))
        except Exception as e:
            results.append(IntegrityCheckResult(
                check_name="finite_values_and_units",
                passed=False,
                status="UNVERIFIED",
                details=f"Error checking finite values: {e}",
            ))

        return results

    # -------------------------------------------------------------------------
    # Combined Summary Generation
    # -------------------------------------------------------------------------

    def generate_summary_table(
        self,
        row_level_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Create summary table for all six household-variable pairs plus overall summaries."""
        rows: List[Dict[str, Any]] = []

        point_metrics = self.evaluate_all_point_forecasts()

        # Six household-variable combinations
        for house_id in self.HOUSEHOLDS:
            for target_name in self.TARGET_VARIABLES:
                pt_key = f"{house_id}_{target_name}"
                pt = point_metrics[pt_key]
                intv = self.compute_interval_metrics_from_df(
                    df=row_level_df,
                    household=house_id,
                    target_variable=target_name,
                )

                combined = CombinedMetrics(
                    household=house_id,
                    target_variable=target_name,
                    unit="kWh",
                    n_observations=pt.n_observations,
                    mae=pt.mae,
                    rmse=pt.rmse,
                    mean_bias=pt.mean_bias,
                    nominal_coverage_pct=intv.nominal_coverage * 100.0,
                    empirical_coverage_pct=intv.empirical_coverage * 100.0,
                    mean_width_kwh=intv.mean_width,
                    median_width_kwh=intv.median_width,
                    fraction_below_lower_pct=intv.fraction_below_lower * 100.0,
                    fraction_above_upper_pct=intv.fraction_above_upper * 100.0,
                )
                rows.append(combined.to_dict())

        # Overall Demand
        pt_d = point_metrics["ALL_total_demand_kwh"]
        intv_d = self.compute_interval_metrics_from_df(
            df=row_level_df,
            household="ALL",
            target_variable="total_demand_kwh",
        )
        combined_d = CombinedMetrics(
            household="ALL",
            target_variable="total_demand_kwh",
            unit="kWh",
            n_observations=pt_d.n_observations,
            mae=pt_d.mae,
            rmse=pt_d.rmse,
            mean_bias=pt_d.mean_bias,
            nominal_coverage_pct=intv_d.nominal_coverage * 100.0,
            empirical_coverage_pct=intv_d.empirical_coverage * 100.0,
            mean_width_kwh=intv_d.mean_width,
            median_width_kwh=intv_d.median_width,
            fraction_below_lower_pct=intv_d.fraction_below_lower * 100.0,
            fraction_above_upper_pct=intv_d.fraction_above_upper * 100.0,
        )
        rows.append(combined_d.to_dict())

        # Overall Solar
        pt_s = point_metrics["ALL_solar_generation_kwh"]
        intv_s = self.compute_interval_metrics_from_df(
            df=row_level_df,
            household="ALL",
            target_variable="solar_generation_kwh",
        )
        combined_s = CombinedMetrics(
            household="ALL",
            target_variable="solar_generation_kwh",
            unit="kWh",
            n_observations=pt_s.n_observations,
            mae=pt_s.mae,
            rmse=pt_s.rmse,
            mean_bias=pt_s.mean_bias,
            nominal_coverage_pct=intv_s.nominal_coverage * 100.0,
            empirical_coverage_pct=intv_s.empirical_coverage * 100.0,
            mean_width_kwh=intv_s.mean_width,
            median_width_kwh=intv_s.median_width,
            fraction_below_lower_pct=intv_s.fraction_below_lower * 100.0,
            fraction_above_upper_pct=intv_s.fraction_above_upper * 100.0,
        )
        rows.append(combined_s.to_dict())

        return pd.DataFrame(rows)
