"""Comprehensive tests for multi-household P2P market clearing (Phase 5B).

Verifies:
1. Physical energy balance conservation across all participants and grid.
2. Financial transaction conservation (total buyer payments == total seller revenues).
3. Deterministic repeatability and matching policies.
4. Comprehensive edge cases: single/multiple sellers/buyers, supply/demand imbalances,
   zero-quantity offers, battery integration, floating-point boundaries, and H003 handling.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.energy.battery import BatteryStorage
from src.energy.energy_balance import (
    BatteryAwareEnergyBalance,
    EnergyBalance,
    compute_battery_aware_balance,
    compute_energy_balance,
)
from src.energy.market_clearing import (
    HouseholdMarketBid,
    MarketClearingPolicy,
    MarketClearingResult,
    clear_multi_household_market,
)
from src.stochastic.monte_carlo import ScenarioDistribution, run_stochastic_multi_household_clearing


# =============================================================================
# 1. BASELINE AND PROPORTIONAL MATCHING TESTS
# =============================================================================

def test_no_surplus_and_no_deficit():
    """Verify market clearing with zero surplus and zero deficit across all houses."""
    b1 = HouseholdMarketBid("H001", surplus_kwh=0.0, deficit_kwh=0.0)
    b2 = HouseholdMarketBid("H002", surplus_kwh=0.0, deficit_kwh=0.0)
    b3 = HouseholdMarketBid("H003", surplus_kwh=0.0, deficit_kwh=0.0)

    res = clear_multi_household_market([b1, b2, b3], p2p_price_aud=0.19)
    assert len(res.transactions) == 0
    assert res.total_traded_kwh == 0.0
    assert res.community_summary.total_p2p_traded_kwh == 0.0
    assert res.community_summary.total_grid_imported_kwh == 0.0
    assert res.community_summary.total_grid_exported_kwh == 0.0
    assert res.community_summary.combined_household_utility_aud == 0.0


def test_one_seller_one_buyer_matches_baseline():
    """Verify 2-household matching reproduces exact bilateral Phase 5A quantities."""
    b1 = compute_energy_balance(0.137, 1.382, "H001")  # Surplus = 1.245 kWh
    b2 = compute_energy_balance(1.838, 0.375, "H002")  # Deficit = 1.463 kWh

    res = clear_multi_household_market([b1, b2], p2p_price_aud=0.19)
    assert len(res.transactions) == 1
    tx = res.transactions[0]
    assert tx.seller_id == "H001"
    assert tx.buyer_id == "H002"
    assert pytest.approx(tx.traded_energy_kwh, abs=1e-5) == 1.245
    assert pytest.approx(tx.total_value_aud, abs=1e-5) == 1.245 * 0.19
    assert pytest.approx(res.unmatched_surplus_kwh["H001"], abs=1e-5) == 0.0
    assert pytest.approx(res.unmet_demand_kwh["H002"], abs=1e-5) == 0.218


def test_multiple_sellers_one_buyer():
    """Verify multiple sellers clearing against a single buyer with demand cap."""
    b1 = HouseholdMarketBid("H001", surplus_kwh=1.0, deficit_kwh=0.0)
    b2 = HouseholdMarketBid("H002", surplus_kwh=0.6, deficit_kwh=0.0)
    b3 = HouseholdMarketBid("H003", surplus_kwh=0.0, deficit_kwh=1.2)

    res = clear_multi_household_market([b1, b2, b3], p2p_price_aud=0.19)
    assert pytest.approx(res.total_traded_kwh, abs=1e-5) == 1.2
    assert len(res.transactions) == 2
    # H001 sells 1.0 to H003
    assert res.transactions[0].seller_id == "H001"
    assert pytest.approx(res.transactions[0].traded_energy_kwh, abs=1e-5) == 1.0
    # H002 sells remaining 0.2 to H003
    assert res.transactions[1].seller_id == "H002"
    assert pytest.approx(res.transactions[1].traded_energy_kwh, abs=1e-5) == 0.2

    assert pytest.approx(res.unmatched_surplus_kwh["H002"], abs=1e-5) == 0.4
    assert pytest.approx(res.unmet_demand_kwh["H003"], abs=1e-5) == 0.0


def test_one_seller_multiple_buyers():
    """Verify single seller clearing across multiple buyers until surplus exhausted."""
    b1 = HouseholdMarketBid("H001", surplus_kwh=1.5, deficit_kwh=0.0)
    b2 = HouseholdMarketBid("H002", surplus_kwh=0.0, deficit_kwh=0.8)
    b3 = HouseholdMarketBid("H003", surplus_kwh=0.0, deficit_kwh=1.0)

    res = clear_multi_household_market([b1, b2, b3], p2p_price_aud=0.19)
    assert pytest.approx(res.total_traded_kwh, abs=1e-5) == 1.5
    assert len(res.transactions) == 2
    # H001 sells 0.8 to H002
    assert res.transactions[0].buyer_id == "H002"
    assert pytest.approx(res.transactions[0].traded_energy_kwh, abs=1e-5) == 0.8
    # H001 sells remaining 0.7 to H003
    assert res.transactions[1].buyer_id == "H003"
    assert pytest.approx(res.transactions[1].traded_energy_kwh, abs=1e-5) == 0.7

    assert pytest.approx(res.unmatched_surplus_kwh["H001"], abs=1e-5) == 0.0
    assert pytest.approx(res.unmet_demand_kwh["H003"], abs=1e-5) == 0.3


def test_multiple_sellers_multiple_buyers():
    """Verify multi-seller multi-buyer simultaneous bilateral clearing."""
    b1 = HouseholdMarketBid("H001", surplus_kwh=1.0, deficit_kwh=0.0)
    b4 = HouseholdMarketBid("H004", surplus_kwh=1.5, deficit_kwh=0.0)
    b2 = HouseholdMarketBid("H002", surplus_kwh=0.0, deficit_kwh=1.2)
    b3 = HouseholdMarketBid("H003", surplus_kwh=0.0, deficit_kwh=0.8)

    res = clear_multi_household_market([b1, b4, b2, b3], p2p_price_aud=0.19)
    assert pytest.approx(res.total_traded_kwh, abs=1e-5) == 2.0
    assert len(res.transactions) == 3

    # H001 sells 1.0 to H002
    assert res.transactions[0].seller_id == "H001" and res.transactions[0].buyer_id == "H002"
    assert pytest.approx(res.transactions[0].traded_energy_kwh, abs=1e-5) == 1.0
    # H004 sells 0.2 to H002
    assert res.transactions[1].seller_id == "H004" and res.transactions[1].buyer_id == "H002"
    assert pytest.approx(res.transactions[1].traded_energy_kwh, abs=1e-5) == 0.2
    # H004 sells 0.8 to H003
    assert res.transactions[2].seller_id == "H004" and res.transactions[2].buyer_id == "H003"
    assert pytest.approx(res.transactions[2].traded_energy_kwh, abs=1e-5) == 0.8

    assert pytest.approx(res.unmatched_surplus_kwh["H004"], abs=1e-5) == 0.5
    assert pytest.approx(res.community_summary.total_grid_exported_kwh, abs=1e-5) == 0.5
    assert pytest.approx(res.community_summary.total_grid_imported_kwh, abs=1e-5) == 0.0


def test_exact_supply_demand_equality():
    """Verify market clearing when total community supply exactly equals total demand."""
    b1 = HouseholdMarketBid("H001", surplus_kwh=1.2, deficit_kwh=0.0)
    b2 = HouseholdMarketBid("H002", surplus_kwh=0.8, deficit_kwh=0.0)
    b3 = HouseholdMarketBid("H003", surplus_kwh=0.0, deficit_kwh=2.0)

    res = clear_multi_household_market([b1, b2, b3], p2p_price_aud=0.19)
    assert pytest.approx(res.total_traded_kwh, abs=1e-5) == 2.0
    assert pytest.approx(res.community_summary.total_grid_imported_kwh, abs=1e-5) == 0.0
    assert pytest.approx(res.community_summary.total_grid_exported_kwh, abs=1e-5) == 0.0
    assert pytest.approx(res.community_summary.combined_household_utility_aud, abs=1e-5) == 0.0


def test_zero_quantity_offers():
    """Verify participants with surplus/deficit who submit max_sell=0 or max_buy=0."""
    b1 = HouseholdMarketBid("H001", surplus_kwh=1.0, deficit_kwh=0.0, max_sell_kwh=0.0)
    b2 = HouseholdMarketBid("H002", surplus_kwh=0.0, deficit_kwh=1.0)

    res = clear_multi_household_market([b1, b2], p2p_price_aud=0.19)
    assert len(res.transactions) == 0
    assert res.total_traded_kwh == 0.0
    assert pytest.approx(res.unmatched_surplus_kwh["H001"], abs=1e-5) == 1.0
    assert pytest.approx(res.unmet_demand_kwh["H002"], abs=1e-5) == 1.0
    # Seller exports to grid, buyer imports from grid
    assert pytest.approx(res.community_summary.total_grid_exported_kwh, abs=1e-5) == 1.0
    assert pytest.approx(res.community_summary.total_grid_imported_kwh, abs=1e-5) == 1.0


# =============================================================================
# 2. MATCHING POLICIES COMPARISON
# =============================================================================

def test_clearing_policies_difference():
    """Verify LARGEST_SURPLUS_FIRST vs PRIORITY_ORDER vs PRO_RATA produce distinct valid allocations."""
    b1 = HouseholdMarketBid("H001", surplus_kwh=0.5, deficit_kwh=0.0)
    b2 = HouseholdMarketBid("H002", surplus_kwh=1.5, deficit_kwh=0.0)
    b3 = HouseholdMarketBid("H003", surplus_kwh=0.0, deficit_kwh=1.0)

    # 1. PRIORITY_ORDER (H001 first, then H002)
    res_priority = clear_multi_household_market([b1, b2, b3], policy=MarketClearingPolicy.PRIORITY_ORDER)
    assert res_priority.transactions[0].seller_id == "H001"
    assert pytest.approx(res_priority.transactions[0].traded_energy_kwh, abs=1e-5) == 0.5
    assert res_priority.transactions[1].seller_id == "H002"
    assert pytest.approx(res_priority.transactions[1].traded_energy_kwh, abs=1e-5) == 0.5

    # 2. LARGEST_SURPLUS_FIRST (H002 first because surplus=1.5 > 0.5)
    res_largest = clear_multi_household_market([b1, b2, b3], policy=MarketClearingPolicy.LARGEST_SURPLUS_FIRST)
    assert len(res_largest.transactions) == 1
    assert res_largest.transactions[0].seller_id == "H002"
    assert pytest.approx(res_largest.transactions[0].traded_energy_kwh, abs=1e-5) == 1.0

    # 3. PRO_RATA (total supply=2.0, demand=1.0 -> each seller sells 50%)
    res_pr = clear_multi_household_market([b1, b2, b3], policy=MarketClearingPolicy.PRO_RATA)
    assert pytest.approx(res_pr.seller_allocations_kwh["H001"], abs=1e-5) == 0.25
    assert pytest.approx(res_pr.seller_allocations_kwh["H002"], abs=1e-5) == 0.75
    assert pytest.approx(res_pr.total_traded_kwh, abs=1e-5) == 1.0


# =============================================================================
# 3. BATTERY STORAGE INTEGRATION & CONSERVATION INVARIANTS
# =============================================================================

def test_battery_dispatch_eliminates_all_market_trades():
    """Verify BTM battery dispatch absorbs surplus and deficit before market clearing."""
    bat1 = BatteryStorage(capacity_kwh=5.0, initial_soc=0.50)  # Headroom = 2.105 kWh
    bat2 = BatteryStorage(capacity_kwh=5.0, initial_soc=0.50)  # Footroom = 1.900 kWh

    b1 = compute_battery_aware_balance(0.137, 1.382, bat1, "H001")
    b2 = compute_battery_aware_balance(1.838, 0.375, bat2, "H002")

    res = clear_multi_household_market([b1, b2], p2p_price_aud=0.19)
    assert len(res.transactions) == 0
    assert res.total_traded_kwh == 0.0
    assert pytest.approx(res.community_summary.total_battery_charged_kwh, abs=1e-5) == 1.245
    assert pytest.approx(res.community_summary.total_battery_discharged_kwh, abs=1e-5) == 1.463
    assert res.community_summary.total_grid_imported_kwh == 0.0
    assert res.community_summary.total_grid_exported_kwh == 0.0


def test_multiple_households_with_batteries_partial_market_clearing():
    """Verify multi-household clearing when batteries are partially saturated/depleted."""
    bat1 = BatteryStorage(capacity_kwh=5.0, initial_soc=0.80)  # Headroom = (4.5 - 4.0)/0.95 = 0.5263 kWh
    bat2 = BatteryStorage(capacity_kwh=5.0, initial_soc=0.30)  # Footroom = (1.5 - 0.5)*0.95 = 0.9500 kWh

    b1 = compute_battery_aware_balance(0.5, 2.5, bat1, "H001")  # Raw surplus = 2.0 -> Post-battery = 1.4737 kWh
    b2 = compute_battery_aware_balance(2.0, 0.5, bat2, "H002")  # Raw deficit = 1.5 -> Post-battery = 0.5500 kWh
    b3 = compute_energy_balance(1.2, 0.2, "H003")               # No battery -> Post-battery = 1.0000 kWh

    res = clear_multi_household_market([b1, b2, b3], p2p_price_aud=0.19)
    assert pytest.approx(res.total_traded_kwh, abs=1e-4) == 1.4737
    assert len(res.transactions) == 2
    # H001 sells 0.55 to H002, and 0.9237 to H003
    assert res.transactions[0].buyer_id == "H002"
    assert pytest.approx(res.transactions[0].traded_energy_kwh, abs=1e-4) == 0.5500
    assert res.transactions[1].buyer_id == "H003"
    assert pytest.approx(res.transactions[1].traded_energy_kwh, abs=1e-4) == 0.9237

    # Residual unmet deficit of H003 imported from grid
    assert pytest.approx(res.unmet_demand_kwh["H003"], abs=1e-4) == 0.0763
    assert pytest.approx(res.community_summary.total_grid_imported_kwh, abs=1e-4) == 0.0763
    assert pytest.approx(res.community_summary.total_grid_exported_kwh, abs=1e-4) == 0.0


def test_h003_ordinary_participant_as_seller():
    """Verify H003 can act as the community seller without any hardcoding of H001."""
    b1 = HouseholdMarketBid("H001", surplus_kwh=0.0, deficit_kwh=0.7)
    b2 = HouseholdMarketBid("H002", surplus_kwh=0.0, deficit_kwh=0.5)
    b3 = HouseholdMarketBid("H003", surplus_kwh=1.5, deficit_kwh=0.0)

    res = clear_multi_household_market([b1, b2, b3], p2p_price_aud=0.19)
    assert pytest.approx(res.total_traded_kwh, abs=1e-5) == 1.2
    assert len(res.transactions) == 2
    assert res.transactions[0].seller_id == "H003" and res.transactions[0].buyer_id == "H001"
    assert res.transactions[1].seller_id == "H003" and res.transactions[1].buyer_id == "H002"
    assert pytest.approx(res.unmatched_surplus_kwh["H003"], abs=1e-5) == 0.3


# =============================================================================
# 4. FINANCIAL CONSERVATION & ERROR HANDLING TESTS
# =============================================================================

def test_financial_payment_conservation():
    """Verify total buyer payments strictly equal total seller revenues."""
    b1 = HouseholdMarketBid("H001", surplus_kwh=1.35, deficit_kwh=0.0)
    b2 = HouseholdMarketBid("H002", surplus_kwh=0.0, deficit_kwh=0.95)
    b3 = HouseholdMarketBid("H003", surplus_kwh=0.0, deficit_kwh=0.85)

    res = clear_multi_household_market([b1, b2, b3], p2p_price_aud=0.19)
    tot_pmt = sum(pay.p2p_payment_aud for pay in res.payoffs.values())
    tot_rev = sum(pay.p2p_revenue_aud for pay in res.payoffs.values())
    assert pytest.approx(tot_pmt, abs=1e-8) == tot_rev
    assert pytest.approx(res.community_summary.payment_conservation_residual_aud, abs=1e-8) == 0.0


def test_invalid_and_non_finite_inputs():
    """Verify rejection of NaN, Inf, and negative quantities."""
    with pytest.raises(ValueError, match="Non-finite input"):
        HouseholdMarketBid("H001", surplus_kwh=np.nan, deficit_kwh=0.0)

    with pytest.raises(ValueError, match="Negative input"):
        HouseholdMarketBid("H001", surplus_kwh=-1.0, deficit_kwh=0.0)

    with pytest.raises(ValueError, match="cannot exceed available surplus"):
        HouseholdMarketBid("H001", surplus_kwh=1.0, deficit_kwh=0.0, max_sell_kwh=1.5)

    with pytest.raises(ValueError, match="cannot simultaneously have surplus"):
        HouseholdMarketBid("H001", surplus_kwh=1.0, deficit_kwh=1.0)


def test_deterministic_reproducibility():
    """Verify that repeated runs with identical inputs produce bit-for-bit identical results."""
    bids = [
        HouseholdMarketBid("H001", surplus_kwh=1.45, deficit_kwh=0.0),
        HouseholdMarketBid("H002", surplus_kwh=0.0, deficit_kwh=0.85),
        HouseholdMarketBid("H003", surplus_kwh=0.0, deficit_kwh=0.75),
    ]

    res1 = clear_multi_household_market(bids, p2p_price_aud=0.19)
    res2 = clear_multi_household_market(bids, p2p_price_aud=0.19)

    assert res1.total_traded_kwh == res2.total_traded_kwh
    assert len(res1.transactions) == len(res2.transactions)
    for tx1, tx2 in zip(res1.transactions, res2.transactions):
        assert tx1.seller_id == tx2.seller_id
        assert tx1.buyer_id == tx2.buyer_id
        assert tx1.traded_energy_kwh == tx2.traded_energy_kwh
        assert tx1.total_value_aud == tx2.total_value_aud


def test_floating_point_precision_boundaries():
    """Verify precision with small quantities at floating point boundaries."""
    b1 = HouseholdMarketBid("H001", surplus_kwh=1e-5, deficit_kwh=0.0)
    b2 = HouseholdMarketBid("H002", surplus_kwh=0.0, deficit_kwh=1e-5)

    res = clear_multi_household_market([b1, b2], p2p_price_aud=0.19)
    assert len(res.transactions) == 1
    assert pytest.approx(res.total_traded_kwh, abs=1e-7) == 1e-5
    assert pytest.approx(res.community_summary.demand_conservation_residual_kwh, abs=1e-8) == 0.0


# =============================================================================
# 5. STOCHASTIC MONTE CARLO INTEGRATION TEST
# =============================================================================

def test_stochastic_multi_household_clearing_integration():
    """Verify scenario-by-scenario multi-household clearing across synthetic distributions."""
    np.random.seed(42)
    n = 100
    d1 = ScenarioDistribution(
        house_id="H001",
        num_scenarios=n,
        forecast_demand_mean_kwh=0.3,
        forecast_solar_mean_kwh=1.5,
        scenarios_demand_kwh=np.maximum(0.0, np.random.normal(0.3, 0.1, n)),
        scenarios_solar_kwh=np.maximum(0.0, np.random.normal(1.5, 0.3, n)),
    )
    d2 = ScenarioDistribution(
        house_id="H002",
        num_scenarios=n,
        forecast_demand_mean_kwh=1.8,
        forecast_solar_mean_kwh=0.4,
        scenarios_demand_kwh=np.maximum(0.0, np.random.normal(1.8, 0.4, n)),
        scenarios_solar_kwh=np.maximum(0.0, np.random.normal(0.4, 0.1, n)),
    )
    d3 = ScenarioDistribution(
        house_id="H003",
        num_scenarios=n,
        forecast_demand_mean_kwh=0.6,
        forecast_solar_mean_kwh=0.2,
        scenarios_demand_kwh=np.maximum(0.0, np.random.normal(0.6, 0.2, n)),
        scenarios_solar_kwh=np.maximum(0.0, np.random.normal(0.2, 0.05, n)),
    )

    summary, df_scenarios = run_stochastic_multi_household_clearing(
        scenario_distributions={"H001": d1, "H002": d2, "H003": d3},
        p2p_price_aud=0.19,
    )

    assert summary.num_scenarios == n
    assert summary.expected_traded_kwh > 0.0
    assert summary.active_trading_frequency_pct > 80.0
    assert len(df_scenarios) == n
    assert "Total_P2P_Traded_kWh" in df_scenarios.columns
    assert "Combined_Utility_AUD" in df_scenarios.columns
    # Check payment equality in summary
    tot_sold = sum(summary.expected_p2p_sold_kwh.values())
    tot_bought = sum(summary.expected_p2p_bought_kwh.values())
    assert pytest.approx(tot_sold, abs=1e-4) == tot_bought


def test_stochastic_multi_household_clearing_with_batteries_and_conservation():
    """Verify stochastic clearing integrates residential battery dispatch and exact conservation."""
    np.random.seed(42)
    n = 100
    d1 = ScenarioDistribution(
        house_id="H001",
        num_scenarios=n,
        forecast_demand_mean_kwh=0.5,
        forecast_solar_mean_kwh=2.5,
        scenarios_demand_kwh=np.maximum(0.0, np.random.normal(0.5, 0.1, n)),
        scenarios_solar_kwh=np.maximum(0.0, np.random.normal(2.5, 0.5, n)),
    )
    d2 = ScenarioDistribution(
        house_id="H002",
        num_scenarios=n,
        forecast_demand_mean_kwh=2.5,
        forecast_solar_mean_kwh=0.5,
        scenarios_demand_kwh=np.maximum(0.0, np.random.normal(2.5, 0.5, n)),
        scenarios_solar_kwh=np.maximum(0.0, np.random.normal(0.5, 0.1, n)),
    )
    d3 = ScenarioDistribution(
        house_id="H003",
        num_scenarios=n,
        forecast_demand_mean_kwh=1.0,
        forecast_solar_mean_kwh=0.2,
        scenarios_demand_kwh=np.maximum(0.0, np.random.normal(1.0, 0.2, n)),
        scenarios_solar_kwh=np.maximum(0.0, np.random.normal(0.2, 0.05, n)),
    )

    batteries = {
        "H001": BatteryStorage(capacity_kwh=5.0, initial_soc=0.50),
        "H002": BatteryStorage(capacity_kwh=5.0, initial_soc=0.50),
        "H003": BatteryStorage(capacity_kwh=5.0, initial_soc=0.50),
    }

    summary, df_scenarios = run_stochastic_multi_household_clearing(
        scenario_distributions={"H001": d1, "H002": d2, "H003": d3},
        batteries=batteries,
        p2p_price_aud=0.19,
        grid_import_price_aud=0.30,
        grid_export_credit_aud=0.08,
    )

    assert summary.num_scenarios == n
    assert len(df_scenarios) == n

    # Total expected sold must equal total expected bought across the community
    tot_sold = sum(summary.expected_p2p_sold_kwh.values())
    tot_bought = sum(summary.expected_p2p_bought_kwh.values())
    assert pytest.approx(tot_sold, abs=1e-5) == tot_bought

    # Verify battery SOC stays within physical limits [0.10, 0.90]
    for hid in ["H001", "H002", "H003"]:
        assert 0.10 <= summary.expected_final_soc[hid] <= 0.90
        assert summary.expected_battery_charged_kwh[hid] >= 0.0
        assert summary.expected_battery_discharged_kwh[hid] >= 0.0

    # Ensure H001 charges on average from high solar surplus, H002 discharges on average
    assert summary.expected_battery_charged_kwh["H001"] > 0.5
    assert summary.expected_battery_discharged_kwh["H002"] > 0.5
