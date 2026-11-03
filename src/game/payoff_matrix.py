"""Normal-form payoff matrix builder for two-household and N-player P2P trading.

Players:
- Player 1: Seller (surplus household, e.g., H001)
  Actions: ['OFFER_P2P', 'EXPORT_GRID']
- Player 2: Buyer (deficit household, e.g., H002)
  Actions: ['ACCEPT_P2P', 'GRID_IMPORT']

N-player extension supports dynamic P2P pricing: the trading price at each
joint action profile is computed from the aggregate supply/demand of the active
trading pool, rather than being a fixed constant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from src.game.utility import HouseholdPayoff, P2PTransaction, compute_household_payoff


@dataclass
class GamePayoffMatrix:
    """Payoff matrix and action metadata for a 2-player normal form game."""

    player1_id: str
    player2_id: str
    actions_p1: List[str]
    actions_p2: List[str]
    payoffs_p1: np.ndarray  # Shape (len(actions_p1), len(actions_p2))
    payoffs_p2: np.ndarray  # Shape (len(actions_p1), len(actions_p2))
    traded_quantities: np.ndarray  # Shape (len(actions_p1), len(actions_p2))
    p2p_price_aud: float
    grid_import_price_aud: float
    grid_export_credit_aud: float
    details: Dict[Tuple[str, str], Tuple[HouseholdPayoff, HouseholdPayoff]]

    def to_dataframe(self) -> pd.DataFrame:
        """Render payoff matrix as a readable DataFrame of (U1, U2) pairs."""
        rows = []
        for i, a1 in enumerate(self.actions_p1):
            for j, a2 in enumerate(self.actions_p2):
                u1 = self.payoffs_p1[i, j]
                u2 = self.payoffs_p2[i, j]
                q = self.traded_quantities[i, j]
                rows.append({
                    f"Action_{self.player1_id}": a1,
                    f"Action_{self.player2_id}": a2,
                    f"Traded_kWh": round(q, 4),
                    f"Utility_{self.player1_id}": round(u1, 4),
                    f"Utility_{self.player2_id}": round(u2, 4),
                    "Payoff_Pair": f"({u1:.4f}, {u2:.4f})",
                })
        return pd.DataFrame(rows)


def build_two_household_payoff_matrix(
    seller_id: str,
    seller_surplus_kwh: float,
    buyer_id: str,
    buyer_deficit_kwh: float,
    grid_import_price_aud: float = 0.30,
    grid_export_credit_aud: float = 0.08,
    p2p_price_aud: Optional[float] = None,
    seller_battery_charged_kwh: float = 0.0,
    seller_battery_discharged_kwh: float = 0.0,
    seller_battery_initial_soc: float = 0.0,
    seller_battery_final_soc: float = 0.0,
    buyer_battery_charged_kwh: float = 0.0,
    buyer_battery_discharged_kwh: float = 0.0,
    buyer_battery_initial_soc: float = 0.0,
    buyer_battery_final_soc: float = 0.0,
    degradation_cost_per_kwh: float = 0.0,
) -> GamePayoffMatrix:
    """Construct a 2x2 normal-form payoff matrix for energy trading.

    Parameters
    ----------
    seller_id : str
        Household ID with surplus solar (e.g. 'H001').
    seller_surplus_kwh : float
        Available solar surplus in kWh (post-battery if battery storage is present).
    buyer_id : str
        Household ID with demand deficit (e.g. 'H002').
    buyer_deficit_kwh : float
        Required grid demand in kWh (post-battery if battery storage is present).
    grid_import_price_aud : float
        Price to import from grid in AUD/kWh.
    grid_export_credit_aud : float
        Feed-in tariff to export to grid in AUD/kWh.
    p2p_price_aud : Optional[float]
        Negotiated P2P price. If None, defaults to mid-market price
        (import_price + export_credit) / 2.
    seller_battery_charged_kwh : float
        Energy charged to seller battery in interval.
    seller_battery_discharged_kwh : float
        Energy discharged from seller battery in interval.
    seller_battery_initial_soc : float
        Seller initial SOC.
    seller_battery_final_soc : float
        Seller final SOC.
    buyer_battery_charged_kwh : float
        Energy charged to buyer battery in interval.
    buyer_battery_discharged_kwh : float
        Energy discharged from buyer battery in interval.
    buyer_battery_initial_soc : float
        Buyer initial SOC.
    buyer_battery_final_soc : float
        Buyer final SOC.
    degradation_cost_per_kwh : float
        Battery degradation cost in AUD/kWh throughput (default 0.0).

    Returns
    -------
    GamePayoffMatrix
        Resolved matrix of payoffs and detailed accounting.
    """
    for name, val in [
        ("seller_surplus_kwh", seller_surplus_kwh),
        ("buyer_deficit_kwh", buyer_deficit_kwh),
        ("grid_import_price_aud", grid_import_price_aud),
        ("grid_export_credit_aud", grid_export_credit_aud),
    ]:
        if not np.isfinite(val):
            raise ValueError(f"Non-finite input detected for {name}: {val}")
        if float(val) < -1e-6:
            raise ValueError(f"{name} must be nonnegative, got {val}")

    if p2p_price_aud is not None:
        if not np.isfinite(p2p_price_aud):
            raise ValueError(f"p2p_price_aud must be finite, got {p2p_price_aud}")
        if float(p2p_price_aud) < -1e-6:
            raise ValueError(f"p2p_price_aud must be nonnegative, got {p2p_price_aud}")

    if seller_id == buyer_id:
        raise ValueError(f"Seller and buyer must be distinct households, got {seller_id}")

    surplus = max(0.0, float(seller_surplus_kwh))
    deficit = max(0.0, float(buyer_deficit_kwh))

    # Mid-market incentive-compatible price
    if p2p_price_aud is None:
        p2p_price = (grid_import_price_aud + grid_export_credit_aud) / 2.0
    else:
        p2p_price = float(p2p_price_aud)

    # Maximum feasible mutually beneficial trade quantity
    max_trade = min(surplus, deficit)

    actions_p1 = ["OFFER_P2P", "EXPORT_GRID"]
    actions_p2 = ["ACCEPT_P2P", "GRID_IMPORT"]

    n1 = len(actions_p1)
    n2 = len(actions_p2)

    payoffs_p1 = np.zeros((n1, n2), dtype=float)
    payoffs_p2 = np.zeros((n1, n2), dtype=float)
    traded_quantities = np.zeros((n1, n2), dtype=float)
    details = {}

    for i, a1 in enumerate(actions_p1):
        for j, a2 in enumerate(actions_p2):
            if a1 == "OFFER_P2P" and a2 == "ACCEPT_P2P":
                # Bilateral agreement
                q_trade = max_trade
            else:
                # Trade fails: seller exports, buyer buys from grid
                q_trade = 0.0

            # Calculate seller payoff
            payoff_seller = compute_household_payoff(
                house_id=seller_id,
                deficit_kwh=0.0,
                surplus_kwh=surplus,
                grid_import_price_aud=grid_import_price_aud,
                grid_export_credit_aud=grid_export_credit_aud,
                p2p_energy_sold_kwh=q_trade,
                p2p_energy_bought_kwh=0.0,
                p2p_price_aud=p2p_price,
                battery_charged_kwh=seller_battery_charged_kwh,
                battery_discharged_kwh=seller_battery_discharged_kwh,
                battery_initial_soc=seller_battery_initial_soc,
                battery_final_soc=seller_battery_final_soc,
                battery_degradation_cost_per_kwh=degradation_cost_per_kwh,
            )

            # Calculate buyer payoff
            payoff_buyer = compute_household_payoff(
                house_id=buyer_id,
                deficit_kwh=deficit,
                surplus_kwh=0.0,
                grid_import_price_aud=grid_import_price_aud,
                grid_export_credit_aud=grid_export_credit_aud,
                p2p_energy_sold_kwh=0.0,
                p2p_energy_bought_kwh=q_trade,
                p2p_price_aud=p2p_price,
                battery_charged_kwh=buyer_battery_charged_kwh,
                battery_discharged_kwh=buyer_battery_discharged_kwh,
                battery_initial_soc=buyer_battery_initial_soc,
                battery_final_soc=buyer_battery_final_soc,
                battery_degradation_cost_per_kwh=degradation_cost_per_kwh,
            )

            payoffs_p1[i, j] = payoff_seller.utility
            payoffs_p2[i, j] = payoff_buyer.utility
            traded_quantities[i, j] = q_trade
            details[(a1, a2)] = (payoff_seller, payoff_buyer)

    return GamePayoffMatrix(
        player1_id=seller_id,
        player2_id=buyer_id,
        actions_p1=actions_p1,
        actions_p2=actions_p2,
        payoffs_p1=payoffs_p1,
        payoffs_p2=payoffs_p2,
        traded_quantities=traded_quantities,
        p2p_price_aud=p2p_price,
        grid_import_price_aud=grid_import_price_aud,
        grid_export_credit_aud=grid_export_credit_aud,
        details=details,
    )


# ---------------------------------------------------------------------------
# N-Player extensions  (battery-aware)
# ---------------------------------------------------------------------------

import itertools
from src.game.pricing import DynamicPricingModel, MidMarketPricing
from src.energy.battery import BatteryStorage, BatteryState as _BatteryState


# ── Battery dispatch helper ──────────────────────────────────────────────────

@dataclass
class BatteryDispatchResult:
    """Per-player outcome of the pre-game battery dispatch step."""

    player_id: str
    initial_soc: float          # SOC before dispatch
    final_soc: float            # SOC after dispatch
    charged_kwh: float          # energy sent INTO battery
    discharged_kwh: float       # energy drawn FROM battery
    net_surplus_kwh: float      # surplus remaining after battery absorbs excess
    net_deficit_kwh: float      # deficit remaining after battery covers shortfall
    raw_surplus_kwh: float      # original surplus before battery
    raw_deficit_kwh: float      # original deficit before battery


def dispatch_battery_pre_game(
    player_id: str,
    raw_surplus_kwh: float,
    raw_deficit_kwh: float,
    battery: Optional[BatteryStorage],
    duration_hours: float = 1.0,
) -> BatteryDispatchResult:
    """Run one-hour battery dispatch for a single player before the P2P game.

    Strategy (greedy priority):
    - If player has **surplus**: charge battery first with excess solar,
      then offer remaining surplus to the P2P pool / grid.
    - If player has **deficit**: discharge battery first to cover demand,
      then meet remaining deficit from P2P pool / grid.

    The battery is mutated in-place (SOC is updated).  Call this once per
    player per hour; the returned ``net_surplus_kwh`` / ``net_deficit_kwh``
    are what enter the game matrix.

    Parameters
    ----------
    player_id : str
    raw_surplus_kwh : float
        Solar surplus before any battery action.
    raw_deficit_kwh : float
        Demand deficit before any battery action.
    battery : Optional[BatteryStorage]
        Battery object (mutated).  Pass ``None`` for no battery.
    duration_hours : float
        Interval length in hours (default 1.0).

    Returns
    -------
    BatteryDispatchResult
    """
    if battery is None:
        return BatteryDispatchResult(
            player_id=player_id,
            initial_soc=0.0, final_soc=0.0,
            charged_kwh=0.0, discharged_kwh=0.0,
            net_surplus_kwh=max(0.0, raw_surplus_kwh),
            net_deficit_kwh=max(0.0, raw_deficit_kwh),
            raw_surplus_kwh=raw_surplus_kwh,
            raw_deficit_kwh=raw_deficit_kwh,
        )

    initial_soc = battery.soc
    charged_kwh = 0.0
    discharged_kwh = 0.0
    net_surplus = max(0.0, raw_surplus_kwh)
    net_deficit = max(0.0, raw_deficit_kwh)

    if net_surplus > 1e-6:
        # Charge battery from surplus
        bstate = battery.step(
            energy_available_to_charge_kwh=net_surplus,
            duration_hours=duration_hours,
        )
        charged_kwh = bstate.charged_kwh
        net_surplus = max(0.0, net_surplus - charged_kwh)

    elif net_deficit > 1e-6:
        # Discharge battery to cover deficit
        bstate = battery.step(
            energy_requested_to_discharge_kwh=net_deficit,
            duration_hours=duration_hours,
        )
        discharged_kwh = bstate.discharged_kwh
        net_deficit = max(0.0, net_deficit - discharged_kwh)

    return BatteryDispatchResult(
        player_id=player_id,
        initial_soc=initial_soc,
        final_soc=battery.soc,
        charged_kwh=charged_kwh,
        discharged_kwh=discharged_kwh,
        net_surplus_kwh=net_surplus,
        net_deficit_kwh=net_deficit,
        raw_surplus_kwh=raw_surplus_kwh,
        raw_deficit_kwh=raw_deficit_kwh,
    )


# ── N-player payoff matrix ───────────────────────────────────────────────────

@dataclass
class NPlayerPayoffMatrix:
    """Payoff matrix for an N-player energy trading game with battery support.

    Each player chooses one of their available actions (``'P2P_TRADE'``,
    ``'GRID_ONLY'``, or ``'SELF_SUFFICIENT'``).  Payoffs are stored as N separate N-dimensional ndarrays,
    one per player, indexed by the joint action profile.

    Battery accounting
    ------------------
    Battery dispatch (charge/discharge) happens **before** the game in a
    deterministic greedy step.  The ``surpluses`` and ``deficits`` stored here
    are the **post-battery net values** that enter the strategic game.  Battery
    statistics (charged/discharged kWh, SOC) are stored per player and passed
    through to ``compute_household_payoff`` so the financial accounting is
    correct.

    Dynamic pricing
    ---------------
    ``p2p_prices_per_profile`` stores the per-profile price; ``p2p_price_aud``
    is the trade-weighted average (kept for backward-compatible display).
    """

    player_ids: List[str]
    actions: List[List[str]]
    payoffs: List[np.ndarray]           # payoffs[i].shape = (n0,…,n_{N-1})
    traded_quantities: np.ndarray
    p2p_prices_per_profile: np.ndarray
    p2p_price_aud: float
    grid_import_price_aud: float
    grid_export_credit_aud: float
    player_surpluses: List[float]       # post-battery net surplus per player
    player_deficits: List[float]        # post-battery net deficit per player
    # Battery dispatch results (one per player; all zeros if no batteries)
    battery_charged_kwh: List[float]
    battery_discharged_kwh: List[float]
    battery_initial_soc: List[float]
    battery_final_soc: List[float]
    battery_degradation_cost_per_kwh: float
    pricing_model_name: str = "MidMarket"


def build_n_player_payoff_matrix(
    player_ids: List[str],
    surpluses_kwh: List[float],
    deficits_kwh: List[float],
    grid_import_price_aud: float = 0.30,
    grid_export_credit_aud: float = 0.08,
    p2p_price_aud: Optional[float] = None,
    pricing_model: Optional[DynamicPricingModel] = None,
    battery_charged_kwh: Optional[List[float]] = None,
    battery_discharged_kwh: Optional[List[float]] = None,
    battery_initial_soc: Optional[List[float]] = None,
    battery_final_soc: Optional[List[float]] = None,
    battery_degradation_cost_per_kwh: float = 0.0,
) -> NPlayerPayoffMatrix:
    """Build a payoff matrix for an N-player peer-to-peer energy trading game.

    Battery accounting
    ------------------
    Battery dispatch happens **before** this function is called.  Pass the
    per-player pre-computed battery statistics via ``battery_charged_kwh``,
    ``battery_discharged_kwh``, ``battery_initial_soc``, ``battery_final_soc``.
    These are forwarded to ``compute_household_payoff`` so the financial
    accounting (degradation cost, SOC trajectory) is correct.  If no lists
    are supplied, all battery fields default to zero (no battery).

    The ``surpluses_kwh`` and ``deficits_kwh`` passed in should already be
    the **post-battery net values** (i.e. output of ``dispatch_battery_pre_game``).

    Dynamic pricing
    ---------------
    When ``pricing_model`` is supplied the P2P price is recomputed for every
    joint action profile from that profile's active trading-pool
    supply/demand.  If ``p2p_price_aud`` is given without a pricing model,
    that fixed price is used (legacy mode).  If both are ``None``, the
    default mid-market price is applied.

    Parameters
    ----------
    player_ids : List[str]
    surpluses_kwh : List[float]
        Post-battery net solar surplus per player.
    deficits_kwh : List[float]
        Post-battery net demand deficit per player.
    grid_import_price_aud : float
    grid_export_credit_aud : float
    p2p_price_aud : Optional[float]
        Fixed P2P price override.
    pricing_model : Optional[DynamicPricingModel]
        Dynamic pricing model; takes precedence over ``p2p_price_aud``.
    battery_charged_kwh : Optional[List[float]]
        Energy charged into each player's battery this interval.
    battery_discharged_kwh : Optional[List[float]]
        Energy discharged from each player's battery this interval.
    battery_initial_soc : Optional[List[float]]
        Battery SOC at start of interval per player.
    battery_final_soc : Optional[List[float]]
        Battery SOC at end of interval per player.
    battery_degradation_cost_per_kwh : float
        Battery wear cost in AUD/kWh throughput.

    Returns
    -------
    NPlayerPayoffMatrix
    """
    N = len(player_ids)
    assert N == len(surpluses_kwh) == len(deficits_kwh), (
        "player_ids, surpluses_kwh, and deficits_kwh must all have the same length"
    )

    surpluses = [max(0.0, float(s)) for s in surpluses_kwh]
    deficits  = [max(0.0, float(d)) for d in deficits_kwh]

    # Battery stats (default to zero if not supplied)
    batt_ch  = list(battery_charged_kwh)     if battery_charged_kwh    is not None else [0.0] * N
    batt_dis = list(battery_discharged_kwh)  if battery_discharged_kwh is not None else [0.0] * N
    batt_i   = list(battery_initial_soc)     if battery_initial_soc    is not None else [0.0] * N
    batt_f   = list(battery_final_soc)       if battery_final_soc      is not None else [0.0] * N

    # Pricing strategy: pricing_model > fixed p2p_price_aud > mid-market
    use_dynamic = pricing_model is not None
    if not use_dynamic:
        _fixed_price = (
            float(p2p_price_aud)
            if p2p_price_aud is not None
            else (grid_import_price_aud + grid_export_credit_aud) / 2.0
        )
        pricing_model = MidMarketPricing()  # for .name() only

    player_actions: List[List[str]] = []
    for k in range(N):
        if surpluses[k] <= 1e-4 and deficits[k] <= 1e-4:
            player_actions.append(["SELF_SUFFICIENT"])
        else:
            player_actions.append(["P2P_TRADE", "GRID_ONLY"])
    shape: Tuple[int, ...] = tuple(len(player_actions[k]) for k in range(N))

    payoff_arrays: List[np.ndarray]  = [np.zeros(shape, dtype=float) for _ in range(N)]
    traded_quantities: np.ndarray    = np.zeros(shape, dtype=float)
    p2p_prices_per_profile: np.ndarray = np.zeros(shape, dtype=float)

    action_index_ranges = [range(len(player_actions[k])) for k in range(N)]

    for profile in itertools.product(*action_index_ranges):
        actions_in_profile = [player_actions[k][profile[k]] for k in range(N)]

        trading_surplus_players = [
            k for k in range(N)
            if actions_in_profile[k] in ("P2P_TRADE", "TRADE") and surpluses[k] > 0.0
        ]
        trading_deficit_players = [
            k for k in range(N)
            if actions_in_profile[k] in ("P2P_TRADE", "TRADE") and deficits[k] > 0.0
        ]

        total_trading_surplus = sum(surpluses[k] for k in trading_surplus_players)
        total_trading_deficit = sum(deficits[k] for k in trading_deficit_players)

        # Dynamic price for this profile
        if use_dynamic:
            profile_price = pricing_model.compute_price(
                total_trading_surplus_kwh=total_trading_surplus,
                total_trading_deficit_kwh=total_trading_deficit,
                grid_import_price_aud=grid_import_price_aud,
                grid_export_credit_aud=grid_export_credit_aud,
            )
        else:
            profile_price = _fixed_price

        p2p_prices_per_profile[profile] = profile_price

        # Trade quantity
        max_trade = (
            min(total_trading_surplus, total_trading_deficit)
            if total_trading_surplus > 0.0 and total_trading_deficit > 0.0
            else 0.0
        )

        p2p_sold   = [0.0] * N
        p2p_bought = [0.0] * N
        if max_trade > 0.0:
            for k in trading_surplus_players:
                p2p_sold[k]   = surpluses[k] / total_trading_surplus * max_trade
            for k in trading_deficit_players:
                p2p_bought[k] = deficits[k]  / total_trading_deficit * max_trade

        # Compute each player's utility — now WITH battery stats
        for k in range(N):
            payoff = compute_household_payoff(
                house_id=player_ids[k],
                deficit_kwh=deficits[k],
                surplus_kwh=surpluses[k],
                grid_import_price_aud=grid_import_price_aud,
                grid_export_credit_aud=grid_export_credit_aud,
                p2p_energy_sold_kwh=p2p_sold[k],
                p2p_energy_bought_kwh=p2p_bought[k],
                p2p_price_aud=profile_price,
                battery_charged_kwh=batt_ch[k],
                battery_discharged_kwh=batt_dis[k],
                battery_initial_soc=batt_i[k],
                battery_final_soc=batt_f[k],
                battery_degradation_cost_per_kwh=battery_degradation_cost_per_kwh,
            )
            payoff_arrays[k][profile] = payoff.utility

        traded_quantities[profile] = max_trade

    # Trade-weighted average price
    nonzero_mask = traded_quantities > 0.0
    avg_price = (
        float(np.average(p2p_prices_per_profile, weights=traded_quantities + 1e-12))
        if nonzero_mask.any()
        else float(p2p_prices_per_profile.mean())
    )

    model_name = pricing_model.name() if pricing_model is not None else "FixedPrice"

    return NPlayerPayoffMatrix(
        player_ids=list(player_ids),
        actions=player_actions,
        payoffs=payoff_arrays,
        traded_quantities=traded_quantities,
        p2p_prices_per_profile=p2p_prices_per_profile,
        p2p_price_aud=avg_price,
        grid_import_price_aud=grid_import_price_aud,
        grid_export_credit_aud=grid_export_credit_aud,
        player_surpluses=surpluses,
        player_deficits=deficits,
        battery_charged_kwh=batt_ch,
        battery_discharged_kwh=batt_dis,
        battery_initial_soc=batt_i,
        battery_final_soc=batt_f,
        battery_degradation_cost_per_kwh=battery_degradation_cost_per_kwh,
        pricing_model_name=model_name,
    )
