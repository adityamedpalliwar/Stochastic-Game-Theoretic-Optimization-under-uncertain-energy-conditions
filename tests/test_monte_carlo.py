"""Unit tests for Monte Carlo uncertainty module."""

import numpy as np
import pandas as pd
import pytest

from src.forecasting.predict import EnergyForecaster, ForecastResult
from src.stochastic.monte_carlo import (
    MonteCarloSimulator,
    ScenarioDistribution,
    ValidationResidualPool,
    derive_observation_seed,
    estimate_expected_payoff_matrix,
)


@pytest.fixture(scope="module")
def residual_pool():
    """Shared residual pool for this test module (expensive to load once)."""
    return ValidationResidualPool()


@pytest.fixture(scope="module")
def forecaster():
    return EnergyForecaster()


# ---------------------------------------------------------------------------
# Residual pool
# ---------------------------------------------------------------------------

def test_residual_pool_shape(residual_pool):
    """Validation residuals must match X_val sequence count."""
    assert len(residual_pool.demand_residuals) == 2103
    assert len(residual_pool.solar_residuals) == 2103
    assert residual_pool.residuals.shape == (2103, 2)


def test_residual_statistics_finite(residual_pool):
    """Residual statistics must all be finite numbers."""
    for house in ["H001", "H002", "H003", None]:
        d_stat, s_stat = residual_pool.get_statistics(house_id=house)
        for attr in ["mean", "std_dev", "median", "q05", "q95", "min_val", "max_val"]:
            assert np.isfinite(getattr(d_stat, attr)), f"Demand {attr} is not finite for {house}"
            assert np.isfinite(getattr(s_stat, attr)), f"Solar {attr} is not finite for {house}"


def test_std_dev_positive(residual_pool):
    """Standard deviation must be positive for real data."""
    d_stat, s_stat = residual_pool.get_statistics()
    assert d_stat.std_dev > 0.0
    assert s_stat.std_dev > 0.0


# ---------------------------------------------------------------------------
# Scenario generation shapes and physical bounds
# ---------------------------------------------------------------------------

def test_scenario_output_shape(forecaster, residual_pool):
    """Generated scenario arrays must have exactly num_scenarios elements."""
    pred = forecaster.predict_next_hour("H001", "2013-06-08 10:00:00")
    mc = MonteCarloSimulator(residual_pool=residual_pool)
    dist = mc.generate_scenarios(pred, num_scenarios=1000, random_seed=42)

    assert len(dist.scenarios_demand_kwh) == 1000
    assert len(dist.scenarios_solar_kwh) == 1000


def test_scenarios_nonnegative(forecaster, residual_pool):
    """All scenario values must be physically nonnegative (energy >= 0)."""
    pred = forecaster.predict_next_hour("H002", "2013-06-08 10:00:00")
    mc = MonteCarloSimulator(residual_pool=residual_pool)
    dist = mc.generate_scenarios(pred, num_scenarios=1000, random_seed=0)

    assert np.all(dist.scenarios_demand_kwh >= 0.0), "Negative demand in scenarios"
    assert np.all(dist.scenarios_solar_kwh >= 0.0), "Negative solar in scenarios"


def test_scenario_reproducible(forecaster, residual_pool):
    """Same seed must produce identical output."""
    pred = forecaster.predict_next_hour("H003", "2013-06-08 10:00:00")
    mc = MonteCarloSimulator(residual_pool=residual_pool)
    d1 = mc.generate_scenarios(pred, num_scenarios=500, random_seed=99)
    d2 = mc.generate_scenarios(pred, num_scenarios=500, random_seed=99)

    np.testing.assert_array_equal(d1.scenarios_demand_kwh, d2.scenarios_demand_kwh)
    np.testing.assert_array_equal(d1.scenarios_solar_kwh,  d2.scenarios_solar_kwh)


def test_scenario_different_seeds_different(forecaster, residual_pool):
    """Different seeds should produce different samples."""
    pred = forecaster.predict_next_hour("H001", "2013-06-08 10:00:00")
    mc = MonteCarloSimulator(residual_pool=residual_pool)
    d1 = mc.generate_scenarios(pred, num_scenarios=1000, random_seed=1)
    d2 = mc.generate_scenarios(pred, num_scenarios=1000, random_seed=2)

    assert not np.array_equal(d1.scenarios_demand_kwh, d2.scenarios_demand_kwh)


