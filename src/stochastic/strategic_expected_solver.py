"""Phase 8E: Stochastic Expected-Payoff Nash Equilibrium Solver.

Implements the authoritative Phase 8E stochastic game-theoretic energy trading engine
under renewable forecast uncertainty:

Mathematical Formulation:
1. Synchronized scenario generation:
   - Jointly samples 1,000 demand-solar realizations for H001, H002, and H003
     using identical validation residual pool indexing (Option 2A).
   - Preserves intra-household paired correlation and inter-household weather synchronization.
2. Frozen non-anticipative battery dispatch:
   - Adopts authoritative Phase 7.1 Stochastic MPC first-stage decisions (C_0, B_0)
     from reports/phase7_hourly_records.csv (Option 3A).
   - C_0 and B_0 remain fixed across all 1,000 scenarios for that timestamp.
3. Ex-ante role-conditioned bidding policy (Option 1A):
   - Computes scenario-dependent net positions:
     n_i(s) = (D_i(s) + C_{0,i}) - (S_i(s) + B_{0,i})
   - Determines ex-ante roles from expected post-battery net position:
     E[n_i] = (1/M) * sum_{s=1}^M n_i(s)
     E[n_i] < -epsilon  ==>  ex-ante SELLER
     E[n_i] > +epsilon  ==>  ex-ante BUYER
     Otherwise          ==>  INACTIVE
   - Each active household chooses one action from STRATEGIC_PRICE_GRID
     (0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30 AUD/kWh):
     * ASK if ex-ante seller
     * BID if ex-ante buyer
   - In each scenario s:
     * If realized role matches ex-ante role, submit MarketOrder with realized surplus/deficit.
     * If realized role conflicts with ex-ante role, submit NO order (zero quantity).
     * Inactive households submit NO order.
4. Expected payoff evaluation:
   - E[U_i(a)] = (1/M) * sum_{s=1}^M U_i(a, omega_s)
   - Evaluates clearing scenario-by-scenario using clear_strategic_double_auction().
   - Precomputes profile expected payoffs over all 1,000 scenarios (preserving M=1,000 denominator).
   - Optional safe zero-trade pruning skips scenarios where trade is physically impossible,
     giving identical results down to numerical tolerance.
5. Stochastic pure Nash equilibrium (PNE):
   - Evaluates all unilateral price deviations using expected payoff tables.
   - Classifies strict vs weak PNE.
   - Computes Pareto-undominated frontier and deterministic 5-step representative selection.
"""

from __future__ import annotations

import gzip
import itertools
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union
import zlib

import numpy as np
import pandas as pd

from src.forecasting.predict import EnergyForecaster, ForecastResult
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
    validate_market_configuration,
    validate_price_grid,
)
from src.game.strategic_solver import (
    EquilibriumClassification,
    check_pareto_dominance,
)
from src.stochastic.monte_carlo import ValidationResidualPool


DEFAULT_PHASE7_RECORDS_PATH = Path("reports/phase7_hourly_records.csv")
DEFAULT_BASE_SEED: int = 42


