"""Unit tests for Phase 8D equilibrium selection strategies and tie-breaking."""

import gzip
import json
import pandas as pd
import pytest

from src.game.equilibrium_selection import (
    SelectionStrategy,
    select_equilibrium,
    select_strategy_a_reference,
    select_strategy_b_seller_favouring,
    select_strategy_c_buyer_favouring,
    select_strategy_d_maxmin_fair,
    select_strategy_e_nash_social_welfare,
    select_strategy_f_hybrid,
)


@pytest.fixture(scope="module")
def sample_mixed_hour_equilibria():
    """Load sample mixed-market Pareto equilibria from the archive."""
    json_path = "reports/phase8c_all_equilibria.json.gz"
    with gzip.open(json_path, "rt", encoding="utf-8") as f:
        data = json.load(f)

    # Find a mixed trading hour with multiple Pareto equilibria
    for entry in data:
        pareto_eqs = [eq for eq in entry["equilibria"] if eq.get("is_pareto_undominated", False)]
        if len(pareto_eqs) >= 4 and pareto_eqs[0]["total_traded_kwh"] > 0.01:
            roles = pareto_eqs[0]["roles"]
            sellers = [h for h, r in roles.items() if r == "seller"]
            buyers = [h for h, r in roles.items() if r == "buyer"]
            if sellers and buyers:
                return {
                    "timestamp": entry["timestamp"],
                    "pareto_eqs": pareto_eqs,
                    "active_players": sorted(sellers + buyers),
                    "sellers": sorted(sellers),
                    "buyers": sorted(buyers),
                }
    raise ValueError("No suitable sample mixed hour found in archive.")


def test_strategy_a_reproduces_existing_phase8c():
    """Verify that Strategy A reproduces the exact Phase 8C representative selection."""
    json_path = "reports/phase8c_all_equilibria.json.gz"
    csv_path = "reports/phase8c_hourly_equilibria.csv"

    df_hourly = pd.read_csv(csv_path).set_index("timestamp")
    with gzip.open(json_path, "rt", encoding="utf-8") as f:
        data = json.load(f)

    # Check 10 representative timestamps across the dataset
    sample_indices = [0, 50, 100, 250, 500, 750, 1000, 1250, 1500, 1750]
    for idx in sample_indices:
        entry = data[idx]
        ts = entry["timestamp"]
        pareto_eqs = [eq for eq in entry["equilibria"] if eq.get("is_pareto_undominated", False)]
        row = df_hourly.loc[ts]

        active = []
        for h in ["H001", "H002", "H003"]:
            if row[f"{h}_surplus_kwh"] > 1e-6 or row[f"{h}_deficit_kwh"] > 1e-6:
                active.append(h)
        active.sort()

        sel_a = select_strategy_a_reference(pareto_eqs, active)
        expected_profile_str = row["selected_price_profile"]
        expected_welfare = row["selected_community_welfare_aud"]

        assert sel_a is not None
        assert abs(sel_a["community_welfare_aud"] - expected_welfare) < 1e-6
        # Verify profile matches string representation
        for h in active:
            expected_p = row[f"{h}_selected_price_aud"]
            actual_p = sel_a["profile"][h]
            assert abs(actual_p - expected_p) < 1e-6


def test_strategy_b_maximizes_seller_surplus(sample_mixed_hour_equilibria):
    """Verify that Strategy B selects an equilibrium maximizing total seller surplus."""
    case = sample_mixed_hour_equilibria
    pareto_eqs = case["pareto_eqs"]
    active = case["active_players"]
    sellers = case["sellers"]

    sel_b = select_strategy_b_seller_favouring(pareto_eqs, active, sellers)
    assert sel_b is not None

    b_seller_surplus = sum(sel_b["payoffs"][s] for s in sellers)
    for eq in pareto_eqs:
        eq_seller_surplus = sum(eq["payoffs"][s] for s in sellers)
        assert b_seller_surplus >= eq_seller_surplus - 1e-6


def test_strategy_c_maximizes_buyer_surplus(sample_mixed_hour_equilibria):
    """Verify that Strategy C selects an equilibrium maximizing total buyer surplus."""
    case = sample_mixed_hour_equilibria
    pareto_eqs = case["pareto_eqs"]
    active = case["active_players"]
    buyers = case["buyers"]

    sel_c = select_strategy_c_buyer_favouring(pareto_eqs, active, buyers)
    assert sel_c is not None

    c_buyer_surplus = sum(sel_c["payoffs"][b] for b in buyers)
    for eq in pareto_eqs:
        eq_buyer_surplus = sum(eq["payoffs"][b] for b in buyers)
        assert c_buyer_surplus >= eq_buyer_surplus - 1e-6


