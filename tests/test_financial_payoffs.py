"""Regression and verification tests for financial utility, payoff matrix, and Nash equilibrium.

Covers Step 4.2 requirements:
- Financial consistency across all four strategy profiles.
- Equality of P2P payments between seller and buyer.
- Correct grid import and export accounting.
- Best-response calculations for both players.
- Pure Nash equilibrium detection on hand-calculated payoff matrices.
- Stochastic expected payoffs matching the arithmetic mean of scenario-level payoffs.
- Zero-surplus and zero-deficit boundary cases.
"""

import pytest
import numpy as np

from src.energy.energy_balance import compute_energy_balance
from src.game.utility import P2PTransaction, compute_household_payoff
from src.game.payoff_matrix import (
    GamePayoffMatrix,
    build_two_household_payoff_matrix,
)
from src.stochastic.monte_carlo import (
    ScenarioDistribution,
    build_stochastic_payoff_matrix,
)
from src.game.best_response import compute_detailed_best_responses, BestResponseDetail
from src.game.nash import find_pure_nash_equilibria, EquilibriumAnalysisResult, NashEquilibrium


# ---------------------------------------------------------------------------
# Task 1 & 2: Deterministic 4-profile financial consistency & hand benchmark
# ---------------------------------------------------------------------------

def test_four_strategy_profiles_financial_consistency():
    """Verify hand-calculated benchmark: S_1 = 2.0 kWh, B_2 = 1.5 kWh.

    Tariffs:
      p_import = 0.30 AUD/kWh
      p_export = 0.08 AUD/kWh
      p_p2p    = 0.19 AUD/kWh (mid-market)

    Expected profiles:
      1. (OFFER_P2P, ACCEPT_P2P):
         q = min(2.0, 1.5) = 1.5 kWh
         Seller: exports 0.5 kWh -> rev = 0.5 * 0.08 = 0.04 AUD.
                 P2P rev = 1.5 * 0.19 = 0.285 AUD.
                 Net exp = -0.325 AUD -> Utility = +0.325 AUD.
         Buyer:  imports 0.0 kWh -> cost = 0.00 AUD.
                 P2P cost = 1.5 * 0.19 = 0.285 AUD.
                 Net exp = +0.285 AUD -> Utility = -0.285 AUD.

      2. (OFFER_P2P, GRID_IMPORT):
         q = 0.0 kWh
         Seller: exports 2.0 kWh -> rev = 0.16 AUD -> Utility = +0.160 AUD.
         Buyer:  imports 1.5 kWh -> cost = 0.45 AUD -> Utility = -0.450 AUD.

      3. (EXPORT_GRID, ACCEPT_P2P):
         q = 0.0 kWh -> Identical to no-trade baseline (+0.160, -0.450).

      4. (EXPORT_GRID, GRID_IMPORT):
         q = 0.0 kWh -> Identical to no-trade baseline (+0.160, -0.450).
    """
    s_surplus = 2.0
    b_deficit = 1.5
    p_import = 0.30
    p_export = 0.08

    m = build_two_household_payoff_matrix(
        seller_id="H001",
        seller_surplus_kwh=s_surplus,
        buyer_id="H002",
        buyer_deficit_kwh=b_deficit,
        grid_import_price_aud=p_import,
        grid_export_credit_aud=p_export,
    )

    i_offer = m.actions_p1.index("OFFER_P2P")
    i_export = m.actions_p1.index("EXPORT_GRID")
    j_accept = m.actions_p2.index("ACCEPT_P2P")
    j_grid = m.actions_p2.index("GRID_IMPORT")

    # Profile 1: (OFFER_P2P, ACCEPT_P2P)
    assert m.traded_quantities[i_offer, j_accept] == pytest.approx(1.5)
    assert m.payoffs_p1[i_offer, j_accept] == pytest.approx(+0.325, abs=1e-6)
    assert m.payoffs_p2[i_offer, j_accept] == pytest.approx(-0.285, abs=1e-6)

    # Profile 2: (OFFER_P2P, GRID_IMPORT)
    assert m.traded_quantities[i_offer, j_grid] == pytest.approx(0.0)
    assert m.payoffs_p1[i_offer, j_grid] == pytest.approx(+0.160, abs=1e-6)
    assert m.payoffs_p2[i_offer, j_grid] == pytest.approx(-0.450, abs=1e-6)

    # Profile 3: (EXPORT_GRID, ACCEPT_P2P)
    assert m.traded_quantities[i_export, j_accept] == pytest.approx(0.0)
    assert m.payoffs_p1[i_export, j_accept] == pytest.approx(+0.160, abs=1e-6)
    assert m.payoffs_p2[i_export, j_accept] == pytest.approx(-0.450, abs=1e-6)

    # Profile 4: (EXPORT_GRID, GRID_IMPORT)
    assert m.traded_quantities[i_export, j_grid] == pytest.approx(0.0)
    assert m.payoffs_p1[i_export, j_grid] == pytest.approx(+0.160, abs=1e-6)
    assert m.payoffs_p2[i_export, j_grid] == pytest.approx(-0.450, abs=1e-6)


