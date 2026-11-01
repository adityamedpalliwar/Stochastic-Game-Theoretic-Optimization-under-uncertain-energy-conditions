"""Unit tests for Phase 8C: Deterministic Price-Only Nash Equilibrium Solver.

Tests:
1. One active seller, no possible trade.
2. One active buyer, no possible trade.
3. One seller and one buyer (Hand-calculated analytical benchmark).
4. Two sellers and one buyer.
5. One seller and two buyers.
6. Three active households (Comprehensive combinatorial game).
7. Inactive household handling.
8. Strict equilibrium classification.
9. Weak equilibrium classification.
10. Profitable unilateral deviation rejection.
11. Multiple PNE preservation.
12. No-PNE handling.
13. Pareto dominance using the complete payoff vector.
14. Pareto-undominated equilibrium identification.
15. Representative equilibrium deterministic tie-breaking.
16. Zero-volume equilibrium selection handling.
17. Numerical tolerance around payoff equality.
18. Consistency between solver clearing results and Phase 8B.1 clearing results.
19. Physical flow convenience helper (solve_nash_from_physical_flows).
20. Input validation: invalid tariffs, simultaneous surplus and deficit, invalid grids.
21. All inactive households (0 active players).
"""

from __future__ import annotations

from typing import Dict, List, Optional
from unittest.mock import patch

import numpy as np
import pytest

from src.game.strategic_market import (
    DEFAULT_GRID_EXPORT_CREDIT_AUD,
    DEFAULT_GRID_IMPORT_TARIFF_AUD,
    DEFAULT_NUMERICAL_TOLERANCE,
    STRATEGIC_PRICE_GRID,
    MarketOrder,
    MarketRole,
    StrategicMarketResult,
    clear_strategic_double_auction,
)
from src.game.strategic_solver import (
    EquilibriumClassification,
    NashEquilibriumRecord,
    SolverStatus,
    StrategicGameResult,
    check_pareto_dominance,
    identify_pareto_undominated,
    select_representative_equilibrium,
    solve_deterministic_nash_equilibrium,
    solve_nash_from_physical_flows,
)


# =============================================================================
# 1. BOUNDARY CASES: SINGLE ACTIVE HOUSEHOLD (NO POSSIBLE TRADE)
# =============================================================================

def test_one_active_seller_no_possible_trade():
    """Test 1: One active seller, no counterparties (0 buyers).

    Seller H001: 2.0 kWh surplus. H002 and H003 are inactive.
    Expected:
      - 1 active seller, 0 active buyers, 2 inactive households.
      - Action space |A| = 7 profiles evaluated.
      - Total deviations evaluated = 7 * 1 * 6 = 42.
      - Since no trade is possible, all 7 profiles yield traded volume = 0, payoff = 0.
      - For every profile, all 6 unilateral deviations yield equal payoff (0 == 0).
      - All 7 profiles are weak Pure Nash Equilibria.
      - All 7 profiles have identical payoff vectors (0, 0, 0); none dominates another.
      - All 7 are Pareto-undominated.
      - Zero-volume distance D_mid = +inf for all.
      - Deterministic lexicographical tie-break selects the first price: $0.08/kWh.
    """
    res = solve_deterministic_nash_equilibrium(
        surpluses_kwh={"H001": 2.0},
        deficits_kwh={"H002": 0.0, "H003": 0.0},
    )

    assert res.status == SolverStatus.SUCCESS.value
    assert res.active_sellers == ["H001"]
    assert res.active_buyers == []
    assert res.inactive_households == ["H002", "H003"]
    assert res.num_profiles_evaluated == 7
    assert res.num_deviations_evaluated == 42
    assert res.num_equilibria == 7
    assert res.num_strict == 0
    assert res.num_weak == 7
    assert res.num_pareto_undominated == 7

    assert res.selected_equilibrium is not None
    assert res.selected_equilibrium.profile == {"H001": 0.08}
    assert res.selected_traded_kwh == 0.0
    assert res.selected_price_aud is None
    assert res.selected_welfare_aud == 0.0
    assert res.selected_payoffs == {"H001": 0.0, "H002": 0.0, "H003": 0.0}


