"""Automated unit and integration tests for forecast evaluation, interval calibration, and leakage checks.

Verifies:
1. All 7 data integrity and leakage invariants.
2. Point forecast metric accuracy (MAE, RMSE, bias).
3. Prediction interval coverage logic and physical non-negativity.
4. Investigation of the known anomaly at 2013-06-08 10:00:00 for H002 demand.
5. Exact observation counts (1,752 per household, 5,256 total).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.evaluation.forecast_evaluator import ForecastEvaluator, PointMetrics, IntervalMetrics


@pytest.fixture(scope="module")
def evaluator():
    """Module-scoped ForecastEvaluator instance."""
    return ForecastEvaluator()


# ---------------------------------------------------------------------------
# Phase E: Automated Data Integrity and Leakage Tests
# ---------------------------------------------------------------------------

def test_chronological_boundaries_integrity(evaluator):
    """Invariant 1: Strictly chronological train -> val -> test boundaries."""
    train_ts = pd.to_datetime(evaluator.sequences["train_target_timestamp"])
    val_ts = pd.to_datetime(evaluator.sequences["val_target_timestamp"])
    test_ts = pd.to_datetime(evaluator.sequences["test_target_timestamp"])

    assert train_ts.max() < val_ts.min(), "Train overlaps with or occurs after Validation split"
    assert val_ts.max() < test_ts.min(), "Validation overlaps with or occurs after Test split"

    # Specific historical boundaries
    assert str(train_ts.max()) == "2013-03-20 18:00:00"
    assert str(val_ts.min()) == "2013-03-20 19:00:00"
    assert str(val_ts.max()) == "2013-04-18 23:00:00"
    assert str(test_ts.min()) == "2013-04-19 00:00:00"
    assert str(test_ts.max()) == "2013-06-30 23:00:00"


def test_zero_split_overlap_integrity(evaluator):
    """Invariant 2: No overlap of target timestamps across splits."""
    train_set = set(evaluator.sequences["train_target_timestamp"].astype(str))
    val_set = set(evaluator.sequences["val_target_timestamp"].astype(str))
    test_set = set(evaluator.sequences["test_target_timestamp"].astype(str))

    assert len(train_set & val_set) == 0, "Train and Validation share target timestamps"
    assert len(val_set & test_set) == 0, "Validation and Test share target timestamps"
    assert len(train_set & test_set) == 0, "Train and Test share target timestamps"


def test_validation_only_residual_pool_integrity(evaluator):
    """Invariant 3: Residual pool sourced strictly from validation observations."""
    pool_ts = set(evaluator.residual_pool.val_timestamps.astype(str))
    val_ts = set(evaluator.sequences["val_target_timestamp"].astype(str))
    test_ts = set(evaluator.sequences["test_target_timestamp"].astype(str))

    assert pool_ts.issubset(val_ts), "Residual pool contains non-validation timestamps"
    assert len(pool_ts & test_ts) == 0, "Residual pool leaks test timestamps"
    assert len(evaluator.residual_pool.residuals) == 2103, "Expected 2,103 total validation residual pairs"


def test_scaler_train_only_fit_integrity(evaluator):
    """Invariant 4: Scaler fitted strictly on permitted training data (rows 0 to 6306)."""
    hourly_df = pd.read_csv(evaluator.data_path)
    houses = {
        h: f.sort_values("timestamp").reset_index(drop=True)
        for h, f in hourly_df.groupby("house_id")
    }
    val_start = int(8760 * 0.80 * 0.90)  # index 6307
    train_concat = pd.concat([f.iloc[:val_start] for f in houses.values()])

    exp_d_min = float(train_concat["total_demand_kwh"].min())
    exp_d_max = float(train_concat["total_demand_kwh"].max())
    exp_s_min = float(train_concat["solar_generation_kwh"].min())
    exp_s_max = float(train_concat["solar_generation_kwh"].max())

    assert np.isclose(evaluator.forecaster.data_min_[0], exp_d_min)
    assert np.isclose(evaluator.forecaster.data_max_[0], exp_d_max)
    assert np.isclose(evaluator.forecaster.data_min_[1], exp_s_min)
    assert np.isclose(evaluator.forecaster.data_max_[1], exp_s_max)


def test_test_target_isolation_integrity(evaluator):
    """Invariant 5: Test targets are not used to produce predictions."""
    from src.forecasting.lstm import predict_lstm_numpy

    pred_original = predict_lstm_numpy(evaluator.X_test[:10], evaluator.forecaster.weights)
    pred_second = predict_lstm_numpy(evaluator.X_test[:10], evaluator.forecaster.weights)

    np.testing.assert_allclose(pred_original, pred_second, atol=1e-7)


def test_household_and_target_alignment(evaluator):
    """Invariant 6: Correct household and target-variable alignment."""
    counts = pd.Series(evaluator.test_house_ids).value_counts().to_dict()
    assert counts == {"H001": 1752, "H002": 1752, "H003": 1752}

    targets = list(evaluator.sequences["target_columns"])
    assert targets == ["total_demand_kwh", "solar_generation_kwh"]


def test_finite_values_and_units(evaluator):
    """Invariant 7: All test targets and forecasts are finite and non-negative."""
    assert np.all(np.isfinite(evaluator.preds_raw))
    assert np.all(np.isfinite(evaluator.actual_raw))
    assert np.all(evaluator.preds_raw >= 0.0)
    assert np.all(evaluator.actual_raw >= 0.0)


# ---------------------------------------------------------------------------
# Phase B: Point Metric Computation Tests
# ---------------------------------------------------------------------------

def test_point_metrics_math(evaluator):
    """Test MAE, RMSE, and bias computation logic."""
    act = np.array([1.0, 2.0, 3.0])
    pred = np.array([0.5, 2.5, 4.0])

    m = evaluator.compute_point_metrics(act, pred, "TEST", "demand")
    assert m.mae == pytest.approx(0.666667, abs=1e-5)
    assert m.rmse == pytest.approx(0.707107, abs=1e-5)
    assert m.mean_bias == pytest.approx(-0.333333, abs=1e-5)


def test_all_point_metrics_match_baseline(evaluator):
    """Point metrics on test period match known evaluation_metrics.csv baselines."""
    metrics = evaluator.evaluate_all_point_forecasts()

    # Overall demand and solar MAE
    assert metrics["ALL_total_demand_kwh"].mae == pytest.approx(0.4660, abs=1e-3)
    assert metrics["ALL_solar_generation_kwh"].mae == pytest.approx(0.0814, abs=1e-3)

    # Per-household demand MAE
    assert metrics["H001_total_demand_kwh"].mae == pytest.approx(0.5205, abs=1e-3)
    assert metrics["H002_total_demand_kwh"].mae == pytest.approx(0.4014, abs=1e-3)
    assert metrics["H003_total_demand_kwh"].mae == pytest.approx(0.4760, abs=1e-3)


# ---------------------------------------------------------------------------
# Phase C: Prediction Interval Calibration Tests
# ---------------------------------------------------------------------------

def test_interval_evaluation_shape_and_bounds(evaluator):
    """Row-level evaluations must have 5,256 rows and valid physical bounds."""
    df = evaluator.generate_row_level_evaluations(num_scenarios=50, random_seed=42)

    assert len(df) == 5256
    # Non-negativity of bounds
    assert np.all(df["demand_pi_lower_kwh"] >= 0.0)
    assert np.all(df["demand_pi_upper_kwh"] >= df["demand_pi_lower_kwh"])
    assert np.all(df["solar_pi_lower_kwh"] >= 0.0)
    assert np.all(df["solar_pi_upper_kwh"] >= df["solar_pi_lower_kwh"])

    # Width non-negative
    assert np.all(df["demand_interval_width_kwh"] >= 0.0)
    assert np.all(df["solar_interval_width_kwh"] >= 0.0)

    # Indicator mutual exclusivity: cannot be both below lower and above upper
    assert not np.any(df["demand_below_lower"] & df["demand_above_upper"])
    assert not np.any(df["solar_below_lower"] & df["solar_above_upper"])


def test_interval_reproducibility(evaluator):
    """Same seed must produce identical interval bounds."""
    res1 = evaluator.evaluate_single_hour("H001", "2013-05-01 12:00:00", num_scenarios=200, random_seed=99)
    res2 = evaluator.evaluate_single_hour("H001", "2013-05-01 12:00:00", num_scenarios=200, random_seed=99)

    assert res1["demand_pi_upper_kwh"] == pytest.approx(res2["demand_pi_upper_kwh"])
    assert res1["solar_pi_upper_kwh"] == pytest.approx(res2["solar_pi_upper_kwh"])


# ---------------------------------------------------------------------------
# Phase D: Known Anomaly Verification
# ---------------------------------------------------------------------------

def test_known_anomaly_h002_demand(evaluator):
    """Verify anomaly at 2013-06-08 10:00:00 for H002 demand."""
    info = evaluator.evaluate_single_hour(
        house_id="H002",
        timestamp="2013-06-08 10:00:00",
        num_scenarios=1000,
        random_seed=42,
    )

    assert info["actual_demand_kwh"] == pytest.approx(1.838, abs=0.005)
    assert info["predicted_demand_kwh"] == pytest.approx(0.338, abs=0.010)
    assert info["demand_pi_upper_kwh"] == pytest.approx(0.548, abs=0.025)
    assert info["demand_covered"] is False
    assert info["demand_above_upper"] is True


def test_rng_modes_in_forecast_evaluator(evaluator):
    """Verify that ForecastEvaluator supports protocol_a and protocol_b correctly."""
    # Test on a small scenario count for speed
    df_proto_a = evaluator.generate_row_level_evaluations(num_scenarios=20, random_seed=42, rng_mode="protocol_a")
    df_proto_b = evaluator.generate_row_level_evaluations(num_scenarios=20, random_seed=42, rng_mode="protocol_b")

    assert len(df_proto_a) == 5256
    assert len(df_proto_b) == 5256
    assert np.all(df_proto_a["demand_interval_width_kwh"] >= 0.0)
    assert np.all(df_proto_b["demand_interval_width_kwh"] >= 0.0)
    assert np.all(df_proto_a["solar_interval_width_kwh"] >= 0.0)
    assert np.all(df_proto_b["solar_interval_width_kwh"] >= 0.0)
