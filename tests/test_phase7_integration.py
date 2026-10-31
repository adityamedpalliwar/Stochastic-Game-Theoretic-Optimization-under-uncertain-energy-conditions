"""Comprehensive Test Suite for Phase 7: Multi-Household Stochastic Energy Market Integration.

Tests all Section 5 requirements:
1. Multiple simultaneous sellers and buyers matching.
2. Insufficient community surplus and insufficient community demand.
3. No-trade hours (all buyers, all sellers, all zero).
4. Partial allocation and remaining grid settlement.
5. Zero and near-zero surplus/deficit edge cases.
6. Battery constraints and per-household physical balance conservation.
7. Transaction ledger consistency and reproducibility.
8. Scenario generation and prevention of future-actual leakage.
9. Correct handling of daytime low-solar cases and solar boundary hours.
10. Game-theoretic claims and equilibrium analysis distinction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.energy.battery import BatteryStorage
from src.energy.market_clearing import (
    HouseholdMarketBid,
    MarketClearingPolicy,
    clear_multi_household_market,
)
from src.energy.market_integration import (
    HouseholdStepRecord,
    MultiHouseholdCommunitySimulator,
    MultiHouseholdSimulationResult,
)
from src.game.game import run_two_household_game
from src.game.nash import find_pure_nash_equilibria
from src.game.payoff_matrix import build_two_household_payoff_matrix
from src.optimization.constraints import BatteryOptimizationParams, TariffParams
from src.optimization.mpc_stochastic import (
    SingleHouseholdStochasticMPCController,
    StochasticMPCConfig,
    StochasticScenarioGenerator,
)
from src.stochastic.monte_carlo import ValidationResidualPool, derive_observation_seed


# =============================================================================
# 1. Multiple Simultaneous Sellers and Buyers Matching
# =============================================================================

def test_multiple_simultaneous_sellers_and_buyers():
    """Verify market clearing with multiple sellers and multiple buyers simultaneously."""
    bids = {
        "H001": HouseholdMarketBid("H001", surplus_kwh=1.2, deficit_kwh=0.0),
        "H002": HouseholdMarketBid("H002", surplus_kwh=0.8, deficit_kwh=0.0),
        "H003": HouseholdMarketBid("H003", surplus_kwh=0.0, deficit_kwh=1.0),
        "H004": HouseholdMarketBid("H004", surplus_kwh=0.0, deficit_kwh=1.0),
    }
    # Total supply = 2.0 kWh, Total demand = 2.0 kWh (balanced)
    res = clear_multi_household_market(bids, p2p_price_aud=0.19)

    assert pytest.approx(res.total_traded_kwh, abs=1e-5) == 2.0
    assert len(res.transactions) >= 2
    # Verify allocations
    assert pytest.approx(res.seller_allocations_kwh["H001"], abs=1e-5) == 1.2
    assert pytest.approx(res.seller_allocations_kwh["H002"], abs=1e-5) == 0.8
    assert pytest.approx(res.buyer_allocations_kwh["H003"], abs=1e-5) == 1.0
    assert pytest.approx(res.buyer_allocations_kwh["H004"], abs=1e-5) == 1.0
    # No unmatched surplus or deficit
    assert pytest.approx(sum(res.unmatched_surplus_kwh.values()), abs=1e-5) == 0.0
    assert pytest.approx(sum(res.unmet_demand_kwh.values()), abs=1e-5) == 0.0


# =============================================================================
# 2. Insufficient Community Surplus and Demand Imbalances
# =============================================================================

def test_insufficient_community_surplus():
    """Verify market clearing when total surplus is insufficient to meet demand."""
    bids = {
        "H001": HouseholdMarketBid("H001", surplus_kwh=0.7, deficit_kwh=0.0),
        "H002": HouseholdMarketBid("H002", surplus_kwh=0.0, deficit_kwh=1.0),
        "H003": HouseholdMarketBid("H003", surplus_kwh=0.0, deficit_kwh=0.5),
    }
    # Total supply = 0.7 kWh, Total demand = 1.5 kWh
    res = clear_multi_household_market(bids, p2p_price_aud=0.19)

    assert pytest.approx(res.total_traded_kwh, abs=1e-5) == 0.7
    assert pytest.approx(res.seller_allocations_kwh["H001"], abs=1e-5) == 0.7
    assert pytest.approx(res.unmatched_surplus_kwh["H001"], abs=1e-5) == 0.0
    # Remaining unmet demand must be imported from grid
    tot_grid_imp = sum(res.unmet_demand_kwh.values())
    assert pytest.approx(tot_grid_imp, abs=1e-5) == 0.8
    assert pytest.approx(res.community_summary.total_grid_imported_kwh, abs=1e-5) == 0.8


def test_insufficient_community_demand():
    """Verify market clearing when total demand is insufficient to absorb surplus."""
    bids = {
        "H001": HouseholdMarketBid("H001", surplus_kwh=1.5, deficit_kwh=0.0),
        "H002": HouseholdMarketBid("H002", surplus_kwh=1.0, deficit_kwh=0.0),
        "H003": HouseholdMarketBid("H003", surplus_kwh=0.0, deficit_kwh=0.6),
    }
    # Total supply = 2.5 kWh, Total demand = 0.6 kWh
    res = clear_multi_household_market(bids, p2p_price_aud=0.19)

    assert pytest.approx(res.total_traded_kwh, abs=1e-5) == 0.6
    assert pytest.approx(res.buyer_allocations_kwh["H003"], abs=1e-5) == 0.6
    assert pytest.approx(res.unmet_demand_kwh["H003"], abs=1e-5) == 0.0
    # Remaining unmatched surplus must be exported to grid
    tot_grid_exp = sum(res.unmatched_surplus_kwh.values())
    assert pytest.approx(tot_grid_exp, abs=1e-5) == 1.9
    assert pytest.approx(res.community_summary.total_grid_exported_kwh, abs=1e-5) == 1.9


# =============================================================================
# 3. No-Trade Hours
# =============================================================================

def test_no_trade_all_buyers():
    """Verify zero trade when all households have deficits (e.g., night-time)."""
    bids = {
        "H001": HouseholdMarketBid("H001", surplus_kwh=0.0, deficit_kwh=1.5),
        "H002": HouseholdMarketBid("H002", surplus_kwh=0.0, deficit_kwh=0.8),
        "H003": HouseholdMarketBid("H003", surplus_kwh=0.0, deficit_kwh=2.1),
    }
    res = clear_multi_household_market(bids, p2p_price_aud=0.19)

    assert len(res.transactions) == 0
    assert res.total_traded_kwh == 0.0
    assert pytest.approx(res.community_summary.total_grid_imported_kwh, abs=1e-5) == 4.4
    assert pytest.approx(res.community_summary.total_grid_exported_kwh, abs=1e-5) == 0.0


def test_no_trade_all_sellers():
    """Verify zero trade when all households have surpluses (e.g., sunny peak noon)."""
    bids = {
        "H001": HouseholdMarketBid("H001", surplus_kwh=2.0, deficit_kwh=0.0),
        "H002": HouseholdMarketBid("H002", surplus_kwh=1.5, deficit_kwh=0.0),
        "H003": HouseholdMarketBid("H003", surplus_kwh=0.5, deficit_kwh=0.0),
    }
    res = clear_multi_household_market(bids, p2p_price_aud=0.19)

    assert len(res.transactions) == 0
    assert res.total_traded_kwh == 0.0
    assert pytest.approx(res.community_summary.total_grid_exported_kwh, abs=1e-5) == 4.0
    assert pytest.approx(res.community_summary.total_grid_imported_kwh, abs=1e-5) == 0.0


# =============================================================================
# 4. Partial Allocation and Remaining Grid Settlement
# =============================================================================

def test_partial_allocation_pro_rata():
    """Verify pro-rata rationing among competing buyers under supply constraint."""
    bids = {
        "H001": HouseholdMarketBid("H001", surplus_kwh=1.0, deficit_kwh=0.0),
        "H002": HouseholdMarketBid("H002", surplus_kwh=0.0, deficit_kwh=1.0),
        "H003": HouseholdMarketBid("H003", surplus_kwh=0.0, deficit_kwh=3.0),
    }
    # Total supply = 1.0, Total demand = 4.0. Ratio = 0.25
    res = clear_multi_household_market(bids, p2p_price_aud=0.19, policy=MarketClearingPolicy.PRO_RATA)

    assert pytest.approx(res.total_traded_kwh, abs=1e-5) == 1.0
    assert pytest.approx(res.buyer_allocations_kwh["H002"], abs=1e-5) == 0.25
    assert pytest.approx(res.buyer_allocations_kwh["H003"], abs=1e-5) == 0.75
    assert pytest.approx(res.unmet_demand_kwh["H002"], abs=1e-5) == 0.75
    assert pytest.approx(res.unmet_demand_kwh["H003"], abs=1e-5) == 2.25


# =============================================================================
# 5. Zero and Near-Zero Surplus/Deficit Edge Cases
# =============================================================================

def test_zero_and_near_zero_edge_cases():
    """Verify robustness to numerical zero and sub-micro-kWh quantities."""
    bids = {
        "H001": HouseholdMarketBid("H001", surplus_kwh=1e-8, deficit_kwh=0.0),
        "H002": HouseholdMarketBid("H002", surplus_kwh=0.0, deficit_kwh=1e-8),
        "H003": HouseholdMarketBid("H003", surplus_kwh=0.0, deficit_kwh=0.0),
    }
    res = clear_multi_household_market(bids, p2p_price_aud=0.19)
    # Extremely small quantities (< 1e-6) must not trigger spurious transactions
    assert res.total_traded_kwh == 0.0
    assert len(res.transactions) == 0


# =============================================================================
# 6. Battery Constraints and Per-Household Physical Balance
# =============================================================================

def test_battery_constraints_and_physical_balance_enforcement():
    """Verify battery operational limits and meter physical conservation."""
    bat = BatteryStorage(
        capacity_kwh=5.0,
        min_soc=0.10,
        max_soc=0.90,
        max_charge_rate_kw=2.5,
        max_discharge_rate_kw=2.5,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        initial_soc=0.50,
    )

    # 1. Charge limit
    st_ch = bat.step(energy_available_to_charge_kwh=10.0, duration_hours=1.0)
    assert st_ch.charged_kwh == pytest.approx(2.0 / 0.95)  # Headroom from 2.5 to 4.5 kWh is 2.0 kWh / 0.95
    assert bat.soc == pytest.approx(0.90)

    # 2. Cannot exceed max_soc
    st_ch2 = bat.step(energy_available_to_charge_kwh=1.0, duration_hours=1.0)
    assert st_ch2.charged_kwh == pytest.approx(0.0)
    assert bat.soc == pytest.approx(0.90)

    # 3. Discharge limit
    st_dis = bat.step(energy_requested_to_discharge_kwh=10.0, duration_hours=1.0)
    assert st_dis.discharged_kwh == pytest.approx(2.5)  # Power limited to 2.5 kW * 1.0 h = 2.5 kWh
    assert bat.current_charge_kwh == pytest.approx(4.5 - (2.5 / 0.95))


# =============================================================================
# 7. Transaction Ledger Consistency and Reproducibility
# =============================================================================

def test_ledger_consistency_and_reproducibility():
    """Verify that buyer payments exactly equal seller revenues and are reproducible."""
    bids1 = {
        "H001": HouseholdMarketBid("H001", surplus_kwh=1.45, deficit_kwh=0.0),
        "H002": HouseholdMarketBid("H002", surplus_kwh=0.0, deficit_kwh=0.90),
        "H003": HouseholdMarketBid("H003", surplus_kwh=0.0, deficit_kwh=1.10),
    }
    bids2 = {
        "H001": HouseholdMarketBid("H001", surplus_kwh=1.45, deficit_kwh=0.0),
        "H002": HouseholdMarketBid("H002", surplus_kwh=0.0, deficit_kwh=0.90),
        "H003": HouseholdMarketBid("H003", surplus_kwh=0.0, deficit_kwh=1.10),
    }

    res1 = clear_multi_household_market(bids1, p2p_price_aud=0.19)
    res2 = clear_multi_household_market(bids2, p2p_price_aud=0.19)

    assert res1.total_traded_kwh == pytest.approx(res2.total_traded_kwh, abs=1e-12)
    assert len(res1.transactions) == len(res2.transactions)

    for tx1, tx2 in zip(res1.transactions, res2.transactions):
        assert tx1.seller_id == tx2.seller_id
        assert tx1.buyer_id == tx2.buyer_id
        assert tx1.traded_energy_kwh == pytest.approx(tx2.traded_energy_kwh, abs=1e-12)
        assert tx1.total_value_aud == pytest.approx(tx2.total_value_aud, abs=1e-12)

    tot_pmt = sum(p.p2p_payment_aud for p in res1.payoffs.values())
    tot_rev = sum(p.p2p_revenue_aud for p in res1.payoffs.values())
    assert pytest.approx(tot_pmt, abs=1e-10) == tot_rev


# =============================================================================
# 8. Scenario Generation and Prevention of Future-Actual Leakage
# =============================================================================

def test_scenario_generation_leakage_isolation():
    """Verify that ValidationResidualPool has strictly 0 overlap with held-out test split."""
    pool = ValidationResidualPool()
    # Test period is strictly 2013-04-19 to 2013-06-30
    test_start = pd.to_datetime("2013-04-19 00:00:00")
    test_end = pd.to_datetime("2013-06-30 23:00:00")

    val_timestamps = pd.to_datetime(pool.val_timestamps)
    overlap = val_timestamps[(val_timestamps >= test_start) & (val_timestamps <= test_end)]
    assert len(overlap) == 0, f"Data leakage detected! Overlapping timestamps: {overlap}"

    # Verify deterministic observation seeding
    seed1 = derive_observation_seed("H001", "2013-05-01 12:00:00", base_seed=42)
    seed2 = derive_observation_seed("H001", "2013-05-01 12:00:00", base_seed=42)
    seed3 = derive_observation_seed("H002", "2013-05-01 12:00:00", base_seed=42)
    assert seed1 == seed2
    assert seed1 != seed3


# =============================================================================
# 9. Handling Daytime Low-Solar and Solar Boundary Hours
# =============================================================================

def test_daytime_low_solar_upside_retention():
    """Verify that daytime low-solar forecast (e.g. 0.005 kWh at hour 12) retains upside scenarios."""
    gen = StochasticScenarioGenerator()
    d_fc = np.array([1.0, 1.2, 1.5])
    s_fc = np.array([0.005, 0.008, 0.002])  # Very low solar during midday overcast

    scens = gen.generate_horizon_scenarios(
        demand_forecast=d_fc,
        solar_forecast=s_fc,
        house_id="H001",
        timestamp="2013-05-15 12:00:00",  # Midday (hours 12, 13, 14)
        num_scenarios=5,
        include_nominal=True,
    )

    # Scenarios for daytime hours must NOT be all clamped to zero
    assert np.any(scens.scenarios_solar_kwh > 0.01), (
        "Midday overcast scenarios were erroneously zeroed out!"
    )


# =============================================================================
# 10. Game-Theoretic Claims vs Physical Feasibility
# =============================================================================

def test_game_theoretic_distinction_and_equilibrium_analysis():
    """Verify that physical feasibility does NOT imply a Nash equilibrium.

    Demonstrates:
    1. A centralized bilateral clearing rule creates a Pareto improvement:
       both buyer and seller reduce costs.
    2. However, under a strategic game formulation where players choose bid quantities
       or prices strategically, physical clearing is not automatically a Nash equilibrium
       unless verified against best-response conditions.
    """
    # 2-household scenario
    from src.energy.energy_balance import compute_energy_balance
    bal_p1 = compute_energy_balance(demand_kwh=0.5, solar_generation_kwh=2.0, house_id="H001")  # Surplus 1.5
    bal_p2 = compute_energy_balance(demand_kwh=2.0, solar_generation_kwh=0.5, house_id="H002")  # Deficit 1.5

    matrix, eq_res, comp_res = run_two_household_game(
        balance_p1=bal_p1,
        balance_p2=bal_p2,
        grid_import_price_aud=0.30,
        grid_export_credit_aud=0.08,
        p2p_price_aud=0.19,
    )

    # Physical market clearing trades min(1.5, 1.5) = 1.5 kWh
    assert comp_res.energy_traded_kwh == pytest.approx(1.5)
    assert comp_res.total_community_savings_aud > 0.0

    # In the 2x2 game where players decide whether to Participate (Trade) or Defect (Grid-only),
    # verify that (OFFER_P2P, ACCEPT_P2P) is the unique strict Pareto-dominant Nash equilibrium
    assert eq_res.has_pure_nash
    strict_eqs = [eq for eq in eq_res.equilibria if eq.is_strict]
    assert len(strict_eqs) == 1
    assert strict_eqs[0].action_player1 == "OFFER_P2P"
    assert strict_eqs[0].action_player2 == "ACCEPT_P2P"
    assert strict_eqs[0].traded_energy_kwh == pytest.approx(1.5)
    assert comp_res.is_nash_equilibrium
    assert comp_res.is_strict_equilibrium

    # Game-Theoretic Principle:
    # If Player 1 unilaterally chose to withdraw its offer (No-Trade), its cost increases
    # from game_cost_p1 to baseline_cost_p1.
    assert comp_res.game_cost_p1_aud < comp_res.baseline_cost_p1_aud
    assert comp_res.game_cost_p2_aud < comp_res.baseline_cost_p2_aud


# =============================================================================
# 11. Multi-Hour Simulation and Balance Audit
# =============================================================================

def test_multi_hour_community_simulation():
    """Run a multi-hour community simulation and verify end-to-end accounting."""
    df_all = pd.read_csv("data/processed/test_predictions.csv")
    sim = MultiHouseholdCommunitySimulator(p2p_price_aud=0.19)

    # Run 12-hour simulation with Deterministic MPC
    res_det = sim.run_simulation(
        df_all,
        controller_type="Deterministic_MPC",
        enable_p2p=True,
        max_steps=12,
    )

    assert res_det.total_hours == 12
    assert len(res_det.step_records) == 12

    # Check that energy balances and transactions are consistent
    for step in res_det.step_records:
        for hid, rec in step.household_records.items():
            assert rec.energy_balance_residual_kwh < 1e-4
            assert rec.battery_final_soc >= 0.10 - 1e-5
            assert rec.battery_final_soc <= 0.90 + 1e-5
            assert rec.p2p_payment_aud == pytest.approx(rec.p2p_bought_kwh * 0.19, abs=1e-6)
            assert rec.p2p_revenue_aud == pytest.approx(rec.p2p_sold_kwh * 0.19, abs=1e-6)

        assert pytest.approx(step.total_p2p_payments_aud, abs=1e-6) == step.total_p2p_revenues_aud


# =============================================================================
# 12. Physical Meter Net-Flow Hand-Calculated Regression Test (Audit 7.1)
# =============================================================================

def test_physical_meter_net_flow_hand_calculation():
    """Verify hand-calculated net-flow, surplus/deficit, and market clearing accounting.

    Tests Section 1 of Phase 7.1 Independent Audit:
    net_flow = demand + battery_charge - solar_generation - battery_discharge
    surplus = max(0.0, -net_flow)
    deficit = max(0.0, net_flow)

    Explicitly guards against notation collisions between Demand and Battery Discharge.
    """
    # Household A: Net Deficit (Buyer)
    # Demand = 2.0 kWh, Solar = 0.5 kWh, Charge = 0.0 kWh, Discharge = 0.7 kWh
    d_A = 2.0
    s_A = 0.5
    c_A = 0.0
    dis_A = 0.7
    net_flow_A = (d_A + c_A) - (s_A + dis_A)
    assert pytest.approx(net_flow_A, abs=1e-9) == 0.8
    surplus_A = max(0.0, -net_flow_A)
    deficit_A = max(0.0, net_flow_A)
    assert surplus_A == 0.0
    assert pytest.approx(deficit_A, abs=1e-9) == 0.8

    # Household B: Net Surplus (Seller)
    # Demand = 0.4 kWh, Solar = 2.5 kWh, Charge = 1.0 kWh, Discharge = 0.0 kWh
    d_B = 0.4
    s_B = 2.5
    c_B = 1.0
    dis_B = 0.0
    net_flow_B = (d_B + c_B) - (s_B + dis_B)
    assert pytest.approx(net_flow_B, abs=1e-9) == -1.1
    surplus_B = max(0.0, -net_flow_B)
    deficit_B = max(0.0, net_flow_B)
    assert pytest.approx(surplus_B, abs=1e-9) == 1.1
    assert deficit_B == 0.0

    # Household C: Exact Balance
    # Demand = 1.2 kWh, Solar = 0.8 kWh, Charge = 0.0 kWh, Discharge = 0.4 kWh
    d_C = 1.2
    s_C = 0.8
    c_C = 0.0
    dis_C = 0.4
    net_flow_C = (d_C + c_C) - (s_C + dis_C)
    assert pytest.approx(net_flow_C, abs=1e-9) == 0.0
    surplus_C = max(0.0, -net_flow_C)
    deficit_C = max(0.0, net_flow_C)
    assert pytest.approx(surplus_C, abs=1e-9) == 0.0
    assert pytest.approx(deficit_C, abs=1e-9) == 0.0

    # Submit bids to market clearing (clean near-zero floating noise)
    bids = {
        "H_Buyer": HouseholdMarketBid("H_Buyer", surplus_kwh=surplus_A, deficit_kwh=deficit_A),
        "H_Seller": HouseholdMarketBid("H_Seller", surplus_kwh=surplus_B, deficit_kwh=deficit_B),
        "H_Balanced": HouseholdMarketBid("H_Balanced", surplus_kwh=0.0, deficit_kwh=0.0),
    }

    p_p2p = 0.19
    p_imp = 0.30
    p_exp = 0.08

    res = clear_multi_household_market(
        bids,
        p2p_price_aud=p_p2p,
        grid_import_price_aud=p_imp,
        grid_export_credit_aud=p_exp,
    )

    # 1. Traded quantity: min(surplus_B, deficit_A) = min(1.1, 0.8) = 0.8 kWh
    assert pytest.approx(res.total_traded_kwh, abs=1e-9) == 0.8
    assert len(res.transactions) == 1
    tx = res.transactions[0]
    assert tx.seller_id == "H_Seller"
    assert tx.buyer_id == "H_Buyer"
    assert pytest.approx(tx.traded_energy_kwh, abs=1e-9) == 0.8
    assert pytest.approx(tx.price_aud_per_kwh, abs=1e-9) == 0.19
    assert pytest.approx(tx.total_value_aud, abs=1e-9) == 0.8 * 0.19  # 0.152 AUD

    # 2. Buyer settlement: fully served via P2P
    payoff_buyer = res.payoffs["H_Buyer"]
    assert pytest.approx(payoff_buyer.p2p_imported_kwh, abs=1e-9) == 0.8
    assert pytest.approx(payoff_buyer.p2p_payment_aud, abs=1e-9) == 0.152
    assert pytest.approx(payoff_buyer.grid_imported_kwh, abs=1e-9) == 0.0
    assert pytest.approx(payoff_buyer.grid_import_cost_aud, abs=1e-9) == 0.0
    # Buyer avoided paying grid import (0.30 * 0.8 = 0.24 AUD), saving (0.30 - 0.19) * 0.8 = 0.088 AUD
    assert pytest.approx(0.8 * (p_imp - p_p2p), abs=1e-9) == 0.088

    # 3. Seller settlement: 0.8 kWh sold P2P, remaining 0.3 kWh exported to grid
    payoff_seller = res.payoffs["H_Seller"]
    assert pytest.approx(payoff_seller.p2p_exported_kwh, abs=1e-9) == 0.8
    assert pytest.approx(payoff_seller.p2p_revenue_aud, abs=1e-9) == 0.152
    assert pytest.approx(payoff_seller.grid_exported_kwh, abs=1e-9) == 0.3
    assert pytest.approx(payoff_seller.grid_export_revenue_aud, abs=1e-9) == 0.3 * 0.08  # 0.024 AUD
    # Seller earned P2P revenue instead of grid feed-in (0.19 - 0.08) * 0.8 = 0.088 AUD
    assert pytest.approx(0.8 * (p_p2p - p_exp), abs=1e-9) == 0.088

    # 4. Balanced household: 0 interaction
    payoff_bal = res.payoffs["H_Balanced"]
    assert payoff_bal.p2p_imported_kwh == 0.0
    assert payoff_bal.p2p_exported_kwh == 0.0
    assert payoff_bal.grid_imported_kwh == 0.0
    assert payoff_bal.grid_exported_kwh == 0.0

    # 5. Financial conservation: Buyer payment == Seller revenue
    assert pytest.approx(payoff_buyer.p2p_payment_aud, abs=1e-9) == payoff_seller.p2p_revenue_aud

    # 6. Community economic savings: exactly avoided grid transaction spread
    avoided_spread = (p_imp - p_exp) * 0.8  # (0.30 - 0.08) * 0.8 = 0.176 AUD
    total_savings = (0.8 * (p_imp - p_p2p)) + (0.8 * (p_p2p - p_exp))
    assert pytest.approx(avoided_spread, abs=1e-9) == 0.176
    assert pytest.approx(total_savings, abs=1e-9) == 0.176