# ---------------------------------------------------------------------------
# Expected payoff matrix
# ---------------------------------------------------------------------------

def test_expected_payoff_matrix_shape(forecaster, residual_pool):
    """Expected payoff matrix must have 4 rows (2x2 action combinations)."""
    pred1 = forecaster.predict_next_hour("H001", "2013-06-08 10:00:00")
    pred2 = forecaster.predict_next_hour("H002", "2013-06-08 10:00:00")
    mc = MonteCarloSimulator(residual_pool=residual_pool)
    dist1 = mc.generate_scenarios(pred1, num_scenarios=1000, random_seed=42)
    dist2 = mc.generate_scenarios(pred2, num_scenarios=1000, random_seed=42)

    df, u1, u2 = estimate_expected_payoff_matrix(dist1, dist2)

    assert len(df) == 4
    assert u1.shape == (2, 2)
    assert u2.shape == (2, 2)


def test_expected_payoff_p2p_better_than_no_trade(forecaster, residual_pool):
    """Expected payoff from P2P trade should not be worse than no-trade for both players."""
    pred1 = forecaster.predict_next_hour("H001", "2013-06-08 10:00:00")
    pred2 = forecaster.predict_next_hour("H002", "2013-06-08 10:00:00")
    mc = MonteCarloSimulator(residual_pool=residual_pool)
    dist1 = mc.generate_scenarios(pred1, num_scenarios=1000, random_seed=42)
    dist2 = mc.generate_scenarios(pred2, num_scenarios=1000, random_seed=42)

    _, u1, u2 = estimate_expected_payoff_matrix(dist1, dist2)

    # Row 0,0 = (OFFER_P2P, ACCEPT_P2P), Row 1,1 = (EXPORT_GRID, GRID_IMPORT)
    trade_u1, trade_u2 = u1[0, 0], u2[0, 0]
    notrade_u1, notrade_u2 = u1[1, 1], u2[1, 1]

    assert trade_u1 >= notrade_u1 - 1e-9
    assert trade_u2 >= notrade_u2 - 1e-9


# ---------------------------------------------------------------------------
# Focused Task 1 Verification Tests
# ---------------------------------------------------------------------------

def test_expected_utility_as_arithmetic_mean():
    """Requirement 7: E[U_i(a)] must be the exact arithmetic mean of scenario-level utilities."""
    from src.stochastic.monte_carlo import ScenarioDistribution, build_stochastic_payoff_matrix

    # Construct known 5-scenario distributions
    d1 = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
    s1 = np.array([1.0, 1.2, 0.8, 1.5, 0.5])
    d2 = np.array([1.5, 1.0, 2.0, 0.5, 1.2])
    s2 = np.array([0.2, 0.3, 0.1, 0.0, 0.4])

    dist1 = ScenarioDistribution("H001", 5, float(np.mean(d1)), float(np.mean(s1)), d1, s1)
    dist2 = ScenarioDistribution("H002", 5, float(np.mean(d2)), float(np.mean(s2)), d2, s2)

    p_import = 0.30
    p_export = 0.08
    p_p2p = 0.19

    surplus1 = np.maximum(0.0, s1 - d1)
    deficit2 = np.maximum(0.0, d2 - s2)
    q_trade = np.minimum(surplus1, deficit2)

    # Scenario-by-scenario direct calculation for (OFFER_P2P, ACCEPT_P2P)
    u1_scenarios = q_trade * p_p2p + (surplus1 - q_trade) * p_export
    u2_scenarios = -(q_trade * p_p2p + (deficit2 - q_trade) * p_import)

    mat, df, _ = build_stochastic_payoff_matrix(dist1, dist2, p_import, p_export, p_p2p)

    assert mat.payoffs_p1[0, 0] == pytest.approx(float(np.mean(u1_scenarios)), abs=1e-9)
    assert mat.payoffs_p2[0, 0] == pytest.approx(float(np.mean(u2_scenarios)), abs=1e-9)
    assert mat.traded_quantities[0, 0] == pytest.approx(float(np.mean(q_trade)), abs=1e-9)


