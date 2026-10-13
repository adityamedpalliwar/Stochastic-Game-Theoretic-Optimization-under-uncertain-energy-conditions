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
    trade_u1, trade_u2  = u1[0, 0], u2[0, 0]
    notrade_u1, notrade_u2 = u1[1, 1], u2[1, 1]

    assert trade_u1 >= notrade_u1 - 1e-9
    assert trade_u2 >= notrade_u2 - 1e-9
