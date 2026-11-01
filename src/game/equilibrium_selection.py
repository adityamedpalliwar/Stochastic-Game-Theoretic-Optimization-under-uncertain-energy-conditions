"""Fairness-aware Nash equilibrium selection strategies for residential microgrids.

Implements six distinct equilibrium selection policies operating strictly on
the Pareto-undominated Pure Nash Equilibrium (PNE) frontier:

- Strategy A: Reference selection (reproducing Phase 8C 5-step heuristic)
- Strategy B: Seller-favouring selection (maximizing aggregate seller surplus)
- Strategy C: Buyer-favouring selection (maximizing aggregate buyer surplus)
- Strategy D: Max-Min fair selection (Rawlsian egalitarianism on active participants)
- Strategy E: Nash Social Welfare selection (proportional fairness via log-product)
- Strategy F: Reference-price and fairness hybrid selection (configurable loss function)

All strategies utilize rigorous deterministic tie-breaking.
"""

from __future__ import annotations

from enum import Enum
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from src.game.fairness_metrics import (
    DEFAULT_NSW_EPSILON,
    DEFAULT_NUMERICAL_TOLERANCE,
    compute_normalized_gini,
)
from src.game.strategic_solver import NashEquilibriumRecord, select_representative_equilibrium


class SelectionStrategy(str, Enum):
    """Supported equilibrium selection strategies."""

    STRATEGY_A_REFERENCE = "Strategy_A_Reference"
    STRATEGY_B_SELLER = "Strategy_B_Seller_Favouring"
    STRATEGY_C_BUYER = "Strategy_C_Buyer_Favouring"
    STRATEGY_D_MAXMIN = "Strategy_D_MaxMin_Fair"
    STRATEGY_E_NSW = "Strategy_E_Nash_Social_Welfare"
    STRATEGY_F_HYBRID = "Strategy_F_Hybrid"


def _extract_eq_data(eq: Union[NashEquilibriumRecord, Dict[str, Any]]) -> Dict[str, Any]:
    """Uniformly access fields from NashEquilibriumRecord or dict."""
    if isinstance(eq, NashEquilibriumRecord):
        return {
            "profile": eq.profile,
            "payoffs": eq.payoffs,
            "total_traded_kwh": eq.total_traded_kwh,
            "weighted_average_price_aud": eq.weighted_average_price_aud,
            "community_welfare_aud": eq.community_welfare_aud,
            "transaction_price_std": eq.transaction_price_std,
            "raw_obj": eq,
        }
    return {
        "profile": eq.get("profile", {}),
        "payoffs": eq.get("payoffs", {}),
        "total_traded_kwh": float(eq.get("total_traded_kwh", 0.0)),
        "weighted_average_price_aud": eq.get("weighted_average_price_aud"),
        "community_welfare_aud": float(eq.get("community_welfare_aud", 0.0)),
        "transaction_price_std": float(eq.get("transaction_price_std", 0.0)),
        "raw_obj": eq,
    }


def _lexicographical_sort_key(eq_data: Dict[str, Any], sorted_active_players: Sequence[str]) -> Tuple[float, ...]:
    """Deterministic tie-breaker based on active player submitted price indices."""
    profile = eq_data["profile"]
    return tuple(float(profile.get(p, 0.0)) for p in sorted_active_players)


# =============================================================================
# STRATEGY IMPLEMENTATIONS
# =============================================================================