def test_p2p_payment_equality_exact():
    """P2P payment paid by buyer must identically match revenue received by seller."""
    for s in [0.5, 1.25, 3.0]:
        for b in [0.3, 1.25, 2.5]:
            for p_p2p in [0.10, 0.19, 0.25]:
                q = min(s, b)
                tx = P2PTransaction(
                    seller_id="H001",
                    buyer_id="H002",
                    traded_energy_kwh=q,
                    price_aud_per_kwh=p_p2p,
                )
                assert tx.total_transaction_value_aud == pytest.approx(q * p_p2p, abs=1e-12)

                p_seller = compute_household_payoff(
                    house_id="H001",
                    deficit_kwh=0.0,
                    surplus_kwh=s,
                    grid_import_price_aud=0.30,
                    grid_export_credit_aud=0.08,
                    p2p_energy_sold_kwh=q,
                    p2p_price_aud=p_p2p,
                )
                p_buyer = compute_household_payoff(
                    house_id="H002",
                    deficit_kwh=b,
                    surplus_kwh=0.0,
                    grid_import_price_aud=0.30,
                    grid_export_credit_aud=0.08,
                    p2p_energy_bought_kwh=q,
                    p2p_price_aud=p_p2p,
                )
                assert p_seller.p2p_revenue_aud == pytest.approx(p_buyer.p2p_payment_aud, abs=1e-12)
                assert p_seller.p2p_payment_aud == 0.0
                assert p_buyer.p2p_revenue_aud == 0.0


def test_grid_import_export_accounting():
    """Verify physical energy balance and grid financial accounting across profiles."""
    s_surplus = 1.8
    b_deficit = 2.4
    p_import = 0.32
    p_export = 0.07
    p_p2p = 0.195

    # Case 1: Trade occurs (q = 1.8)
    q = min(s_surplus, b_deficit)
    p_seller_trade = compute_household_payoff(
        house_id="H001", deficit_kwh=0.0, surplus_kwh=s_surplus,
        grid_import_price_aud=p_import, grid_export_credit_aud=p_export,
        p2p_energy_sold_kwh=q, p2p_price_aud=p_p2p
    )
    p_buyer_trade = compute_household_payoff(
        house_id="H002", deficit_kwh=b_deficit, surplus_kwh=0.0,
        grid_import_price_aud=p_import, grid_export_credit_aud=p_export,
        p2p_energy_bought_kwh=q, p2p_price_aud=p_p2p
    )

    assert p_seller_trade.grid_exported_kwh == pytest.approx(0.0)
    assert p_seller_trade.grid_export_revenue_aud == pytest.approx(0.0)
    assert p_buyer_trade.grid_imported_kwh == pytest.approx(b_deficit - q)
    assert p_buyer_trade.grid_import_cost_aud == pytest.approx((b_deficit - q) * p_import)

    # Case 2: No trade (q = 0.0)
    p_seller_base = compute_household_payoff(
        house_id="H001", deficit_kwh=0.0, surplus_kwh=s_surplus,
        grid_import_price_aud=p_import, grid_export_credit_aud=p_export,
        p2p_energy_sold_kwh=0.0, p2p_price_aud=p_p2p
    )
    p_buyer_base = compute_household_payoff(
        house_id="H002", deficit_kwh=b_deficit, surplus_kwh=0.0,
        grid_import_price_aud=p_import, grid_export_credit_aud=p_export,
        p2p_energy_bought_kwh=0.0, p2p_price_aud=p_p2p
    )

    assert p_seller_base.grid_exported_kwh == pytest.approx(s_surplus)
    assert p_seller_base.grid_export_revenue_aud == pytest.approx(s_surplus * p_export)
    assert p_buyer_base.grid_imported_kwh == pytest.approx(b_deficit)
    assert p_buyer_base.grid_import_cost_aud == pytest.approx(b_deficit * p_import)