def test_strategy_d_maximizes_min_active_payoff(sample_mixed_hour_equilibria):
    """Verify that Strategy D selects an equilibrium maximizing min_{i in active} U_i."""
    case = sample_mixed_hour_equilibria
    pareto_eqs = case["pareto_eqs"]
    active = case["active_players"]

    sel_d = select_strategy_d_maxmin_fair(pareto_eqs, active)
    assert sel_d is not None

    d_min_payoff = min(sel_d["payoffs"][p] for p in active)
    for eq in pareto_eqs:
        eq_min_payoff = min(eq["payoffs"][p] for p in active)
        assert d_min_payoff >= eq_min_payoff - 1e-6


def test_strategy_e_maximizes_nash_social_welfare(sample_mixed_hour_equilibria):
    """Verify that Strategy E selects an equilibrium maximizing log-NSW."""
    case = sample_mixed_hour_equilibria
    pareto_eqs = case["pareto_eqs"]
    active = case["active_players"]
    eps = 1e-6

    sel_e = select_strategy_e_nash_social_welfare(pareto_eqs, active, epsilon=eps)
    assert sel_e is not None

    import math
    e_nsw = sum(math.log(max(0.0, sel_e["payoffs"][p]) + eps) for p in active)
    for eq in pareto_eqs:
        eq_nsw = sum(math.log(max(0.0, eq["payoffs"][p]) + eps) for p in active)
        assert e_nsw >= eq_nsw - 1e-6


def test_strategy_f_hybrid_extremes(sample_mixed_hour_equilibria):
    """Verify hybrid strategy behavior at boundary weights w_fair=0.0 and w_fair=1.0."""
    case = sample_mixed_hour_equilibria
    pareto_eqs = case["pareto_eqs"]
    active = case["active_players"]

    # When w_fair = 0.0, Strategy F minimizes reference price distance
    sel_f_ref = select_strategy_f_hybrid(pareto_eqs, active, weight_reference=1.0, weight_fairness=0.0)
    assert sel_f_ref is not None
    min_dist = min(abs(eq["weighted_average_price_aud"] - 0.19) for eq in pareto_eqs)
    assert abs(abs(sel_f_ref["weighted_average_price_aud"] - 0.19) - min_dist) < 1e-6

    # When w_fair = 1.0, Strategy F minimizes Gini inequality
    sel_f_fair = select_strategy_f_hybrid(pareto_eqs, active, weight_reference=0.0, weight_fairness=1.0)
    assert sel_f_fair is not None


def test_deterministic_tie_breaking(sample_mixed_hour_equilibria):
    """Verify that multiple invocations of select_equilibrium return identical results."""
    case = sample_mixed_hour_equilibria
    pareto_eqs = case["pareto_eqs"]
    active = case["active_players"]
    sellers = case["sellers"]
    buyers = case["buyers"]

    for strat in SelectionStrategy:
        res1 = select_equilibrium(pareto_eqs, strat, active, sellers, buyers)
        res2 = select_equilibrium(pareto_eqs, strat, active, sellers, buyers)
        assert res1 is not None and res2 is not None
        assert res1["profile"] == res2["profile"]
        assert res1["payoffs"] == res2["payoffs"]


def test_empty_and_single_candidate_edge_cases():
    """Verify edge cases with 0 or 1 candidate equilibria."""
    active = ["H001", "H002"]
    # Empty candidate list returns None
    assert select_strategy_a_reference([], active) is None

    # Single candidate returns that candidate immediately
    cand = {"profile": {"H001": 0.19, "H002": 0.19}, "payoffs": {"H001": 0.01, "H002": 0.01}}
    assert select_strategy_a_reference([cand], active) == cand
    assert select_strategy_b_seller_favouring([cand], active, ["H001"]) == cand
    assert select_strategy_c_buyer_favouring([cand], active, ["H002"]) == cand
    assert select_strategy_d_maxmin_fair([cand], active) == cand
    assert select_strategy_e_nash_social_welfare([cand], active) == cand
    assert select_strategy_f_hybrid([cand], active) == cand