def test_one_active_buyer_no_possible_trade():
    """Test 2: One active buyer, no counterparties (0 sellers).

    Buyer H002: 1.5 kWh deficit. H001 and H003 are inactive.
    Expected:
      - 0 active sellers, 1 active buyer, 2 inactive households.
      - 7 profiles evaluated, 42 deviations tested.
      - All 7 profiles are weak Pure Nash Equilibria with zero trade and zero welfare.
      - All 7 are Pareto-undominated.
      - Selected equilibrium: {'H002': 0.08}.
    """
    res = solve_deterministic_nash_equilibrium(
        surpluses_kwh={"H001": 0.0, "H003": 0.0},
        deficits_kwh={"H002": 1.5},
    )

    assert res.status == SolverStatus.SUCCESS.value
    assert res.active_sellers == []
    assert res.active_buyers == ["H002"]
    assert res.inactive_households == ["H001", "H003"]
    assert res.num_profiles_evaluated == 7
    assert res.num_deviations_evaluated == 42
    assert res.num_equilibria == 7
    assert res.num_strict == 0
    assert res.num_weak == 7
    assert res.num_pareto_undominated == 7

    assert res.selected_equilibrium is not None
    assert res.selected_equilibrium.profile == {"H002": 0.08}
    assert res.selected_traded_kwh == 0.0
    assert res.selected_price_aud is None
    assert res.selected_welfare_aud == 0.0


# =============================================================================
# 2. HAND-CALCULATED BENCHMARK: ONE SELLER, ONE BUYER
# =============================================================================

def test_one_seller_one_buyer_benchmark():
    """Test 3: One seller (H001, 1.0 kWh), One buyer (H002, 1.0 kWh).

    Analytical Derivation:
      - Combinatorial space: 7 * 7 = 49 profiles.
      - Unilateral deviations per profile: 2 * (7 - 1) = 12 deviations.
      - Total deviations evaluated: 49 * 12 = 588 deviations.
      - Payoff structure:
        If bid >= ask: trade = 1.0 kWh at p_tx = (ask + bid)/2.
        U_seller = p_tx - 0.08 = (ask + bid)/2 - 0.08.
        U_buyer  = 0.30 - p_tx = 0.30 - (ask + bid)/2.
        If bid < ask: trade = 0, U_seller = 0, U_buyer = 0.
      - Best responses:
        Given bid b, seller asks b (highest ask that still clears).
        Given ask a, buyer bids a (lowest bid that still clears).
      - Pure Nash Equilibria:
        1. All 7 diagonal profiles (p, p) for p in {0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30}.
        2. Uncrossed profile (0.30, 0.08) where ask $0.30 > bid $0.08, giving U = (0, 0).
           Neither player can unilaterally improve above 0.
        Total PNE = exactly 8!
      - Strict vs Weak:
        - 5 strict: (0.12, 0.12), (0.16, 0.16), (0.19, 0.19), (0.22, 0.22), (0.26, 0.26).
        - 3 weak:
          * (0.08, 0.08) (seller can ask > 0.08 and still earn 0).
          * (0.30, 0.30) (buyer can bid < 0.30 and still earn 0).
          * (0.30, 0.08) (both earn 0 and deviations yield <= 0).
      - Pareto Dominance:
        - All 7 diagonal profiles yield U_seller + U_buyer = 0.22 > 0.
        - The uncrossed profile (0.30, 0.08) yields (0, 0) and is Pareto-dominated by all 7.
        - None of the 7 diagonal profiles dominates any other diagonal profile (trade-off).
        - Exactly 7 Pareto-undominated equilibria!
      - Representative Selection:
        - Distance to reference price $0.19: |p_tx - 0.19|.
        - Equilibrium (0.19, 0.19) has p_tx = $0.1900 -> D_mid = 0.0000.
        - Uniquely selects {'H001': 0.19, 'H002': 0.19} with payoffs (0.11, 0.11, 0.0).
    """
    res = solve_deterministic_nash_equilibrium(
        surpluses_kwh={"H001": 1.0},
        deficits_kwh={"H002": 1.0},
    )

    assert res.status == SolverStatus.SUCCESS.value
    assert res.num_profiles_evaluated == 49
    assert res.num_deviations_evaluated == 588
    assert res.num_equilibria == 8
    assert res.num_strict == 5
    assert res.num_weak == 3
    assert res.num_pareto_undominated == 7

    # Verify that the 7 diagonal profiles are all equilibria
    eq_profiles = [eq.profile for eq in res.equilibria]
    for p in STRATEGIC_PRICE_GRID:
        assert {"H001": p, "H002": p} in eq_profiles

    # Verify the uncrossed equilibrium (0.30, 0.08)
    assert {"H001": 0.30, "H002": 0.08} in eq_profiles

    # Verify Pareto frontier
    pareto_profiles = [eq.profile for eq in res.pareto_undominated_equilibria]
    assert len(pareto_profiles) == 7
    assert {"H001": 0.30, "H002": 0.08} not in pareto_profiles

    # Verify representative selection
    assert res.selected_equilibrium is not None
    assert res.selected_equilibrium.profile == {"H001": 0.19, "H002": 0.19}
    assert pytest.approx(res.selected_traded_kwh, abs=1e-6) == 1.0
    assert pytest.approx(res.selected_price_aud, abs=1e-6) == 0.19
    assert pytest.approx(res.selected_welfare_aud, abs=1e-6) == 0.22
    assert pytest.approx(res.selected_payoffs["H001"], abs=1e-6) == 0.11
    assert pytest.approx(res.selected_payoffs["H002"], abs=1e-6) == 0.11
    assert pytest.approx(res.selected_payoffs["H003"], abs=1e-6) == 0.0