def test_deterministic_stochastic_consistency():
    """Requirement 8: Scenario-level accounting matches deterministic accounting on identical values."""
    from src.energy.energy_balance import compute_energy_balance
    from src.game.payoff_matrix import build_two_household_payoff_matrix
    from src.stochastic.monte_carlo import ScenarioDistribution, build_stochastic_payoff_matrix

    # Ground truth values at 2013-06-08 10:00:00
    b1 = compute_energy_balance(0.137, 1.382, house_id="H001")
    b2 = compute_energy_balance(1.838, 0.375, house_id="H002")

    det_mat = build_two_household_payoff_matrix(
        "H001", b1.surplus_kwh,
        "H002", b2.deficit_kwh,
        grid_import_price_aud=0.30,
        grid_export_credit_aud=0.08,
    )

    # 1-scenario distribution with exactly the deterministic ground truth values
    dist1 = ScenarioDistribution(
        "H001", 1, 0.137, 1.382,
        np.array([0.137]), np.array([1.382]),
    )
    dist2 = ScenarioDistribution(
        "H002", 1, 1.838, 0.375,
        np.array([1.838]), np.array([0.375]),
    )

    stoch_mat, _, _ = build_stochastic_payoff_matrix(
        dist1, dist2,
        grid_import_price_aud=0.30,
        grid_export_credit_aud=0.08,
    )

    np.testing.assert_allclose(stoch_mat.payoffs_p1, det_mat.payoffs_p1, atol=1e-6)
    np.testing.assert_allclose(stoch_mat.payoffs_p2, det_mat.payoffs_p2, atol=1e-6)
    np.testing.assert_allclose(stoch_mat.traded_quantities, det_mat.traded_quantities, atol=1e-6)


def test_nash_equilibrium_recomputation_from_expected_matrix(forecaster, residual_pool):
    """Requirement 9: Run pure-strategy Nash solver on expected payoff matrix."""
    from src.game.best_response import compute_detailed_best_responses
    from src.game.nash import find_pure_nash_equilibria
    from src.stochastic.monte_carlo import build_stochastic_payoff_matrix

    pred1 = forecaster.predict_next_hour("H001", "2013-06-08 10:00:00")
    pred2 = forecaster.predict_next_hour("H002", "2013-06-08 10:00:00")
    mc = MonteCarloSimulator(residual_pool=residual_pool)
    dist1 = mc.generate_scenarios(pred1, num_scenarios=1000, random_seed=42)
    dist2 = mc.generate_scenarios(pred2, num_scenarios=1000, random_seed=42)

    stoch_mat, _, stats = build_stochastic_payoff_matrix(dist1, dist2)
    eq_res = find_pure_nash_equilibria(stoch_mat)
    br_p1, br_p2 = compute_detailed_best_responses(stoch_mat)

    # Must detect pure Nash equilibria
    assert eq_res.has_pure_nash is True
    eq_profiles = [(e.action_player1, e.action_player2) for e in eq_res.equilibria]
    assert ("OFFER_P2P", "ACCEPT_P2P") in eq_profiles
    assert ("EXPORT_GRID", "GRID_IMPORT") in eq_profiles

    # Strictness check
    p2p_eq = [e for e in eq_res.equilibria if e.action_player1 == "OFFER_P2P"][0]
    base_eq = [e for e in eq_res.equilibria if e.action_player1 == "EXPORT_GRID"][0]
    assert p2p_eq.is_strict is True, "(OFFER_P2P, ACCEPT_P2P) must be a strict equilibrium"
    assert base_eq.is_strict is False, "(EXPORT_GRID, GRID_IMPORT) must be a weak equilibrium"

    # Stability proof: neither player can unilaterally improve
    u1 = stoch_mat.payoffs_p1
    u2 = stoch_mat.payoffs_p2
    assert u1[0, 0] > u1[1, 0]  # P1 strictly worse deviating to EXPORT_GRID
    assert u2[0, 0] > u2[0, 1]  # P2 strictly worse deviating to GRID_IMPORT


