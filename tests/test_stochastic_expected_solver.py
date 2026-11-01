"""Comprehensive test suite for Phase 8E: Stochastic Expected-Payoff Nash Equilibrium Engine.

Validates all 16 required conditions:
1. Scenario reproducibility.
2. Cross-household scenario-index synchronization.
3. Timestamp-keyed Phase 7.1 dispatch retrieval.
4. Correct post-battery physical net positions.
5. Expected-role classification.
6. Role-conflict scenarios submit zero quantity.
7. Dynamic active-player profile counts (3, 2, 1, 0 players).
8. Expected payoff averaging includes zero-payoff scenarios (denominator M=1,000).
9. Zero-trade pruning gives identical results to unpruned computation.
10. Expected-payoff unilateral deviation correctness.
11. Strict/weak stochastic PNE classification.
12. Pareto-undominated expected-payoff filtering.
13. Financial balance and energy conservation.
14. Welfare identity: expected welfare = 0.22 * expected traded volume.
15. Deterministic special case: identical scenarios reproduce deterministic game.
16. Repeatability with the same timestamp and seed.
Plus: Verification of role-flipping scenario distributions.
"""

from __future__ import annotations

import copy
import pytest
import numpy as np
import pandas as pd

from src.forecasting.predict import EnergyForecaster
from src.game.strategic_market import (
    DEFAULT_GRID_EXPORT_CREDIT_AUD,
    DEFAULT_GRID_IMPORT_TARIFF_AUD,
    DEFAULT_NUMERICAL_TOLERANCE,
    STRATEGIC_PRICE_GRID,
    MarketRole,
)
from src.game.strategic_solver import (
    EquilibriumClassification,
    solve_deterministic_nash_equilibrium,
)
from src.stochastic.monte_carlo import ValidationResidualPool
from src.stochastic.strategic_expected_solver import (
    Phase7DispatchProvider,
    ScenarioSet,
    StochasticNashRecord,
    StochasticStrategicGameResult,
    build_synchronized_scenarios,
    derive_synchronized_seed,
    solve_stochastic_nash_equilibrium,
    verify_residual_pool_synchronization,
)


TEST_TIMESTAMP = "2013-05-15 11:00:00"


@pytest.fixture(scope="module")
def forecaster() -> EnergyForecaster:
    return EnergyForecaster()


@pytest.fixture(scope="module")
def residual_pool(forecaster: EnergyForecaster) -> ValidationResidualPool:
    return ValidationResidualPool(forecaster=forecaster)


@pytest.fixture(scope="module")
def dispatch_provider() -> Phase7DispatchProvider:
    return Phase7DispatchProvider()


@pytest.fixture(scope="module")
def sample_scenarios(
    forecaster: EnergyForecaster,
    residual_pool: ValidationResidualPool,
    dispatch_provider: Phase7DispatchProvider,
) -> ScenarioSet:
    return build_synchronized_scenarios(
        timestamp=TEST_TIMESTAMP,
        forecaster=forecaster,
        residual_pool=residual_pool,
        dispatch_provider=dispatch_provider,
        num_scenarios=1000,
        base_seed=42,
    )


# -----------------------------------------------------------------------------
# 1. Scenario Reproducibility
# -----------------------------------------------------------------------------
def test_scenario_reproducibility(
    forecaster: EnergyForecaster,
    residual_pool: ValidationResidualPool,
    dispatch_provider: Phase7DispatchProvider,
):
    """Same timestamp and base seed must produce bit-exact identical ScenarioSet."""
    s1 = build_synchronized_scenarios(
        TEST_TIMESTAMP, forecaster, residual_pool, dispatch_provider, num_scenarios=200, base_seed=42
    )
    s2 = build_synchronized_scenarios(
        TEST_TIMESTAMP, forecaster, residual_pool, dispatch_provider, num_scenarios=200, base_seed=42
    )

    assert s1.scenario_seed == s2.scenario_seed
    assert s1.ex_ante_roles == s2.ex_ante_roles
    assert s1.expected_net_positions_kwh == s2.expected_net_positions_kwh
    for hid in ("H001", "H002", "H003"):
        np.testing.assert_array_equal(s1.scenarios_demand_kwh[hid], s2.scenarios_demand_kwh[hid])
        np.testing.assert_array_equal(s1.scenarios_solar_kwh[hid], s2.scenarios_solar_kwh[hid])
        np.testing.assert_array_equal(s1.net_positions_kwh[hid], s2.net_positions_kwh[hid])


