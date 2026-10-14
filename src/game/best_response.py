"""Best-response analysis and dominant strategy identification for energy games.

For a 2-player normal-form game:
BR_1(a_2) = {a_1 in A_1 : U_1(a_1, a_2) >= U_1(a_1', a_2) for all a_1' in A_1}
BR_2(a_1) = {a_2 in A_2 : U_2(a_1, a_2) >= U_2(a_1, a_2') for all a_2' in A_2}

An action profile (a_1*, a_2*) is a Nash Equilibrium if and only if
a_1* in BR_1(a_2*) and a_2* in BR_2(a_1*).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from src.game.payoff_matrix import GamePayoffMatrix


@dataclass
class BestResponseDetail:
    """Detailed step-by-step evaluation of best response for a given opponent action."""

    player_id: str
    opponent_id: str
    opponent_action: str
    best_actions: List[str]
    best_utility: float
    all_action_utilities: Dict[str, float]
    is_strictly_dominant_against_action: bool
    advantage_over_alternatives: Dict[str, float]


def compute_detailed_best_responses(
    matrix: GamePayoffMatrix,
    tolerance: float = 1e-6,
) -> Tuple[Dict[str, BestResponseDetail], Dict[str, BestResponseDetail]]:
    """Compute exhaustive best-response details for both players.

    Returns
    -------
    br_details_p1 : Dict[str, BestResponseDetail]
        Keyed by Player 2's action name.
    br_details_p2 : Dict[str, BestResponseDetail]
        Keyed by Player 1's action name.
    """
    m1 = matrix.payoffs_p1  # (n1, n2)
    m2 = matrix.payoffs_p2  # (n1, n2)
    n1, n2 = m1.shape

    details_p1: Dict[str, BestResponseDetail] = {}
    details_p2: Dict[str, BestResponseDetail] = {}

    # Player 1's best responses to each action of Player 2
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
            advantage_over_alternatives=advantages,
        )

    # Player 2's best responses to each action of Player 1
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
            advantage_over_alternatives=advantages,
        )

    return details_p1, details_p2