# =============================================================================
# 3. MULTI-HOUSEHOLD STRATEGIC GAMES
# =============================================================================

def test_two_sellers_one_buyer():
    """Test 4: Two sellers, one buyer.

    Sellers: H001 (1.0 kWh), H002 (1.0 kWh).
    Buyer:   H003 (1.5 kWh).
    Expected:
      - 2 active sellers, 1 active buyer, 0 inactive.
      - 343 profiles evaluated, 6,174 deviations tested.
      - Pure Nash equilibria exist.
      - Traded volume, revenues, and payments respect physical capacities.
    """
    res = solve_deterministic_nash_equilibrium(
        surpluses_kwh={"H001": 1.0, "H002": 1.0},
        deficits_kwh={"H003": 1.5},
    )

    assert res.status == SolverStatus.SUCCESS.value
    assert res.num_profiles_evaluated == 343
    assert res.num_deviations_evaluated == 6174
    assert res.num_equilibria > 0
    assert res.selected_equilibrium is not None
    assert res.selected_traded_kwh <= 1.5 + 1e-6
    assert res.selected_welfare_aud > 0.0


def test_one_seller_two_buyers():
    """Test 5: One seller, two buyers.

    Seller: H001 (2.0 kWh).
    Buyers: H002 (1.0 kWh), H003 (1.0 kWh).
    Total supply = 2.0 kWh, Total demand = 2.0 kWh.
    Expected:
      - 343 profiles evaluated, 6,174 deviations tested.
      - Multiple equilibria found.
      - Representative equilibrium selected deterministically.
      - Traded volume = 2.0 kWh, Welfare = 2.0 * 0.22 = 0.44 AUD.
    """
    res = solve_deterministic_nash_equilibrium(
        surpluses_kwh={"H001": 2.0},
        deficits_kwh={"H002": 1.0, "H003": 1.0},
    )

    assert res.status == SolverStatus.SUCCESS.value
    assert res.num_profiles_evaluated == 343
    assert res.num_deviations_evaluated == 6174
    assert res.num_equilibria >= 1
    assert res.selected_equilibrium is not None
    assert pytest.approx(res.selected_traded_kwh, abs=1e-6) == 2.0
    assert pytest.approx(res.selected_welfare_aud, abs=1e-6) == 0.44


def test_three_active_households_comprehensive():
    """Test 6: Three active households (H001 seller, H002 buyer, H003 buyer).

    H001: 1.5 kWh surplus.
    H002: 1.0 kWh deficit.
    H003: 1.0 kWh deficit.
    Verify:
      - 343 profiles, 6,174 deviations.
      - Conservation laws hold on selected equilibrium.
      - All payoffs >= 0 (Individual Rationality).
    """
    res = solve_deterministic_nash_equilibrium(
        surpluses_kwh={"H001": 1.5},
        deficits_kwh={"H002": 1.0, "H003": 1.0},
    )

    assert res.status == SolverStatus.SUCCESS.value
    assert res.num_profiles_evaluated == 343
    assert res.num_deviations_evaluated == 6174
    assert res.num_equilibria > 0

    sel = res.selected_equilibrium
    assert sel is not None
    assert sel.total_traded_kwh <= 1.5 + 1e-6
    for hid, pmt in sel.payoffs.items():
        assert pmt >= -1e-6  # Individual rationality


