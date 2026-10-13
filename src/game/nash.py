"""Pure-strategy Nash equilibrium solver and best-response analysis.

A strategy profile (a_1*, a_2*) is a pure-strategy Nash equilibrium if:
U_1(a_1*, a_2*) >= U_1(a_1, a_2*) for all a_1 in A_1
and
U_2(a_1*, a_2*) >= U_2(a_1*, a_2) for all a_2 in A_2.

Strict vs Weak Nash equilibria are explicitly identified.
Does NOT fabricate an equilibrium if none exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

from src.game.payoff_matrix import GamePayoffMatrix


@dataclass
class NashEquilibrium:
    """A verified pure-strategy Nash equilibrium."""

    action_player1: str
    action_player2: str
    action_index_player1: int
    action_index_player2: int
    utility_player1: float
    utility_player2: float
    is_strict: bool
    traded_energy_kwh: float

    def to_dict(self) -> Dict[str, Union[str, int, float, bool]]:
        return {
            "action_player1": self.action_player1,
            "action_player2": self.action_player2,
            "utility_player1": round(self.utility_player1, 4),
            "utility_player2": round(self.utility_player2, 4),
            "is_strict": self.is_strict,
            "traded_energy_kwh": round(self.traded_energy_kwh, 4),
        }


@dataclass
class EquilibriumAnalysisResult:
    """Complete equilibrium report for a 2-player normal-form game."""

    player1_id: str
    player2_id: str
    has_pure_nash: bool
    num_equilibria: int
    equilibria: List[NashEquilibrium]
    best_responses_p1: Dict[str, List[str]]  # a2 -> list of best a1
    best_responses_p2: Dict[str, List[str]]  # a1 -> list of best a2
    baseline_profile: Tuple[str, str]
    baseline_utilities: Tuple[float, float]
    selected_equilibrium: Optional[NashEquilibrium] = None

    @property
    def welfare_gain_aud(self) -> Optional[float]:
        """Community welfare gain of selected equilibrium over baseline."""
        if self.selected_equilibrium is None:
            return None
        eq_total = self.selected_equilibrium.utility_player1 + self.selected_equilibrium.utility_player2
        base_total = self.baseline_utilities[0] + self.baseline_utilities[1]
        return eq_total - base_total


def find_pure_nash_equilibria(matrix: GamePayoffMatrix, tolerance: float = 1e-6) -> EquilibriumAnalysisResult:
    """Find all pure-strategy Nash equilibria in a 2-player game.

    Parameters
    ----------
    matrix : GamePayoffMatrix
        The normal-form game matrix.
    tolerance : float
        Numerical tolerance for comparing floating-point payoffs.

    Returns
    -------
    EquilibriumAnalysisResult
        Comprehensive equilibrium report.
    """
    m1 = matrix.payoffs_p1  # shape (n1, n2)
    m2 = matrix.payoffs_p2  # shape (n1, n2)
    n1, n2 = m1.shape

    # 1. Best responses of Player 1 to each action j of Player 2
    # BR_1(j) = {i : m1[i, j] >= max_k m1[k, j] - tol}
    br_p1_indices: Dict[int, List[int]] = {}
    br_p1_names: Dict[str, List[str]] = {}
    for j in range(n2):
        col = m1[:, j]
        max_val = np.max(col)
        best_i = [i for i in range(n1) if col[i] >= max_val - tolerance]
        br_p1_indices[j] = best_i
        br_p1_names[matrix.actions_p2[j]] = [matrix.actions_p1[i] for i in best_i]

    # 2. Best responses of Player 2 to each action i of Player 1
    # BR_2(i) = {j : m2[i, j] >= max_k m2[i, k] - tol}
    br_p2_indices: Dict[int, List[int]] = {}
    br_p2_names: Dict[str, List[str]] = {}
    for i in range(n1):
        row = m2[i, :]
        max_val = np.max(row)
        best_j = [j for j in range(n2) if row[j] >= max_val - tolerance]
        br_p2_indices[i] = best_j
        br_p2_names[matrix.actions_p1[i]] = [matrix.actions_p2[j] for j in best_j]

    # 3. Find intersection (pure Nash equilibria)
    equilibria: List[NashEquilibrium] = []
    for i in range(n1):
        for j in range(n2):
            if i in br_p1_indices[j] and j in br_p2_indices[i]:
                # Check strictness
                u1 = m1[i, j]
                u2 = m2[i, j]
                strict_p1 = all(u1 > m1[k, j] + tolerance for k in range(n1) if k != i)
                strict_p2 = all(u2 > m2[i, k] + tolerance for k in range(n2) if k != j)
                is_strict = strict_p1 and strict_p2

                equilibria.append(
                    NashEquilibrium(
                        action_player1=matrix.actions_p1[i],
                        action_player2=matrix.actions_p2[j],
                        action_index_player1=i,
                        action_index_player2=j,
                        utility_player1=float(u1),
                        utility_player2=float(u2),
                        is_strict=is_strict,
                        traded_energy_kwh=float(matrix.traded_quantities[i, j]),
                    )
                )

    # Identify baseline (EXPORT_GRID, GRID_IMPORT)
    base_i = matrix.actions_p1.index("EXPORT_GRID") if "EXPORT_GRID" in matrix.actions_p1 else -1
    base_j = matrix.actions_p2.index("GRID_IMPORT") if "GRID_IMPORT" in matrix.actions_p2 else -1
    if base_i >= 0 and base_j >= 0:
        base_u1 = float(m1[base_i, base_j])
        base_u2 = float(m2[base_i, base_j])
        baseline_profile = ("EXPORT_GRID", "GRID_IMPORT")
    else:
        base_u1 = float(m1[0, 0])
        base_u2 = float(m2[0, 0])
        baseline_profile = (matrix.actions_p1[0], matrix.actions_p2[0])

    # Select preferred equilibrium (Pareto-dominant or unique)
    selected_eq = None
    if len(equilibria) == 1:
        selected_eq = equilibria[0]
    elif len(equilibria) > 1:
        # Select one with maximum total community welfare
        selected_eq = max(equilibria, key=lambda eq: eq.utility_player1 + eq.utility_player2)

    return EquilibriumAnalysisResult(
        player1_id=matrix.player1_id,
        player2_id=matrix.player2_id,
        has_pure_nash=len(equilibria) > 0,
        num_equilibria=len(equilibria),
        equilibria=equilibria,
        best_responses_p1=br_p1_names,
        best_responses_p2=br_p2_names,
        baseline_profile=baseline_profile,
        baseline_utilities=(base_u1, base_u2),
        selected_equilibrium=selected_eq,
    )