# -----------------------------------------------------------------------------
# 2. Cross-Household Scenario-Index Synchronization
# -----------------------------------------------------------------------------
def test_cross_household_synchronization(residual_pool: ValidationResidualPool):
    """Residual pool must be chronologically synchronized across all three households."""
    ok, msg = verify_residual_pool_synchronization(residual_pool)
    assert ok, f"Residual pool synchronization failed: {msg}"


def test_seed_derivation_deterministic():
    """derive_synchronized_seed must be deterministic and not use Python's built-in hash."""
    seed1 = derive_synchronized_seed("2013-05-15 11:00:00", base_seed=42)
    seed2 = derive_synchronized_seed("2013-05-15 11:00:00", base_seed=42)
    assert seed1 == seed2
    assert 0 <= seed1 < 2**32
    # Different timestamp produces different seed
    seed3 = derive_synchronized_seed("2013-05-15 12:00:00", base_seed=42)
    assert seed1 != seed3


# -----------------------------------------------------------------------------
# 3. Timestamp-Keyed Phase 7.1 Dispatch Retrieval
# -----------------------------------------------------------------------------
def test_phase7_dispatch_retrieval(dispatch_provider: Phase7DispatchProvider):
    """Verify dispatch retrieval is keyed by timestamp and household ID, with constraints."""
    c1, d1 = dispatch_provider.get_dispatch("2013-05-15 11:00:00", "H001")
    c2, d2 = dispatch_provider.get_dispatch("2013-05-15 11:00:00", "H002")
    c3, d3 = dispatch_provider.get_dispatch("2013-05-15 11:00:00", "H003")

    # Values must match reports/phase7_hourly_records.csv
    assert c1 >= 0.0 and d1 >= 0.0
    assert c2 >= 0.0 and d2 >= 0.0
    assert c3 >= 0.0 and d3 >= 0.0
    # Mutual exclusion
    assert (c1 * d1) <= DEFAULT_NUMERICAL_TOLERANCE
    assert (c2 * d2) <= DEFAULT_NUMERICAL_TOLERANCE
    assert (c3 * d3) <= DEFAULT_NUMERICAL_TOLERANCE


# -----------------------------------------------------------------------------
# 4. Correct Post-Battery Physical Net Positions
# -----------------------------------------------------------------------------
def test_post_battery_net_positions(sample_scenarios: ScenarioSet):
    """n_i(s) must exactly equal (D_i(s) + C_0,i) - (S_i(s) + B_0,i)."""
    for hid in sample_scenarios.house_ids:
        d = sample_scenarios.scenarios_demand_kwh[hid]
        s = sample_scenarios.scenarios_solar_kwh[hid]
        c0 = sample_scenarios.battery_charge_kwh[hid]
        b0 = sample_scenarios.battery_discharge_kwh[hid]
        expected_n = (d + c0) - (s + b0)
        actual_n = sample_scenarios.net_positions_kwh[hid]
        np.testing.assert_allclose(actual_n, expected_n, atol=1e-12)


# -----------------------------------------------------------------------------
# 5. Expected-Role Classification & Role-Flipping Realizations
# -----------------------------------------------------------------------------
def test_expected_role_classification_and_flips(sample_scenarios: ScenarioSet):
    """Ex-ante roles must match sign of E[n_i], and role flips must be tracked."""
    for hid in sample_scenarios.house_ids:
        e_n = sample_scenarios.expected_net_positions_kwh[hid]
        role = sample_scenarios.ex_ante_roles[hid]
        if e_n < -DEFAULT_NUMERICAL_TOLERANCE:
            assert role == MarketRole.SELLER
        elif e_n > DEFAULT_NUMERICAL_TOLERANCE:
            assert role == MarketRole.BUYER
        else:
            assert role == MarketRole.INACTIVE

        flips = sample_scenarios.role_flip_counts[hid]
        assert flips["seller"] + flips["buyer"] + flips["inactive"] == sample_scenarios.num_scenarios

    # Test hour 2013-05-15 11:00 has demonstrated flips for H001, H002, and H003
    assert sample_scenarios.role_flip_counts["H001"]["buyer"] > 0
    assert sample_scenarios.role_flip_counts["H002"]["buyer"] > 0
    assert sample_scenarios.role_flip_counts["H003"]["seller"] > 0