def select_strategy_a_reference(
    pareto_equilibria: Sequence[Union[NashEquilibriumRecord, Dict[str, Any]]],
    active_players: Sequence[str],
    reference_price_aud: float = 0.19,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
) -> Optional[Union[NashEquilibriumRecord, Dict[str, Any]]]:
    """Select representative equilibrium using existing Phase 8C 5-step heuristic."""
    if not pareto_equilibria:
        return None

    # If already NashEquilibriumRecord objects, call existing solver function directly
    if isinstance(pareto_equilibria[0], NashEquilibriumRecord):
        return select_representative_equilibrium(
            undominated_equilibria=pareto_equilibria,  # type: ignore[arg-type]
            active_players=active_players,
            reference_price_aud=reference_price_aud,
            tolerance=tolerance,
        )

    # For dict entries (e.g. from JSON archive), execute the exact same 5-step logic
    if len(pareto_equilibria) == 1:
        return pareto_equilibria[0]

    extracted = [_extract_eq_data(eq) for eq in pareto_equilibria]

    # Step 2: Distance to reference price
    dists = []
    for d in extracted:
        p = d["weighted_average_price_aud"]
        if d["total_traded_kwh"] > tolerance and p is not None:
            dists.append(abs(float(p) - reference_price_aud))
        else:
            dists.append(float("inf"))

    min_d = min(dists)
    if math.isinf(min_d):
        cands_step2 = list(extracted)
    else:
        cands_step2 = [
            d for d, dist in zip(extracted, dists)
            if abs(dist - min_d) <= tolerance
        ]

    if len(cands_step2) == 1:
        return cands_step2[0]["raw_obj"]

    # Step 3: Maximize welfare
    max_w = max(d["community_welfare_aud"] for d in cands_step2)
    cands_step3 = [d for d in cands_step2 if abs(d["community_welfare_aud"] - max_w) <= tolerance]

    if len(cands_step3) == 1:
        return cands_step3[0]["raw_obj"]

    # Step 4: Minimize transaction price std
    min_std = min(d["transaction_price_std"] for d in cands_step3)
    cands_step4 = [d for d in cands_step3 if abs(d["transaction_price_std"] - min_std) <= tolerance]

    if len(cands_step4) == 1:
        return cands_step4[0]["raw_obj"]

    # Step 5: Deterministic lexicographical tie-break
    sorted_players = sorted(active_players)
    best = min(cands_step4, key=lambda d: _lexicographical_sort_key(d, sorted_players))
    return best["raw_obj"]


def select_strategy_b_seller_favouring(
    pareto_equilibria: Sequence[Union[NashEquilibriumRecord, Dict[str, Any]]],
    active_players: Sequence[str],
    active_sellers: Sequence[str],
    reference_price_aud: float = 0.19,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
) -> Optional[Union[NashEquilibriumRecord, Dict[str, Any]]]:
    """Select equilibrium that maximizes aggregate active seller surplus."""
    if not pareto_equilibria:
        return None
    if len(pareto_equilibria) == 1:
        return pareto_equilibria[0]

    extracted = [_extract_eq_data(eq) for eq in pareto_equilibria]

    # 1. Primary: Maximize seller surplus
    seller_surplus = [
        sum(float(d["payoffs"].get(s, 0.0)) for s in active_sellers)
        for d in extracted
    ]
    max_surplus = max(seller_surplus)
    cands1 = [d for d, s in zip(extracted, seller_surplus) if abs(s - max_surplus) <= tolerance]

    if len(cands1) == 1:
        return cands1[0]["raw_obj"]

    # 2. Tie-break 1: Minimize variance among seller payoffs
    def seller_var(d: Dict[str, Any]) -> float:
        vals = [float(d["payoffs"].get(s, 0.0)) for s in active_sellers]
        return float(np.var(vals)) if len(vals) > 1 else 0.0

    min_var = min(seller_var(d) for d in cands1)
    cands2 = [d for d in cands1 if abs(seller_var(d) - min_var) <= tolerance]

    if len(cands2) == 1:
        return cands2[0]["raw_obj"]

    # 3. Tie-break 2: Proximity to reference price
    dists = [
        abs(float(d["weighted_average_price_aud"]) - reference_price_aud)
        if d["weighted_average_price_aud"] is not None and d["total_traded_kwh"] > tolerance
        else float("inf")
        for d in cands2
    ]
    min_dist = min(dists)
    if not math.isinf(min_dist):
        cands3 = [d for d, dist in zip(cands2, dists) if abs(dist - min_dist) <= tolerance]
    else:
        cands3 = list(cands2)

    if len(cands3) == 1:
        return cands3[0]["raw_obj"]

    # 4. Final tie-break: Deterministic lexicographical on active player prices
    sorted_players = sorted(active_players)
    best = min(cands3, key=lambda d: _lexicographical_sort_key(d, sorted_players))
    return best["raw_obj"]