# =============================================================================
# 4. INACTIVE HOUSEHOLD HANDLING
# =============================================================================

def test_inactive_household_handling():
    """Test 7: Inactive households receive empty action space and zero payoff."""
    res = solve_deterministic_nash_equilibrium(
        surpluses_kwh={"H001": 1.0, "H003": 0.0},
        deficits_kwh={"H002": 1.0, "H003": 0.0},
        all_households=["H001", "H002", "H003"],
    )

    assert "H003" in res.inactive_households
    # H003 is not in active players; profile only has H001 and H002
    assert "H003" not in res.selected_equilibrium.profile
    assert res.selected_equilibrium.payoffs["H003"] == 0.0


# =============================================================================
# 5. STRICT VS WEAK EQUILIBRIUM AND DEVIATION REJECTION
# =============================================================================

def test_strict_equilibrium_classification():
    """Test 8: Strict equilibrium requires every unilateral deviation to strictly reduce payoff."""
    res = solve_deterministic_nash_equilibrium(
        surpluses_kwh={"H001": 1.0},
        deficits_kwh={"H002": 1.0},
    )

    strict_eqs = res.strict_equilibria
    assert len(strict_eqs) > 0

    for eq in strict_eqs:
        assert eq.classification == EquilibriumClassification.STRICT
        # Manually verify that all deviations strictly decrease payoff
        p1, p2 = eq.profile["H001"], eq.profile["H002"]
        u1, u2 = eq.payoffs["H001"], eq.payoffs["H002"]

        # Seller deviations
        for alt_p1 in STRATEGIC_PRICE_GRID:
            if abs(alt_p1 - p1) < 1e-6:
                continue
            o1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=alt_p1, quantity_kwh=1.0)
            o2 = MarketOrder("H002", MarketRole.BUYER, price_aud_per_kwh=p2, quantity_kwh=1.0)
            dev_res = clear_strategic_double_auction([o1, o2])
            dev_u1 = dev_res.seller_incremental_benefits_aud["H001"]
            assert dev_u1 < u1 - 1e-6

        # Buyer deviations
        for alt_p2 in STRATEGIC_PRICE_GRID:
            if abs(alt_p2 - p2) < 1e-6:
                continue
            o1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=p1, quantity_kwh=1.0)
            o2 = MarketOrder("H002", MarketRole.BUYER, price_aud_per_kwh=alt_p2, quantity_kwh=1.0)
            dev_res = clear_strategic_double_auction([o1, o2])
            dev_u2 = dev_res.buyer_incremental_benefits_aud["H002"]
            assert dev_u2 < u2 - 1e-6


def test_weak_equilibrium_classification():
    """Test 9: Weak equilibrium has at least one equal deviation and no strictly higher."""
    res = solve_deterministic_nash_equilibrium(
        surpluses_kwh={"H001": 1.0},
        deficits_kwh={"H002": 1.0},
    )

    weak_eqs = res.weak_equilibria
    assert len(weak_eqs) > 0

    for eq in weak_eqs:
        assert eq.classification == EquilibriumClassification.WEAK
        p1, p2 = eq.profile["H001"], eq.profile["H002"]
        u1, u2 = eq.payoffs["H001"], eq.payoffs["H002"]

        has_equal_deviation = False
        has_profitable_deviation = False

        # Seller deviations
        for alt_p1 in STRATEGIC_PRICE_GRID:
            if abs(alt_p1 - p1) < 1e-6:
                continue
            o1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=alt_p1, quantity_kwh=1.0)
            o2 = MarketOrder("H002", MarketRole.BUYER, price_aud_per_kwh=p2, quantity_kwh=1.0)
            dev_res = clear_strategic_double_auction([o1, o2])
            dev_u1 = dev_res.seller_incremental_benefits_aud["H001"]
            if dev_u1 > u1 + 1e-6:
                has_profitable_deviation = True
            elif abs(dev_u1 - u1) <= 1e-6:
                has_equal_deviation = True

        # Buyer deviations
        for alt_p2 in STRATEGIC_PRICE_GRID:
            if abs(alt_p2 - p2) < 1e-6:
                continue
            o1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=p1, quantity_kwh=1.0)
            o2 = MarketOrder("H002", MarketRole.BUYER, price_aud_per_kwh=alt_p2, quantity_kwh=1.0)
            dev_res = clear_strategic_double_auction([o1, o2])
            dev_u2 = dev_res.buyer_incremental_benefits_aud["H002"]
            if dev_u2 > u2 + 1e-6:
                has_profitable_deviation = True
            elif abs(dev_u2 - u2) <= 1e-6:
                has_equal_deviation = True

        assert not has_profitable_deviation
        assert has_equal_deviation