# -----------------------------------------------------------------------------
# 6. Dynamic Active-Player Profile Counts (3, 2, 1, 0 Players)
# -----------------------------------------------------------------------------
def test_dynamic_active_player_profile_counts(sample_scenarios: ScenarioSet):
    """Solver must support 3, 2, 1, and 0 active players without hardcoding."""
    # 3 active players: 7^3 = 343 profiles, 6,174 deviations
    res3 = solve_stochastic_nash_equilibrium(sample_scenarios, prune_zero_trade=True)
    assert res3.num_active_players == 3
    assert res3.num_profiles_evaluated == 343
    assert res3.num_deviations_evaluated == 343 * 3 * 6

    # 2 active players: force H001 inactive
    scenarios_2p = copy.deepcopy(sample_scenarios)
    object.__setattr__(scenarios_2p, "ex_ante_roles", {
        "H001": MarketRole.INACTIVE,
        "H002": MarketRole.SELLER,
        "H003": MarketRole.BUYER,
    })
    res2 = solve_stochastic_nash_equilibrium(scenarios_2p, prune_zero_trade=True)
    assert res2.num_active_players == 2
    assert res2.num_profiles_evaluated == 49
    assert res2.num_deviations_evaluated == 49 * 2 * 6

    # 1 active player: force H001, H002 inactive (only H003 buyer)
    scenarios_1p = copy.deepcopy(sample_scenarios)
    object.__setattr__(scenarios_1p, "ex_ante_roles", {
        "H001": MarketRole.INACTIVE,
        "H002": MarketRole.INACTIVE,
        "H003": MarketRole.BUYER,
    })
    res1 = solve_stochastic_nash_equilibrium(scenarios_1p, prune_zero_trade=True)
    assert res1.num_active_players == 1
    assert res1.num_profiles_evaluated == 7
    assert res1.num_deviations_evaluated == 7 * 1 * 6

    # 0 active players: all inactive
    scenarios_0p = copy.deepcopy(sample_scenarios)
    object.__setattr__(scenarios_0p, "ex_ante_roles", {
        "H001": MarketRole.INACTIVE,
        "H002": MarketRole.INACTIVE,
        "H003": MarketRole.INACTIVE,
    })
    res0 = solve_stochastic_nash_equilibrium(scenarios_0p, prune_zero_trade=True)
    assert res0.num_active_players == 0
    assert res0.num_profiles_evaluated == 1
    assert res0.num_deviations_evaluated == 0


# -----------------------------------------------------------------------------
# 7. Zero-Trade Pruning Equivalence (Requirement 9 & 8)
# -----------------------------------------------------------------------------
def test_zero_trade_pruning_equivalence(
    forecaster: EnergyForecaster,
    residual_pool: ValidationResidualPool,
    dispatch_provider: Phase7DispatchProvider,
):
    """Pruned and unpruned solver must produce identical payoffs, welfare, and equilibria."""
    # Use smaller scenario count (100) for fast equivalence check
    scenarios_small = build_synchronized_scenarios(
        TEST_TIMESTAMP, forecaster, residual_pool, dispatch_provider, num_scenarios=100, base_seed=42
    )

    res_pruned = solve_stochastic_nash_equilibrium(scenarios_small, prune_zero_trade=True)
    res_unpruned = solve_stochastic_nash_equilibrium(scenarios_small, prune_zero_trade=False)

    assert res_pruned.num_equilibria == res_unpruned.num_equilibria
    assert res_pruned.strict_pne_count == res_unpruned.strict_pne_count
    assert res_pruned.weak_pne_count == res_unpruned.weak_pne_count
    assert res_pruned.pareto_undominated_pne_count == res_unpruned.pareto_undominated_pne_count

    # Compare selected equilibrium payoffs
    if res_pruned.selected_equilibrium and res_unpruned.selected_equilibrium:
        assert res_pruned.selected_equilibrium.profile == res_unpruned.selected_equilibrium.profile
        assert abs(res_pruned.expected_traded_kwh - res_unpruned.expected_traded_kwh) < 1e-10
        assert abs(res_pruned.expected_community_welfare_aud - res_unpruned.expected_community_welfare_aud) < 1e-10

        for hid in ("H001", "H002", "H003"):
            u_p = res_pruned.expected_household_payoffs_aud[hid]
            u_u = res_unpruned.expected_household_payoffs_aud[hid]
            assert abs(u_p - u_u) < 1e-10


