"""Comprehensive tests for battery storage integration (Phase 5A).

Tests all 10 Stage 5 requirements:
1. Empty battery, full permitted battery, and intermediate SOC.
2. Charge and discharge power limits with duration dt.
3. Efficiency losses and SOC state transitions.
4. Insufficient solar surplus for charging.
5. Insufficient stored energy for discharging.
6. Mutual exclusion / no simultaneous charging and discharging.
7. Physical energy conservation with battery, P2P trade, and grid flows.
8. Financial payoff consistency across all four strategy profiles.
9. Reproducible battery-aware Monte Carlo evaluation (Protocol B).
10. Compatibility with original battery-free baseline.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.energy.battery import BatteryState, BatteryStorage
from src.energy.energy_balance import (
    BatteryAwareEnergyBalance,
    BatteryAwarePostTradeBalance,
    EnergyBalance,
    compute_battery_aware_balance,
    compute_battery_post_trade_balance,
    compute_energy_balance,
    compute_post_trade_balance,
)
from src.game.game import run_two_household_game
from src.game.nash import find_pure_nash_equilibria
from src.game.payoff_matrix import build_two_household_payoff_matrix
from src.game.utility import compute_household_payoff
from src.stochastic.monte_carlo import (
    ScenarioDistribution,
    build_stochastic_payoff_matrix,
    derive_observation_seed,
)


# ---------------------------------------------------------------------------
# 1. Empty battery, full permitted battery, and intermediate SOC
# ---------------------------------------------------------------------------

def test_battery_soc_boundary_states():
    """Verify operation at empty permitted SOC (10%), full permitted SOC (90%), and 50%."""
    # Empty permitted battery: SOC = 0.10 (0.50 kWh stored)
    bat_empty = BatteryStorage(capacity_kwh=5.0, initial_soc=0.10, min_soc=0.10, max_soc=0.90)
    assert bat_empty.current_charge_kwh == pytest.approx(0.50)
    assert bat_empty.soc == pytest.approx(0.10)

    # Cannot discharge below min_soc: request 1.0 kWh -> deliver 0.0 kWh
    state_dis = bat_empty.step(energy_requested_to_discharge_kwh=1.0)
    assert state_dis.discharged_kwh == pytest.approx(0.0)
    assert bat_empty.current_charge_kwh == pytest.approx(0.50)
    assert bat_empty.soc == pytest.approx(0.10)

    # Can charge from empty: available 1.0 kWh -> actual charged 1.0 kWh
    state_ch = bat_empty.step(energy_available_to_charge_kwh=1.0)
    assert state_ch.charged_kwh == pytest.approx(1.0)
    assert bat_empty.current_charge_kwh == pytest.approx(0.50 + 1.0 * 0.95)

    # Full permitted battery: SOC = 0.90 (4.50 kWh stored)
    bat_full = BatteryStorage(capacity_kwh=5.0, initial_soc=0.90, min_soc=0.10, max_soc=0.90)
    assert bat_full.current_charge_kwh == pytest.approx(4.50)

    # Cannot charge above max_soc: available 1.0 kWh -> actual charged 0.0 kWh
    state_ch_full = bat_full.step(energy_available_to_charge_kwh=1.0)
    assert state_ch_full.charged_kwh == pytest.approx(0.0)
    assert bat_full.current_charge_kwh == pytest.approx(4.50)

    # Can discharge from full: request 1.0 kWh -> actual discharged 1.0 kWh
    state_dis_full = bat_full.step(energy_requested_to_discharge_kwh=1.0)
    assert state_dis_full.discharged_kwh == pytest.approx(1.0)
    assert bat_full.current_charge_kwh == pytest.approx(4.50 - 1.0 / 0.95)

    # Intermediate battery: SOC = 0.50 (2.50 kWh stored)
    bat_mid = BatteryStorage(capacity_kwh=5.0, initial_soc=0.50)
    assert bat_mid.available_charge_headroom_kwh(1.0) == pytest.approx(min(2.5, (4.5 - 2.5) / 0.95))
    assert bat_mid.available_discharge_capacity_kwh(1.0) == pytest.approx(min(2.5, (2.5 - 0.5) * 0.95))


# ---------------------------------------------------------------------------
# 2. Charge and discharge power limits with duration dt
# ---------------------------------------------------------------------------

def test_power_limits_across_durations():
    """Verify charge and discharge power limits convert correctly with duration dt."""
    bat = BatteryStorage(capacity_kwh=10.0, max_charge_rate_kw=2.5, max_discharge_rate_kw=2.5, initial_soc=0.50)

    # 1.0 hour duration: max power limit is 2.5 kW * 1.0 h = 2.5 kWh
    state1 = bat.step(energy_available_to_charge_kwh=5.0, duration_hours=1.0)
    assert state1.charged_kwh == pytest.approx(2.5)

    # Reset to mid
    bat.reset(0.50)

    # 0.5 hour duration: max power limit is 2.5 kW * 0.5 h = 1.25 kWh
    state2 = bat.step(energy_available_to_charge_kwh=5.0, duration_hours=0.5)
    assert state2.charged_kwh == pytest.approx(1.25)

    # Discharge power limit for 1.0 hour
    bat.reset(0.50)
    state_dis1 = bat.step(energy_requested_to_discharge_kwh=5.0, duration_hours=1.0)
    assert state_dis1.discharged_kwh == pytest.approx(2.5)

    # Discharge power limit for 0.5 hour
    bat.reset(0.50)
    state_dis2 = bat.step(energy_requested_to_discharge_kwh=5.0, duration_hours=0.5)
    assert state_dis2.discharged_kwh == pytest.approx(1.25)


# ---------------------------------------------------------------------------
# 3. Efficiency losses and SOC state transitions
# ---------------------------------------------------------------------------

def test_efficiency_losses_and_exact_soc_transitions():
    """Verify exact formula: E[t+1] = E[t] + eta_ch * C[t] - D[t] / eta_dis."""
    bat = BatteryStorage(
        capacity_kwh=5.0,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        initial_soc=0.40,  # 2.0 kWh
    )
    e_0 = 2.0

    # Charge C = 1.5 kWh
    state_c = bat.step(energy_available_to_charge_kwh=1.5, duration_hours=1.0)
    assert state_c.charged_kwh == pytest.approx(1.5)
    e_1 = e_0 + 0.95 * 1.5  # 2.0 + 1.425 = 3.425 kWh
    assert bat.current_charge_kwh == pytest.approx(e_1)
    assert state_c.initial_charge_kwh == pytest.approx(e_0)
    assert state_c.net_stored_energy_change_kwh == pytest.approx(1.425)

    # Discharge D = 0.95 kWh
    state_d = bat.step(energy_requested_to_discharge_kwh=0.95, duration_hours=1.0)
    assert state_d.discharged_kwh == pytest.approx(0.95)
    # Stored depletion is D / eta_dis = 0.95 / 0.95 = 1.0 kWh
    e_2 = e_1 - (0.95 / 0.95)  # 3.425 - 1.0 = 2.425 kWh
    assert bat.current_charge_kwh == pytest.approx(e_2)
    assert state_d.initial_charge_kwh == pytest.approx(e_1)
    assert state_d.net_stored_energy_change_kwh == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# 4. Insufficient solar surplus for charging
# ---------------------------------------------------------------------------

def test_insufficient_solar_surplus_clamping():
    """When solar surplus is smaller than headroom/power limit, charge only the available surplus."""
    bat = BatteryStorage(capacity_kwh=5.0, initial_soc=0.20)
    # Demand = 1.0 kWh, Solar = 1.25 kWh -> raw surplus = 0.25 kWh
    balance = compute_battery_aware_balance(
        demand_kwh=1.0,
        solar_generation_kwh=1.25,
        battery=bat,
        house_id="H001",
    )
    # Battery can take up to 2.5 kW, but only 0.25 kWh is available
    assert balance.solar_to_battery_kwh == pytest.approx(0.25)
    assert balance.surplus_kwh == pytest.approx(0.0)  # all surplus absorbed
    assert balance.deficit_kwh == pytest.approx(0.0)
    assert balance.self_consumption_kwh == pytest.approx(1.0)
    assert balance.battery_final_kwh == pytest.approx(1.0 + 0.25 * 0.95)


# ---------------------------------------------------------------------------
# 5. Insufficient stored energy for discharging
# ---------------------------------------------------------------------------

def test_insufficient_stored_energy_clamping():
    """When stored energy above min_soc is less than requested deficit, discharge only available footroom."""
    bat = BatteryStorage(capacity_kwh=5.0, min_soc=0.10, initial_soc=0.16)
    # Stored energy = 0.80 kWh. Min stored = 0.50 kWh. Stored above min = 0.30 kWh.
    # Max deliverable = 0.30 * 0.95 = 0.285 kWh.
    # Household has Demand = 2.0 kWh, Solar = 1.0 kWh -> raw deficit = 1.0 kWh.
    balance = compute_battery_aware_balance(
        demand_kwh=2.0,
        solar_generation_kwh=1.0,
        battery=bat,
        house_id="H002",
    )
    assert balance.battery_to_demand_kwh == pytest.approx(0.285)
    assert balance.deficit_kwh == pytest.approx(1.0 - 0.285)  # 0.715 kWh unserved deficit
    assert balance.surplus_kwh == pytest.approx(0.0)
    assert balance.battery_final_soc == pytest.approx(0.10)
    assert balance.battery_final_kwh == pytest.approx(0.50)


# ---------------------------------------------------------------------------
# 6. Mutual exclusion / No simultaneous charging and discharging
# ---------------------------------------------------------------------------

def test_mutual_exclusion_enforcement():
    """Charging and discharging in the same interval is forbidden by all guards."""
    bat = BatteryStorage()
    with pytest.raises(ValueError, match="simultaneously"):
        bat.step(energy_available_to_charge_kwh=1.0, energy_requested_to_discharge_kwh=1.0)

    # In BatteryAwareEnergyBalance, simultaneous C and D raises ValueError
    with pytest.raises(ValueError, match="Mutual exclusion violation"):
        BatteryAwareEnergyBalance(
            house_id="H001",
            demand_kwh=2.0,
            solar_generation_kwh=2.0,
            self_consumption_kwh=1.0,
            solar_to_battery_kwh=1.0,
            battery_to_demand_kwh=1.0,
            battery_initial_soc=0.5,
            battery_final_soc=0.5,
            battery_initial_kwh=2.5,
            battery_final_kwh=2.5,
            battery_losses_kwh=0.0,
            raw_deficit_kwh=0.0,
            raw_surplus_kwh=0.0,
            deficit_kwh=0.0,
            surplus_kwh=0.0,
        )


# ---------------------------------------------------------------------------
# 7. Energy conservation with battery, P2P trade, and grid flows
# ---------------------------------------------------------------------------

def test_energy_conservation_comprehensive_benchmark():
    """Verify hand-calculated physical energy conservation across both households and microgrid.

    Seller H001:
      Demand = 1.0 kWh, Solar = 4.0 kWh. Self-consumption = 1.0 kWh.
      Raw surplus = 3.0 kWh.
      Battery (initial 2.50 kWh): Headroom = (4.5 - 2.5) / 0.95 = 2.105263 kWh.
      Charged = 2.105263 kWh. Final stored = 4.50 kWh (SOC = 0.90).
      Post-battery surplus = 3.0 - 2.105263 = 0.894737 kWh.

    Buyer H002:
      Demand = 3.0 kWh, Solar = 0.5 kWh. Self-consumption = 0.5 kWh.
      Raw deficit = 2.5 kWh.
      Battery (initial 2.50 kWh): Footroom = (2.5 - 0.5) * 0.95 = 1.90 kWh.
      Discharged = 1.90 kWh. Final stored = 0.50 kWh (SOC = 0.10).
      Post-battery deficit = 2.5 - 1.90 = 0.60 kWh.

    P2P Market:
      Traded quantity = min(0.894737, 0.60) = 0.60 kWh.
      Seller exports to grid = 0.894737 - 0.60 = 0.294737 kWh.
      Buyer imports from grid = 0.60 - 0.60 = 0.00 kWh.
    """
    bat1 = BatteryStorage(capacity_kwh=5.0, initial_soc=0.50)
    bat2 = BatteryStorage(capacity_kwh=5.0, initial_soc=0.50)

    bal1 = compute_battery_aware_balance(1.0, 4.0, battery=bat1, house_id="H001")
    bal2 = compute_battery_aware_balance(3.0, 0.5, battery=bat2, house_id="H002")

    assert bal1.self_consumption_kwh == pytest.approx(1.0)
    assert bal1.solar_to_battery_kwh == pytest.approx(2.105263, abs=1e-5)
    assert bal1.battery_final_soc == pytest.approx(0.90)
    assert bal1.surplus_kwh == pytest.approx(0.894737, abs=1e-5)
    assert bal1.deficit_kwh == 0.0

    assert bal2.self_consumption_kwh == pytest.approx(0.5)
    assert bal2.battery_to_demand_kwh == pytest.approx(1.90)
    assert bal2.battery_final_soc == pytest.approx(0.10)
    assert bal2.deficit_kwh == pytest.approx(0.60)
    assert bal2.surplus_kwh == 0.0

    # Execute bilateral post-trade balance
    q_trade = min(bal1.surplus_kwh, bal2.deficit_kwh)
    assert q_trade == pytest.approx(0.60)

    post1 = compute_battery_post_trade_balance(bal1, p2p_sold_kwh=q_trade, p2p_bought_kwh=0.0)
    post2 = compute_battery_post_trade_balance(bal2, p2p_sold_kwh=0.0, p2p_bought_kwh=q_trade)

    # Check seller conservation identities
    assert post1.grid_exported_kwh == pytest.approx(0.894737 - 0.60, abs=1e-5)
    assert post1.grid_imported_kwh == 0.0
    # D1 = self + bat_dis + p2p_buy + grid_import
    assert post1.demand_kwh == pytest.approx(post1.self_consumption_kwh + post1.battery_to_demand_kwh + post1.p2p_bought_kwh + post1.grid_imported_kwh)
    # G1 = self + bat_ch + p2p_sell + grid_export
    assert post1.solar_generation_kwh == pytest.approx(post1.self_consumption_kwh + post1.solar_to_battery_kwh + post1.p2p_sold_kwh + post1.grid_exported_kwh)

    # Check buyer conservation identities
    assert post2.grid_imported_kwh == pytest.approx(0.0)
    assert post2.grid_exported_kwh == 0.0
    # D2 = self + bat_dis + p2p_buy + grid_import
    assert post2.demand_kwh == pytest.approx(post2.self_consumption_kwh + post2.battery_to_demand_kwh + post2.p2p_bought_kwh + post2.grid_imported_kwh)
    # G2 = self + bat_ch + p2p_sell + grid_export
    assert post2.solar_generation_kwh == pytest.approx(post2.self_consumption_kwh + post2.solar_to_battery_kwh + post2.p2p_sold_kwh + post2.grid_exported_kwh)

    # Community net conservation
    comm_d = post1.demand_kwh + post2.demand_kwh  # 4.0
    comm_g = post1.solar_generation_kwh + post2.solar_generation_kwh  # 4.5
    net_grid = (post1.grid_imported_kwh + post2.grid_imported_kwh) - (post1.grid_exported_kwh + post2.grid_exported_kwh)
    net_battery = (post1.battery_to_demand_kwh + post2.battery_to_demand_kwh) - (post1.solar_to_battery_kwh + post2.solar_to_battery_kwh)
    # (D - G) == NetGrid + NetBattery
    assert (comm_d - comm_g) == pytest.approx(net_grid + net_battery, abs=1e-5)


# ---------------------------------------------------------------------------
# 8. Financial payoff consistency across all four strategy profiles
# ---------------------------------------------------------------------------

def test_financial_payoff_consistency_all_profiles():
    """Verify financial cash flows, P2P cancellation, and payoffs across all 4 strategy profiles."""
    s_surplus = 0.894737
    b_deficit = 0.60
    p_imp = 0.30
    p_exp = 0.08
    p_p2p = 0.19
    q_trade = min(s_surplus, b_deficit)

    matrix = build_two_household_payoff_matrix(
        seller_id="H001",
        seller_surplus_kwh=s_surplus,
        buyer_id="H002",
        buyer_deficit_kwh=b_deficit,
        grid_import_price_aud=p_imp,
        grid_export_credit_aud=p_exp,
        p2p_price_aud=p_p2p,
    )

    i_offer = matrix.actions_p1.index("OFFER_P2P")
    i_export = matrix.actions_p1.index("EXPORT_GRID")
    j_accept = matrix.actions_p2.index("ACCEPT_P2P")
    j_grid = matrix.actions_p2.index("GRID_IMPORT")

    # Profile (OFFER_P2P, ACCEPT_P2P)
    p_seller, p_buyer = matrix.details[("OFFER_P2P", "ACCEPT_P2P")]
    # Buyer payment == Seller revenue
    assert p_seller.p2p_revenue_aud == pytest.approx(q_trade * p_p2p)
    assert p_buyer.p2p_payment_aud == pytest.approx(q_trade * p_p2p)
    assert p_seller.p2p_revenue_aud == pytest.approx(p_buyer.p2p_payment_aud)

    # Seller utility: P2P rev (0.114) + grid export rev ((0.894737 - 0.60)*0.08 = 0.023579) = 0.137579 AUD
    exp_u1_trade = 0.60 * 0.19 + (s_surplus - 0.60) * 0.08
    assert matrix.payoffs_p1[i_offer, j_accept] == pytest.approx(exp_u1_trade, abs=1e-5)

    # Buyer utility: -(P2P cost (0.114) + grid import cost (0.0)) = -0.114 AUD
    exp_u2_trade = -(0.60 * 0.19 + 0.0 * 0.30)
    assert matrix.payoffs_p2[i_offer, j_accept] == pytest.approx(exp_u2_trade, abs=1e-5)

    # Off-diagonal and baseline profiles: no trade (q = 0)
    exp_u1_base = s_surplus * 0.08
    exp_u2_base = -(b_deficit * 0.30)

    for a1, a2 in [("OFFER_P2P", "GRID_IMPORT"), ("EXPORT_GRID", "ACCEPT_P2P"), ("EXPORT_GRID", "GRID_IMPORT")]:
        i = matrix.actions_p1.index(a1)
        j = matrix.actions_p2.index(a2)
        assert matrix.traded_quantities[i, j] == 0.0
        assert matrix.payoffs_p1[i, j] == pytest.approx(exp_u1_base, abs=1e-5)
        assert matrix.payoffs_p2[i, j] == pytest.approx(exp_u2_base, abs=1e-5)

    # Cooperative equilibrium strictly Pareto dominates status quo baseline
    assert matrix.payoffs_p1[i_offer, j_accept] > matrix.payoffs_p1[i_export, j_grid]
    assert matrix.payoffs_p2[i_offer, j_accept] > matrix.payoffs_p2[i_export, j_grid]


# ---------------------------------------------------------------------------
# 9. Reproducible battery-aware Monte Carlo evaluation (Protocol B)
# ---------------------------------------------------------------------------

def test_reproducible_battery_monte_carlo():
    """Verify Monte Carlo stochastic payoff matrix produces bit-for-bit deterministic results under Protocol B."""
    seed = derive_observation_seed("H001", "2013-06-08 10:00:00", base_seed=42)
    rng = np.random.default_rng(seed)

    n_scen = 500
    s_d = rng.uniform(0.2, 0.8, size=n_scen)
    s_g = rng.uniform(1.0, 3.5, size=n_scen)
    b_d = rng.uniform(1.0, 3.0, size=n_scen)
    b_g = rng.uniform(0.0, 0.6, size=n_scen)

    dist_s = ScenarioDistribution("H001", n_scen, float(np.mean(s_d)), float(np.mean(s_g)), s_d, s_g)
    dist_b = ScenarioDistribution("H002", n_scen, float(np.mean(b_d)), float(np.mean(b_g)), b_d, b_g)

    bat_s = BatteryStorage(capacity_kwh=5.0, initial_soc=0.50)
    bat_b = BatteryStorage(capacity_kwh=5.0, initial_soc=0.50)

    # Run 1
    m1, df1, stats1 = build_stochastic_payoff_matrix(
        dist_s, dist_b,
        battery_seller=bat_s,
        battery_buyer=bat_b,
    )

    # Run 2 with freshly initialized identical objects
    bat_s2 = BatteryStorage(capacity_kwh=5.0, initial_soc=0.50)
    bat_b2 = BatteryStorage(capacity_kwh=5.0, initial_soc=0.50)

    m2, df2, stats2 = build_stochastic_payoff_matrix(
        dist_s, dist_b,
        battery_seller=bat_s2,
        battery_buyer=bat_b2,
    )

    # Assert exact reproducibility
    np.testing.assert_array_equal(m1.payoffs_p1, m2.payoffs_p1)
    np.testing.assert_array_equal(m1.payoffs_p2, m2.payoffs_p2)
    np.testing.assert_array_equal(m1.traded_quantities, m2.traded_quantities)
    assert stats1["mean_feasible_trade_kwh"] == pytest.approx(stats2["mean_feasible_trade_kwh"])
    assert stats1["seller_battery_final_soc_mean"] == pytest.approx(stats2["seller_battery_final_soc_mean"])
    assert stats1["buyer_battery_final_soc_mean"] == pytest.approx(stats2["buyer_battery_final_soc_mean"])


# ---------------------------------------------------------------------------
# 10. Compatibility with original battery-free baseline
# ---------------------------------------------------------------------------

def test_compatibility_with_battery_free_baseline():
    """Verify that battery-disabled or None battery produces identical output to original baseline."""
    rng = np.random.default_rng(999)
    n = 100
    s_d = rng.uniform(0.1, 0.5, size=n)
    s_g = rng.uniform(0.5, 2.0, size=n)
    b_d = rng.uniform(0.8, 2.5, size=n)
    b_g = rng.uniform(0.0, 0.3, size=n)

    dist_s = ScenarioDistribution("H001", n, float(np.mean(s_d)), float(np.mean(s_g)), s_d, s_g)
    dist_b = ScenarioDistribution("H002", n, float(np.mean(b_d)), float(np.mean(b_g)), b_d, b_g)

    # Case A: Standard battery-free call (omitting battery args)
    m_baseline, df_baseline, stats_baseline = build_stochastic_payoff_matrix(dist_s, dist_b)

    # Case B: Explicitly passing None
    m_none, df_none, stats_none = build_stochastic_payoff_matrix(dist_s, dist_b, battery_seller=None, battery_buyer=None)

    # Case C: Zero-power battery (cannot charge or discharge)
    bat_zero_s = BatteryStorage(capacity_kwh=5.0, max_charge_rate_kw=0.0, max_discharge_rate_kw=0.0)
    bat_zero_b = BatteryStorage(capacity_kwh=5.0, max_charge_rate_kw=0.0, max_discharge_rate_kw=0.0)
    m_zero, df_zero, stats_zero = build_stochastic_payoff_matrix(dist_s, dist_b, battery_seller=bat_zero_s, battery_buyer=bat_zero_b)

    # All three must produce identical payoffs and traded quantities
    np.testing.assert_allclose(m_baseline.payoffs_p1, m_none.payoffs_p1, atol=1e-12)
    np.testing.assert_allclose(m_baseline.payoffs_p2, m_none.payoffs_p2, atol=1e-12)
    np.testing.assert_allclose(m_baseline.traded_quantities, m_none.traded_quantities, atol=1e-12)

    np.testing.assert_allclose(m_baseline.payoffs_p1, m_zero.payoffs_p1, atol=1e-12)
    np.testing.assert_allclose(m_baseline.payoffs_p2, m_zero.payoffs_p2, atol=1e-12)
    np.testing.assert_allclose(m_baseline.traded_quantities, m_zero.traded_quantities, atol=1e-12)

    # Point energy balance compatibility
    bal_raw = compute_energy_balance(1.5, 2.5, house_id="H001")
    bal_bat_none = compute_battery_aware_balance(1.5, 2.5, battery=None, house_id="H001")
    assert bal_raw.self_consumption_kwh == pytest.approx(bal_bat_none.self_consumption_kwh)
    assert bal_raw.surplus_kwh == pytest.approx(bal_bat_none.surplus_kwh)
    assert bal_raw.deficit_kwh == pytest.approx(bal_bat_none.deficit_kwh)