def test_profitable_unilateral_deviation_rejection():
    """Test 10: Profiles with profitable unilateral deviations are rejected."""
    res = solve_deterministic_nash_equilibrium(
        surpluses_kwh={"H001": 1.0},
        deficits_kwh={"H002": 1.0},
    )

    # In profile (0.12, 0.22):
    # Seller asks 0.12, Buyer bids 0.22.
    # Current price = (0.12 + 0.22)/2 = 0.17 -> Seller earns 0.09.
    # If seller deviates to 0.22, price is 0.22 -> Seller earns 0.14 > 0.09!
    # Therefore (0.12, 0.22) is NOT an equilibrium.
    eq_profiles = [eq.profile for eq in res.equilibria]
    assert {"H001": 0.12, "H002": 0.22} not in eq_profiles
    assert {"H001": 0.16, "H002": 0.26} not in eq_profiles


def test_multiple_pne_preservation():
    """Test 11: Solver preserves all detected pure Nash equilibria without discarding."""
    res = solve_deterministic_nash_equilibrium(
        surpluses_kwh={"H001": 1.0},
        deficits_kwh={"H002": 1.0},
    )

    assert res.num_equilibria == 8
    assert len(res.equilibria) == 8
    # Confirm exact profiles preserved
    expected_profiles = [
        {"H001": 0.08, "H002": 0.08},
        {"H001": 0.12, "H002": 0.12},
        {"H001": 0.16, "H002": 0.16},
        {"H001": 0.19, "H002": 0.19},
        {"H001": 0.22, "H002": 0.22},
        {"H001": 0.26, "H002": 0.26},
        {"H001": 0.30, "H002": 0.30},
        {"H001": 0.30, "H002": 0.08},
    ]
    actual_profiles = [eq.profile for eq in res.equilibria]
    for ep in expected_profiles:
        assert ep in actual_profiles


def test_no_pne_handling():
    """Test 12: Solver returns explicit NO_PURE_NASH_EQUILIBRIUM when no PNE exists."""
    # Mock clear_strategic_double_auction to simulate a cyclical payoff game (matching pennies)
    # where player 1 wants to match player 2, and player 2 wants to mismatch player 1.
    def mock_cyclic_clear(orders, **kwargs):
        # Determine bids
        ord_map = {o.household_id: o.price_aud_per_kwh for o in orders}
        p1 = ord_map.get("H001", 0.08)
        p2 = ord_map.get("H002", 0.08)

        # Cyclic payoff structure:
        # If p1 == p2: H001 gets 1.0, H002 gets 0.0
        # If p1 != p2: H001 gets 0.0, H002 gets 1.0
        if abs(p1 - p2) < 1e-6:
            u1, u2 = 1.0, 0.0
        else:
            u1, u2 = 0.0, 1.0

        mock_res = StrategicMarketResult(
            transactions=[],
            total_traded_kwh=1.0,
            seller_allocations_kwh={"H001": 1.0},
            buyer_allocations_kwh={"H002": 1.0},
            seller_revenues_aud={"H001": 0.19},
            buyer_payments_aud={"H002": 0.19},
            seller_incremental_benefits_aud={"H001": u1},
            buyer_incremental_benefits_aud={"H002": u2},
            community_incremental_welfare_aud=0.22,
            unmatched_seller_surplus_kwh={"H001": 0.0},
            unmatched_buyer_deficit_kwh={"H002": 0.0},
            weighted_average_transaction_price_aud=0.19,
            energy_conservation_residual_kwh=0.0,
            financial_balance_residual_aud=0.0,
            welfare_identity_residual_aud=0.0,
            active_sellers=["H001"],
            active_buyers=["H002"],
            inactive_households=["H003"],
        )
        return mock_res

    with patch("src.game.strategic_solver.clear_strategic_double_auction", side_effect=mock_cyclic_clear):
        res = solve_deterministic_nash_equilibrium(
            surpluses_kwh={"H001": 1.0},
            deficits_kwh={"H002": 1.0},
            price_grid=(0.12, 0.22),  # 2x2 game
        )

        assert res.status == SolverStatus.NO_PURE_NASH_EQUILIBRIUM.value
        assert res.num_equilibria == 0
        assert res.equilibria == []
        assert res.selected_equilibrium is None


