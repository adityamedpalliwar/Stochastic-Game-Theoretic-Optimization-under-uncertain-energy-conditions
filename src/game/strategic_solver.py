"""Phase 8C: Deterministic Price-Only Nash Equilibrium Solver.

Implements an exhaustive deterministic, ex-post, price-only Nash equilibrium solver
for the multi-household strategic double-auction energy market.

Key Capabilities:
1. Dynamic household role and action-space generation:
   - Seller: A_i = P (7 discrete ask prices)
   - Buyer:  A_j = P (7 discrete bid prices)
   - Inactive: A_k = {None} (no strategic actions; 0 deviations)
2. Exact transaction-level payoff computation:
   - Seller: U_i = sum_j q_ij * (p_ij - p_exp)
   - Buyer:  U_j = sum_i q_ij * (p_imp - p_ij)
   - Inactive: U_k = 0.0
3. Exhaustive unilateral deviation verification:
   - Evaluates all alternative actions for every active player.
   - Strict PNE: every deviation strictly reduces payoff.
   - Weak PNE: at least one deviation yields equal payoff, none strictly higher.
   - Non-equilibrium: at least one deviation strictly increases payoff.
4. Comprehensive multi-equilibrium preservation:
   - Retains all detected pure Nash equilibria.
   - Returns status "NO_PURE_NASH_EQUILIBRIUM" if no pure equilibrium exists.
5. Multi-household Pareto dominance analysis:
   - Full vector comparison: a >= b for all i, and a > b for at least one j.
   - Filters to Pareto-undominated frontier.
6. Deterministic 5-step representative equilibrium selection:
   - 1. Pareto-undominated filter.
   - 2. Volume-weighted price proximity to reference price $0.19/kWh.
   - 3. Maximize community incremental welfare.
   - 4. Minimize transaction-price standard deviation.
   - 5. Deterministic lexicographical order of player prices.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import numpy as np
import pandas as pd

from src.game.strategic_market import (
    DEFAULT_GRID_EXPORT_CREDIT_AUD,
    DEFAULT_GRID_IMPORT_TARIFF_AUD,
    DEFAULT_GRID_SPREAD_MARKUP_AUD,
    DEFAULT_NUMERICAL_TOLERANCE,
    STRATEGIC_PRICE_GRID,
    MarketOrder,
    MarketRole,
    StrategicMarketResult,
    StrategicTransaction,
    clear_strategic_double_auction,
    compute_physical_net_position,
    create_order_from_physical_position,
    validate_market_configuration,
    validate_price_grid,
)


class EquilibriumClassification(str, Enum):
    """Classification of pure-strategy Nash equilibrium."""

    STRICT = "strict"
    WEAK = "weak"


class SolverStatus(str, Enum):
    """Execution status of the Nash equilibrium solver."""

    SUCCESS = "SUCCESS"
    NO_PURE_NASH_EQUILIBRIUM = "NO_PURE_NASH_EQUILIBRIUM"
    NO_TRADE_HOUR = "NO_TRADE_HOUR"


@dataclass(frozen=True)
class NashEquilibriumRecord:
    """Comprehensive record of a detected pure-strategy Nash equilibrium.

    Attributes:
        profile: Mapping from household_id to submitted price (AUD/kWh).
        roles: Mapping from household_id to MarketRole.
        payoffs: Mapping from household_id to incremental financial payoff (AUD).
        total_traded_kwh: Total energy cleared in P2P market (kWh).
        weighted_average_price_aud: Volume-weighted transaction price (AUD/kWh), or None.
        community_welfare_aud: Total community incremental welfare (AUD).
        num_transactions: Count of cleared bilateral trades.
        classification: EquilibriumClassification (STRICT or WEAK).
        is_pareto_undominated: Whether equilibrium lies on the Pareto frontier.
        transaction_price_std: Standard deviation of cleared transaction prices.
        market_result: Complete underlying StrategicMarketResult.
    """

    profile: Dict[str, float]
    roles: Dict[str, MarketRole]
    payoffs: Dict[str, float]
    total_traded_kwh: float
    weighted_average_price_aud: Optional[float]
    community_welfare_aud: float
    num_transactions: int
    classification: EquilibriumClassification
    is_pareto_undominated: bool
    transaction_price_std: float
    market_result: StrategicMarketResult

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to serializable dictionary."""
        return {
            "profile": dict(self.profile),
            "roles": {k: v.value for k, v in self.roles.items()},
            "payoffs": dict(self.payoffs),
            "total_traded_kwh": self.total_traded_kwh,
            "weighted_average_price_aud": self.weighted_average_price_aud,
            "community_welfare_aud": self.community_welfare_aud,
            "num_transactions": self.num_transactions,
            "classification": self.classification.value,
            "is_pareto_undominated": self.is_pareto_undominated,
            "transaction_price_std": self.transaction_price_std,
        }