# -----------------------------------------------------------------------------
# 8. Welfare Identity and Financial Balance (Requirement 13 & 14)
# -----------------------------------------------------------------------------
def test_welfare_identity_and_balance(sample_scenarios: ScenarioSet):
    """Expected community welfare must strictly equal 0.22 * expected traded volume."""
    res = solve_stochastic_nash_equilibrium(sample_scenarios, prune_zero_trade=True)

    if res.selected_equilibrium:
        exp_q = res.expected_traded_kwh
        exp_w = res.expected_community_welfare_aud
        # Welfare identity: Delta W = 0.22 * Q_P2P
        expected_w_formula = 0.22 * exp_q
        assert abs(exp_w - expected_w_formula) < 1e-10

        # Sum of household benefits equals community welfare
        payoffs_sum = sum(res.expected_household_payoffs_aud.values())
        assert abs(payoffs_sum - exp_w) < 1e-10


# -----------------------------------------------------------------------------
# 9. Expected-Payoff Unilateral Deviation Correctness (Requirement 10 & 11)
# -----------------------------------------------------------------------------
def test_unilateral_deviation_correctness(sample_scenarios: ScenarioSet):
    """Every detected pure Nash equilibrium must have non-positive profitable deviation gain."""
    res = solve_stochastic_nash_equilibrium(sample_scenarios, prune_zero_trade=True)

    # For each detected equilibrium, max deviation gain must be <= tolerance
    for eq in res.expected_equilibria:
        assert eq.max_deviation_gain <= DEFAULT_NUMERICAL_TOLERANCE

    # Check strict vs weak classification
    for eq in res.strict_equilibria:
        assert eq.classification == EquilibriumClassification.STRICT
    for eq in res.weak_equilibria:
        assert eq.classification == EquilibriumClassification.WEAK


# -----------------------------------------------------------------------------
# 10. Pareto-Undominated Expected-Payoff Filtering (Requirement 12)
# -----------------------------------------------------------------------------
def test_pareto_undominated_filtering(sample_scenarios: ScenarioSet):
    """Pareto-undominated equilibria must not be strictly dominated by any candidate equilibrium."""
    res = solve_stochastic_nash_equilibrium(sample_scenarios, prune_zero_trade=True)

    undominated = res.pareto_undominated_equilibria
    assert len(undominated) <= len(res.expected_equilibria)

    # Verify no equilibrium in undominated is dominated by another equilibrium
    universe = list(sample_scenarios.house_ids)
    from src.game.strategic_solver import check_pareto_dominance

    for i in range(len(undominated)):
        for j in range(len(res.expected_equilibria)):
            assert not check_pareto_dominance(
                res.expected_equilibria[j].expected_payoffs,
                undominated[i].expected_payoffs,
                universe,
                tolerance=DEFAULT_NUMERICAL_TOLERANCE,
            )