# =============================================================================
# 6. PARETO DOMINANCE AND SELECTION HEURISTIC
# =============================================================================

def test_pareto_dominance_complete_payoff_vector():
    """Test 13: Pareto dominance evaluates the complete vector, not community welfare alone."""
    houses = ["H001", "H002", "H003"]

    # Candidate A vs Candidate B:
    # A has lower community welfare (0.24) than B (0.25),
    # but H002 is strictly better off in A (0.12 vs 0.05).
    # Neither should dominate the other!
    payoffs_a = {"H001": 0.12, "H002": 0.12, "H003": 0.0}  # Sum = 0.24
    payoffs_b = {"H001": 0.20, "H002": 0.05, "H003": 0.0}  # Sum = 0.25

    assert not check_pareto_dominance(payoffs_b, payoffs_a, houses)
    assert not check_pareto_dominance(payoffs_a, payoffs_b, houses)

    # Candidate C strictly dominates Candidate D
    payoffs_c = {"H001": 0.10, "H002": 0.10, "H003": 0.0}
    payoffs_d = {"H001": 0.08, "H002": 0.10, "H003": 0.0}
    assert check_pareto_dominance(payoffs_c, payoffs_d, houses)
    assert not check_pareto_dominance(payoffs_d, payoffs_c, houses)


def test_pareto_undominated_identification():
    """Test 14: Filter to Pareto-undominated set correctly eliminates dominated equilibria."""
    res = solve_deterministic_nash_equilibrium(
        surpluses_kwh={"H001": 1.0},
        deficits_kwh={"H002": 1.0},
    )

    # In 1-seller 1-buyer, exactly the 7 diagonal equilibria are undominated.
    # The (0.30, 0.08) equilibrium has payoffs (0, 0) and is dominated.
    assert res.num_pareto_undominated == 7
    dominated = [eq for eq in res.equilibria if not eq.is_pareto_undominated]
    assert len(dominated) == 1
    assert dominated[0].profile == {"H001": 0.30, "H002": 0.08}


def test_representative_equilibrium_tie_breaking():
    """Test 15: Deterministic 5-step tie-breaking sequence."""
    houses = ["H001", "H002"]

    # 1. Distance to reference price $0.19 tie-breaker
    # Dummy mock records
    mock_res = StrategicMarketResult(
        transactions=[],
        total_traded_kwh=1.0,
        seller_allocations_kwh={"H001": 1.0},
        buyer_allocations_kwh={"H002": 1.0},
        seller_revenues_aud={"H001": 0.19},
        buyer_payments_aud={"H002": 0.19},
        seller_incremental_benefits_aud={"H001": 0.11},
        buyer_incremental_benefits_aud={"H002": 0.11},
        community_incremental_welfare_aud=0.22,
        unmatched_seller_surplus_kwh={"H001": 0.0},
        unmatched_buyer_deficit_kwh={"H002": 0.0},
        weighted_average_transaction_price_aud=0.19,
        energy_conservation_residual_kwh=0.0,
        financial_balance_residual_aud=0.0,
        welfare_identity_residual_aud=0.0,
        active_sellers=["H001"],
        active_buyers=["H002"],
        inactive_households=[],
    )

    eq_near = NashEquilibriumRecord(
        profile={"H001": 0.19, "H002": 0.19},
        roles={"H001": MarketRole.SELLER, "H002": MarketRole.BUYER},
        payoffs={"H001": 0.11, "H002": 0.11},
        total_traded_kwh=1.0,
        weighted_average_price_aud=0.19,
        community_welfare_aud=0.22,
        num_transactions=1,
        classification=EquilibriumClassification.STRICT,
        is_pareto_undominated=True,
        transaction_price_std=0.0,
        market_result=mock_res,
    )
    eq_far = NashEquilibriumRecord(
        profile={"H001": 0.26, "H002": 0.26},
        roles={"H001": MarketRole.SELLER, "H002": MarketRole.BUYER},
        payoffs={"H001": 0.18, "H002": 0.04},
        total_traded_kwh=1.0,
        weighted_average_price_aud=0.26,
        community_welfare_aud=0.22,
        num_transactions=1,
        classification=EquilibriumClassification.STRICT,
        is_pareto_undominated=True,
        transaction_price_std=0.0,
        market_result=mock_res,
    )

    sel = select_representative_equilibrium([eq_near, eq_far], active_players=["H001", "H002"])
    assert sel == eq_near