def test_energy_and_payment_conservation_across_scenarios():
    """Requirements 4, 5, 6: Conservation invariants across all scenarios and profiles."""
    from src.stochastic.monte_carlo import ScenarioDistribution, build_stochastic_payoff_matrix

    rng = np.random.default_rng(999)
    n = 200
    d1 = rng.uniform(0.0, 3.0, size=n)
    s1 = rng.uniform(0.0, 3.0, size=n)
    d2 = rng.uniform(0.0, 3.0, size=n)
    s2 = rng.uniform(0.0, 3.0, size=n)

    dist1 = ScenarioDistribution("H001", n, float(np.mean(d1)), float(np.mean(s1)), d1, s1)
    dist2 = ScenarioDistribution("H002", n, float(np.mean(d2)), float(np.mean(s2)), d2, s2)

    mat, df, _ = build_stochastic_payoff_matrix(dist1, dist2, grid_import_price_aud=0.30, grid_export_credit_aud=0.08)

    # 1. Traded quantities only nonzero for coordinated profile (0, 0)
    assert mat.traded_quantities[0, 0] >= 0.0
    assert mat.traded_quantities[0, 1] == pytest.approx(0.0)
    assert mat.traded_quantities[1, 0] == pytest.approx(0.0)
    assert mat.traded_quantities[1, 1] == pytest.approx(0.0)

    # 2. Check each row in summary dataframe
    for _, row in df.iterrows():
        a1 = row["Action_H001"]
        a2 = row["Action_H002"]
        # Expected trade bounded by surplus and deficit
        if a1 == "OFFER_P2P" and a2 == "ACCEPT_P2P":
            assert row["Expected_P2P_Traded_kWh"] >= 0.0
            assert row["Expected_Gross_P2P_Payment_AUD"] == pytest.approx(row["Expected_P2P_Traded_kWh"] * 0.19, abs=1e-4)
        else:
            assert row["Expected_P2P_Traded_kWh"] == pytest.approx(0.0)
            assert row["Expected_Gross_P2P_Payment_AUD"] == pytest.approx(0.0)


def test_boundary_cases_zero_demand_generation():
    """Requirement 10: Zero demand, zero generation, and boundary limits."""
    from src.stochastic.monte_carlo import ScenarioDistribution, build_stochastic_payoff_matrix

    # Case 1: Both houses have zero demand and zero solar
    zeros = np.zeros(10)
    dist1 = ScenarioDistribution("H001", 10, 0.0, 0.0, zeros, zeros)
    dist2 = ScenarioDistribution("H002", 10, 0.0, 0.0, zeros, zeros)

    mat, df, stats = build_stochastic_payoff_matrix(dist1, dist2)
    assert np.allclose(mat.traded_quantities, 0.0)
    assert np.allclose(mat.payoffs_p1, 0.0)
    assert np.allclose(mat.payoffs_p2, 0.0)
    assert stats["tradeable_scenarios_count"] == 0

    # Case 2: Seller zero surplus, Buyer large deficit -> trade must be 0
    dist_buyer_only = ScenarioDistribution("H002", 10, 2.0, 0.0, np.full(10, 2.0), zeros)
    mat2, _, stats2 = build_stochastic_payoff_matrix(dist1, dist_buyer_only)
    assert np.allclose(mat2.traded_quantities, 0.0)
    assert stats2["tradeable_scenarios_count"] == 0
    # Buyer pays grid import in all 4 profiles
    assert np.allclose(mat2.payoffs_p2, -2.0 * 0.30)


# ---------------------------------------------------------------------------
# Phase 2 Validation Tests (Step 3: Scenario Properties and Invariants)
# ---------------------------------------------------------------------------