def derive_synchronized_seed(
    timestamp: Union[str, pd.Timestamp],
    base_seed: int = DEFAULT_BASE_SEED,
) -> int:
    """Generate a deterministic, 32-bit unsigned integer seed from timestamp and base seed.

    Guarantees stable, order-independent, platform-independent random number generation.
    Does NOT use Python's non-deterministic built-in hash().
    """
    ts_str = pd.to_datetime(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    identifier = f"phase8e_sync_{ts_str}_{base_seed}"
    return zlib.crc32(identifier.encode("utf-8"))


def verify_residual_pool_synchronization(
    residual_pool: ValidationResidualPool,
    households: Sequence[str] = ("H001", "H002", "H003"),
) -> Tuple[bool, str]:
    """Verify that validation residual sequences are chronologically sorted and aligned across households."""
    timestamps_by_house: Dict[str, np.ndarray] = {}
    for hid in households:
        mask = (residual_pool.val_house_ids == hid)
        ts_h = residual_pool.val_timestamps[mask]
        if len(ts_h) == 0:
            return False, f"Household {hid} has 0 validation sequences in residual pool."
        # Verify monotonicity
        s = pd.Series(ts_h)
        if not s.is_monotonic_increasing:
            return False, f"Validation timestamps for {hid} are not strictly monotonic increasing."
        timestamps_by_house[hid] = ts_h

    ref_hid = households[0]
    ref_ts = timestamps_by_house[ref_hid]
    for hid in households[1:]:
        ts_h = timestamps_by_house[hid]
        if len(ts_h) != len(ref_ts):
            return False, f"Length mismatch: {ref_hid} has {len(ref_ts)}, {hid} has {len(ts_h)}."
        if not np.array_equal(ref_ts, ts_h):
            return False, f"Validation timestamp mismatch between {ref_hid} and {hid}."

    return True, f"Verified: All {len(households)} households share {len(ref_ts)} synchronized validation hours."


class Phase7DispatchProvider:
    """Thread-safe, indexed provider for authoritative Phase 7.1 Stochastic MPC battery dispatch."""

    def __init__(
        self,
        csv_path: Union[str, Path] = DEFAULT_PHASE7_RECORDS_PATH,
        controller: str = "Stochastic_MPC",
        enable_p2p: bool = True,
        tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
    ) -> None:
        self.csv_path = Path(csv_path)
        self.controller = controller
        self.enable_p2p = enable_p2p
        self.tolerance = tolerance

        if not self.csv_path.exists():
            raise FileNotFoundError(f"Phase 7 records CSV not found at {self.csv_path}")

        df = pd.read_csv(self.csv_path)
        sub = df[(df["controller"] == self.controller) & (df["enable_p2p"] == self.enable_p2p)].copy()

        if len(sub) == 0:
            raise ValueError(
                f"No records found in {self.csv_path} for controller={self.controller}, enable_p2p={self.enable_p2p}"
            )

        # Validate total rows (1,752 hours * 3 households = 5,256)
        if len(sub) != 5256:
            raise ValueError(f"Expected 5,256 Phase 7 records, got {len(sub)}")

        # Build in-memory lookup table: (timestamp_str, house_id) -> (charged_kwh, discharged_kwh)
        self._dispatch_map: Dict[Tuple[str, str], Tuple[float, float, float, float]] = {}

        for _, row in sub.iterrows():
            ts_str = pd.to_datetime(row["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            hid = str(row["house_id"])
            c = float(row["charged_kwh"])
            d = float(row["discharged_kwh"])
            init_soc = float(row["battery_initial_soc"])
            final_soc = float(row["battery_final_soc"])

            # Constraint validation against physical bounds
            if c < -self.tolerance or d < -self.tolerance:
                raise ValueError(f"Negative dispatch at {ts_str} {hid}: charged={c}, discharged={d}")
            if c > 2.5 + self.tolerance or d > 2.5 + self.tolerance:
                raise ValueError(f"Power limit exceeded at {ts_str} {hid}: charged={c}, discharged={d}")
            if (c * d) > self.tolerance:
                raise ValueError(f"Mutual exclusion violation at {ts_str} {hid}: charged={c}, discharged={d}")

            self._dispatch_map[(ts_str, hid)] = (
                max(0.0, c),
                max(0.0, d),
                max(0.0, init_soc),
                max(0.0, final_soc),
            )

    def get_dispatch(self, timestamp: Union[str, pd.Timestamp], house_id: str) -> Tuple[float, float]:
        """Retrieve fixed first-stage (charge_kwh, discharge_kwh) for household at timestamp."""
        ts_str = pd.to_datetime(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        key = (ts_str, house_id)
        if key not in self._dispatch_map:
            raise KeyError(f"No Phase 7.1 dispatch record for timestamp={ts_str}, house_id={house_id}")
        c, d, _, _ = self._dispatch_map[key]
        return c, d

    def get_full_dispatch_record(
        self, timestamp: Union[str, pd.Timestamp], house_id: str
    ) -> Dict[str, float]:
        """Retrieve full battery record: charge, discharge, initial_soc, final_soc."""
        ts_str = pd.to_datetime(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        key = (ts_str, house_id)
        if key not in self._dispatch_map:
            raise KeyError(f"No Phase 7.1 dispatch record for timestamp={ts_str}, house_id={house_id}")
        c, d, init_soc, final_soc = self._dispatch_map[key]
        return {
            "charged_kwh": c,
            "discharged_kwh": d,
            "battery_initial_soc": init_soc,
            "battery_final_soc": final_soc,
        }


@dataclass(frozen=True)
class ScenarioSet:
    """Pre-computed synchronized Monte Carlo physical scenario realizations for one timestamp."""

    timestamp: str
    num_scenarios: int
    house_ids: Tuple[str, ...]
    scenarios_demand_kwh: Dict[str, np.ndarray]
    scenarios_solar_kwh: Dict[str, np.ndarray]
    battery_charge_kwh: Dict[str, float]
    battery_discharge_kwh: Dict[str, float]
    net_positions_kwh: Dict[str, np.ndarray]  # n_i(s) = (D + C) - (S + B)
    expected_net_positions_kwh: Dict[str, float]  # E[n_i]
    ex_ante_roles: Dict[str, MarketRole]
    role_flip_counts: Dict[str, Dict[str, int]]
    tradeable_scenario_indices: Tuple[int, ...]
    scenario_seed: int

    @property
    def num_tradeable_scenarios(self) -> int:
        return len(self.tradeable_scenario_indices)


def build_synchronized_scenarios(
    timestamp: Union[str, pd.Timestamp],
    forecaster: EnergyForecaster,
    residual_pool: ValidationResidualPool,
    dispatch_provider: Phase7DispatchProvider,
    house_ids: Sequence[str] = ("H001", "H002", "H003"),
    num_scenarios: int = 1000,
    base_seed: int = DEFAULT_BASE_SEED,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
) -> ScenarioSet:
    """Construct synchronized, physical post-battery Monte Carlo scenarios for a target timestamp.

    Guarantees:
    1. Cross-household scenario-index synchronization: all households use identical historical
       validation sequence indices.
    2. Exact non-anticipative first-stage battery dispatch from Phase 7.1.
    3. Ex-ante role classification based on expected post-battery net position E[n_i].
    4. Exact identification of tradeable scenarios (where at least one ex-ante seller has realized
       surplus and at least one ex-ante buyer has realized deficit).
    """
    ts_str = pd.to_datetime(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    sorted_houses = tuple(sorted(house_ids))

    # Derive synchronized seed
    sync_seed = derive_synchronized_seed(ts_str, base_seed=base_seed)
    rng = np.random.default_rng(sync_seed)

    # All households share 701 validation hours in lstm_sequences.npz
    # Sample synchronized indices ONCE
    mask_h0 = (residual_pool.val_house_ids == sorted_houses[0])
    pool_len = int(np.sum(mask_h0))
    if pool_len == 0:
        raise ValueError(f"No validation sequences found for household {sorted_houses[0]}")

    sampled_indices = rng.choice(pool_len, size=num_scenarios, replace=True)

    d_scenarios: Dict[str, np.ndarray] = {}
    s_scenarios: Dict[str, np.ndarray] = {}
    bat_c: Dict[str, float] = {}
    bat_d: Dict[str, float] = {}
    net_pos: Dict[str, np.ndarray] = {}
    exp_net: Dict[str, float] = {}
    roles: Dict[str, MarketRole] = {}
    flip_counts: Dict[str, Dict[str, int]] = {}

    for hid in sorted_houses:
        pred: ForecastResult = forecaster.predict_next_hour(hid, ts_str)
        mask = (residual_pool.val_house_ids == hid)
        res_h = residual_pool.residuals[mask]

        if len(res_h) != pool_len:
            raise ValueError(f"Household {hid} residual pool length {len(res_h)} != {pool_len}")

        res_sampled = res_h[sampled_indices]
        d_arr = np.maximum(0.0, pred.predicted_demand_kwh + res_sampled[:, 0])
        s_arr = np.maximum(0.0, pred.predicted_solar_generation_kwh + res_sampled[:, 1])

        c0, b0 = dispatch_provider.get_dispatch(ts_str, hid)

        # Net position: n_i(s) = (D_i + C_0,i) - (S_i + B_0,i)
        n_arr = (d_arr + c0) - (s_arr + b0)
        e_n = float(np.mean(n_arr))

        if e_n < -tolerance:
            role = MarketRole.SELLER
        elif e_n > tolerance:
            role = MarketRole.BUYER
        else:
            role = MarketRole.INACTIVE

        # Track role flips across scenarios
        n_seller_flips = int(np.sum(n_arr < -tolerance))
        n_buyer_flips = int(np.sum(n_arr > tolerance))
        n_inactive_flips = int(np.sum(np.abs(n_arr) <= tolerance))

        d_scenarios[hid] = d_arr
        s_scenarios[hid] = s_arr
        bat_c[hid] = c0
        bat_d[hid] = b0
        net_pos[hid] = n_arr
        exp_net[hid] = e_n
        roles[hid] = role
        flip_counts[hid] = {
            "seller": n_seller_flips,
            "buyer": n_buyer_flips,
            "inactive": n_inactive_flips,
        }

    # Pre-identify tradeable scenarios where at least 1 ex-ante seller has realized surplus
    # AND at least 1 ex-ante buyer has realized deficit
    ex_ante_sellers = [h for h in sorted_houses if roles[h] == MarketRole.SELLER]
    ex_ante_buyers = [h for h in sorted_houses if roles[h] == MarketRole.BUYER]

    tradeable_idx: List[int] = []
    for s in range(num_scenarios):
        has_active_seller = any(net_pos[h][s] < -tolerance for h in ex_ante_sellers)
        has_active_buyer = any(net_pos[h][s] > tolerance for h in ex_ante_buyers)
        if has_active_seller and has_active_buyer:
            tradeable_idx.append(s)

    return ScenarioSet(
        timestamp=ts_str,
        num_scenarios=num_scenarios,
        house_ids=sorted_houses,
        scenarios_demand_kwh=d_scenarios,
        scenarios_solar_kwh=s_scenarios,
        battery_charge_kwh=bat_c,
        battery_discharge_kwh=bat_d,
        net_positions_kwh=net_pos,
        expected_net_positions_kwh=exp_net,
        ex_ante_roles=roles,
        role_flip_counts=flip_counts,
        tradeable_scenario_indices=tuple(tradeable_idx),
        scenario_seed=sync_seed,
    )


@dataclass(frozen=True)
class StochasticNashRecord:
    """Comprehensive record of a detected pure-strategy Nash equilibrium under forecast uncertainty."""

    profile: Dict[str, float]
    ex_ante_roles: Dict[str, MarketRole]
    expected_payoffs: Dict[str, float]
    expected_traded_kwh: float
    expected_community_welfare_aud: float
    expected_vwap_aud_per_kwh: Optional[float]
    classification: EquilibriumClassification
    is_pareto_undominated: bool
    max_deviation_gain: float
    transaction_price_std: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile": dict(self.profile),
            "ex_ante_roles": {k: v.value for k, v in self.ex_ante_roles.items()},
            "expected_payoffs": dict(self.expected_payoffs),
            "expected_traded_kwh": self.expected_traded_kwh,
            "expected_community_welfare_aud": self.expected_community_welfare_aud,
            "expected_vwap_aud_per_kwh": self.expected_vwap_aud_per_kwh,
            "classification": self.classification.value,
            "is_pareto_undominated": self.is_pareto_undominated,
            "max_deviation_gain": self.max_deviation_gain,
            "transaction_price_std": self.transaction_price_std,
        }


@dataclass
class StochasticStrategicGameResult:
    """Complete results of Phase 8E stochastic expected-payoff Nash equilibrium solving for an evaluated hour."""

    timestamp: str
    num_scenarios: int
    num_tradeable_scenarios: int
    ex_ante_roles: Dict[str, MarketRole]
    expected_net_positions_kwh: Dict[str, float]
    scenario_role_flip_counts: Dict[str, Dict[str, int]]
    num_active_players: int
    active_sellers: List[str]
    active_buyers: List[str]
    inactive_households: List[str]
    num_profiles_evaluated: int
    num_deviations_evaluated: int
    expected_payoff_table: List[Dict[str, Any]]
    expected_equilibria: List[StochasticNashRecord] = field(default_factory=list)
    strict_equilibria: List[StochasticNashRecord] = field(default_factory=list)
    weak_equilibria: List[StochasticNashRecord] = field(default_factory=list)
    pareto_undominated_equilibria: List[StochasticNashRecord] = field(default_factory=list)
    selected_equilibrium: Optional[StochasticNashRecord] = None
    scenario_seed: int = 0
    modeling_metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def num_equilibria(self) -> int:
        return len(self.expected_equilibria)

    @property
    def strict_pne_count(self) -> int:
        return len(self.strict_equilibria)

    @property
    def weak_pne_count(self) -> int:
        return len(self.weak_equilibria)

    @property
    def pareto_undominated_pne_count(self) -> int:
        return len(self.pareto_undominated_equilibria)

    @property
    def expected_traded_kwh(self) -> Optional[float]:
        return self.selected_equilibrium.expected_traded_kwh if self.selected_equilibrium else None

    @property
    def expected_community_welfare_aud(self) -> Optional[float]:
        return self.selected_equilibrium.expected_community_welfare_aud if self.selected_equilibrium else None

    @property
    def expected_household_payoffs_aud(self) -> Optional[Dict[str, float]]:
        return self.selected_equilibrium.expected_payoffs if self.selected_equilibrium else None

    @property
    def expected_vwap_aud_per_kwh(self) -> Optional[float]:
        return self.selected_equilibrium.expected_vwap_aud_per_kwh if self.selected_equilibrium else None

    @property
    def maximum_unilateral_deviation_gain(self) -> float:
        if not self.expected_equilibria:
            return float("nan")
        return max(rec.max_deviation_gain for rec in self.expected_equilibria)

    def get_summary_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "status": "SUCCESS" if self.num_equilibria > 0 else "NO_PURE_NASH_EQUILIBRIUM",
            "num_scenarios": self.num_scenarios,
            "num_tradeable_scenarios": self.num_tradeable_scenarios,
            "num_active_players": self.num_active_players,
            "active_sellers": self.active_sellers,
            "active_buyers": self.active_buyers,
            "inactive_households": self.inactive_households,
            "num_profiles_evaluated": self.num_profiles_evaluated,
            "num_deviations_evaluated": self.num_deviations_evaluated,
            "num_stochastic_pne": self.num_equilibria,
            "strict_pne_count": self.strict_pne_count,
            "weak_pne_count": self.weak_pne_count,
            "pareto_undominated_pne_count": self.pareto_undominated_pne_count,
            "has_selected_equilibrium": self.selected_equilibrium is not None,
            "selected_profile": self.selected_equilibrium.profile if self.selected_equilibrium else None,
            "expected_traded_kwh": self.expected_traded_kwh,
            "expected_community_welfare_aud": self.expected_community_welfare_aud,
            "expected_household_payoffs_aud": self.expected_household_payoffs_aud,
            "expected_vwap_aud_per_kwh": self.expected_vwap_aud_per_kwh,
            "scenario_seed": self.scenario_seed,
            "modeling_metadata": self.modeling_metadata,
        }

    def to_dict(self) -> Dict[str, Any]:
        summary = self.get_summary_dict()
        summary["ex_ante_roles"] = {k: v.value for k, v in self.ex_ante_roles.items()}
        summary["expected_net_positions_kwh"] = self.expected_net_positions_kwh
        summary["scenario_role_flip_counts"] = self.scenario_role_flip_counts
        summary["expected_equilibria"] = [eq.to_dict() for eq in self.expected_equilibria]
        return summary

    def get_equilibria_dataframe(self) -> pd.DataFrame:
        if not self.expected_equilibria:
            return pd.DataFrame()
        return pd.DataFrame([eq.to_dict() for eq in self.expected_equilibria])

    def get_payoff_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.expected_payoff_table)


def select_representative_stochastic_equilibrium(
    undominated_equilibria: Sequence[StochasticNashRecord],
    active_players: Sequence[str],
    reference_price_aud: float = 0.19,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
) -> Optional[StochasticNashRecord]:
    """Apply the deterministic 5-step representative selection heuristic to expected equilibria.

    Hierarchy:
    1. Filter to Pareto-undominated set (input).
    2. Minimize distance of volume-weighted average price to reference price $0.19/kWh:
       D_mid = |p_vwap - 0.19|. Zero-volume equilibria have D_mid = +infinity.
    3. If tied: Maximize expected community welfare E[W].
    4. If tied: Minimize transaction price standard deviation.
    5. If tied: Deterministic lexicographical tie-break by player price indices.
    """
    if not undominated_equilibria:
        return None

    if len(undominated_equilibria) == 1:
        return undominated_equilibria[0]

    # Step 2: Distance to reference price
    distances = []
    for eq in undominated_equilibria:
        if eq.expected_traded_kwh > tolerance and eq.expected_vwap_aud_per_kwh is not None:
            dist = abs(eq.expected_vwap_aud_per_kwh - reference_price_aud)
        else:
            dist = float("inf")
        distances.append(dist)

    min_dist = min(distances)
    if np.isneginf(min_dist) or np.isposinf(min_dist):
        cands_step2 = list(undominated_equilibria)
    else:
        cands_step2 = [
            eq for eq, d in zip(undominated_equilibria, distances)
            if abs(d - min_dist) <= tolerance
        ]

    if len(cands_step2) == 1:
        return cands_step2[0]

    # Step 3: Maximize expected community welfare
    max_welfare = max(eq.expected_community_welfare_aud for eq in cands_step2)
    cands_step3 = [
        eq for eq in cands_step2
        if abs(eq.expected_community_welfare_aud - max_welfare) <= tolerance
    ]

    if len(cands_step3) == 1:
        return cands_step3[0]

    # Step 4: Minimize transaction price std
    min_std = min(eq.transaction_price_std for eq in cands_step3)
    cands_step4 = [
        eq for eq in cands_step3
        if abs(eq.transaction_price_std - min_std) <= tolerance
    ]

    if len(cands_step4) == 1:
        return cands_step4[0]

    # Step 5: Deterministic lexicographical tie-break by player price indices
    sorted_players = sorted(active_players)

    def sort_key(eq: StochasticNashRecord) -> Tuple[float, ...]:
        return tuple(eq.profile.get(pid, 0.0) for pid in sorted_players)

    return min(cands_step4, key=sort_key)


def solve_stochastic_nash_equilibrium(
    scenario_set: ScenarioSet,
    grid_import_tariff_aud: float = DEFAULT_GRID_IMPORT_TARIFF_AUD,
    grid_export_credit_aud: float = DEFAULT_GRID_EXPORT_CREDIT_AUD,
    price_grid: Sequence[float] = STRATEGIC_PRICE_GRID,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
    reference_price_aud: float = 0.19,
    prune_zero_trade: bool = True,
) -> StochasticStrategicGameResult:
    """Exhaustively solve for pure-strategy Nash equilibria under Monte Carlo uncertainty.

    Parameters
    ----------
    scenario_set : ScenarioSet
        Synchronized Monte Carlo realizations and ex-ante role classifications.
    grid_import_tariff_aud : float
        Commercial retail import tariff (default $0.30/kWh).
    grid_export_credit_aud : float
        Solar export credit (default $0.08/kWh).
    price_grid : Sequence[float]
        Admissible strategic price grid (default 7 prices).
    tolerance : float
        Numerical zero threshold (default 1e-6).
    reference_price_aud : float
        Reference price for 5-step selection heuristic (default $0.19/kWh).
    prune_zero_trade : bool
        If True, skips clearing evaluations for scenarios where trade is physically impossible.
        Preserves exact mathematical denominator M=1,000. Verified to yield identical results.

    Returns
    -------
    StochasticStrategicGameResult
        Comprehensive result with all stochastic equilibria, classifications, and selection.
    """
    validated_grid = validate_market_configuration(
        grid_import_tariff_aud=grid_import_tariff_aud,
        grid_export_credit_aud=grid_export_credit_aud,
        tolerance=tolerance,
        price_grid=price_grid,
    )

    universe = sorted(list(scenario_set.house_ids))
    roles = scenario_set.ex_ante_roles

    active_sellers = sorted([h for h in universe if roles[h] == MarketRole.SELLER])
    active_buyers = sorted([h for h in universe if roles[h] == MarketRole.BUYER])
    inactive_households = sorted([h for h in universe if roles[h] == MarketRole.INACTIVE])
    active_players = sorted(active_sellers + active_buyers)

    num_active = len(active_players)
    grid_prices = list(validated_grid)
    num_scenarios = scenario_set.num_scenarios

    # Handle zero active players or strictly unilateral market (no bilateral trade possible)
    if num_active == 0 or len(active_sellers) == 0 or len(active_buyers) == 0:
        # Zero trade is physically guaranteed
        if num_active == 0:
            profile_tuples = [()]
            total_deviations = 0
        else:
            profile_tuples = list(itertools.product(grid_prices, repeat=num_active))
            total_deviations = len(profile_tuples) * num_active * (len(grid_prices) - 1)

        empty_records: List[StochasticNashRecord] = []
        for p_tup in profile_tuples:
            prof_dict = {active_players[i]: p_tup[i] for i in range(num_active)}
            rec = StochasticNashRecord(
                profile=prof_dict,
                ex_ante_roles=dict(roles),
                expected_payoffs={h: 0.0 for h in universe},
                expected_traded_kwh=0.0,
                expected_community_welfare_aud=0.0,
                expected_vwap_aud_per_kwh=None,
                classification=EquilibriumClassification.STRICT if total_deviations == 0 else EquilibriumClassification.WEAK,
                is_pareto_undominated=True,
                max_deviation_gain=0.0,
                transaction_price_std=0.0,
            )
            empty_records.append(rec)

        selected = empty_records[0] if empty_records else None
        return StochasticStrategicGameResult(
            timestamp=scenario_set.timestamp,
            num_scenarios=num_scenarios,
            num_tradeable_scenarios=0,
            ex_ante_roles=dict(roles),
            expected_net_positions_kwh=dict(scenario_set.expected_net_positions_kwh),
            scenario_role_flip_counts=dict(scenario_set.role_flip_counts),
            num_active_players=num_active,
            active_sellers=active_sellers,
            active_buyers=active_buyers,
            inactive_households=inactive_households,
            num_profiles_evaluated=len(profile_tuples),
            num_deviations_evaluated=total_deviations,
            expected_payoff_table=[],
            expected_equilibria=empty_records,
            strict_equilibria=[r for r in empty_records if r.classification == EquilibriumClassification.STRICT],
            weak_equilibria=[r for r in empty_records if r.classification == EquilibriumClassification.WEAK],
            pareto_undominated_equilibria=empty_records,
            selected_equilibrium=selected,
            scenario_seed=scenario_set.scenario_seed,
            modeling_metadata={
                "prune_zero_trade": prune_zero_trade,
                "note": "No bilateral trade physically possible (0 active sellers or 0 active buyers).",
            },
        )

    # 1. Combinatorial Profile Enumeration
    profile_tuples = list(itertools.product(grid_prices, repeat=num_active))
    num_profiles = len(profile_tuples)
    deviations_per_player = len(grid_prices) - 1
    total_deviations = num_profiles * num_active * deviations_per_player

    # Scenarios to evaluate
    if prune_zero_trade:
        scenarios_to_eval = scenario_set.tradeable_scenario_indices
    else:
        scenarios_to_eval = tuple(range(num_scenarios))

    # Pre-extract scenario physical quantities and pre-instantiate MarketOrders for fast access
    # order_lookup[hid][price][s] -> Optional[MarketOrder]
    order_lookup: Dict[str, Dict[float, Dict[int, Optional[MarketOrder]]]] = {
        hid: {p: {} for p in grid_prices} for hid in active_players
    }

    for s in scenarios_to_eval:
        for hid in active_players:
            ex_role = roles[hid]
            n_val = scenario_set.net_positions_kwh[hid][s]

            if ex_role == MarketRole.SELLER and n_val < -tolerance:
                role = MarketRole.SELLER
                qty = -n_val
            elif ex_role == MarketRole.BUYER and n_val > tolerance:
                role = MarketRole.BUYER
                qty = n_val
            else:
                role = MarketRole.INACTIVE
                qty = 0.0

            for p in grid_prices:
                if role != MarketRole.INACTIVE and qty > tolerance:
                    ord_obj = MarketOrder(
                        household_id=hid,
                        role=role,
                        price_aud_per_kwh=p,
                        quantity_kwh=qty,
                        allowed_price_grid=validated_grid,
                    )
                else:
                    ord_obj = None
                order_lookup[hid][p][s] = ord_obj

    # Cache of expected outcomes per profile tuple
    # p_tup -> (expected_payoffs_dict, exp_traded_kwh, exp_welfare_aud, exp_vwap_aud, exp_price_std)
    profile_expected_cache: Dict[
        Tuple[float, ...], Tuple[Dict[str, float], float, float, Optional[float], float]
    ] = {}

    payoff_table_rows: List[Dict[str, Any]] = []

    for p_tup in profile_tuples:
        price_by_player = {active_players[i]: p_tup[i] for i in range(num_active)}

        tot_u = {hid: 0.0 for hid in universe}
        tot_q = 0.0
        tot_val = 0.0
        tot_welfare = 0.0
        all_tx_prices: List[float] = []

        for s in scenarios_to_eval:
            # Retrieve pre-instantiated MarketOrders for scenario s
            orders = []
            for hid in active_players:
                p = price_by_player[hid]
                ord_obj = order_lookup[hid][p][s]
                if ord_obj is not None:
                    orders.append(ord_obj)

            if not orders:
                continue

            # Execute double auction
            res: StrategicMarketResult = clear_strategic_double_auction(
                orders=orders,
                grid_import_tariff_aud=grid_import_tariff_aud,
                grid_export_credit_aud=grid_export_credit_aud,
                all_households=universe,
                tolerance=tolerance,
                price_grid=validated_grid,
            )

            if res.total_traded_kwh > tolerance:
                tot_q += res.total_traded_kwh
                tot_welfare += res.community_incremental_welfare_aud
                for tx in res.transactions:
                    tot_val += tx.traded_energy_kwh * tx.price_aud_per_kwh
                    all_tx_prices.append(tx.price_aud_per_kwh)

                for hid in universe:
                    if roles[hid] == MarketRole.SELLER:
                        tot_u[hid] += res.seller_incremental_benefits_aud.get(hid, 0.0)
                    elif roles[hid] == MarketRole.BUYER:
                        tot_u[hid] += res.buyer_incremental_benefits_aud.get(hid, 0.0)

        # Average strictly over all M=num_scenarios (preserving original denominator)
        exp_u = {hid: tot_u[hid] / num_scenarios for hid in universe}
        exp_q = tot_q / num_scenarios
        exp_welfare = tot_welfare / num_scenarios
        exp_val = tot_val / num_scenarios

        if exp_q > tolerance:
            # Expected VWAP = Expected Transaction Value / Expected Traded Volume
            exp_vwap: Optional[float] = exp_val / exp_q
        else:
            exp_vwap = None

        if len(all_tx_prices) > 1:
            exp_tx_std = float(np.std(all_tx_prices))
        else:
            exp_tx_std = 0.0

        profile_expected_cache[p_tup] = (exp_u, exp_q, exp_welfare, exp_vwap, exp_tx_std)

        # Tabulate row
        row_dict: Dict[str, Any] = {
            f"Action_{hid}": price_by_player[hid] for hid in active_players
        }
        for hid in universe:
            row_dict[f"Expected_Payoff_{hid}"] = exp_u[hid]
        row_dict["Expected_Traded_kWh"] = exp_q
        row_dict["Expected_Welfare_AUD"] = exp_welfare
        row_dict["Expected_VWAP_AUD"] = exp_vwap
        payoff_table_rows.append(row_dict)

    # 2. Exhaustive Unilateral Deviation Verification
    candidate_equilibria: List[StochasticNashRecord] = []

    for p_tup in profile_tuples:
        orig_u, orig_q, orig_welfare, orig_vwap, orig_std = profile_expected_cache[p_tup]

        is_pne = True
        is_strict = True
        max_profile_dev_gain = 0.0

        for p_idx, player_id in enumerate(active_players):
            orig_payoff = orig_u[player_id]
            curr_price = p_tup[p_idx]

            for alt_price in grid_prices:
                if abs(alt_price - curr_price) <= tolerance:
                    continue

                dev_list = list(p_tup)
                dev_list[p_idx] = alt_price
                dev_tup = tuple(dev_list)

                dev_u, _, _, _, _ = profile_expected_cache[dev_tup]
                dev_payoff = dev_u[player_id]
                gain = dev_payoff - orig_payoff

                if gain > max_profile_dev_gain:
                    max_profile_dev_gain = gain

                if dev_payoff > orig_payoff + tolerance:
                    is_pne = False
                elif abs(dev_payoff - orig_payoff) <= tolerance:
                    is_strict = False

        if is_pne:
            classification = (
                EquilibriumClassification.STRICT
                if is_strict
                else EquilibriumClassification.WEAK
            )
            prof_dict = {active_players[i]: p_tup[i] for i in range(num_active)}

            rec = StochasticNashRecord(
                profile=prof_dict,
                ex_ante_roles=dict(roles),
                expected_payoffs=dict(orig_u),
                expected_traded_kwh=orig_q,
                expected_community_welfare_aud=orig_welfare,
                expected_vwap_aud_per_kwh=orig_vwap,
                classification=classification,
                is_pareto_undominated=False,  # Updated below
                max_deviation_gain=max_profile_dev_gain,
                transaction_price_std=orig_std,
            )
            candidate_equilibria.append(rec)

    if not candidate_equilibria:
        return StochasticStrategicGameResult(
            timestamp=scenario_set.timestamp,
            num_scenarios=num_scenarios,
            num_tradeable_scenarios=scenario_set.num_tradeable_scenarios,
            ex_ante_roles=dict(roles),
            expected_net_positions_kwh=dict(scenario_set.expected_net_positions_kwh),
            scenario_role_flip_counts=dict(scenario_set.role_flip_counts),
            num_active_players=num_active,
            active_sellers=active_sellers,
            active_buyers=active_buyers,
            inactive_households=inactive_households,
            num_profiles_evaluated=num_profiles,
            num_deviations_evaluated=total_deviations,
            expected_payoff_table=payoff_table_rows,
            expected_equilibria=[],
            strict_equilibria=[],
            weak_equilibria=[],
            pareto_undominated_equilibria=[],
            selected_equilibrium=None,
            scenario_seed=scenario_set.scenario_seed,
            modeling_metadata={
                "prune_zero_trade": prune_zero_trade,
                "status": "NO_PURE_NASH_EQUILIBRIUM",
            },
        )

    # 3. Pareto Dominance Analysis across full household universe
    n_cands = len(candidate_equilibria)
    undominated_indices: Set[int] = set(range(n_cands))

    for i in range(n_cands):
        pay_i = candidate_equilibria[i].expected_payoffs
        for j in range(n_cands):
            if i == j:
                continue
            pay_j = candidate_equilibria[j].expected_payoffs
            if check_pareto_dominance(pay_j, pay_i, universe, tolerance=tolerance):
                undominated_indices.discard(i)
                break

    final_equilibria: List[StochasticNashRecord] = []
    strict_equilibria: List[StochasticNashRecord] = []
    weak_equilibria: List[StochasticNashRecord] = []
    pareto_undominated: List[StochasticNashRecord] = []

    for idx, rec in enumerate(candidate_equilibria):
        is_undom = idx in undominated_indices
        updated_rec = StochasticNashRecord(
            profile=rec.profile,
            ex_ante_roles=rec.ex_ante_roles,
            expected_payoffs=rec.expected_payoffs,
            expected_traded_kwh=rec.expected_traded_kwh,
            expected_community_welfare_aud=rec.expected_community_welfare_aud,
            expected_vwap_aud_per_kwh=rec.expected_vwap_aud_per_kwh,
            classification=rec.classification,
            is_pareto_undominated=is_undom,
            max_deviation_gain=rec.max_deviation_gain,
            transaction_price_std=rec.transaction_price_std,
        )
        final_equilibria.append(updated_rec)
        if updated_rec.classification == EquilibriumClassification.STRICT:
            strict_equilibria.append(updated_rec)
        else:
            weak_equilibria.append(updated_rec)

        if is_undom:
            pareto_undominated.append(updated_rec)

    # 4. Representative Equilibrium Selection (5-Step Heuristic)
    selected_rec = select_representative_stochastic_equilibrium(
        undominated_equilibria=pareto_undominated,
        active_players=active_players,
        reference_price_aud=reference_price_aud,
        tolerance=tolerance,
    )

    return StochasticStrategicGameResult(
        timestamp=scenario_set.timestamp,
        num_scenarios=num_scenarios,
        num_tradeable_scenarios=scenario_set.num_tradeable_scenarios,
        ex_ante_roles=dict(roles),
        expected_net_positions_kwh=dict(scenario_set.expected_net_positions_kwh),
        scenario_role_flip_counts=dict(scenario_set.role_flip_counts),
        num_active_players=num_active,
        active_sellers=active_sellers,
        active_buyers=active_buyers,
        inactive_households=inactive_households,
        num_profiles_evaluated=num_profiles,
        num_deviations_evaluated=total_deviations,
        expected_payoff_table=payoff_table_rows,
        expected_equilibria=final_equilibria,
        strict_equilibria=strict_equilibria,
        weak_equilibria=weak_equilibria,
        pareto_undominated_equilibria=pareto_undominated,
        selected_equilibrium=selected_rec,
        scenario_seed=scenario_set.scenario_seed,
        modeling_metadata={
            "prune_zero_trade": prune_zero_trade,
            "status": "SUCCESS",
            "reference_price_aud": reference_price_aud,
            "tolerance": tolerance,
        },
    )

