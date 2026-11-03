"""Pure-strategy Nash equilibrium solver for N-player energy games.

A profile (a_0*, ..., a_{N-1}*) is a PSNE iff for every player i,
a_i* is a best response to the others' actions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from itertools import product
import numpy as np

from src.game.payoff_matrix import NPlayerPayoffMatrix, GamePayoffMatrix


@dataclass
class NPlayerNashEquilibrium:
    """A verified pure-strategy Nash equilibrium for N players."""
    action_profile: Dict[str, str]          # {player_id: action_name}
    action_indices: Dict[str, int]           # {player_id: action_index}
    utilities: Dict[str, float]              # {player_id: utility}
    is_strict: bool
    total_welfare: float
    traded_energy_kwh: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_profile": self.action_profile,
            "utilities": {k: round(v, 4) for k, v in self.utilities.items()},
            "is_strict": self.is_strict,
            "total_welfare": round(self.total_welfare, 4),
            "traded_energy_kwh": round(self.traded_energy_kwh, 4),
        }


@dataclass
class NPlayerEquilibriumResult:
    """Complete N-player equilibrium analysis result."""
    player_ids: List[str]
    has_pure_nash: bool
    num_equilibria: int
    equilibria: List[NPlayerNashEquilibrium]
    # best_responses[player_id][opp_key] = List[best_action_names]
    best_responses: Dict[str, Dict[tuple, List[str]]]
    baseline_profile: Dict[str, str]
    baseline_utilities: Dict[str, float]
    selected_equilibrium: Optional[NPlayerNashEquilibrium] = None

    @property
    def welfare_gain(self) -> Optional[float]:
        if self.selected_equilibrium is None:
            return None
        eq_welfare = self.selected_equilibrium.total_welfare
        base_welfare = sum(self.baseline_utilities.values())
        return eq_welfare - base_welfare


def find_nash_equilibria_n_players(
    matrix: NPlayerPayoffMatrix,
    tolerance: float = 1e-6,
) -> NPlayerEquilibriumResult:
    """Find all pure-strategy Nash equilibria for an N-player game.

    Returns NPlayerEquilibriumResult where best_responses is keyed by player_id.
    """
    N = len(matrix.player_ids)

    # Compute best response sets for each player and each opponent profile
    # br_indices[player_idx][opp_combo_tuple] = List[best own action indices]
    br_indices: List[Dict[tuple, List[int]]] = []
    br_names: Dict[str, Dict[tuple, List[str]]] = {}

    for player_idx, player_id in enumerate(matrix.player_ids):
        payoff_array = matrix.payoffs[player_idx]
        player_actions = matrix.actions[player_idx]
        n_own = len(player_actions)

        other_indices = [k for k in range(N) if k != player_idx]
        other_ranges = [range(len(matrix.actions[k])) for k in other_indices]

        br_for_player: Dict[tuple, List[int]] = {}
        br_for_player_names: Dict[tuple, List[str]] = {}

        for opp_combo in product(*other_ranges):
            action_utils = []
            for ai in range(n_own):
                idx = list(opp_combo)
                idx.insert(player_idx, ai)
                action_utils.append(float(payoff_array[tuple(idx)]))

            max_u = max(action_utils)
            best_own = [ai for ai, u in enumerate(action_utils) if u >= max_u - tolerance]
            br_for_player[opp_combo] = best_own
            br_for_player_names[opp_combo] = [player_actions[ai] for ai in best_own]

        br_indices.append(br_for_player)
        br_names[player_id] = {
            tuple(sorted({
                matrix.player_ids[other_indices[ki]]: matrix.actions[other_indices[ki]][opp_combo[ki]]
                for ki in range(len(other_indices))
            }.items())): br_for_player_names[opp_combo]
            for opp_combo in br_for_player_names
        }

    # Enumerate all joint action profiles and find Nash equilibria
    all_action_ranges = [range(len(matrix.actions[k])) for k in range(N)]
    equilibria: List[NPlayerNashEquilibrium] = []

    for profile in product(*all_action_ranges):
        # profile = (i0, i1, ..., i_{N-1})
        is_nash = True
        strict_flags = []

        for player_idx in range(N):
            own_idx = profile[player_idx]
            # Build opponent combo (all indices except player_idx)
            opp_combo = tuple(profile[k] for k in range(N) if k != player_idx)

            best_own = br_indices[player_idx].get(opp_combo, [])
            if own_idx not in best_own:
                is_nash = False
                break

            # Check strict: own action is uniquely best
            payoff_array = matrix.payoffs[player_idx]
            own_u = float(payoff_array[profile])
            other_utils = []
            for ai in range(len(matrix.actions[player_idx])):
                if ai != own_idx:
                    alt_profile = list(profile)
                    alt_profile[player_idx] = ai
                    other_utils.append(float(payoff_array[tuple(alt_profile)]))
            strict_flags.append(all(own_u > u + tolerance for u in other_utils) if other_utils else True)

        if is_nash:
            action_profile_names = {
                matrix.player_ids[k]: matrix.actions[k][profile[k]] for k in range(N)
            }
            utilities = {
                matrix.player_ids[k]: float(matrix.payoffs[k][profile]) for k in range(N)
            }
            total_welfare = sum(utilities.values())
            traded_kwh = float(matrix.traded_quantities[profile])
            is_strict = all(strict_flags)

            equilibria.append(NPlayerNashEquilibrium(
                action_profile=action_profile_names,
                action_indices={matrix.player_ids[k]: profile[k] for k in range(N)},
                utilities=utilities,
                is_strict=is_strict,
                total_welfare=total_welfare,
                traded_energy_kwh=traded_kwh,
            ))

    # Baseline: everyone uses GRID_ONLY (or SELF_SUFFICIENT if self-sufficient)
    baseline_idx = tuple(
        matrix.actions[k].index("GRID_ONLY") if "GRID_ONLY" in matrix.actions[k]
        else (matrix.actions[k].index("SELF_SUFFICIENT") if "SELF_SUFFICIENT" in matrix.actions[k] else 0)
        for k in range(N)
    )
    baseline_profile_names = {
        matrix.player_ids[k]: matrix.actions[k][baseline_idx[k]] for k in range(N)
    }
    baseline_utilities = {
        matrix.player_ids[k]: float(matrix.payoffs[k][baseline_idx]) for k in range(N)
    }

    # Select equilibrium with maximum total welfare
    selected_eq = None
    if len(equilibria) == 1:
        selected_eq = equilibria[0]
    elif len(equilibria) > 1:
        selected_eq = max(equilibria, key=lambda eq: eq.total_welfare)

    return NPlayerEquilibriumResult(
        player_ids=matrix.player_ids,
        has_pure_nash=len(equilibria) > 0,
        num_equilibria=len(equilibria),
        equilibria=equilibria,
        best_responses=br_names,
        baseline_profile=baseline_profile_names,
        baseline_utilities=baseline_utilities,
        selected_equilibrium=selected_eq,
    )


# ---------------------------------------------------------------------------
# 2-Player Backward Compatibility
# ---------------------------------------------------------------------------

@dataclass
class NashEquilibrium:
    """A verified pure-strategy Nash equilibrium for 2 players."""

    action_player1: str
    action_player2: str
    action_index_player1: int
    action_index_player2: int
    utility_player1: float
    utility_player2: float
    is_strict: bool
    traded_energy_kwh: float

    def to_dict(self) -> Dict[str, Any]:
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
    best_responses_p1: Dict[str, List[str]]
    best_responses_p2: Dict[str, List[str]]
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
    """Find all pure-strategy Nash equilibria in a 2-player game."""
    m1 = matrix.payoffs_p1
    m2 = matrix.payoffs_p2
    n1, n2 = m1.shape

    br_p1_indices: Dict[int, List[int]] = {}
    br_p1_names: Dict[str, List[str]] = {}
    for j in range(n2):
        col = m1[:, j]
        max_val = np.max(col)
        best_i = [i for i in range(n1) if col[i] >= max_val - tolerance]
        br_p1_indices[j] = best_i
        br_p1_names[matrix.actions_p2[j]] = [matrix.actions_p1[i] for i in best_i]

    br_p2_indices: Dict[int, List[int]] = {}
    br_p2_names: Dict[str, List[str]] = {}
    for i in range(n1):
        row = m2[i, :]
        max_val = np.max(row)
        best_j = [j for j in range(n2) if row[j] >= max_val - tolerance]
        br_p2_indices[i] = best_j
        br_p2_names[matrix.actions_p1[i]] = [matrix.actions_p2[j] for j in best_j]

    equilibria: List[NashEquilibrium] = []
    for i in range(n1):
        for j in range(n2):
            if i in br_p1_indices[j] and j in br_p2_indices[i]:
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

    selected_eq = None
    if len(equilibria) == 1:
        selected_eq = equilibria[0]
    elif len(equilibria) > 1:
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