@dataclass
class StrategicGameResult:
    """Complete results of exhaustive Nash equilibrium solving for an evaluated hour.

    Attributes:
        status: Solver execution status ('SUCCESS', 'NO_PURE_NASH_EQUILIBRIUM', etc.).
        active_sellers: List of active seller household IDs.
        active_buyers: List of active buyer household IDs.
        inactive_households: List of inactive household IDs.
        num_profiles_evaluated: Total combinatorial profiles evaluated.
        num_deviations_evaluated: Total unilateral deviations tested.
        equilibria: Full list of all detected pure Nash equilibria.
        strict_equilibria: Subset of strict pure Nash equilibria.
        weak_equilibria: Subset of weak pure Nash equilibria.
        pareto_undominated_equilibria: Subset of Pareto-undominated equilibria.
        selected_equilibrium: Selected representative equilibrium (if one exists).
    """

    status: str
    active_sellers: List[str]
    active_buyers: List[str]
    inactive_households: List[str]
    num_profiles_evaluated: int
    num_deviations_evaluated: int
    equilibria: List[NashEquilibriumRecord] = field(default_factory=list)
    strict_equilibria: List[NashEquilibriumRecord] = field(default_factory=list)
    weak_equilibria: List[NashEquilibriumRecord] = field(default_factory=list)
    pareto_undominated_equilibria: List[NashEquilibriumRecord] = field(default_factory=list)
    selected_equilibrium: Optional[NashEquilibriumRecord] = None

    @property
    def num_equilibria(self) -> int:
        return len(self.equilibria)

    @property
    def num_strict(self) -> int:
        return len(self.strict_equilibria)

    @property
    def num_weak(self) -> int:
        return len(self.weak_equilibria)

    @property
    def num_pareto_undominated(self) -> int:
        return len(self.pareto_undominated_equilibria)

    @property
    def selected_payoffs(self) -> Optional[Dict[str, float]]:
        return self.selected_equilibrium.payoffs if self.selected_equilibrium else None

    @property
    def selected_traded_kwh(self) -> Optional[float]:
        return self.selected_equilibrium.total_traded_kwh if self.selected_equilibrium else None

    @property
    def selected_price_aud(self) -> Optional[float]:
        return self.selected_equilibrium.weighted_average_price_aud if self.selected_equilibrium else None

    @property
    def selected_welfare_aud(self) -> Optional[float]:
        return self.selected_equilibrium.community_welfare_aud if self.selected_equilibrium else None

    def get_summary_dict(self) -> Dict[str, Any]:
        """Summary metrics dictionary for reporting and table exports."""
        return {
            "status": self.status,
            "num_active_sellers": len(self.active_sellers),
            "num_active_buyers": len(self.active_buyers),
            "num_inactive_households": len(self.inactive_households),
            "num_profiles_evaluated": self.num_profiles_evaluated,
            "num_deviations_evaluated": self.num_deviations_evaluated,
            "num_pure_nash_equilibria": self.num_equilibria,
            "num_strict_equilibria": self.num_strict,
            "num_weak_equilibria": self.num_weak,
            "num_pareto_undominated": self.num_pareto_undominated,
            "has_selected_equilibrium": self.selected_equilibrium is not None,
            "selected_traded_kwh": self.selected_traded_kwh,
            "selected_price_aud": self.selected_price_aud,
            "selected_welfare_aud": self.selected_welfare_aud,
            "selected_profile": self.selected_equilibrium.profile if self.selected_equilibrium else None,
            "selected_payoffs": self.selected_payoffs,
        }

    def get_equilibria_dataframe(self) -> pd.DataFrame:
        """Tabulate all equilibria into a pandas DataFrame."""
        if not self.equilibria:
            return pd.DataFrame()
        rows = []
        for eq in self.equilibria:
            row = eq.to_dict()
            rows.append(row)
        return pd.DataFrame(rows)