# ---------------------------------------------------------------------------
# Task 2: Best response & Nash equilibrium verification
# ---------------------------------------------------------------------------

def test_best_response_and_nash_benchmark():
    """Verify best responses and Nash equilibrium on the benchmark matrix."""
    m = build_two_household_payoff_matrix(
        seller_id="H001",
        seller_surplus_kwh=2.0,
        buyer_id="H002",
        buyer_deficit_kwh=1.5,
        grid_import_price_aud=0.30,
        grid_export_credit_aud=0.08,
    )

    br_p1, br_p2 = compute_detailed_best_responses(m)

    # Against ACCEPT_P2P, Seller strictly prefers OFFER_P2P (+0.325 > +0.160)
    assert br_p1["ACCEPT_P2P"].best_actions == ["OFFER_P2P"]
    assert br_p1["ACCEPT_P2P"].is_strictly_dominant_against_action is True

    # Against GRID_IMPORT, Seller is indifferent (+0.160 == +0.160)
    assert set(br_p1["GRID_IMPORT"].best_actions) == {"OFFER_P2P", "EXPORT_GRID"}
    assert br_p1["GRID_IMPORT"].is_strictly_dominant_against_action is False

    # Against OFFER_P2P, Buyer strictly prefers ACCEPT_P2P (-0.285 > -0.450)
    assert br_p2["OFFER_P2P"].best_actions == ["ACCEPT_P2P"]
    assert br_p2["OFFER_P2P"].is_strictly_dominant_against_action is True

    # Against EXPORT_GRID, Buyer is indifferent (-0.450 == -0.450)
    assert set(br_p2["EXPORT_GRID"].best_actions) == {"ACCEPT_P2P", "GRID_IMPORT"}
    assert br_p2["EXPORT_GRID"].is_strictly_dominant_against_action is False

    # Nash equilibria
    nash = find_pure_nash_equilibria(m)
    assert nash.has_pure_nash is True
    eq_set = {(e.action_player1, e.action_player2) for e in nash.equilibria}
    assert ("OFFER_P2P", "ACCEPT_P2P") in eq_set
    assert ("EXPORT_GRID", "GRID_IMPORT") in eq_set


# ---------------------------------------------------------------------------
# Task 3: Stochastic expected payoffs match scenario-level arithmetic mean
# ---------------------------------------------------------------------------

