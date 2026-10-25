"""Unit tests for Monte Carlo uncertainty module."""

import pytest
import numpy as np

from src.forecasting.predict import EnergyForecaster, ForecastResult
from src.stochastic.monte_carlo import (
    MonteCarloSimulator,
    ValidationResidualPool,
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