def check_pareto_dominance(
    payoffs_a: Dict[str, float],
    payoffs_b: Dict[str, float],
    all_households: Sequence[str],
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
) -> bool:
    """Determine whether payoff vector a strictly Pareto-dominates payoff vector b.

    Condition:
        U_i(a) >= U_i(b) - tolerance for ALL i in all_households
        AND
        U_j(a) > U_j(b) + tolerance for AT LEAST ONE j in all_households

    Parameters
    ----------
    payoffs_a : Dict[str, float]
        Payoffs under candidate equilibrium a.
    payoffs_b : Dict[str, float]
        Payoffs under candidate equilibrium b.
    all_households : Sequence[str]
        Complete universe of evaluated households.
    tolerance : float
        Numerical zero threshold for floating-point comparisons.

    Returns
    -------
    bool
        True if a Pareto-dominates b; False otherwise.
    """
    strictly_better = False
    for hid in all_households:
        u_a = payoffs_a.get(hid, 0.0)
        u_b = payoffs_b.get(hid, 0.0)
        if u_a < u_b - tolerance:
            # Player is worse off in a; a cannot dominate b
            return False
        if u_a > u_b + tolerance:
            strictly_better = True
    return strictly_better


def identify_pareto_undominated(
    records: Sequence[NashEquilibriumRecord],
    all_households: Sequence[str],
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
) -> List[NashEquilibriumRecord]:
    """Identify the Pareto-undominated subset of Nash equilibria.

    An equilibrium b is Pareto-dominated if there exists some equilibrium a in records
    such that check_pareto_dominance(a.payoffs, b.payoffs) is True.
    """
    if not records:
        return []

    undominated = []
    n = len(records)
    for i in range(n):
        rec_i = records[i]
        is_dominated = False
        for j in range(n):
            if i == j:
                continue
            rec_j = records[j]
            if check_pareto_dominance(rec_j.payoffs, rec_i.payoffs, all_households, tolerance=tolerance):
                is_dominated = True
                break
        if not is_dominated:
            undominated.append(rec_i)
    return undominated


def select_representative_equilibrium(
    undominated_equilibria: Sequence[NashEquilibriumRecord],
    active_players: Sequence[str],
    reference_price_aud: float = 0.19,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
) -> Optional[NashEquilibriumRecord]:
    """Apply the deterministic 5-step reporting selection heuristic.

    Hierarchy:
    1. Filter to Pareto-undominated equilibria (passed as input).
    2. Minimize volume-weighted price distance to reference price $0.19/kWh:
       D_mid = |p_tx - 0.19|. Zero-volume equilibria have D_mid = +infinity.
    3. If tied: Maximize community incremental welfare (Delta W).
    4. If tied: Minimize transaction price standard deviation (Std(p_tx)).
    5. If tied: Deterministic lexicographical tie-break by player prices.

    Returns None if undominated_equilibria is empty.
    """
    if not undominated_equilibria:
        return None

    if len(undominated_equilibria) == 1:
        return undominated_equilibria[0]

    # Step 2: Distance to reference price
    distances = []
    for eq in undominated_equilibria:
        if eq.total_traded_kwh > tolerance and eq.weighted_average_price_aud is not None:
            dist = abs(eq.weighted_average_price_aud - reference_price_aud)
        else:
            dist = float("inf")
        distances.append(dist)

    min_dist = min(distances)
    if np.isneginf(min_dist) or np.isposinf(min_dist):
        # All have zero volume
        cands_step2 = list(undominated_equilibria)
    else:
        cands_step2 = [
            eq for eq, d in zip(undominated_equilibria, distances)
            if abs(d - min_dist) <= tolerance
        ]

    if len(cands_step2) == 1:
        return cands_step2[0]

    # Step 3: Maximize community welfare
    max_welfare = max(eq.community_welfare_aud for eq in cands_step2)
    cands_step3 = [
        eq for eq in cands_step2
        if abs(eq.community_welfare_aud - max_welfare) <= tolerance
    ]

    if len(cands_step3) == 1:
        return cands_step3[0]

    # Step 4: Minimize transaction price standard deviation
    min_std = min(eq.transaction_price_std for eq in cands_step3)
    cands_step4 = [
        eq for eq in cands_step3
        if abs(eq.transaction_price_std - min_std) <= tolerance
    ]

    if len(cands_step4) == 1:
        return cands_step4[0]

    # Step 5: Deterministic lexicographical tie-break by player price indices
    # Sort active players deterministically
    sorted_players = sorted(active_players)

    def sort_key(eq: NashEquilibriumRecord) -> Tuple[float, ...]:
        return tuple(eq.profile.get(pid, 0.0) for pid in sorted_players)

    return min(cands_step4, key=sort_key)