def test_stochastic_payoffs_match_scenario_mean_exactly():
    """build_stochastic_payoff_matrix must compute exact arithmetic mean of scenario payoffs."""
    rng = np.random.default_rng(42)
    n_scenarios = 100

    # Synthetic scenarios
    s_demand = rng.uniform(0.1, 0.5, size=n_scenarios)
    s_solar = rng.uniform(0.5, 2.0, size=n_scenarios)
    b_demand = rng.uniform(1.0, 2.5, size=n_scenarios)
    b_solar = rng.uniform(0.0, 0.5, size=n_scenarios)

    s_surpluses = np.maximum(0.0, s_solar - s_demand)
    b_deficits = np.maximum(0.0, b_demand - b_solar)

    p_import = 0.30
    p_export = 0.08
    p_p2p = 0.19

    dist_seller = ScenarioDistribution(
        house_id="H001",
        num_scenarios=n_scenarios,
        forecast_demand_mean_kwh=float(np.mean(s_demand)),
        forecast_solar_mean_kwh=float(np.mean(s_solar)),
        scenarios_demand_kwh=s_demand,
        scenarios_solar_kwh=s_solar,
    )
    dist_buyer = ScenarioDistribution(
        house_id="H002",
        num_scenarios=n_scenarios,
        forecast_demand_mean_kwh=float(np.mean(b_demand)),
        forecast_solar_mean_kwh=float(np.mean(b_solar)),
        scenarios_demand_kwh=b_demand,
        scenarios_solar_kwh=b_solar,
    )

    # Build stochastic matrix
    m_stoch, _, _ = build_stochastic_payoff_matrix(
        dist_seller=dist_seller,
        dist_buyer=dist_buyer,
        grid_import_price_aud=p_import,
        grid_export_credit_aud=p_export,
        p2p_price_aud=p_p2p,
    )

    # Manually compute arithmetic mean of scenario-level payoffs
    u1_scenarios = {
        ("OFFER_P2P", "ACCEPT_P2P"): [],
        ("OFFER_P2P", "GRID_IMPORT"): [],
        ("EXPORT_GRID", "ACCEPT_P2P"): [],
        ("EXPORT_GRID", "GRID_IMPORT"): [],
    }
    u2_scenarios = {
        ("OFFER_P2P", "ACCEPT_P2P"): [],
        ("OFFER_P2P", "GRID_IMPORT"): [],
        ("EXPORT_GRID", "ACCEPT_P2P"): [],
        ("EXPORT_GRID", "GRID_IMPORT"): [],
    }

    for s, b in zip(s_surpluses, b_deficits):
        m_s = build_two_household_payoff_matrix(
            seller_id="H001", seller_surplus_kwh=s,
            buyer_id="H002",  buyer_deficit_kwh=b,
            grid_import_price_aud=p_import, grid_export_credit_aud=p_export,
        )
        for a1 in ["OFFER_P2P", "EXPORT_GRID"]:
            for a2 in ["ACCEPT_P2P", "GRID_IMPORT"]:
                i = m_s.actions_p1.index(a1)
                j = m_s.actions_p2.index(a2)
                u1_scenarios[(a1, a2)].append(m_s.payoffs_p1[i, j])
                u2_scenarios[(a1, a2)].append(m_s.payoffs_p2[i, j])

    # Assert exact match to floating point precision
    for a1 in ["OFFER_P2P", "EXPORT_GRID"]:
        for a2 in ["ACCEPT_P2P", "GRID_IMPORT"]:
            i = m_stoch.actions_p1.index(a1)
            j = m_stoch.actions_p2.index(a2)
            expected_u1 = float(np.mean(u1_scenarios[(a1, a2)]))
            expected_u2 = float(np.mean(u2_scenarios[(a1, a2)]))

            assert m_stoch.payoffs_p1[i, j] == pytest.approx(expected_u1, abs=1e-12)
            assert m_stoch.payoffs_p2[i, j] == pytest.approx(expected_u2, abs=1e-12)


