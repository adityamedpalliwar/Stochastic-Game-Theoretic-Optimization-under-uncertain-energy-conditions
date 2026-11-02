"""Best-response analysis for N-player energy games."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
from itertools import product

from src.game.payoff_matrix import NPlayerPayoffMatrix, GamePayoffMatrix


@dataclass
class BestResponseDetail:
    player_id: str
    best_actions: List[str]
    best_utility: float
    all_action_utilities: Dict[str, float]
    opponents_profile: Dict[str, str] = field(default_factory=dict)
    opponent_id: str = ""
    opponent_action: str = ""
    is_strictly_dominant_against_profile: bool = False
    is_strictly_dominant_against_action: bool = False
    advantage_over_alternatives: Dict[str, float] = field(default_factory=dict)


def compute_best_responses_n_players(
    matrix: NPlayerPayoffMatrix,
    tolerance: float = 1e-6,
) -> Dict[str, Dict[tuple, BestResponseDetail]]:
    """Compute best responses for all N players.

    Returns
    -------
    Dict keyed by player_id. Value is Dict keyed by opponents' action tuple,
    mapping to BestResponseDetail.
    The opponents' action tuple is a tuple of (player_id, action) pairs
    for all OTHER players in sorted player order.
    """
    N = len(matrix.player_ids)
    result: Dict[str, Dict[tuple, BestResponseDetail]] = {}

    for player_idx, player_id in enumerate(matrix.player_ids):
        payoff_array = matrix.payoffs[player_idx]  # shape (n0, n1, ..., n_{N-1})
        player_actions = matrix.actions[player_idx]

        # Enumerate all opponent profiles
        other_indices = [k for k in range(N) if k != player_idx]
        other_ranges = [range(len(matrix.actions[k])) for k in other_indices]

        br_dict: Dict[tuple, BestResponseDetail] = {}

        for opp_combo in product(*other_ranges):
            # Build opponent profile name mapping
            opponents_profile_names = {
                matrix.player_ids[other_indices[ki]]: matrix.actions[other_indices[ki]][opp_combo[ki]]
                for ki in range(len(other_indices))
            }

            # Gather utilities for each of this player's actions given opponents' profile
            action_utilities = {}
            for ai, action_name in enumerate(player_actions):
                # Build full index tuple by inserting this player's action index at the right position
                idx = list(opp_combo)
                idx.insert(player_idx, ai)
                action_utilities[action_name] = float(payoff_array[tuple(idx)])

            max_u = max(action_utilities.values())
            best_acts = [a for a, u in action_utilities.items() if u >= max_u - tolerance]
            advantages = {a: float(max_u - u) for a, u in action_utilities.items() if a not in best_acts}
            is_strict = len(best_acts) == 1 and all(v > 0 for v in advantages.values())

            # Key: sorted tuple of (other_player_id, action)
            opp_key = tuple(sorted(opponents_profile_names.items()))

            br_dict[opp_key] = BestResponseDetail(
                player_id=player_id,
                opponents_profile=opponents_profile_names,
                best_actions=best_acts,
                best_utility=max_u,
                all_action_utilities=action_utilities,
                is_strictly_dominant_against_profile=is_strict,
                advantage_over_alternatives=advantages,
            )

        result[player_id] = br_dict

    return result


def get_dominant_strategy(
    matrix: NPlayerPayoffMatrix,
    player_id: str,
    tolerance: float = 1e-6,
) -> List[str]:
    """Return dominant strategies for a player (actions that are best response to ALL opponent profiles)."""
    br_map = compute_best_responses_n_players(matrix, tolerance)
    player_br = br_map[player_id]

    if not player_br:
        return []

    # Intersection of best actions across all opponent profiles
    all_profiles_best = [set(detail.best_actions) for detail in player_br.values()]
    dominant = all_profiles_best[0].intersection(*all_profiles_best[1:])
    return sorted(dominant)


# ---------------------------------------------------------------------------
# 2-Player Backward Compatibility
# ---------------------------------------------------------------------------

def compute_detailed_best_responses(
    matrix: GamePayoffMatrix,
    tolerance: float = 1e-6,
) -> Tuple[Dict[str, BestResponseDetail], Dict[str, BestResponseDetail]]:
    """Compute exhaustive best-response details for both players in a 2-player game."""
    m1 = matrix.payoffs_p1
    m2 = matrix.payoffs_p2
    n1, n2 = m1.shape

    details_p1: Dict[str, BestResponseDetail] = {}
    details_p2: Dict[str, BestResponseDetail] = {}

    for j, a2 in enumerate(matrix.actions_p2):
        col = m1[:, j]
        max_u = float(np.max(col))
        best_indices = [i for i in range(n1) if col[i] >= max_u - tolerance]
        best_names = [matrix.actions_p1[i] for i in best_indices]

        all_u = {matrix.actions_p1[i]: float(col[i]) for i in range(n1)}
        advantages = {
            matrix.actions_p1[i]: float(max_u - col[i])
            for i in range(n1)
            if i not in best_indices
        }
        is_strict = len(best_indices) == 1 and all(
            max_u > col[i] + tolerance for i in range(n1) if i not in best_indices
        )

        details_p1[a2] = BestResponseDetail(
            player_id=matrix.player1_id,
            opponent_id=matrix.player2_id,
            opponent_action=a2,
            best_actions=best_names,
            best_utility=max_u,
            all_action_utilities=all_u,
            is_strictly_dominant_against_action=is_strict,
            is_strictly_dominant_against_profile=is_strict,
            advantage_over_alternatives=advantages,
        )

    for i, a1 in enumerate(matrix.actions_p1):
        row = m2[i, :]
        max_u = float(np.max(row))
        best_indices = [j for j in range(n2) if row[j] >= max_u - tolerance]
        best_names = [matrix.actions_p2[j] for j in best_indices]

        all_u = {matrix.actions_p2[j]: float(row[j]) for j in range(n2)}
        advantages = {
            matrix.actions_p2[j]: float(max_u - row[j])
            for j in range(n2)
            if j not in best_indices
        }
        is_strict = len(best_indices) == 1 and all(
            max_u > row[j] + tolerance for j in range(n2) if j not in best_indices
        )

        details_p2[a1] = BestResponseDetail(
            player_id=matrix.player2_id,
            opponent_id=matrix.player1_id,
            opponent_action=a1,
            best_actions=best_names,
            best_utility=max_u,
            all_action_utilities=all_u,
            is_strictly_dominant_against_action=is_strict,
            is_strictly_dominant_against_profile=is_strict,
            advantage_over_alternatives=advantages,
        )

    return details_p1, details_p2