def solve_deterministic_nash_equilibrium(
    surpluses_kwh: Optional[Dict[str, float]] = None,
    deficits_kwh: Optional[Dict[str, float]] = None,
    orders: Optional[Sequence[MarketOrder]] = None,
    all_households: Sequence[str] = ("H001", "H002", "H003"),
    grid_import_tariff_aud: float = DEFAULT_GRID_IMPORT_TARIFF_AUD,
    grid_export_credit_aud: float = DEFAULT_GRID_EXPORT_CREDIT_AUD,
    price_grid: Sequence[float] = STRATEGIC_PRICE_GRID,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
    reference_price_aud: float = 0.19,
) -> StrategicGameResult:
    """Exhaustively solve for pure-strategy Nash equilibria in price-only double auction.

    Parameters
    ----------
    surpluses_kwh : Optional[Dict[str, float]]
        Post-battery available surplus energy per household (kWh).
    deficits_kwh : Optional[Dict[str, float]]
        Post-battery available deficit energy per household (kWh).
    orders : Optional[Sequence[MarketOrder]]
        Pre-constructed market orders (used to extract quantities and roles if provided).
    all_households : Sequence[str]
        Universe of households (default ['H001', 'H002', 'H003']).
    grid_import_tariff_aud : float
        Commercial retail import tariff (AUD/kWh).
    grid_export_credit_aud : float
        Solar export feed-in credit (AUD/kWh).
    price_grid : Sequence[float]
        Admissible discrete strategic bidding price grid.
    tolerance : float
        Numerical zero threshold for floating-point comparisons.
    reference_price_aud : float
        Reference price for reporting tie-breaker (default $0.19/kWh).

    Returns
    -------
    StrategicGameResult
        Comprehensive result containing all pure equilibria, strict/weak classifications,
        Pareto frontier, and the selected representative equilibrium.
    """
    # 1. Validate market configuration and price grid
    validated_grid = validate_market_configuration(
        grid_import_tariff_aud=grid_import_tariff_aud,
        grid_export_credit_aud=grid_export_credit_aud,
        tolerance=tolerance,
        price_grid=price_grid,
    )

    universe = sorted(list(all_households))
    for hid in universe:
        if not isinstance(hid, str) or not hid.strip():
            raise ValueError(f"Invalid household_id in all_households: {hid!r}")

    # 2. Extract household roles and physical quantities
    physical_roles: Dict[str, MarketRole] = {}
    physical_quantities: Dict[str, float] = {}

    if orders is not None:
        for ord_obj in orders:
            if not isinstance(ord_obj, MarketOrder):
                raise TypeError(f"Expected MarketOrder, got {type(ord_obj)}")
            hid = ord_obj.household_id
            if hid in physical_roles:
                raise ValueError(f"Duplicate order provided for household {hid}")
            if ord_obj.quantity_kwh > tolerance:
                physical_roles[hid] = ord_obj.role
                physical_quantities[hid] = ord_obj.quantity_kwh
            else:
                physical_roles[hid] = MarketRole.INACTIVE
                physical_quantities[hid] = 0.0

        for hid in universe:
            if hid not in physical_roles:
                physical_roles[hid] = MarketRole.INACTIVE
                physical_quantities[hid] = 0.0
    else:
        surp_dict = surpluses_kwh if surpluses_kwh is not None else {}
        def_dict = deficits_kwh if deficits_kwh is not None else {}

        for hid in universe:
            s_val = float(surp_dict.get(hid, 0.0))
            d_val = float(def_dict.get(hid, 0.0))

            if not np.isfinite(s_val) or s_val < -tolerance:
                raise ValueError(f"Invalid surplus for household {hid}: {s_val}")
            if not np.isfinite(d_val) or d_val < -tolerance:
                raise ValueError(f"Invalid deficit for household {hid}: {d_val}")

            if s_val > tolerance and d_val > tolerance:
                raise ValueError(
                    f"Household {hid} cannot simultaneously have positive surplus ({s_val}) "
                    f"and deficit ({d_val})."
                )

            if s_val > tolerance:
                physical_roles[hid] = MarketRole.SELLER
                physical_quantities[hid] = s_val
            elif d_val > tolerance:
                physical_roles[hid] = MarketRole.BUYER
                physical_quantities[hid] = d_val
            else:
                physical_roles[hid] = MarketRole.INACTIVE
                physical_quantities[hid] = 0.0

    active_sellers = sorted([h for h in universe if physical_roles[h] == MarketRole.SELLER])
    active_buyers = sorted([h for h in universe if physical_roles[h] == MarketRole.BUYER])
    inactive_households = sorted([h for h in universe if physical_roles[h] == MarketRole.INACTIVE])

    active_players = sorted(active_sellers + active_buyers)

    # 3. Handle zero active players or boundary cases
    if len(active_players) == 0:
        # Trivial equilibrium with no active players
        res_empty = clear_strategic_double_auction(
            [],
            grid_import_tariff_aud=grid_import_tariff_aud,
            grid_export_credit_aud=grid_export_credit_aud,
            all_households=universe,
            tolerance=tolerance,
            price_grid=validated_grid,
        )
        trivial_rec = NashEquilibriumRecord(
            profile={},
            roles=physical_roles,
            payoffs={h: 0.0 for h in universe},
            total_traded_kwh=0.0,
            weighted_average_price_aud=None,
            community_welfare_aud=0.0,
            num_transactions=0,
            classification=EquilibriumClassification.STRICT,
            is_pareto_undominated=True,
            transaction_price_std=0.0,
            market_result=res_empty,
        )
        return StrategicGameResult(
            status=SolverStatus.SUCCESS.value,
            active_sellers=active_sellers,
            active_buyers=active_buyers,
            inactive_households=inactive_households,
            num_profiles_evaluated=1,
            num_deviations_evaluated=0,
            equilibria=[trivial_rec],
            strict_equilibria=[trivial_rec],
            weak_equilibria=[],
            pareto_undominated_equilibria=[trivial_rec],
            selected_equilibrium=trivial_rec,
        )

    # 4. Combinatorial Action Space Enumeration
    # Active players choose prices from validated_grid
    # Inactive players have empty action space
    grid_prices = list(validated_grid)
    num_active = len(active_players)

    # Deterministic product ordering
    profile_tuples = list(itertools.product(grid_prices, repeat=num_active))
    num_profiles = len(profile_tuples)
    deviations_per_player = len(grid_prices) - 1
    total_deviations = num_profiles * num_active * deviations_per_player

    # Pre-compute market clearings for all profiles in combinatorial space
    # Map profile tuple to (StrategicMarketResult, payoffs_dict)
    cleared_cache: Dict[Tuple[float, ...], Tuple[StrategicMarketResult, Dict[str, float]]] = {}

    for p_tup in profile_tuples:
        order_list = []
        for idx, hid in enumerate(active_players):
            role = physical_roles[hid]
            qty = physical_quantities[hid]
            price = p_tup[idx]
            order_list.append(
                MarketOrder(
                    household_id=hid,
                    role=role,
                    price_aud_per_kwh=price,
                    quantity_kwh=qty,
                    allowed_price_grid=validated_grid,
                )
            )

        res = clear_strategic_double_auction(
            orders=order_list,
            grid_import_tariff_aud=grid_import_tariff_aud,
            grid_export_credit_aud=grid_export_credit_aud,
            all_households=universe,
            tolerance=tolerance,
            price_grid=validated_grid,
        )

        payoffs = {}
        for hid in universe:
            if hid in active_sellers:
                payoffs[hid] = res.seller_incremental_benefits_aud.get(hid, 0.0)
            elif hid in active_buyers:
                payoffs[hid] = res.buyer_incremental_benefits_aud.get(hid, 0.0)
            else:
                payoffs[hid] = 0.0

        cleared_cache[p_tup] = (res, payoffs)

    # 5. Exhaustive Unilateral Deviation Verification
    candidate_equilibria: List[NashEquilibriumRecord] = []

    for p_tup in profile_tuples:
        orig_res, orig_payoffs = cleared_cache[p_tup]

        is_pne = True
        is_strict = True

        for p_idx, player_id in enumerate(active_players):
            orig_payoff = orig_payoffs[player_id]
            curr_price = p_tup[p_idx]

            for alt_price in grid_prices:
                if abs(alt_price - curr_price) <= tolerance:
                    continue  # Not an alternative deviation

                # Construct deviated profile tuple
                dev_list = list(p_tup)
                dev_list[p_idx] = alt_price
                dev_tup = tuple(dev_list)

                _, dev_payoffs = cleared_cache[dev_tup]
                dev_payoff = dev_payoffs[player_id]

                # Check profitability of deviation
                if dev_payoff > orig_payoff + tolerance:
                    # Profitable deviation exists; not an equilibrium
                    is_pne = False
                    break
                elif abs(dev_payoff - orig_payoff) <= tolerance:
                    # Deviation gives equal payoff; equilibrium cannot be strict
                    is_strict = False

            if not is_pne:
                break

        if is_pne:
            # Profile is a pure Nash equilibrium!
            classification = (
                EquilibriumClassification.STRICT
                if is_strict
                else EquilibriumClassification.WEAK
            )

            # Compute transaction price standard deviation
            if len(orig_res.transactions) > 1:
                tx_prices = [tx.price_aud_per_kwh for tx in orig_res.transactions]
                tx_std = float(np.std(tx_prices))
            else:
                tx_std = 0.0

            profile_dict = {
                active_players[i]: p_tup[i] for i in range(num_active)
            }

            candidate_equilibria.append(
                NashEquilibriumRecord(
                    profile=profile_dict,
                    roles=dict(physical_roles),
                    payoffs=dict(orig_payoffs),
                    total_traded_kwh=orig_res.total_traded_kwh,
                    weighted_average_price_aud=orig_res.weighted_average_transaction_price_aud,
                    community_welfare_aud=orig_res.community_incremental_welfare_aud,
                    num_transactions=len(orig_res.transactions),
                    classification=classification,
                    is_pareto_undominated=False,  # Updated below
                    transaction_price_std=tx_std,
                    market_result=orig_res,
                )
            )

    # 6. Check if equilibria were found
    if len(candidate_equilibria) == 0:
        return StrategicGameResult(
            status=SolverStatus.NO_PURE_NASH_EQUILIBRIUM.value,
            active_sellers=active_sellers,
            active_buyers=active_buyers,
            inactive_households=inactive_households,
            num_profiles_evaluated=num_profiles,
            num_deviations_evaluated=total_deviations,
            equilibria=[],
            strict_equilibria=[],
            weak_equilibria=[],
            pareto_undominated_equilibria=[],
            selected_equilibrium=None,
        )

    # 7. Pareto Dominance Analysis across full household universe
    undominated_set = set(
        id(rec)
        for rec in identify_pareto_undominated(candidate_equilibria, universe, tolerance=tolerance)
    )

    final_equilibria: List[NashEquilibriumRecord] = []
    strict_equilibria: List[NashEquilibriumRecord] = []
    weak_equilibria: List[NashEquilibriumRecord] = []
    pareto_undominated: List[NashEquilibriumRecord] = []

    for rec in candidate_equilibria:
        is_undom = id(rec) in undominated_set
        updated_rec = NashEquilibriumRecord(
            profile=rec.profile,
            roles=rec.roles,
            payoffs=rec.payoffs,
            total_traded_kwh=rec.total_traded_kwh,
            weighted_average_price_aud=rec.weighted_average_price_aud,
            community_welfare_aud=rec.community_welfare_aud,
            num_transactions=rec.num_transactions,
            classification=rec.classification,
            is_pareto_undominated=is_undom,
            transaction_price_std=rec.transaction_price_std,
            market_result=rec.market_result,
        )
        final_equilibria.append(updated_rec)
        if updated_rec.classification == EquilibriumClassification.STRICT:
            strict_equilibria.append(updated_rec)
        else:
            weak_equilibria.append(updated_rec)

        if is_undom:
            pareto_undominated.append(updated_rec)

    # 8. Representative Equilibrium Selection
    selected_rec = select_representative_equilibrium(
        undominated_equilibria=pareto_undominated,
        active_players=active_players,
        reference_price_aud=reference_price_aud,
        tolerance=tolerance,
    )

    return StrategicGameResult(
        status=SolverStatus.SUCCESS.value,
        active_sellers=active_sellers,
        active_buyers=active_buyers,
        inactive_households=inactive_households,
        num_profiles_evaluated=num_profiles,
        num_deviations_evaluated=total_deviations,
        equilibria=final_equilibria,
        strict_equilibria=strict_equilibria,
        weak_equilibria=weak_equilibria,
        pareto_undominated_equilibria=pareto_undominated,
        selected_equilibrium=selected_rec,
    )


