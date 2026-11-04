"""N-household energy game runner with dynamic P2P pricing and battery storage.

The game supports:
1. Battery energy storage for each household (SOC limits, charge/discharge power, efficiency)
2. Greedy pre-game battery dispatch (excess solar charges battery first; deficit draws from battery first)
3. Dynamic P2P pricing responding to aggregate trading pool supply/demand
4. Pure-strategy Nash equilibrium and best-response analysis for N players

Usage
-----
    from src.game.game import run_n_player_game, create_default_batteries
    from src.game.pricing import LinearDemandPricing

    batteries = create_default_batteries(player_ids, capacity_kwh=5.0)
    result = run_n_player_game(
        player_ids, raw_surpluses, raw_deficits,
        batteries=batteries,
        pricing_model=LinearDemandPricing(max_pressure=2.0)
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from src.energy.battery import BatteryStorage
from src.game.payoff_matrix import (
    NPlayerPayoffMatrix,
    build_n_player_payoff_matrix,
    dispatch_battery_pre_game,
    BatteryDispatchResult,
    GamePayoffMatrix,
    build_two_household_payoff_matrix,
)
from src.game.nash import (
    NPlayerEquilibriumResult,
    NPlayerNashEquilibrium,
    find_nash_equilibria_n_players,
    EquilibriumAnalysisResult,
    find_pure_nash_equilibria,
)
from src.energy.energy_balance import EnergyBalance
from src.game.best_response import compute_best_responses_n_players, BestResponseDetail
from src.game.pricing import DynamicPricingModel, MidMarketPricing


def create_default_batteries(
    player_ids: List[str],
    capacity_kwh: float = 5.0,
    max_charge_rate_kw: float = 2.5,
    max_discharge_rate_kw: float = 2.5,
    charge_efficiency: float = 0.95,
    discharge_efficiency: float = 0.95,
    min_soc: float = 0.10,
    max_soc: float = 0.90,
    initial_soc: float = 0.50,
) -> Dict[str, BatteryStorage]:
    """Create independent BatteryStorage instances for each household.

    Parameters
    ----------
    player_ids : List[str]
        List of household IDs.
    capacity_kwh : float
        Nominal capacity per household in kWh (default 5.0 kWh).
    max_charge_rate_kw : float
        Max charging power (default 2.5 kW).
    max_discharge_rate_kw : float
        Max discharging power (default 2.5 kW).
    charge_efficiency : float
        One-way charging efficiency (default 0.95).
    discharge_efficiency : float
        One-way discharging efficiency (default 0.95).
    min_soc : float
        Minimum state of charge allowable (default 0.10).
    max_soc : float
        Maximum state of charge allowable (default 0.90).
    initial_soc : float
        Starting state of charge (default 0.50).

    Returns
    -------
    Dict[str, BatteryStorage]
    """
    return {
        pid: BatteryStorage(
            capacity_kwh=capacity_kwh,
            max_charge_rate_kw=max_charge_rate_kw,
            max_discharge_rate_kw=max_discharge_rate_kw,
            charge_efficiency=charge_efficiency,
            discharge_efficiency=discharge_efficiency,
            min_soc=min_soc,
            max_soc=max_soc,
            initial_soc=initial_soc,
        )
        for pid in player_ids
    }


@dataclass
class NPlayerGameResult:
    """Result of running the N-player energy game with battery support."""

    timestamp: Optional[pd.Timestamp]
    player_ids: List[str]

    # ── Per-player energy info (post-battery net values that enter P2P game) ──
    surpluses_kwh: Dict[str, float]     # {player_id: net surplus after battery}
    deficits_kwh: Dict[str, float]      # {player_id: net deficit after battery}

    # ── Pre-battery raw energy info ──────────────────────────────────────────
    raw_surpluses_kwh: Dict[str, float] = field(default_factory=dict)
    raw_deficits_kwh: Dict[str, float] = field(default_factory=dict)

    # ── Battery diagnostics ──────────────────────────────────────────────────
    battery_charged_kwh: Dict[str, float] = field(default_factory=dict)
    battery_discharged_kwh: Dict[str, float] = field(default_factory=dict)
    battery_initial_soc: Dict[str, float] = field(default_factory=dict)
    battery_final_soc: Dict[str, float] = field(default_factory=dict)
    battery_degradation_cost_per_kwh: float = 0.0

    # ── Pricing info ─────────────────────────────────────────────────────────
    p2p_price_aud: float = 0.19         # avg / effective price at equilibrium
    grid_import_price_aud: float = 0.30
    grid_export_credit_aud: float = 0.08
    pricing_model_name: str = "MidMarket"

    # ── Raw game objects ─────────────────────────────────────────────────────
    matrix: Optional[NPlayerPayoffMatrix] = None
    equilibrium_result: Optional[NPlayerEquilibriumResult] = None
    best_responses: Dict[str, Dict[tuple, BestResponseDetail]] = field(default_factory=dict)

    # ── Financial outcomes ───────────────────────────────────────────────────
    baseline_costs_aud: Dict[str, float] = field(default_factory=dict)
    baseline_benefits_aud: Dict[str, float] = field(default_factory=dict)
    game_costs_aud: Dict[str, float] = field(default_factory=dict)
    game_benefits_aud: Dict[str, float] = field(default_factory=dict)
    savings_aud: Dict[str, float] = field(default_factory=dict)
    total_community_savings_aud: float = 0.0
    has_equilibrium: bool = False
    selected_actions: Dict[str, str] = field(default_factory=dict)

    # ── Dynamic pricing diagnostics ──────────────────────────────────────────
    equilibrium_p2p_price_aud: Optional[float] = None
    equilibrium_demand_pressure: Optional[float] = None

    def to_summary_dataframe(self) -> pd.DataFrame:
        """Return a tidy DataFrame with one row per player plus a community row."""
        rows = []
        for pid in self.player_ids:
            rows.append({
                "player_id":              pid,
                "raw_surplus_kwh":        round(self.raw_surpluses_kwh.get(pid, self.surpluses_kwh.get(pid, 0.0)), 4),
                "raw_deficit_kwh":        round(self.raw_deficits_kwh.get(pid, self.deficits_kwh.get(pid, 0.0)), 4),
                "battery_charged_kwh":    round(self.battery_charged_kwh.get(pid, 0.0), 4),
                "battery_discharged_kwh": round(self.battery_discharged_kwh.get(pid, 0.0), 4),
                "battery_soc":            round(self.battery_final_soc.get(pid, 0.0), 4),
                "net_surplus_kwh":        round(self.surpluses_kwh.get(pid, 0.0), 4),
                "net_deficit_kwh":        round(self.deficits_kwh.get(pid, 0.0), 4),
                "baseline_cost_aud":      round(self.baseline_costs_aud.get(pid, 0.0), 4),
                "game_cost_aud":          round(self.game_costs_aud.get(pid, 0.0), 4),
                "saving_aud":             round(self.savings_aud.get(pid, 0.0), 4),
                "selected_action":        self.selected_actions.get(pid, ""),
                "utility_at_eq":          round(
                    self.equilibrium_result.selected_equilibrium.utilities.get(pid, 0.0)
                    if self.equilibrium_result and self.equilibrium_result.selected_equilibrium else 0.0, 4
                ),
                "p2p_price_aud":          round(self.equilibrium_p2p_price_aud or self.p2p_price_aud, 4),
                "pricing_model":          self.pricing_model_name,
            })
        rows.append({
            "player_id":              "COMMUNITY_TOTAL",
            "raw_surplus_kwh":        round(sum(self.raw_surpluses_kwh.values()) if self.raw_surpluses_kwh else sum(self.surpluses_kwh.values()), 4),
            "raw_deficit_kwh":        round(sum(self.raw_deficits_kwh.values()) if self.raw_deficits_kwh else sum(self.deficits_kwh.values()), 4),
            "battery_charged_kwh":    round(sum(self.battery_charged_kwh.values()), 4),
            "battery_discharged_kwh": round(sum(self.battery_discharged_kwh.values()), 4),
            "battery_soc":            round(float(np.mean(list(self.battery_final_soc.values()))) if self.battery_final_soc else 0.0, 4),
            "net_surplus_kwh":        round(sum(self.surpluses_kwh.values()), 4),
            "net_deficit_kwh":        round(sum(self.deficits_kwh.values()), 4),
            "baseline_cost_aud":      round(sum(self.baseline_costs_aud.values()), 4),
            "game_cost_aud":          round(sum(self.game_costs_aud.values()), 4),
            "saving_aud":             round(self.total_community_savings_aud, 4),
            "selected_action":        "COORDINATED" if self.has_equilibrium else "NO_EQUILIBRIUM",
            "utility_at_eq":          round(
                self.equilibrium_result.selected_equilibrium.total_welfare
                if self.equilibrium_result and self.equilibrium_result.selected_equilibrium else 0.0, 4
            ),
            "p2p_price_aud":          round(self.equilibrium_p2p_price_aud or self.p2p_price_aud, 4),
            "pricing_model":          self.pricing_model_name,
        })
        return pd.DataFrame(rows)


def run_n_player_game(
    player_ids: List[str],
    surpluses_kwh: List[float],
    deficits_kwh: List[float],
    grid_import_price_aud: float = 0.30,
    grid_export_credit_aud: float = 0.08,
    p2p_price_aud: Optional[float] = None,
    pricing_model: Optional[DynamicPricingModel] = None,
    timestamp: Optional[pd.Timestamp] = None,
    batteries: Optional[Union[Dict[str, BatteryStorage], List[Optional[BatteryStorage]]]] = None,
    battery_degradation_cost_per_kwh: float = 0.0,
    duration_hours: float = 1.0,
    battery_charged_kwh: Optional[List[float]] = None,
    battery_discharged_kwh: Optional[List[float]] = None,
    battery_initial_soc: Optional[List[float]] = None,
    battery_final_soc: Optional[List[float]] = None,
) -> NPlayerGameResult:
    """Run an N-player energy trading game with battery storage and dynamic P2P pricing.

    Parameters
    ----------
    player_ids : List[str]
        IDs for all players, e.g. ``['H001', 'H002', 'H003', 'H004', 'H005']``.
    surpluses_kwh : List[float]
        Solar surplus for each player. If batteries are passed, this is treated
        as the raw solar surplus before battery charging.
    deficits_kwh : List[float]
        Energy deficit for each player. If batteries are passed, this is treated
        as the raw demand deficit before battery discharging.
    grid_import_price_aud : float
        Grid retail price in AUD/kWh (default 0.30).
    grid_export_credit_aud : float
        Grid feed-in tariff in AUD/kWh (default 0.08).
    p2p_price_aud : Optional[float]
        Fixed P2P price override.
    pricing_model : Optional[DynamicPricingModel]
        Dynamic pricing model (e.g. LinearDemandPricing, ElasticDemandPricing).
    timestamp : Optional[pd.Timestamp]
        Hour timestamp label.
    batteries : Optional[Union[Dict[str, BatteryStorage], List[Optional[BatteryStorage]]]]
        Battery instances for each household. If supplied, pre-game battery
        dispatch is automatically executed (excess solar charges battery; deficit
        discharges battery), and net surplus/deficit are passed into the game.
    battery_degradation_cost_per_kwh : float
        Battery wear cost in AUD/kWh throughput.
    duration_hours : float
        Timestep length (default 1.0 hr).
    battery_charged_kwh, battery_discharged_kwh, battery_initial_soc, battery_final_soc : Optional[List[float]]
        Explicit battery statistics if pre-dispatched externally.

    Returns
    -------
    NPlayerGameResult
    """
    assert len(player_ids) == len(surpluses_kwh) == len(deficits_kwh), (
        "player_ids, surpluses_kwh, deficits_kwh must have the same length"
    )
    N = len(player_ids)

    raw_surpluses = [max(0.0, float(s)) for s in surpluses_kwh]
    raw_deficits = [max(0.0, float(d)) for d in deficits_kwh]

    # ── 1. Battery pre-game dispatch ─────────────────────────────────────────
    if batteries is not None:
        if isinstance(batteries, dict):
            batt_list = [batteries.get(pid) for pid in player_ids]
        else:
            batt_list = list(batteries)
            assert len(batt_list) == N, "batteries list must match player_ids length"

        net_surpluses = []
        net_deficits = []
        b_ch = []
        b_dis = []
        b_init_soc = []
        b_fin_soc = []

        for i, pid in enumerate(player_ids):
            disp = dispatch_battery_pre_game(
                player_id=pid,
                raw_surplus_kwh=raw_surpluses[i],
                raw_deficit_kwh=raw_deficits[i],
                battery=batt_list[i],
                duration_hours=duration_hours,
            )
            net_surpluses.append(disp.net_surplus_kwh)
            net_deficits.append(disp.net_deficit_kwh)
            b_ch.append(disp.charged_kwh)
            b_dis.append(disp.discharged_kwh)
            b_init_soc.append(disp.initial_soc)
            b_fin_soc.append(disp.final_soc)
    else:
        net_surpluses = raw_surpluses
        net_deficits = raw_deficits
        b_ch = list(battery_charged_kwh) if battery_charged_kwh is not None else [0.0] * N
        b_dis = list(battery_discharged_kwh) if battery_discharged_kwh is not None else [0.0] * N
        b_init_soc = list(battery_initial_soc) if battery_initial_soc is not None else [0.0] * N
        b_fin_soc = list(battery_final_soc) if battery_final_soc is not None else [0.0] * N

    # ── 2. Build payoff matrix ───────────────────────────────────────────────
    matrix = build_n_player_payoff_matrix(
        player_ids=player_ids,
        surpluses_kwh=net_surpluses,
        deficits_kwh=net_deficits,
        grid_import_price_aud=grid_import_price_aud,
        grid_export_credit_aud=grid_export_credit_aud,
        p2p_price_aud=p2p_price_aud,
        pricing_model=pricing_model,
        battery_charged_kwh=b_ch,
        battery_discharged_kwh=b_dis,
        battery_initial_soc=b_init_soc,
        battery_final_soc=b_fin_soc,
        battery_degradation_cost_per_kwh=battery_degradation_cost_per_kwh,
    )

    # ── 3. Solve for equilibria and best responses ───────────────────────────
    eq_result = find_nash_equilibria_n_players(matrix)
    br_result = compute_best_responses_n_players(matrix)

    # ── 4. Baseline costs (GRID_ONLY for everyone) ───────────────────────────
    baseline_utilities = eq_result.baseline_utilities
    baseline_costs = {pid: -u for pid, u in baseline_utilities.items()}

    # ── 5. Equilibrium outcomes ──────────────────────────────────────────────
    if eq_result.selected_equilibrium is not None:
        eq = eq_result.selected_equilibrium
        game_utilities   = eq.utilities
        raw_actions      = eq.action_profile
        has_eq           = True

        # Extract price and demand-pressure at the selected equilibrium profile
        eq_idx_tuple = tuple(eq.action_indices[pid] for pid in player_ids)
        eq_p2p_price = float(matrix.p2p_prices_per_profile[eq_idx_tuple])

        # Demand pressure from active trading pool post-battery
        trading_surpluses = [
            net_surpluses[i] for i, pid in enumerate(player_ids)
            if raw_actions[pid] in ("P2P_TRADE", "TRADE") and net_surpluses[i] > 0
        ]
        trading_deficits = [
            net_deficits[i] for i, pid in enumerate(player_ids)
            if raw_actions[pid] in ("P2P_TRADE", "TRADE") and net_deficits[i] > 0
        ]
        ts_total = sum(trading_surpluses)
        td_total = sum(trading_deficits)
        eq_demand_pressure = td_total / (ts_total + 1e-9) if ts_total > 1e-9 else None

        # Equilibrium traded energy
        eq_traded_q = float(matrix.traded_quantities[eq_idx_tuple])

        # Resolve explicit operational action for each household:
        # 1. "SELF_SUFFICIENT": enough local energy (solar + battery) to meet demand, no need to buy from anyone
        # 2. "P2P_TRADE": actively made a peer-to-peer trade with community members
        # 3. "GRID_ONLY": buys/sells electricity directly from the grid
        selected_actions = {}
        for i, pid in enumerate(player_ids):
            if net_surpluses[i] <= 1e-4 and net_deficits[i] <= 1e-4:
                selected_actions[pid] = "SELF_SUFFICIENT"
            elif eq_traded_q > 1e-4 and raw_actions[pid] in ("P2P_TRADE", "TRADE") and (
                (net_surpluses[i] > 1e-4 and ts_total > 1e-4) or
                (net_deficits[i] > 1e-4 and td_total > 1e-4)
            ):
                selected_actions[pid] = "P2P_TRADE"
            else:
                selected_actions[pid] = "GRID_ONLY"
    else:
        game_utilities      = baseline_utilities
        selected_actions    = {
            pid: "SELF_SUFFICIENT" if net_surpluses[i] <= 1e-4 and net_deficits[i] <= 1e-4 else "GRID_ONLY"
            for i, pid in enumerate(player_ids)
        }
        has_eq              = False
        eq_p2p_price        = matrix.p2p_price_aud
        eq_demand_pressure  = None

    game_costs    = {pid: -u for pid, u in game_utilities.items()}
    savings       = {pid: baseline_costs[pid] - game_costs[pid] for pid in player_ids}
    total_savings = sum(savings.values())

    return NPlayerGameResult(
        timestamp=timestamp,
        player_ids=player_ids,
        surpluses_kwh=dict(zip(player_ids, net_surpluses)),
        deficits_kwh=dict(zip(player_ids, net_deficits)),
        raw_surpluses_kwh=dict(zip(player_ids, raw_surpluses)),
        raw_deficits_kwh=dict(zip(player_ids, raw_deficits)),
        battery_charged_kwh=dict(zip(player_ids, b_ch)),
        battery_discharged_kwh=dict(zip(player_ids, b_dis)),
        battery_initial_soc=dict(zip(player_ids, b_init_soc)),
        battery_final_soc=dict(zip(player_ids, b_fin_soc)),
        battery_degradation_cost_per_kwh=battery_degradation_cost_per_kwh,
        p2p_price_aud=matrix.p2p_price_aud,
        grid_import_price_aud=grid_import_price_aud,
        grid_export_credit_aud=grid_export_credit_aud,
        pricing_model_name=matrix.pricing_model_name,
        matrix=matrix,
        equilibrium_result=eq_result,
        best_responses=br_result,
        baseline_costs_aud=baseline_costs,
        baseline_benefits_aud={pid: max(0.0, -baseline_costs[pid]) for pid in player_ids},
        game_costs_aud=game_costs,
        game_benefits_aud={pid: max(0.0, -game_costs[pid]) for pid in player_ids},
        savings_aud=savings,
        total_community_savings_aud=total_savings,
        has_equilibrium=has_eq,
        selected_actions=selected_actions,
        equilibrium_p2p_price_aud=eq_p2p_price,
        equilibrium_demand_pressure=eq_demand_pressure,
    )


# ---------------------------------------------------------------------------
# 2-Player Backward Compatibility
# ---------------------------------------------------------------------------

@dataclass
class GameComparisonResult:
    """Comparison between uncoordinated baseline and game equilibrium."""

    timestamp: Optional[pd.Timestamp]
    player1_id: str
    player2_id: str
    player1_surplus_kwh: float
    player2_deficit_kwh: float
    energy_traded_kwh: float
    p2p_price_aud: float
    baseline_cost_p1_aud: float
    baseline_cost_p2_aud: float
    baseline_total_cost_aud: float
    game_cost_p1_aud: float
    game_cost_p2_aud: float
    game_total_cost_aud: float
    saving_p1_aud: float
    saving_p2_aud: float
    total_community_savings_aud: float
    selected_strategy_p1: str
    selected_strategy_p2: str
    is_nash_equilibrium: bool
    is_strict_equilibrium: bool
    battery_p1_charged_kwh: float = 0.0
    battery_p1_discharged_kwh: float = 0.0
    battery_p1_initial_soc: float = 0.0
    battery_p1_final_soc: float = 0.0
    battery_p2_charged_kwh: float = 0.0
    battery_p2_discharged_kwh: float = 0.0
    battery_p2_initial_soc: float = 0.0
    battery_p2_final_soc: float = 0.0

    def to_dataframe(self) -> pd.DataFrame:
        """Present comparison as a clear summary table."""
        return pd.DataFrame([
            {
                "Household": self.player1_id,
                "Role": "Seller (Surplus)",
                "Energy_Available_kWh": round(self.player1_surplus_kwh, 4),
                "Baseline_Cost_AUD": round(self.baseline_cost_p1_aud, 4),
                "Game_Cost_AUD": round(self.game_cost_p1_aud, 4),
                "Cost_Savings_AUD": round(self.saving_p1_aud, 4),
                "Action": self.selected_strategy_p1,
            },
            {
                "Household": self.player2_id,
                "Role": "Buyer (Deficit)",
                "Energy_Available_kWh": round(self.player2_deficit_kwh, 4),
                "Baseline_Cost_AUD": round(self.baseline_cost_p2_aud, 4),
                "Game_Cost_AUD": round(self.game_cost_p2_aud, 4),
                "Cost_Savings_AUD": round(self.saving_p2_aud, 4),
                "Action": self.selected_strategy_p2,
            },
            {
                "Household": "TOTAL_COMMUNITY",
                "Role": "Microgrid Aggregation",
                "Energy_Available_kWh": round(self.energy_traded_kwh, 4),
                "Baseline_Cost_AUD": round(self.baseline_total_cost_aud, 4),
                "Game_Cost_AUD": round(self.game_total_cost_aud, 4),
                "Cost_Savings_AUD": round(self.total_community_savings_aud, 4),
                "Action": "COORDINATED_EQUILIBRIUM" if self.is_nash_equilibrium else "NO_EQUILIBRIUM",
            },
        ])


def run_two_household_game(
    balance_p1: EnergyBalance,
    balance_p2: EnergyBalance,
    grid_import_price_aud: float = 0.30,
    grid_export_credit_aud: float = 0.08,
    p2p_price_aud: Optional[float] = None,
) -> Tuple[GamePayoffMatrix, EquilibriumAnalysisResult, GameComparisonResult]:
    """Execute a 2-household energy trading game from energy balances."""
    seller = balance_p1 if balance_p1.surplus_kwh >= balance_p2.surplus_kwh else balance_p2
    buyer = balance_p2 if seller == balance_p1 else balance_p1

    s_ch = getattr(seller, "solar_to_battery_kwh", 0.0)
    s_dis = getattr(seller, "battery_to_demand_kwh", 0.0)
    s_isoc = getattr(seller, "battery_initial_soc", 0.0)
    s_fsoc = getattr(seller, "battery_final_soc", 0.0)

    b_ch = getattr(buyer, "solar_to_battery_kwh", 0.0)
    b_dis = getattr(buyer, "battery_to_demand_kwh", 0.0)
    b_isoc = getattr(buyer, "battery_initial_soc", 0.0)
    b_fsoc = getattr(buyer, "battery_final_soc", 0.0)

    matrix = build_two_household_payoff_matrix(
        seller_id=seller.house_id,
        seller_surplus_kwh=seller.surplus_kwh,
        buyer_id=buyer.house_id,
        buyer_deficit_kwh=buyer.deficit_kwh,
        grid_import_price_aud=grid_import_price_aud,
        grid_export_credit_aud=grid_export_credit_aud,
        p2p_price_aud=p2p_price_aud,
        seller_battery_charged_kwh=s_ch,
        seller_battery_discharged_kwh=s_dis,
        seller_battery_initial_soc=s_isoc,
        seller_battery_final_soc=s_fsoc,
        buyer_battery_charged_kwh=b_ch,
        buyer_battery_discharged_kwh=b_dis,
        buyer_battery_initial_soc=b_isoc,
        buyer_battery_final_soc=b_fsoc,
    )

    eq_result = find_pure_nash_equilibria(matrix)

    base_u_seller, base_u_buyer = eq_result.baseline_utilities
    base_cost_seller = -base_u_seller
    base_cost_buyer = -base_u_buyer

    if eq_result.selected_equilibrium is not None:
        eq = eq_result.selected_equilibrium
        game_cost_seller = -eq.utility_player1
        game_cost_buyer = -eq.utility_player2
        trade_q = eq.traded_energy_kwh
        act_seller = eq.action_player1
        act_buyer = eq.action_player2
        is_nash = True
        is_strict = eq.is_strict
    else:
        game_cost_seller = base_cost_seller
        game_cost_buyer = base_cost_buyer
        trade_q = 0.0
        act_seller = "NO_EQUILIBRIUM"
        act_buyer = "NO_EQUILIBRIUM"
        is_nash = False
        is_strict = False

    comp = GameComparisonResult(
        timestamp=balance_p1.timestamp,
        player1_id=seller.house_id,
        player2_id=buyer.house_id,
        player1_surplus_kwh=seller.surplus_kwh,
        player2_deficit_kwh=buyer.deficit_kwh,
        energy_traded_kwh=trade_q,
        p2p_price_aud=matrix.p2p_price_aud,
        baseline_cost_p1_aud=base_cost_seller,
        baseline_cost_p2_aud=base_cost_buyer,
        baseline_total_cost_aud=base_cost_seller + base_cost_buyer,
        game_cost_p1_aud=game_cost_seller,
        game_cost_p2_aud=game_cost_buyer,
        game_total_cost_aud=game_cost_seller + game_cost_buyer,
        saving_p1_aud=base_cost_seller - game_cost_seller,
        saving_p2_aud=base_cost_buyer - game_cost_buyer,
        total_community_savings_aud=(base_cost_seller + base_cost_buyer) - (game_cost_seller + game_cost_buyer),
        selected_strategy_p1=act_seller,
        selected_strategy_p2=act_buyer,
        is_nash_equilibrium=is_nash,
        is_strict_equilibrium=is_strict,
        battery_p1_charged_kwh=s_ch,
        battery_p1_discharged_kwh=s_dis,
        battery_p1_initial_soc=s_isoc,
        battery_p1_final_soc=s_fsoc,
        battery_p2_charged_kwh=b_ch,
        battery_p2_discharged_kwh=b_dis,
        battery_p2_initial_soc=b_isoc,
        battery_p2_final_soc=b_fsoc,
    )

    return matrix, eq_result, comp
