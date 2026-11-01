"""Phase 8B.1: Price-Only Strategic Double-Auction Market Engine.

Implements an ex-post perfect-information analytical benchmark market:
1. Dynamic household role assignment based on post-battery physical positions:
   n_i = (D_i + C_i) - (S_i + B_i)
   s_i = max(0, -n_i)  [available seller surplus]
   d_i = max(0, n_i)   [available buyer deficit]
2. Strict discrete price grid validation:
   P = {0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30} AUD/kWh
3. Continuous double-auction matching:
   - Sellers ordered by lowest ask first, tie-break by house_id
   - Buyers ordered by highest bid first, tie-break by house_id
   - Overlap execution condition: b_j^bid >= a_i^ask
   - Midpoint transaction pricing: p_ij = (a_i^ask + b_j^bid) / 2
4. Exact deterministic pro-rata volume rationing for tied price levels:
   q_i^alloc = Q_trade * (s_i^rem / sum s_k^rem)
   q_j^alloc = Q_trade * (d_j^rem / sum d_k^rem)
   q_ij = (q_i^alloc * q_j^alloc) / Q_trade
5. Transaction-level financial accounting and conservation invariants:
   - Energy conservation: sum q_i^sold == sum q_j^bought == Q_P2P
   - Bilateral financial balance: sum Revenue_i == sum Payment_j
   - Community economic welfare identity: Delta W == 0.22 * Q_P2P
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import numpy as np
import pandas as pd


# Exact allowed strategic price grid (AUD/kWh)
STRATEGIC_PRICE_GRID: Tuple[float, ...] = (0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30)
DEFAULT_GRID_IMPORT_TARIFF_AUD: float = 0.30
DEFAULT_GRID_EXPORT_CREDIT_AUD: float = 0.08
DEFAULT_GRID_SPREAD_MARKUP_AUD: float = DEFAULT_GRID_IMPORT_TARIFF_AUD - DEFAULT_GRID_EXPORT_CREDIT_AUD  # 0.22
DEFAULT_NUMERICAL_TOLERANCE: float = 1e-6


class MarketRole(str, Enum):
    """Participant role in the peer-to-peer double-auction market."""

    SELLER = "seller"
    BUYER = "buyer"
    INACTIVE = "inactive"


def validate_price_grid(
    price_grid: Sequence[float],
    grid_export_credit_aud: float = DEFAULT_GRID_EXPORT_CREDIT_AUD,
    grid_import_tariff_aud: float = DEFAULT_GRID_IMPORT_TARIFF_AUD,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
) -> Tuple[float, ...]:
    """Validate that price grid is non-empty, finite, strictly increasing, and within bounds.

    Parameters
    ----------
    price_grid : Sequence[float]
        Discrete price levels.
    grid_export_credit_aud : float
        Lower economic bound (export credit).
    grid_import_tariff_aud : float
        Upper economic bound (retail import tariff).
    tolerance : float
        Numerical tolerance.

    Returns
    -------
    Tuple[float, ...]
        Validated, immutable price grid tuple.
    """
    if not isinstance(price_grid, (list, tuple, np.ndarray)) or len(price_grid) == 0:
        raise ValueError("price_grid must be a non-empty sequence of floats.")

    grid_tuple = tuple(float(p) for p in price_grid)
    for idx, p in enumerate(grid_tuple):
        if not np.isfinite(p):
            raise ValueError(f"Non-finite price in price_grid at index {idx}: {p}")
        if p < grid_export_credit_aud - tolerance or p > grid_import_tariff_aud + tolerance:
            raise ValueError(
                f"Price grid element {p} at index {idx} is outside commercial tariff bounds "
                f"[{grid_export_credit_aud}, {grid_import_tariff_aud}]."
            )

    for i in range(len(grid_tuple) - 1):
        if grid_tuple[i + 1] <= grid_tuple[i] + tolerance:
            raise ValueError(
                f"price_grid must be strictly increasing: element {i} ({grid_tuple[i]}) "
                f">= element {i + 1} ({grid_tuple[i + 1]})."
            )

    return grid_tuple


def validate_market_configuration(
    grid_import_tariff_aud: float,
    grid_export_credit_aud: float,
    tolerance: float,
    price_grid: Sequence[float],
) -> Tuple[float, ...]:
    """Validate global market clearing parameters and price grid.

    Parameters
    ----------
    grid_import_tariff_aud : float
        Retail grid import tariff (AUD/kWh).
    grid_export_credit_aud : float
        Solar export feed-in credit (AUD/kWh).
    tolerance : float
        Numerical zero threshold (kWh/AUD).
    price_grid : Sequence[float]
        Admissible discrete strategic bidding price grid.

    Returns
    -------
    Tuple[float, ...]
        Validated immutable price grid.

    Raises
    ------
    ValueError
        If any market parameter violates physical/economic feasibility.
    """
    if not np.isfinite(grid_import_tariff_aud):
        raise ValueError(f"grid_import_tariff_aud must be finite, got {grid_import_tariff_aud}")
    if grid_import_tariff_aud < 0.0:
        raise ValueError(f"grid_import_tariff_aud must be nonnegative, got {grid_import_tariff_aud}")

    if not np.isfinite(grid_export_credit_aud):
        raise ValueError(f"grid_export_credit_aud must be finite, got {grid_export_credit_aud}")
    if grid_export_credit_aud < 0.0:
        raise ValueError(f"grid_export_credit_aud must be nonnegative, got {grid_export_credit_aud}")

    if grid_import_tariff_aud < grid_export_credit_aud:
        raise ValueError(
            f"grid_import_tariff_aud ({grid_import_tariff_aud}) cannot be less than "
            f"grid_export_credit_aud ({grid_export_credit_aud})."
        )

    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError(f"tolerance must be strictly positive and finite, got {tolerance}")

    return validate_price_grid(
        price_grid=price_grid,
        grid_export_credit_aud=grid_export_credit_aud,
        grid_import_tariff_aud=grid_import_tariff_aud,
        tolerance=tolerance,
    )


def is_valid_strategic_price(
    price: float,
    price_grid: Sequence[float] = STRATEGIC_PRICE_GRID,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
) -> bool:
    """Check if price belongs to the discrete strategic price grid."""
    if not np.isfinite(price):
        return False
    return any(abs(price - p_allowed) <= tolerance for p_allowed in price_grid)


def compute_physical_net_position(
    demand_kwh: float,
    battery_charge_kwh: float,
    solar_generation_kwh: float,
    battery_discharge_kwh: float,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
) -> Tuple[float, float, float]:
    """Calculate post-battery net meter flow, surplus, and deficit.

    Formula:
        net_flow = (demand + battery_charge) - (solar_generation + battery_discharge)
        surplus = max(0.0, -net_flow)
        deficit = max(0.0, net_flow)

    Parameters
    ----------
    demand_kwh : float
        Actual electrical consumption load (kWh).
    battery_charge_kwh : float
        Electrical energy delivered into battery to charge (kWh).
    solar_generation_kwh : float
        Actual rooftop solar PV generation (kWh).
    battery_discharge_kwh : float
        Electrical energy supplied by battery discharge (kWh).
    tolerance : float
        Numerical zero threshold (default 1e-6 kWh).

    Returns
    -------
    Tuple[float, float, float]
        (net_flow_kwh, surplus_kwh, deficit_kwh)
    """
    for name, val in [
        ("demand_kwh", demand_kwh),
        ("battery_charge_kwh", battery_charge_kwh),
        ("solar_generation_kwh", solar_generation_kwh),
        ("battery_discharge_kwh", battery_discharge_kwh),
    ]:
        if not np.isfinite(val):
            raise ValueError(f"Non-finite input for {name}: {val}")
        if float(val) < -tolerance:
            raise ValueError(f"{name} must be nonnegative, got {val}")

    net_flow = (float(demand_kwh) + float(battery_charge_kwh)) - (
        float(solar_generation_kwh) + float(battery_discharge_kwh)
    )

    if net_flow < -tolerance:
        surplus = -net_flow
        deficit = 0.0
    elif net_flow > tolerance:
        surplus = 0.0
        deficit = net_flow
    else:
        net_flow = 0.0
        surplus = 0.0
        deficit = 0.0

    return net_flow, surplus, deficit


@dataclass(frozen=True)
class MarketOrder:
    """Represents a validated strategic double-auction market order.

    Attributes:
        household_id: Unique household identifier (e.g. 'H001').
        role: MarketRole ('seller' or 'buyer').
        price_aud_per_kwh: Strategic ask (for seller) or bid (for buyer).
        quantity_kwh: Available physical surplus (seller) or deficit (buyer).
        allowed_price_grid: Optional custom price grid. If None, uses STRATEGIC_PRICE_GRID.
    """

    household_id: str
    role: MarketRole
    price_aud_per_kwh: float
    quantity_kwh: float
    allowed_price_grid: Optional[Tuple[float, ...]] = None

    def __post_init__(self) -> None:
        if not isinstance(self.household_id, str) or not self.household_id.strip():
            raise ValueError(f"Invalid household_id: {self.household_id!r}")

        if isinstance(self.role, str):
            object.__setattr__(self, "role", MarketRole(self.role))

        if self.role not in (MarketRole.SELLER, MarketRole.BUYER):
            raise ValueError(
                f"Active market order must have role SELLER or BUYER, got {self.role}."
            )

        if not np.isfinite(self.quantity_kwh):
            raise ValueError(f"quantity_kwh must be finite, got {self.quantity_kwh}")
        if self.quantity_kwh < -DEFAULT_NUMERICAL_TOLERANCE:
            raise ValueError(f"quantity_kwh must be nonnegative, got {self.quantity_kwh}")

        object.__setattr__(self, "quantity_kwh", max(0.0, float(self.quantity_kwh)))

        if not np.isfinite(self.price_aud_per_kwh):
            raise ValueError(f"price_aud_per_kwh must be finite, got {self.price_aud_per_kwh}")

        if self.allowed_price_grid is not None:
            grid = validate_price_grid(self.allowed_price_grid)
            object.__setattr__(self, "allowed_price_grid", grid)
        else:
            grid = STRATEGIC_PRICE_GRID

        if not any(abs(self.price_aud_per_kwh - p_allowed) <= DEFAULT_NUMERICAL_TOLERANCE for p_allowed in grid):
            raise ValueError(
                f"Submitted price {self.price_aud_per_kwh} for household {self.household_id} "
                f"does not belong to allowed strategic price grid {grid}."
            )

        object.__setattr__(self, "price_aud_per_kwh", float(self.price_aud_per_kwh))


@dataclass(frozen=True)
class StrategicTransaction:
    """Individual cleared bilateral transaction in the strategic double auction."""

    transaction_id: str
    seller_id: str
    buyer_id: str
    seller_ask_aud_per_kwh: float
    buyer_bid_aud_per_kwh: float
    price_aud_per_kwh: float
    traded_energy_kwh: float
    seller_revenue_aud: float
    buyer_payment_aud: float

    def __post_init__(self) -> None:
        if self.seller_id == self.buyer_id:
            raise ValueError(f"Self-trading prohibited: seller={self.seller_id}, buyer={self.buyer_id}")
        if self.traded_energy_kwh < -DEFAULT_NUMERICAL_TOLERANCE:
            raise ValueError(f"traded_energy_kwh must be nonnegative, got {self.traded_energy_kwh}")
        if self.price_aud_per_kwh < -DEFAULT_NUMERICAL_TOLERANCE:
            raise ValueError(f"price_aud_per_kwh must be nonnegative, got {self.price_aud_per_kwh}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "seller_id": self.seller_id,
            "buyer_id": self.buyer_id,
            "seller_ask_aud_per_kwh": self.seller_ask_aud_per_kwh,
            "buyer_bid_aud_per_kwh": self.buyer_bid_aud_per_kwh,
            "price_aud_per_kwh": self.price_aud_per_kwh,
            "traded_energy_kwh": self.traded_energy_kwh,
            "seller_revenue_aud": self.seller_revenue_aud,
            "buyer_payment_aud": self.buyer_payment_aud,
        }


@dataclass
class StrategicMarketResult:
    """Comprehensive result of strategic double-auction market clearing."""

    transactions: List[StrategicTransaction]
    total_traded_kwh: float
    seller_allocations_kwh: Dict[str, float]
    buyer_allocations_kwh: Dict[str, float]
    seller_revenues_aud: Dict[str, float]
    buyer_payments_aud: Dict[str, float]
    seller_incremental_benefits_aud: Dict[str, float]
    buyer_incremental_benefits_aud: Dict[str, float]
    community_incremental_welfare_aud: float
    unmatched_seller_surplus_kwh: Dict[str, float]
    unmatched_buyer_deficit_kwh: Dict[str, float]
    weighted_average_transaction_price_aud: Optional[float]
    energy_conservation_residual_kwh: float
    financial_balance_residual_aud: float
    welfare_identity_residual_aud: float
    active_sellers: List[str] = field(default_factory=list)
    active_buyers: List[str] = field(default_factory=list)
    inactive_households: List[str] = field(default_factory=list)
    rounds_executed: int = 0

    def get_ledger_dataframe(self) -> pd.DataFrame:
        """Tabulate transaction ledger."""
        if not self.transactions:
            return pd.DataFrame(
                columns=[
                    "Transaction_ID",
                    "Seller_ID",
                    "Buyer_ID",
                    "Seller_Ask_AUD",
                    "Buyer_Bid_AUD",
                    "Price_AUD_per_kWh",
                    "Traded_kWh",
                    "Seller_Rev_AUD",
                    "Buyer_Pmt_AUD",
                ]
            )
        return pd.DataFrame([tx.to_dict() for tx in self.transactions])

    def get_household_summary_dataframe(self) -> pd.DataFrame:
        """Tabulate per-household physical and financial summary."""
        all_houses = sorted(
            set(self.seller_allocations_kwh.keys())
            | set(self.buyer_allocations_kwh.keys())
            | set(self.inactive_households)
        )
        rows = []
        for hid in all_houses:
            sold_q = self.seller_allocations_kwh.get(hid, 0.0)
            bought_q = self.buyer_allocations_kwh.get(hid, 0.0)
            unmatched_s = self.unmatched_seller_surplus_kwh.get(hid, 0.0)
            unmatched_d = self.unmatched_buyer_deficit_kwh.get(hid, 0.0)
            rev = self.seller_revenues_aud.get(hid, 0.0)
            pmt = self.buyer_payments_aud.get(hid, 0.0)
            inc_s = self.seller_incremental_benefits_aud.get(hid, 0.0)
            inc_b = self.buyer_incremental_benefits_aud.get(hid, 0.0)

            if hid in self.active_sellers:
                role_label = "Seller"
            elif hid in self.active_buyers:
                role_label = "Buyer"
            else:
                role_label = "Inactive"

            rows.append({
                "Household": hid,
                "Role": role_label,
                "P2P_Sold_kWh": float(sold_q),
                "P2P_Bought_kWh": float(bought_q),
                "Unmatched_Surplus_kWh": float(unmatched_s),
                "Unmatched_Deficit_kWh": float(unmatched_d),
                "P2P_Revenue_AUD": float(rev),
                "P2P_Payment_AUD": float(pmt),
                "Incremental_Benefit_AUD": float(inc_s + inc_b),
            })
        return pd.DataFrame(rows)


def create_order_from_physical_position(
    house_id: str,
    demand_kwh: float,
    battery_charge_kwh: float,
    solar_generation_kwh: float,
    battery_discharge_kwh: float,
    price_aud_per_kwh: float,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
    allowed_price_grid: Optional[Tuple[float, ...]] = None,
) -> Optional[MarketOrder]:
    """Construct a MarketOrder from physical meter components post-battery dispatch.

    Returns None if household is inactive (|net_flow| <= tolerance).
    """
    net_flow, surplus, deficit = compute_physical_net_position(
        demand_kwh=demand_kwh,
        battery_charge_kwh=battery_charge_kwh,
        solar_generation_kwh=solar_generation_kwh,
        battery_discharge_kwh=battery_discharge_kwh,
        tolerance=tolerance,
    )

    if surplus > tolerance:
        return MarketOrder(
            household_id=house_id,
            role=MarketRole.SELLER,
            price_aud_per_kwh=price_aud_per_kwh,
            quantity_kwh=surplus,
            allowed_price_grid=allowed_price_grid,
        )
    elif deficit > tolerance:
        return MarketOrder(
            household_id=house_id,
            role=MarketRole.BUYER,
            price_aud_per_kwh=price_aud_per_kwh,
            quantity_kwh=deficit,
            allowed_price_grid=allowed_price_grid,
        )
    else:
        return None


def clear_strategic_double_auction(
    orders: Union[Sequence[MarketOrder], Dict[str, MarketOrder]],
    grid_import_tariff_aud: float = DEFAULT_GRID_IMPORT_TARIFF_AUD,
    grid_export_credit_aud: float = DEFAULT_GRID_EXPORT_CREDIT_AUD,
    all_households: Optional[Sequence[str]] = None,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
    price_grid: Sequence[float] = STRATEGIC_PRICE_GRID,
) -> StrategicMarketResult:
    """Execute multi-household price-only double-auction market clearing.

    Algorithm:
    1. Validate market configuration and admissible price grid.
    2. Filter, validate, and check uniqueness of submitted orders.
    3. Sort sellers by lowest ask first (merit order), then household_id.
    4. Sort buyers by highest bid first, then household_id.
    5. Iteratively match lowest seller ask with highest buyer bid:
       - Cross check: bid >= ask. If bid < ask, stop.
       - Pro-rata volume allocation across tied groups.
       - Bilateral transaction matrix q_ij = (q_i^alloc * q_j^alloc) / Q_trade.
       - Transaction midpoint price p_ij = (ask + bid) / 2.
    6. Verify strict physical energy and financial conservation.
    """
    # 1. Validate market configuration and admissible price grid
    validated_grid = validate_market_configuration(
        grid_import_tariff_aud=grid_import_tariff_aud,
        grid_export_credit_aud=grid_export_credit_aud,
        tolerance=tolerance,
        price_grid=price_grid,
    )

    # 2. Normalize and validate orders
    if isinstance(orders, dict):
        order_list = [ord_obj for ord_obj in orders.values() if ord_obj is not None]
    else:
        order_list = [ord_obj for ord_obj in orders if ord_obj is not None]

    for ord_obj in order_list:
        if not isinstance(ord_obj, MarketOrder):
            raise TypeError(f"Expected MarketOrder instance, got {type(ord_obj)}")
        if not any(abs(ord_obj.price_aud_per_kwh - p_allowed) <= tolerance for p_allowed in validated_grid):
            raise ValueError(
                f"Submitted price {ord_obj.price_aud_per_kwh} for household {ord_obj.household_id} "
                f"does not belong to active market price grid {validated_grid}."
            )

    # Check for duplicate orders per household
    seen_houses: Set[str] = set()
    for ord_obj in order_list:
        if ord_obj.household_id in seen_houses:
            raise ValueError(f"Duplicate order submitted for household {ord_obj.household_id}")
        seen_houses.add(ord_obj.household_id)

    # Establish full household universe
    if all_households is not None:
        for hid in all_households:
            if not isinstance(hid, str) or not hid.strip():
                raise ValueError(f"Invalid household_id in all_households: {hid!r}")
        universe = sorted(set(all_households) | seen_houses)
    else:
        universe = sorted(seen_houses)

    # Separate active sellers and buyers (ignore zero quantities)
    sellers_dict: Dict[str, float] = {}
    seller_asks: Dict[str, float] = {}
    buyers_dict: Dict[str, float] = {}
    buyer_bids: Dict[str, float] = {}
    inactive_houses: List[str] = []

    for hid in universe:
        ord_obj = next((o for o in order_list if o.household_id == hid), None)
        if ord_obj is None or ord_obj.quantity_kwh <= tolerance:
            inactive_houses.append(hid)
        elif ord_obj.role == MarketRole.SELLER:
            sellers_dict[hid] = ord_obj.quantity_kwh
            seller_asks[hid] = ord_obj.price_aud_per_kwh
        elif ord_obj.role == MarketRole.BUYER:
            buyers_dict[hid] = ord_obj.quantity_kwh
            buyer_bids[hid] = ord_obj.price_aud_per_kwh

    active_sellers = sorted(sellers_dict.keys())
    active_buyers = sorted(buyers_dict.keys())

    # Initial state tracking
    seller_rem = {hid: sellers_dict[hid] for hid in active_sellers}
    buyer_rem = {hid: buyers_dict[hid] for hid in active_buyers}

    seller_allocations = {hid: 0.0 for hid in universe}
    buyer_allocations = {hid: 0.0 for hid in universe}
    seller_revenues = {hid: 0.0 for hid in universe}
    buyer_payments = {hid: 0.0 for hid in universe}
    seller_benefits = {hid: 0.0 for hid in universe}
    buyer_benefits = {hid: 0.0 for hid in universe}

    transactions: List[StrategicTransaction] = []
    tx_idx = 1

    # 3. Iterative Double Auction Matching
    # Upper bound based on active order groups:
    # Each matching round exhausts at least one price group on the seller or buyer side.
    max_matching_rounds = max(1, len(active_sellers) + len(active_buyers))
    rounds_executed = 0

    while rounds_executed < max_matching_rounds:
        # Remaining active sellers with positive capacity
        avail_sellers = [hid for hid in active_sellers if seller_rem[hid] > tolerance]
        avail_buyers = [hid for hid in active_buyers if buyer_rem[hid] > tolerance]

        if not avail_sellers or not avail_buyers:
            break

        # Find best price levels
        min_ask = min(seller_asks[hid] for hid in avail_sellers)
        max_bid = max(buyer_bids[hid] for hid in avail_buyers)

        # Overlap / crossing check
        if max_bid < min_ask - tolerance:
            # Order book does not cross; no further trades possible
            break

        rounds_executed += 1

        # Group tied sellers at min_ask (sorted deterministically by house_id)
        s_tied = sorted(
            [hid for hid in avail_sellers if abs(seller_asks[hid] - min_ask) <= tolerance]
        )
        # Group tied buyers at max_bid (sorted deterministically by house_id)
        b_tied = sorted(
            [hid for hid in avail_buyers if abs(buyer_bids[hid] - max_bid) <= tolerance]
        )

        tot_supply_tied = sum(seller_rem[hid] for hid in s_tied)
        tot_demand_tied = sum(buyer_rem[hid] for hid in b_tied)

        q_trade = min(tot_supply_tied, tot_demand_tied)

        if q_trade <= tolerance:
            break

        # Transaction clearing price: midpoint of submitted ask and bid
        tx_price = (min_ask + max_bid) / 2.0

        # Pro-rata capacity allocations for tied groups
        q_s_alloc = {
            s_id: q_trade * (seller_rem[s_id] / tot_supply_tied) for s_id in s_tied
        }
        q_b_alloc = {
            b_id: q_trade * (buyer_rem[b_id] / tot_demand_tied) for b_id in b_tied
        }

        # Bilateral transaction decomposition
        for s_id in s_tied:
            for b_id in b_tied:
                q_ij = (q_s_alloc[s_id] * q_b_alloc[b_id]) / q_trade

                if q_ij > tolerance:
                    tx_value = q_ij * tx_price
                    tx = StrategicTransaction(
                        transaction_id=f"STRAT_TX_{tx_idx:04d}",
                        seller_id=s_id,
                        buyer_id=b_id,
                        seller_ask_aud_per_kwh=min_ask,
                        buyer_bid_aud_per_kwh=max_bid,
                        price_aud_per_kwh=tx_price,
                        traded_energy_kwh=q_ij,
                        seller_revenue_aud=tx_value,
                        buyer_payment_aud=tx_value,
                    )
                    transactions.append(tx)
                    tx_idx += 1

                    seller_allocations[s_id] += q_ij
                    buyer_allocations[b_id] += q_ij
                    seller_revenues[s_id] += tx_value
                    buyer_payments[b_id] += tx_value

                    seller_benefits[s_id] += q_ij * (tx_price - grid_export_credit_aud)
                    buyer_benefits[b_id] += q_ij * (grid_import_tariff_aud - tx_price)

        # Update remaining quantities
        for s_id in s_tied:
            seller_rem[s_id] = max(0.0, seller_rem[s_id] - q_s_alloc[s_id])
        for b_id in b_tied:
            buyer_rem[b_id] = max(0.0, buyer_rem[b_id] - q_b_alloc[b_id])

    # 3. Post-Trade Unmatched Energy Calculation
    unmatched_surplus: Dict[str, float] = {}
    unmatched_deficit: Dict[str, float] = {}

    for hid in universe:
        init_s = sellers_dict.get(hid, 0.0)
        init_d = buyers_dict.get(hid, 0.0)
        unmatched_surplus[hid] = max(0.0, init_s - seller_allocations[hid])
        unmatched_deficit[hid] = max(0.0, init_d - buyer_allocations[hid])

    total_traded = sum(tx.traded_energy_kwh for tx in transactions)
    tot_seller_alloc = sum(seller_allocations.values())
    tot_buyer_alloc = sum(buyer_allocations.values())
    tot_revenue = sum(seller_revenues.values())
    tot_payment = sum(buyer_payments.values())
    tot_seller_ben = sum(seller_benefits.values())
    tot_buyer_ben = sum(buyer_benefits.values())

    community_welfare = (
        grid_import_tariff_aud - grid_export_credit_aud
    ) * total_traded

    # Weighted average price
    if total_traded > tolerance:
        weighted_avg_price: Optional[float] = (
            sum(tx.traded_energy_kwh * tx.price_aud_per_kwh for tx in transactions)
            / total_traded
        )
    else:
        weighted_avg_price = None

    # 4. Rigorous Conservation & Financial Invariant Checks
    energy_res = abs(tot_seller_alloc - tot_buyer_alloc)
    total_traded_res = abs(total_traded - tot_seller_alloc)
    payment_res = abs(tot_payment - tot_revenue)
    welfare_res = abs((tot_seller_ben + tot_buyer_ben) - community_welfare)

    if energy_res > tolerance:
        raise ValueError(
            f"Physical energy conservation violation: total_sold={tot_seller_alloc:.6f} "
            f"!= total_bought={tot_buyer_alloc:.6f} (residual={energy_res:.6e})"
        )

    if total_traded_res > tolerance:
        raise ValueError(
            f"Ledger traded energy mismatch: sum(transactions)={total_traded:.6f} "
            f"!= allocations={tot_seller_alloc:.6f}"
        )

    if payment_res > tolerance:
        raise ValueError(
            f"Financial balance violation: total_payments={tot_payment:.6f} "
            f"!= total_revenues={tot_revenue:.6f} (residual={payment_res:.6e})"
        )

    if welfare_res > tolerance:
        raise ValueError(
            f"Welfare identity violation: sum(benefits)={tot_seller_ben + tot_buyer_ben:.6f} "
            f"!= 0.22*Q={community_welfare:.6f} (residual={welfare_res:.6e})"
        )

    # Feasibility bounds check
    for hid in active_sellers:
        if seller_allocations[hid] > sellers_dict[hid] + tolerance:
            raise ValueError(
                f"Seller allocation infeasibility for {hid}: allocated={seller_allocations[hid]:.6f} "
                f"> surplus={sellers_dict[hid]:.6f}"
            )
    for hid in active_buyers:
        if buyer_allocations[hid] > buyers_dict[hid] + tolerance:
            raise ValueError(
                f"Buyer allocation infeasibility for {hid}: allocated={buyer_allocations[hid]:.6f} "
                f"> deficit={buyers_dict[hid]:.6f}"
            )

    return StrategicMarketResult(
        transactions=transactions,
        total_traded_kwh=total_traded,
        seller_allocations_kwh=seller_allocations,
        buyer_allocations_kwh=buyer_allocations,
        seller_revenues_aud=seller_revenues,
        buyer_payments_aud=buyer_payments,
        seller_incremental_benefits_aud=seller_benefits,
        buyer_incremental_benefits_aud=buyer_benefits,
        community_incremental_welfare_aud=community_welfare,
        unmatched_seller_surplus_kwh=unmatched_surplus,
        unmatched_buyer_deficit_kwh=unmatched_deficit,
        weighted_average_transaction_price_aud=weighted_avg_price,
        energy_conservation_residual_kwh=energy_res,
        financial_balance_residual_aud=payment_res,
        welfare_identity_residual_aud=welfare_res,
        active_sellers=active_sellers,
        active_buyers=active_buyers,
        inactive_households=inactive_houses,
        rounds_executed=rounds_executed,
    )