def solve_nash_from_physical_flows(
    household_flows: Dict[str, Dict[str, float]],
    all_households: Sequence[str] = ("H001", "H002", "H003"),
    grid_import_tariff_aud: float = DEFAULT_GRID_IMPORT_TARIFF_AUD,
    grid_export_credit_aud: float = DEFAULT_GRID_EXPORT_CREDIT_AUD,
    price_grid: Sequence[float] = STRATEGIC_PRICE_GRID,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
    reference_price_aud: float = 0.19,
) -> StrategicGameResult:
    """Convenience helper to compute Nash equilibrium directly from meter flow dictionaries.

    household_flows mapping:
        household_id -> {
            'demand_kwh': float,
            'battery_charge_kwh': float,
            'solar_generation_kwh': float,
            'battery_discharge_kwh': float,
        }
    """
    surpluses: Dict[str, float] = {}
    deficits: Dict[str, float] = {}

    for hid in all_households:
        flows = household_flows.get(hid, {})
        d = float(flows.get("demand_kwh", 0.0))
        c = float(flows.get("battery_charge_kwh", 0.0))
        s = float(flows.get("solar_generation_kwh", 0.0))
        b = float(flows.get("battery_discharge_kwh", 0.0))

        net_flow, surp, defc = compute_physical_net_position(
            demand_kwh=d,
            battery_charge_kwh=c,
            solar_generation_kwh=s,
            battery_discharge_kwh=b,
            tolerance=tolerance,
        )
        surpluses[hid] = surp
        deficits[hid] = defc

    return solve_deterministic_nash_equilibrium(
        surpluses_kwh=surpluses,
        deficits_kwh=deficits,
        all_households=all_households,
        grid_import_tariff_aud=grid_import_tariff_aud,
        grid_export_credit_aud=grid_export_credit_aud,
        price_grid=price_grid,
        tolerance=tolerance,
        reference_price_aud=reference_price_aud,
    )