def test_residual_sign_convention(residual_pool):
    """Residual sign convention must strictly be e = actual - predicted."""
    # Check definition across the residual pool
    expected_residuals = residual_pool.actual_val_raw - residual_pool.preds_val_raw
    np.testing.assert_allclose(residual_pool.residuals, expected_residuals, atol=1e-7)

    # Hand-calculated example:
    # If actual = 2.5 kWh and point forecast = 1.0 kWh:
    actual = 2.5
    point_forecast = 1.0
    correct_residual = actual - point_forecast  # +1.5
    inverted_residual = point_forecast - actual  # -1.5

    # Adding correct residual recovers actual:
    scenario_correct = max(0.0, point_forecast + correct_residual)
    scenario_inverted = max(0.0, point_forecast + inverted_residual)
    assert scenario_correct == pytest.approx(actual)
    assert scenario_inverted != pytest.approx(actual)


def test_household_and_target_alignment(residual_pool):
    """Validation residual pool must strictly preserve household and target variable alignment."""
    # Pool size: exactly 2103 pairs (701 per household across 3 households)
    assert len(residual_pool.residuals) == 2103
    for house_id in ["H001", "H002", "H003"]:
        mask = (residual_pool.val_house_ids == house_id)
        assert np.sum(mask) == 701, f"{house_id} must have exactly 701 validation residual pairs"

        # Check target variables: column 0 is demand, column 1 is solar
        d_stat, s_stat = residual_pool.get_statistics(house_id=house_id)
        assert d_stat.target_name == "demand_residual_kwh"
        assert s_stat.target_name == "solar_residual_kwh"
        assert d_stat.sample_size == 701
        assert s_stat.sample_size == 701

        # Check that individual household statistics match manual slicing
        d_sub = residual_pool.demand_residuals[mask]
        s_sub = residual_pool.solar_residuals[mask]
        assert d_stat.mean == pytest.approx(float(np.mean(d_sub)), abs=1e-4)
        assert s_stat.mean == pytest.approx(float(np.mean(s_sub)), abs=1e-4)
        assert d_stat.std_dev == pytest.approx(float(np.std(d_sub, ddof=1)), abs=1e-4)
        assert s_stat.std_dev == pytest.approx(float(np.std(s_sub, ddof=1)), abs=1e-4)


def test_paired_residual_sampling_preserves_joint_distribution(residual_pool):
    """Paired empirical resampling must draw demand and solar residuals from identical time steps."""
    num_scenarios = 500
    ed, es = residual_pool.sample_residuals(
        num_scenarios=num_scenarios,
        house_id="H001",
        random_seed=42,
        paired=True,
        method="empirical",
    )
    mask = (residual_pool.val_house_ids == "H001")
    pool_h1 = residual_pool.residuals[mask]

    # Every sampled pair (ed[i], es[i]) must exist as an exact row in the household's pool
    for i in range(num_scenarios):
        diff = np.abs(pool_h1 - np.array([ed[i], es[i]]))
        match = np.any(np.all(diff < 1e-9, axis=1))
        assert match, f"Sampled pair ({ed[i]}, {es[i]}) not found in validation pool"

    # When paired=False, joint pairing is broken
    ed_unpaired, es_unpaired = residual_pool.sample_residuals(
        num_scenarios=num_scenarios,
        house_id="H001",
        random_seed=42,
        paired=False,
        method="empirical",
    )
    # Check that not all pairs exist as simultaneous observations
    unpaired_matches = [
        np.any(np.all(np.abs(pool_h1 - np.array([ed_unpaired[i], es_unpaired[i]])) < 1e-9, axis=1))
        for i in range(num_scenarios)
    ]
    assert not all(unpaired_matches), "Unpaired sampling should not preserve all joint pairs"