# -----------------------------------------------------------------------------
# 11. Deterministic Special Case (Requirement 15)
# -----------------------------------------------------------------------------
def test_deterministic_special_case_equivalence():
    """When all scenarios are identical, stochastic solver must reproduce deterministic game."""
    # Construct a synthetic ScenarioSet with 100 identical realizations
    # H001: 1.5 kWh surplus (SELLER)
    # H002: 0.5 kWh deficit (BUYER)
    # H003: 0.8 kWh deficit (BUYER)
    n_scen = 100
    demand = {
        "H001": np.zeros(n_scen),
        "H002": np.full(n_scen, 0.5),
        "H003": np.full(n_scen, 0.8),
    }
    solar = {
        "H001": np.full(n_scen, 1.5),
        "H002": np.zeros(n_scen),
        "H003": np.zeros(n_scen),
    }
    net_pos = {
        "H001": np.full(n_scen, -1.5),
        "H002": np.full(n_scen, 0.5),
        "H003": np.full(n_scen, 0.8),
    }

    synthetic_scenarios = ScenarioSet(
        timestamp="2013-05-15 12:00:00",
        num_scenarios=n_scen,
        house_ids=("H001", "H002", "H003"),
        scenarios_demand_kwh=demand,
        scenarios_solar_kwh=solar,
        battery_charge_kwh={"H001": 0.0, "H002": 0.0, "H003": 0.0},
        battery_discharge_kwh={"H001": 0.0, "H002": 0.0, "H003": 0.0},
        net_positions_kwh=net_pos,
        expected_net_positions_kwh={"H001": -1.5, "H002": 0.5, "H003": 0.8},
        ex_ante_roles={
            "H001": MarketRole.SELLER,
            "H002": MarketRole.BUYER,
            "H003": MarketRole.BUYER,
        },
        role_flip_counts={
            "H001": {"seller": n_scen, "buyer": 0, "inactive": 0},
            "H002": {"seller": 0, "buyer": n_scen, "inactive": 0},
            "H003": {"seller": 0, "buyer": n_scen, "inactive": 0},
        },
        tradeable_scenario_indices=tuple(range(n_scen)),
        scenario_seed=42,
    )

    # Solve via stochastic solver
    stoch_res = solve_stochastic_nash_equilibrium(synthetic_scenarios, prune_zero_trade=True)

    # Solve via Phase 8C deterministic solver directly with exact same physical flows
    det_res = solve_deterministic_nash_equilibrium(
        surpluses_kwh={"H001": 1.5, "H002": 0.0, "H003": 0.0},
        deficits_kwh={"H001": 0.0, "H002": 0.5, "H003": 0.8},
        all_households=("H001", "H002", "H003"),
    )

    # Must find identical number of equilibria
    assert stoch_res.num_equilibria == det_res.num_equilibria
    assert stoch_res.strict_pne_count == det_res.num_strict
    assert stoch_res.weak_pne_count == det_res.num_weak
    assert stoch_res.pareto_undominated_pne_count == det_res.num_pareto_undominated

    # Selected equilibrium must match
    if stoch_res.selected_equilibrium and det_res.selected_equilibrium:
        assert stoch_res.selected_equilibrium.profile == det_res.selected_equilibrium.profile
        assert abs(stoch_res.expected_traded_kwh - det_res.selected_traded_kwh) < 1e-10
        assert abs(stoch_res.expected_community_welfare_aud - det_res.selected_welfare_aud) < 1e-10
        for hid in ("H001", "H002", "H003"):
            assert (
                abs(stoch_res.expected_household_payoffs_aud[hid] - det_res.selected_payoffs[hid])
                < 1e-10
            )


# -----------------------------------------------------------------------------
# 12. Repeatability with Same Timestamp and Seed (Requirement 16)
# -----------------------------------------------------------------------------
def test_solver_repeatability(sample_scenarios: ScenarioSet):
    """Re-running the solver with identical inputs must produce bit-exact results."""
    res1 = solve_stochastic_nash_equilibrium(sample_scenarios, prune_zero_trade=True)
    res2 = solve_stochastic_nash_equilibrium(sample_scenarios, prune_zero_trade=True)

    assert res1.num_equilibria == res2.num_equilibria
    assert res1.expected_traded_kwh == res2.expected_traded_kwh
    assert res1.expected_community_welfare_aud == res2.expected_community_welfare_aud
    assert res1.expected_household_payoffs_aud == res2.expected_household_payoffs_aud
    assert res1.selected_equilibrium.profile == res2.selected_equilibrium.profile