def test_jensens_inequality_distinction_from_mean_payoff():
    """Demonstrate E[U(min(S, B))] != U(min(E[S], E[B])) due to non-linearity."""
    # S oscillates between 0 and 2; B is fixed at 1
    # E[S] = 1.0, E[B] = 1.0 -> min(E[S], E[B]) = 1.0
    # In scenarios: s1=(0, 1) -> min=0; s2=(2, 1) -> min=1
    # E[min(S, B)] = 0.5 != min(E[S], E[B]) = 1.0!
    dist_seller = ScenarioDistribution(
        house_id="H001",
        num_scenarios=2,
        forecast_demand_mean_kwh=0.0,
        forecast_solar_mean_kwh=1.0,
        scenarios_demand_kwh=np.array([0.0, 0.0]),
        scenarios_solar_kwh=np.array([0.0, 2.0]),
    )
    dist_buyer = ScenarioDistribution(
        house_id="H002",
        num_scenarios=2,
        forecast_demand_mean_kwh=1.0,
        forecast_solar_mean_kwh=0.0,
        scenarios_demand_kwh=np.array([1.0, 1.0]),
        scenarios_solar_kwh=np.array([0.0, 0.0]),
    )

    m_stoch, _, _ = build_stochastic_payoff_matrix(
        dist_seller=dist_seller,
        dist_buyer=dist_buyer,
        grid_import_price_aud=0.30,
        grid_export_credit_aud=0.08,
    )

    # Average traded energy is 0.5, NOT 1.0
    i_offer = m_stoch.actions_p1.index("OFFER_P2P")
    j_accept = m_stoch.actions_p2.index("ACCEPT_P2P")
    assert m_stoch.traded_quantities[i_offer, j_accept] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Task 4: Boundary cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("s,b", [
    (0.0, 1.5),  # Zero surplus
    (2.0, 0.0),  # Zero deficit
    (0.0, 0.0),  # Both zero
])
def test_zero_surplus_and_zero_deficit_boundary_cases(s, b):
    """Zero-trade boundary conditions must yield zero P2P trade and valid payoff matrices."""
    m = build_two_household_payoff_matrix(
        seller_id="H001", seller_surplus_kwh=s,
        buyer_id="H002",  buyer_deficit_kwh=b,
        grid_import_price_aud=0.30, grid_export_credit_aud=0.08,
    )
    assert np.all(m.traded_quantities == 0.0)
    assert not np.isnan(m.payoffs_p1).any()
    assert not np.isnan(m.payoffs_p2).any()

    # When trade is zero everywhere, payoffs are identical across all 4 profiles
    assert np.all(m.payoffs_p1 == m.payoffs_p1[0, 0])
    assert np.all(m.payoffs_p2 == m.payoffs_p2[0, 0])

    # Equilibrium finder must execute cleanly
    nash = find_pure_nash_equilibria(m)
    assert nash.has_pure_nash is True
    # All 4 profiles are weak Nash equilibria because no one can unilaterally improve
    assert len(nash.equilibria) == 4


# ---------------------------------------------------------------------------
# Step 4.3: Equilibrium multiplicity, reconciliation, and financial metrics
# ---------------------------------------------------------------------------

def test_equilibrium_multiplicity_and_coordination_failure():
    """Verify that pure Nash equilibrium is never unique in positive-trade games.

    In every positive-trade hour:
    - (OFFER_P2P, ACCEPT_P2P) is STRICT pure Nash equilibrium.
    - (EXPORT_GRID, GRID_IMPORT) is WEAK pure Nash equilibrium (coordination failure).
    - Off-diagonal profiles are NEVER equilibria.
    - Total pure Nash equilibria == 2 (multiplicity > 1, uniqueness == False).
    """
    m = build_two_household_payoff_matrix(
        seller_id="H001", seller_surplus_kwh=1.8,
        buyer_id="H002",  buyer_deficit_kwh=1.2,
        grid_import_price_aud=0.30, grid_export_credit_aud=0.08,
    )
    result = find_pure_nash_equilibria(m)

    assert result.num_equilibria == 2, f"Expected exactly 2 equilibria, got {result.num_equilibria}"

    eq_dict = {(e.action_player1, e.action_player2): e for e in result.equilibria}

    # 1. Cooperative profile is strict
    assert ("OFFER_P2P", "ACCEPT_P2P") in eq_dict
    assert eq_dict[("OFFER_P2P", "ACCEPT_P2P")].is_strict is True

    # 2. Grid-baseline profile is weak
    assert ("EXPORT_GRID", "GRID_IMPORT") in eq_dict
    assert eq_dict[("EXPORT_GRID", "GRID_IMPORT")].is_strict is False

    # 3. Off-diagonals are not equilibria
    assert ("OFFER_P2P", "GRID_IMPORT") not in eq_dict
    assert ("EXPORT_GRID", "ACCEPT_P2P") not in eq_dict

    # 4. Cooperative strictly Pareto dominates grid baseline
    coop_e = eq_dict[("OFFER_P2P", "ACCEPT_P2P")]
    base_e = eq_dict[("EXPORT_GRID", "GRID_IMPORT")]
    assert coop_e.utility_player1 > base_e.utility_player1
    assert coop_e.utility_player2 > base_e.utility_player2