def test_percentiles_calculation_and_hand_calculated_example():
    """Verify 5th, 50th, and 95th percentiles match hand-calculated ground truth."""
    # Synthetic distribution of 20 equally spaced points from 1.0 to 20.0
    demand_vals = np.linspace(1.0, 20.0, 20)  # [1, 2, 3, ..., 20]
    solar_vals = np.linspace(0.0, 10.0, 20)   # [0, 0.526, ..., 10]

    dist = ScenarioDistribution(
        house_id="H_TEST",
        num_scenarios=20,
        forecast_demand_mean_kwh=10.5,
        forecast_solar_mean_kwh=5.0,
        scenarios_demand_kwh=demand_vals,
        scenarios_solar_kwh=solar_vals,
        actual_demand_kwh=10.0,
        actual_solar_kwh=5.0,
    )
    df = dist.get_summary_dataframe()
    d_row = df[df["Variable"] == "Demand (kWh)"].iloc[0]

    # Hand-calculations for demand:
    # 5th percentile of [1, ..., 20]: 1.0 + 0.05 * 19 = 1.95
    # Median (50th percentile): (10 + 11) / 2 = 10.5
    # 95th percentile: 1.0 + 0.95 * 19 = 19.05
    # Mean: 10.5
    # Min: 1.0, Max: 20.0
    assert d_row["Q05"] == pytest.approx(1.95, abs=1e-4)
    assert d_row["Median"] == pytest.approx(10.5, abs=1e-4)
    assert d_row["Q95"] == pytest.approx(19.05, abs=1e-4)
    assert d_row["Scenario_Mean"] == pytest.approx(10.5, abs=1e-4)
    assert d_row["Min"] == pytest.approx(1.0, abs=1e-4)
    assert d_row["Max"] == pytest.approx(20.0, abs=1e-4)
    assert bool(d_row["In_90pct_PI"]) is True


def test_scenario_summary_dataframe_consistency(forecaster, residual_pool):
    """ScenarioDistribution summary DataFrame must strictly match array-level statistics."""
    pred = forecaster.predict_next_hour("H001", "2013-05-15 14:00:00")
    mc = MonteCarloSimulator(residual_pool=residual_pool)
    dist = mc.generate_scenarios(pred, num_scenarios=1000, random_seed=123)

    df = dist.get_summary_dataframe()
    d_row = df[df["Variable"] == "Demand (kWh)"].iloc[0]
    s_row = df[df["Variable"] == "Solar (kWh)"].iloc[0]

    d_arr = dist.scenarios_demand_kwh
    s_arr = dist.scenarios_solar_kwh

    # Demand check
    assert d_row["Scenario_Mean"] == pytest.approx(float(np.mean(d_arr)), abs=1e-4)
    assert d_row["Scenario_Std"] == pytest.approx(float(np.std(d_arr, ddof=1)), abs=1e-4)
    assert d_row["Q05"] == pytest.approx(float(np.percentile(d_arr, 5)), abs=1e-4)
    assert d_row["Median"] == pytest.approx(float(np.median(d_arr)), abs=1e-4)
    assert d_row["Q95"] == pytest.approx(float(np.percentile(d_arr, 95)), abs=1e-4)
    assert d_row["Min"] == pytest.approx(float(np.min(d_arr)), abs=1e-4)
    assert d_row["Max"] == pytest.approx(float(np.max(d_arr)), abs=1e-4)

    # Solar check
    assert s_row["Scenario_Mean"] == pytest.approx(float(np.mean(s_arr)), abs=1e-4)
    assert s_row["Scenario_Std"] == pytest.approx(float(np.std(s_arr, ddof=1)), abs=1e-4)
    assert s_row["Q05"] == pytest.approx(float(np.percentile(s_arr, 5)), abs=1e-4)
    assert s_row["Median"] == pytest.approx(float(np.median(s_arr)), abs=1e-4)
    assert s_row["Q95"] == pytest.approx(float(np.percentile(s_arr, 95)), abs=1e-4)
    assert s_row["Min"] == pytest.approx(float(np.min(s_arr)), abs=1e-4)
    assert s_row["Max"] == pytest.approx(float(np.max(s_arr)), abs=1e-4)