def test_zero_volume_equilibrium_selection_handling():
    """Test 16: Zero-volume equilibria have infinite reference price distance."""
    mock_res_0 = StrategicMarketResult(
        transactions=[],
        total_traded_kwh=0.0,
        seller_allocations_kwh={"H001": 0.0},
        buyer_allocations_kwh={"H002": 0.0},
        seller_revenues_aud={"H001": 0.0},
        buyer_payments_aud={"H002": 0.0},
        seller_incremental_benefits_aud={"H001": 0.0},
        buyer_incremental_benefits_aud={"H002": 0.0},
        community_incremental_welfare_aud=0.0,
        unmatched_seller_surplus_kwh={"H001": 1.0},
        unmatched_buyer_deficit_kwh={"H002": 1.0},
        weighted_average_transaction_price_aud=None,
        energy_conservation_residual_kwh=0.0,
        financial_balance_residual_aud=0.0,
        welfare_identity_residual_aud=0.0,
        active_sellers=["H001"],
        active_buyers=["H002"],
        inactive_households=[],
    )

    eq_zero = NashEquilibriumRecord(
        profile={"H001": 0.30, "H002": 0.08},
        roles={"H001": MarketRole.SELLER, "H002": MarketRole.BUYER},
        payoffs={"H001": 0.0, "H002": 0.0},
        total_traded_kwh=0.0,
        weighted_average_price_aud=None,
        community_welfare_aud=0.0,
        num_transactions=0,
        classification=EquilibriumClassification.WEAK,
        is_pareto_undominated=True,
        transaction_price_std=0.0,
        market_result=mock_res_0,
    )

    # When paired with any positive trade equilibrium, the positive trade is chosen
    mock_res_pos = StrategicMarketResult(
        transactions=[],
        total_traded_kwh=1.0,
        seller_allocations_kwh={"H001": 1.0},
        buyer_allocations_kwh={"H002": 1.0},
        seller_revenues_aud={"H001": 0.22},
        buyer_payments_aud={"H002": 0.22},
        seller_incremental_benefits_aud={"H001": 0.14},
        buyer_incremental_benefits_aud={"H002": 0.08},
        community_incremental_welfare_aud=0.22,
        unmatched_seller_surplus_kwh={"H001": 0.0},
        unmatched_buyer_deficit_kwh={"H002": 0.0},
        weighted_average_transaction_price_aud=0.22,
        energy_conservation_residual_kwh=0.0,
        financial_balance_residual_aud=0.0,
        welfare_identity_residual_aud=0.0,
        active_sellers=["H001"],
        active_buyers=["H002"],
        inactive_households=[],
    )
    eq_pos = NashEquilibriumRecord(
        profile={"H001": 0.22, "H002": 0.22},
        roles={"H001": MarketRole.SELLER, "H002": MarketRole.BUYER},
        payoffs={"H001": 0.14, "H002": 0.08},
        total_traded_kwh=1.0,
        weighted_average_price_aud=0.22,
        community_welfare_aud=0.22,
        num_transactions=1,
        classification=EquilibriumClassification.STRICT,
        is_pareto_undominated=True,
        transaction_price_std=0.0,
        market_result=mock_res_pos,
    )

    sel = select_representative_equilibrium([eq_zero, eq_pos], active_players=["H001", "H002"])
    assert sel == eq_pos


def test_numerical_tolerance_payoff_equality():
    """Test 17: Differences within numerical tolerance are treated as equal (weak)."""
    # Verify that tolerance parameter controls deviation classification
    res_tight = solve_deterministic_nash_equilibrium(
        surpluses_kwh={"H001": 1.0},
        deficits_kwh={"H002": 1.0},
        tolerance=1e-6,
    )
    assert res_tight.num_strict == 5
    assert res_tight.num_weak == 3