def test_combined_household_utility_and_p2p_payment_cancellation():
    """Verify P2P payment cancels identically when summing household utilities.

    U_1 = (S_1 - q)*p_exp + q*p_p2p
    U_2 = -[(B_2 - q)*p_imp + q*p_p2p]
    Combined Utility = U_1 + U_2 = (S_1 - q)*p_exp - (B_2 - q)*p_imp
    The internal P2P transaction cancels to 0.0, leaving prosumers' net grid cash flow.
    """
    s = 2.5
    b = 1.6
    q = min(s, b)
    p_imp = 0.30
    p_exp = 0.08
    p_p2p = 0.19

    payoff_s = compute_household_payoff(
        house_id="H001", deficit_kwh=0.0, surplus_kwh=s,
        grid_import_price_aud=p_imp, grid_export_credit_aud=p_exp,
        p2p_energy_sold_kwh=q, p2p_price_aud=p_p2p,
    )
    payoff_b = compute_household_payoff(
        house_id="H002", deficit_kwh=b, surplus_kwh=0.0,
        grid_import_price_aud=p_imp, grid_export_credit_aud=p_exp,
        p2p_energy_bought_kwh=q, p2p_price_aud=p_p2p,
    )

    # 1. P2P Payment cancels identically
    p2p_transfer = payoff_s.p2p_revenue_aud - payoff_b.p2p_payment_aud
    assert p2p_transfer == pytest.approx(0.0, abs=1e-12)

    # 2. Combined household utility
    combined_u = payoff_s.utility + payoff_b.utility
    net_grid_cash_flow = payoff_s.grid_export_revenue_aud - payoff_b.grid_import_cost_aud
    assert combined_u == pytest.approx(net_grid_cash_flow, abs=1e-12)


def test_stochastic_payoff_scenario_alignment_and_expected_trade():
    """Verify stochastic matrix uses exact scenario alignment and scenario-level trade."""
    rng = np.random.default_rng(123)
    n = 200

    s_demand = rng.uniform(0.1, 0.4, size=n)
    s_solar = rng.uniform(0.3, 1.5, size=n)
    b_demand = rng.uniform(0.5, 2.0, size=n)
    b_solar = rng.uniform(0.0, 0.3, size=n)

    dist_s = ScenarioDistribution("H001", n, float(np.mean(s_demand)), float(np.mean(s_solar)), s_demand, s_solar)
    dist_b = ScenarioDistribution("H002", n, float(np.mean(b_demand)), float(np.mean(b_solar)), b_demand, b_solar)

    matrix, df_summary, stats = build_stochastic_payoff_matrix(dist_s, dist_b, 0.30, 0.08)

    # Traded energy across scenarios
    s_surplus = np.maximum(0.0, s_solar - s_demand)
    b_deficit = np.maximum(0.0, b_demand - b_solar)
    q_scenarios = np.minimum(s_surplus, b_deficit)

    # Traded quantity must equal scenario arithmetic mean
    expected_q = float(np.mean(q_scenarios))
    i_offer = matrix.actions_p1.index("OFFER_P2P")
    j_accept = matrix.actions_p2.index("ACCEPT_P2P")
    assert matrix.traded_quantities[i_offer, j_accept] == pytest.approx(expected_q, abs=1e-12)

    # Verify column naming in summary dataframe
    assert "Expected_Combined_Household_Utility_AUD" in df_summary.columns
    assert "Expected_Social_Welfare_AUD" in df_summary.columns  # backward compatibility alias