def test_zero_forecasts_and_extreme_residuals(residual_pool):
    """Test handling of zero forecasts, large negative residuals, and extreme positive spikes."""
    mc = MonteCarloSimulator(residual_pool=residual_pool)

    # Case 1: Point forecast is exactly zero
    zero_forecast = ForecastResult(
        house_id="H001",
        forecast_timestamp=pd.Timestamp("2013-05-01 00:00:00"),
        predicted_demand_kwh=0.0,
        predicted_solar_generation_kwh=0.0,
        actual_demand_kwh=0.0,
        actual_solar_generation_kwh=0.0,
        is_held_out_period=True,
    )
    dist_zero = mc.generate_scenarios(zero_forecast, num_scenarios=500, random_seed=42)
    # Scenarios must be nonnegative
    assert np.all(dist_zero.scenarios_demand_kwh >= 0.0)
    assert np.all(dist_zero.scenarios_solar_kwh >= 0.0)
    # Any negative sampled residuals must be clipped to zero
    assert np.any(dist_zero.scenarios_demand_kwh == 0.0)

    # Case 2: Extreme positive residual does not overflow and preserves value
    large_pos_forecast = ForecastResult(
        house_id="H001",
        forecast_timestamp=pd.Timestamp("2013-05-01 00:00:00"),
        predicted_demand_kwh=50.0,
        predicted_solar_generation_kwh=20.0,
        actual_demand_kwh=50.0,
        actual_solar_generation_kwh=20.0,
        is_held_out_period=True,
    )
    dist_large = mc.generate_scenarios(large_pos_forecast, num_scenarios=100, random_seed=42)
    assert np.all(dist_large.scenarios_demand_kwh > 45.0)
    assert np.all(np.isfinite(dist_large.scenarios_demand_kwh))


def test_protocol_b_deterministic_seed():
    """Protocol B (stable identifier seed derivation) must be order-independent and deterministic."""
    s1 = derive_observation_seed("H001", "2013-05-01 12:00:00", base_seed=42)
    s2 = derive_observation_seed("H001", "2013-05-01 12:00:00", base_seed=42)
    assert s1 == s2, "Identical inputs must produce identical 32-bit seeds"

    # Different timestamp produces different seed
    s3 = derive_observation_seed("H001", "2013-05-01 13:00:00", base_seed=42)
    assert s1 != s3

    # Different household produces different seed
    s4 = derive_observation_seed("H002", "2013-05-01 12:00:00", base_seed=42)
    assert s1 != s4

    # Seed is a valid unsigned 32-bit integer
    assert 0 <= s1 < 2**32


def test_protocol_a_sequential_generator(forecaster, residual_pool):
    """Protocol A (shared generator stream) advances state across sequential calls."""
    mc = MonteCarloSimulator(residual_pool=residual_pool)
    pred = forecaster.predict_next_hour("H001", "2013-05-01 12:00:00")

    # Call 1 and Call 2 sharing single generator
    shared_rng = np.random.default_rng(42)
    d1 = mc.generate_scenarios(pred, num_scenarios=100, random_seed=shared_rng)
    d2 = mc.generate_scenarios(pred, num_scenarios=100, random_seed=shared_rng)

    # Scenarios must differ between consecutive steps
    assert not np.array_equal(d1.scenarios_demand_kwh, d2.scenarios_demand_kwh)

    # Re-running from fresh generator with same seed must reproduce the exact sequence
    fresh_rng = np.random.default_rng(42)
    d1_rep = mc.generate_scenarios(pred, num_scenarios=100, random_seed=fresh_rng)
    d2_rep = mc.generate_scenarios(pred, num_scenarios=100, random_seed=fresh_rng)
    np.testing.assert_array_equal(d1.scenarios_demand_kwh, d1_rep.scenarios_demand_kwh)
    np.testing.assert_array_equal(d2.scenarios_demand_kwh, d2_rep.scenarios_demand_kwh)


def test_physical_units_in_kwh(residual_pool, forecaster):
    """Residuals, predictions, and scenarios must be in physical kWh units, not normalized [0, 1]."""
    pred = forecaster.predict_next_hour("H001", "2013-06-08 10:00:00")
    mc = MonteCarloSimulator(residual_pool=residual_pool)
    dist = mc.generate_scenarios(pred, num_scenarios=500, random_seed=42)

    # H001 peak demand in validation/test exceeds 1.0 kWh
    d_max = float(np.max(dist.scenarios_demand_kwh))
    assert d_max > 1.0, f"Scenario demand maximum {d_max} must exceed 1.0 kWh (confirming unscaled units)"

    # Validation residual max exceeds 1.0 kWh
    d_stat, _ = residual_pool.get_statistics("H001")
    assert d_stat.max_val > 1.0, "Validation residual max must exceed 1.0 kWh"

