"""Unit tests for payoff matrix, Nash equilibrium detection, and game model."""

import pytest
import numpy as np

from src.energy.energy_balance import compute_energy_balance
from src.game.payoff_matrix import build_two_household_payoff_matrix
from src.game.nash import find_pure_nash_equilibria
from src.game.game import run_two_household_game


# ---------------------------------------------------------------------------
# Payoff matrix construction
# ---------------------------------------------------------------------------

def test_payoff_matrix_shape():
    """Matrix must be (2, 2) for a 2-action game."""
    m = build_two_household_payoff_matrix(
        seller_id="H001", seller_surplus_kwh=1.0,
        buyer_id="H002",  buyer_deficit_kwh=1.0,
        grid_import_price_aud=0.30, grid_export_credit_aud=0.08,
    )
    assert m.payoffs_p1.shape == (2, 2)
    assert m.payoffs_p2.shape == (2, 2)
    assert m.traded_quantities.shape == (2, 2)


def test_no_trade_payoff_symmetric():
    """When seller offers but buyer rejects, or seller exports and buyer accepts,
    outcome must equal the (EXPORT_GRID, GRID_IMPORT) no-trade baseline."""
    m = build_two_household_payoff_matrix(
        seller_id="H001", seller_surplus_kwh=1.0,
        buyer_id="H002",  buyer_deficit_kwh=1.0,
        grid_import_price_aud=0.30, grid_export_credit_aud=0.08,
    )
    i_offer  = m.actions_p1.index("OFFER_P2P")
    i_export = m.actions_p1.index("EXPORT_GRID")
    j_accept = m.actions_p2.index("ACCEPT_P2P")
    j_grid   = m.actions_p2.index("GRID_IMPORT")

    # (OFFER, GRID_IMPORT) → no trade
    assert m.traded_quantities[i_offer, j_grid] == pytest.approx(0.0)
    # (EXPORT, ACCEPT) → no trade
    assert m.traded_quantities[i_export, j_accept] == pytest.approx(0.0)

    # Payoffs from unilateral deviations must equal no-trade baseline
    for j in [j_grid]:
        assert m.payoffs_p1[i_offer, j] == pytest.approx(m.payoffs_p1[i_export, j])
        assert m.payoffs_p2[i_offer, j] == pytest.approx(m.payoffs_p2[i_export, j])


def test_trade_quantity_bounded_by_min_surplus_deficit():
    """Trade quantity must be min(surplus, deficit) when both agree."""
    surplus = 0.8
    deficit = 1.2
    m = build_two_household_payoff_matrix(
        seller_id="H001", seller_surplus_kwh=surplus,
        buyer_id="H002",  buyer_deficit_kwh=deficit,
        grid_import_price_aud=0.30, grid_export_credit_aud=0.08,
    )
    i_offer  = m.actions_p1.index("OFFER_P2P")
    j_accept = m.actions_p2.index("ACCEPT_P2P")
    assert m.traded_quantities[i_offer, j_accept] == pytest.approx(min(surplus, deficit))


def test_p2p_trade_improves_both_payoffs():
    """Both players should have payoff >= baseline when they trade at mid-market price."""
    m = build_two_household_payoff_matrix(
        seller_id="H001", seller_surplus_kwh=1.5,
        buyer_id="H002",  buyer_deficit_kwh=1.5,
        grid_import_price_aud=0.30, grid_export_credit_aud=0.08,
    )
    i_offer  = m.actions_p1.index("OFFER_P2P")
    i_export = m.actions_p1.index("EXPORT_GRID")
    j_accept = m.actions_p2.index("ACCEPT_P2P")
    j_grid   = m.actions_p2.index("GRID_IMPORT")

    # Trade outcome vs no-trade baseline
    trade_u1 = m.payoffs_p1[i_offer, j_accept]
    trade_u2 = m.payoffs_p2[i_offer, j_accept]
    base_u1  = m.payoffs_p1[i_export, j_grid]
    base_u2  = m.payoffs_p2[i_export, j_grid]

    assert trade_u1 >= base_u1 - 1e-9
    assert trade_u2 >= base_u2 - 1e-9


# ---------------------------------------------------------------------------
# Nash equilibrium detection
# ---------------------------------------------------------------------------