def select_strategy_c_buyer_favouring(
    pareto_equilibria: Sequence[Union[NashEquilibriumRecord, Dict[str, Any]]],
    active_players: Sequence[str],
    active_buyers: Sequence[str],
    reference_price_aud: float = 0.19,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
) -> Optional[Union[NashEquilibriumRecord, Dict[str, Any]]]:
    """Select equilibrium that maximizes aggregate active buyer surplus."""
    if not pareto_equilibria:
        return None
    if len(pareto_equilibria) == 1:
        return pareto_equilibria[0]

    extracted = [_extract_eq_data(eq) for eq in pareto_equilibria]

    # 1. Primary: Maximize buyer surplus
    buyer_surplus = [
        sum(float(d["payoffs"].get(b, 0.0)) for b in active_buyers)
        for d in extracted
    ]
    max_surplus = max(buyer_surplus)
    cands1 = [d for d, b in zip(extracted, buyer_surplus) if abs(b - max_surplus) <= tolerance]

    if len(cands1) == 1:
        return cands1[0]["raw_obj"]

    # 2. Tie-break 1: Minimize variance among buyer payoffs
    def buyer_var(d: Dict[str, Any]) -> float:
        vals = [float(d["payoffs"].get(b, 0.0)) for b in active_buyers]
        return float(np.var(vals)) if len(vals) > 1 else 0.0

    min_var = min(buyer_var(d) for d in cands1)
    cands2 = [d for d in cands1 if abs(buyer_var(d) - min_var) <= tolerance]

    if len(cands2) == 1:
        return cands2[0]["raw_obj"]

    # 3. Tie-break 2: Proximity to reference price
    dists = [
        abs(float(d["weighted_average_price_aud"]) - reference_price_aud)
        if d["weighted_average_price_aud"] is not None and d["total_traded_kwh"] > tolerance
        else float("inf")
        for d in cands2
    ]
    min_dist = min(dists)
    if not math.isinf(min_dist):
        cands3 = [d for d, dist in zip(cands2, dists) if abs(dist - min_dist) <= tolerance]
    else:
        cands3 = list(cands2)

    if len(cands3) == 1:
        return cands3[0]["raw_obj"]

    # 4. Final tie-break: Deterministic lexicographical on active player prices
    sorted_players = sorted(active_players)
    best = min(cands3, key=lambda d: _lexicographical_sort_key(d, sorted_players))
    return best["raw_obj"]


def select_strategy_d_maxmin_fair(
    pareto_equilibria: Sequence[Union[NashEquilibriumRecord, Dict[str, Any]]],
    active_players: Sequence[str],
    reference_price_aud: float = 0.19,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
) -> Optional[Union[NashEquilibriumRecord, Dict[str, Any]]]:
    """Select equilibrium that maximizes the minimum benefit among active participants."""
    if not pareto_equilibria:
        return None
    if len(pareto_equilibria) == 1:
        return pareto_equilibria[0]

    extracted = [_extract_eq_data(eq) for eq in pareto_equilibria]

    # 1. Primary: Maximize min_{i in active} U_i
    min_payoffs = [
        min(float(d["payoffs"].get(p, 0.0)) for p in active_players)
        for d in extracted
    ]
    max_min_val = max(min_payoffs)
    cands1 = [d for d, m in zip(extracted, min_payoffs) if abs(m - max_min_val) <= tolerance]

    if len(cands1) == 1:
        return cands1[0]["raw_obj"]

    # 2. Tie-break 1: Lexicographic Max-Min (maximize 2nd lowest payoff if >= 2 active)
    if len(active_players) >= 2:
        def second_lowest(d: Dict[str, Any]) -> float:
            vals = sorted(float(d["payoffs"].get(p, 0.0)) for p in active_players)
            return vals[1]

        max_sec = max(second_lowest(d) for d in cands1)
        cands2 = [d for d in cands1 if abs(second_lowest(d) - max_sec) <= tolerance]
    else:
        cands2 = list(cands1)

    if len(cands2) == 1:
        return cands2[0]["raw_obj"]

    # 3. Tie-break 2: Proximity to reference price
    dists = [
        abs(float(d["weighted_average_price_aud"]) - reference_price_aud)
        if d["weighted_average_price_aud"] is not None and d["total_traded_kwh"] > tolerance
        else float("inf")
        for d in cands2
    ]
    min_dist = min(dists)
    if not math.isinf(min_dist):
        cands3 = [d for d, dist in zip(cands2, dists) if abs(dist - min_dist) <= tolerance]
    else:
        cands3 = list(cands2)

    if len(cands3) == 1:
        return cands3[0]["raw_obj"]

    # 4. Final tie-break: Deterministic lexicographical on active player prices
    sorted_players = sorted(active_players)
    best = min(cands3, key=lambda d: _lexicographical_sort_key(d, sorted_players))
    return best["raw_obj"]