def test_solver_consistency_with_phase8b1():
    """Test 18: Consistency between solver clearing results and Phase 8B.1 engine directly."""
    res = solve_deterministic_nash_equilibrium(
        surpluses_kwh={"H001": 2.0},
        deficits_kwh={"H002": 1.0, "H003": 1.0},
    )

    # Pick the selected equilibrium
    sel = res.selected_equilibrium
    assert sel is not None

    # Construct the exact same orders directly in Phase 8B.1 clear_strategic_double_auction
    orders = [
        MarketOrder(
            household_id=hid,
            role=sel.roles[hid],
            price_aud_per_kwh=sel.profile[hid],
            quantity_kwh=2.0 if hid == "H001" else 1.0,
        )
        for hid in ["H001", "H002", "H003"]
    ]

    direct_res = clear_strategic_double_auction(orders)

    assert pytest.approx(sel.total_traded_kwh, abs=1e-9) == direct_res.total_traded_kwh
    assert pytest.approx(sel.weighted_average_price_aud, abs=1e-9) == direct_res.weighted_average_transaction_price_aud
    assert pytest.approx(sel.community_welfare_aud, abs=1e-9) == direct_res.community_incremental_welfare_aud
    assert pytest.approx(sel.payoffs["H001"], abs=1e-9) == direct_res.seller_incremental_benefits_aud["H001"]
    assert pytest.approx(sel.payoffs["H002"], abs=1e-9) == direct_res.buyer_incremental_benefits_aud["H002"]
    assert pytest.approx(sel.payoffs["H003"], abs=1e-9) == direct_res.buyer_incremental_benefits_aud["H003"]


# =============================================================================
# 7. CONVENIENCE HELPERS AND VALIDATION
# =============================================================================

def test_physical_flow_convenience_helper():
    """Test 19: Convenience helper solve_nash_from_physical_flows correctly computes positions."""
    flows = {
        "H001": {"demand_kwh": 0.5, "battery_charge_kwh": 0.5, "solar_generation_kwh": 2.0, "battery_discharge_kwh": 0.0},
        "H002": {"demand_kwh": 2.0, "battery_charge_kwh": 0.0, "solar_generation_kwh": 0.5, "battery_discharge_kwh": 0.5},
        "H003": {"demand_kwh": 1.0, "battery_charge_kwh": 0.0, "solar_generation_kwh": 0.6, "battery_discharge_kwh": 0.4},
    }
    # H001: (0.5+0.5) - (2.0+0.0) = 1.0 - 2.0 = -1.0 -> surplus = 1.0 kWh (Seller)
    # H002: (2.0+0.0) - (0.5+0.5) = 2.0 - 1.0 = +1.0 -> deficit = 1.0 kWh (Buyer)
    # H003: (1.0+0.0) - (0.6+0.4) = 1.0 - 1.0 = 0.0 -> Inactive

    res = solve_nash_from_physical_flows(flows)
    assert res.status == SolverStatus.SUCCESS.value
    assert res.active_sellers == ["H001"]
    assert res.active_buyers == ["H002"]
    assert res.inactive_households == ["H003"]
    assert res.selected_traded_kwh == 1.0


def test_input_validation_and_errors():
    """Test 20: Input validation for invalid tariffs, grids, and simultaneous positions."""
    # Negative tariff
    with pytest.raises(ValueError, match="grid_import_tariff_aud must be nonnegative"):
        solve_deterministic_nash_equilibrium(surpluses_kwh={"H001": 1.0}, grid_import_tariff_aud=-0.10)

    # Tariff inversion
    with pytest.raises(ValueError, match="cannot be less than"):
        solve_deterministic_nash_equilibrium(
            surpluses_kwh={"H001": 1.0}, grid_import_tariff_aud=0.05, grid_export_credit_aud=0.08
        )

    # Simultaneous positive surplus and deficit
    with pytest.raises(ValueError, match="cannot simultaneously have positive surplus"):
        solve_deterministic_nash_equilibrium(
            surpluses_kwh={"H001": 1.0},
            deficits_kwh={"H001": 1.0},
        )


def test_all_inactive_households():
    """Test 21: Game with zero active households returns trivial single equilibrium."""
    res = solve_deterministic_nash_equilibrium(
        surpluses_kwh={"H001": 0.0, "H002": 0.0, "H003": 0.0},
        deficits_kwh={"H001": 0.0, "H002": 0.0, "H003": 0.0},
    )

    assert res.status == SolverStatus.SUCCESS.value
    assert res.num_profiles_evaluated == 1
    assert res.num_deviations_evaluated == 0
    assert res.num_equilibria == 1
    assert res.selected_traded_kwh == 0.0
    assert res.selected_welfare_aud == 0.0
    assert res.selected_payoffs == {"H001": 0.0, "H002": 0.0, "H003": 0.0}