def test_nash_equilibrium_found_on_real_data_hour():
    """At 2013-06-08 10:00, H001 surplus and H002 deficit → P2P Nash equilibrium exists."""
    b1 = compute_energy_balance(0.137, 1.382, house_id="H001")  # surplus 1.245
    b2 = compute_energy_balance(1.838, 0.375, house_id="H002")  # deficit 1.463

    m = build_two_household_payoff_matrix(
        seller_id="H001", seller_surplus_kwh=b1.surplus_kwh,
        buyer_id="H002",  buyer_deficit_kwh=b2.deficit_kwh,
        grid_import_price_aud=0.30, grid_export_credit_aud=0.08,
    )
    result = find_pure_nash_equilibria(m)

    assert result.has_pure_nash, "Expected at least one pure-strategy Nash equilibrium"
    # The (OFFER_P2P, ACCEPT_P2P) profile must be one of the equilibria
    eq_actions = [(e.action_player1, e.action_player2) for e in result.equilibria]
    assert ("OFFER_P2P", "ACCEPT_P2P") in eq_actions


def test_nash_equilibrium_best_response_consistency():
    """Verify BR definitions: no player can unilaterally improve payoff from any equilibrium."""
    b1 = compute_energy_balance(0.2, 1.0, house_id="H001")  # surplus 0.8
    b2 = compute_energy_balance(1.5, 0.3, house_id="H002")  # deficit 1.2

    m = build_two_household_payoff_matrix(
        seller_id="H001", seller_surplus_kwh=b1.surplus_kwh,
        buyer_id="H002",  buyer_deficit_kwh=b2.deficit_kwh,
        grid_import_price_aud=0.30, grid_export_credit_aud=0.08,
    )
    result = find_pure_nash_equilibria(m)
    n1, n2 = len(m.actions_p1), len(m.actions_p2)

    for eq in result.equilibria:
        i = eq.action_index_player1
        j = eq.action_index_player2
        # Player 1 cannot improve by deviating
        for i2 in range(n1):
            assert m.payoffs_p1[i, j] >= m.payoffs_p1[i2, j] - 1e-9, (
                f"P1 can deviate from {m.actions_p1[i]} to {m.actions_p1[i2]} and improve"
            )
        # Player 2 cannot improve by deviating
        for j2 in range(n2):
            assert m.payoffs_p2[i, j] >= m.payoffs_p2[i, j2] - 1e-9, (
                f"P2 can deviate from {m.actions_p2[j]} to {m.actions_p2[j2]} and improve"
            )


def test_no_surplus_no_beneficial_trade():
    """When seller has zero surplus, traded quantity must be zero."""
    m = build_two_household_payoff_matrix(
        seller_id="H001", seller_surplus_kwh=0.0,
        buyer_id="H002",  buyer_deficit_kwh=1.5,
        grid_import_price_aud=0.30, grid_export_credit_aud=0.08,
    )
    assert m.traded_quantities.max() == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# End-to-end game run
# ---------------------------------------------------------------------------

def test_full_game_run_produces_valid_comparison():
    """run_two_household_game must return internally consistent comparison results."""
    b1 = compute_energy_balance(0.137, 1.382, house_id="H001")
    b2 = compute_energy_balance(1.838, 0.375, house_id="H002")

    _, eq_result, comp = run_two_household_game(
        b1, b2, grid_import_price_aud=0.30, grid_export_credit_aud=0.08
    )

    # Community savings must equal sum of individual savings
    assert comp.total_community_savings_aud == pytest.approx(
        comp.saving_p1_aud + comp.saving_p2_aud, abs=1e-6
    )
    # Game costs must be baseline minus savings
    assert comp.game_cost_p1_aud == pytest.approx(
        comp.baseline_cost_p1_aud - comp.saving_p1_aud, abs=1e-6
    )
    assert comp.game_cost_p2_aud == pytest.approx(
        comp.baseline_cost_p2_aud - comp.saving_p2_aud, abs=1e-6
    )
    # If a Nash equilibrium was found, the savings must be non-negative
    if comp.is_nash_equilibrium:
        assert comp.saving_p1_aud >= -1e-9
        assert comp.saving_p2_aud >= -1e-9


def test_detailed_best_responses():
    """Verify detailed best response mapping and strict dominance indicators."""
    from src.game.best_response import compute_detailed_best_responses

    m = build_two_household_payoff_matrix(
        seller_id="H001", seller_surplus_kwh=1.245,
        buyer_id="H002",  buyer_deficit_kwh=1.463,
        grid_import_price_aud=0.30, grid_export_credit_aud=0.08,
    )
    br_p1, br_p2 = compute_detailed_best_responses(m)

    assert "OFFER_P2P" in br_p1["ACCEPT_P2P"].best_actions
    assert br_p1["ACCEPT_P2P"].is_strictly_dominant_against_action is True
    assert "ACCEPT_P2P" in br_p2["OFFER_P2P"].best_actions
    assert br_p2["OFFER_P2P"].is_strictly_dominant_against_action is True