def select_strategy_e_nash_social_welfare(
    pareto_equilibria: Sequence[Union[NashEquilibriumRecord, Dict[str, Any]]],
    active_players: Sequence[str],
    reference_price_aud: float = 0.19,
    epsilon: float = DEFAULT_NSW_EPSILON,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
) -> Optional[Union[NashEquilibriumRecord, Dict[str, Any]]]:
    """Select equilibrium that maximizes Nash Social Welfare (proportional fairness)."""
    if not pareto_equilibria:
        return None
    if len(pareto_equilibria) == 1:
        return pareto_equilibria[0]

    extracted = [_extract_eq_data(eq) for eq in pareto_equilibria]

    # 1. Primary: Maximize sum_{i in active} log(U_i + epsilon)
    def log_nsw(d: Dict[str, Any]) -> float:
        return sum(
            math.log(max(0.0, float(d["payoffs"].get(p, 0.0))) + epsilon)
            for p in active_players
        )

    nsw_vals = [log_nsw(d) for d in extracted]
    max_nsw = max(nsw_vals)
    cands1 = [d for d, nsw in zip(extracted, nsw_vals) if abs(nsw - max_nsw) <= tolerance]

    if len(cands1) == 1:
        return cands1[0]["raw_obj"]

    # 2. Tie-break 1: Proximity to reference price
    dists = [
        abs(float(d["weighted_average_price_aud"]) - reference_price_aud)
        if d["weighted_average_price_aud"] is not None and d["total_traded_kwh"] > tolerance
        else float("inf")
        for d in cands1
    ]
    min_dist = min(dists)
    if not math.isinf(min_dist):
        cands2 = [d for d, dist in zip(cands1, dists) if abs(dist - min_dist) <= tolerance]
    else:
        cands2 = list(cands1)

    if len(cands2) == 1:
        return cands2[0]["raw_obj"]

    # 3. Final tie-break: Deterministic lexicographical on active player prices
    sorted_players = sorted(active_players)
    best = min(cands2, key=lambda d: _lexicographical_sort_key(d, sorted_players))
    return best["raw_obj"]


def select_strategy_f_hybrid(
    pareto_equilibria: Sequence[Union[NashEquilibriumRecord, Dict[str, Any]]],
    active_players: Sequence[str],
    weight_reference: float = 0.5,
    weight_fairness: float = 0.5,
    reference_price_aud: float = 0.19,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
) -> Optional[Union[NashEquilibriumRecord, Dict[str, Any]]]:
    """Select equilibrium minimizing weighted compromise loss between reference tracking and Gini inequality.

    Loss function:
        L(e) = w_ref * (|p_vwap - 0.19| / 0.11) + w_fair * G_norm(U_active)
    """
    if not pareto_equilibria:
        return None
    if len(pareto_equilibria) == 1:
        return pareto_equilibria[0]

    extracted = [_extract_eq_data(eq) for eq in pareto_equilibria]

    def loss(d: Dict[str, Any]) -> float:
        p = d["weighted_average_price_aud"]
        if p is not None and d["total_traded_kwh"] > tolerance:
            loss_ref = abs(float(p) - reference_price_aud) / 0.11
        else:
            loss_ref = 0.0

        g_norm = compute_normalized_gini(d["payoffs"], active_players, tolerance=tolerance)
        loss_fair = float(g_norm) if g_norm is not None else 0.0

        return weight_reference * loss_ref + weight_fairness * loss_fair

    losses = [loss(d) for d in extracted]
    min_loss = min(losses)
    cands1 = [d for d, l in zip(extracted, losses) if abs(l - min_loss) <= tolerance]

    if len(cands1) == 1:
        return cands1[0]["raw_obj"]

    # 2. Tie-break 1: Minimize transaction price std
    min_std = min(d["transaction_price_std"] for d in cands1)
    cands2 = [d for d in cands1 if abs(d["transaction_price_std"] - min_std) <= tolerance]

    if len(cands2) == 1:
        return cands2[0]["raw_obj"]

    # 3. Final tie-break: Deterministic lexicographical on active player prices
    sorted_players = sorted(active_players)
    best = min(cands2, key=lambda d: _lexicographical_sort_key(d, sorted_players))
    return best["raw_obj"]


# =============================================================================
# GENERAL SELECTION DISPATCHER
# =============================================================================

def select_equilibrium(
    pareto_equilibria: Sequence[Union[NashEquilibriumRecord, Dict[str, Any]]],
    strategy: SelectionStrategy,
    active_players: Sequence[str],
    active_sellers: Sequence[str] = (),
    active_buyers: Sequence[str] = (),
    reference_price_aud: float = 0.19,
    weight_reference: float = 0.5,
    weight_fairness: float = 0.5,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
    epsilon: float = DEFAULT_NSW_EPSILON,
) -> Optional[Union[NashEquilibriumRecord, Dict[str, Any]]]:
    """Unified entry point to select an equilibrium from Pareto-undominated PNE set.

    Parameters
    ----------
    pareto_equilibria : Sequence[Union[NashEquilibriumRecord, Dict[str, Any]]]
        Candidate Pareto-undominated equilibria.
    strategy : SelectionStrategy
        Selection policy to evaluate.
    active_players : Sequence[str]
        Households with positive net surplus or deficit.
    active_sellers : Sequence[str]
        Active sellers.
    active_buyers : Sequence[str]
        Active buyers.
    reference_price_aud : float
        Mid-market reference benchmark (default $0.19/kWh).
    weight_reference : float
        Reference tracking weight for Strategy F.
    weight_fairness : float
        Fairness weight for Strategy F.
    tolerance : float
        Numerical zero threshold.
    epsilon : float
        Regularization for Nash Social Welfare.

    Returns
    -------
    Optional[Union[NashEquilibriumRecord, Dict[str, Any]]]
        Selected equilibrium object, or None if input candidate set is empty.
    """
    if not pareto_equilibria:
        return None

    if strategy == SelectionStrategy.STRATEGY_A_REFERENCE:
        return select_strategy_a_reference(
            pareto_equilibria, active_players, reference_price_aud, tolerance
        )
    elif strategy == SelectionStrategy.STRATEGY_B_SELLER:
        return select_strategy_b_seller_favouring(
            pareto_equilibria, active_players, active_sellers, reference_price_aud, tolerance
        )
    elif strategy == SelectionStrategy.STRATEGY_C_BUYER:
        return select_strategy_c_buyer_favouring(
            pareto_equilibria, active_players, active_buyers, reference_price_aud, tolerance
        )
    elif strategy == SelectionStrategy.STRATEGY_D_MAXMIN:
        return select_strategy_d_maxmin_fair(
            pareto_equilibria, active_players, reference_price_aud, tolerance
        )
    elif strategy == SelectionStrategy.STRATEGY_E_NSW:
        return select_strategy_e_nash_social_welfare(
            pareto_equilibria, active_players, reference_price_aud, epsilon, tolerance
        )
    elif strategy == SelectionStrategy.STRATEGY_F_HYBRID:
        return select_strategy_f_hybrid(
            pareto_equilibria, active_players, weight_reference, weight_fairness, reference_price_aud, tolerance
        )
    else:
        raise ValueError(f"Unsupported selection strategy: {strategy}")

