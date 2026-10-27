"""Multi-household peer-to-peer (P2P) market clearing module.

This module provides a modular, deterministic market-clearing engine for microgrid
communities with multiple prosumer households (e.g., H001, H002, H003).

Key Features:
1. Accepts post-battery surplus and deficit from each household (battery-first policy).
2. Matches multiple sellers with multiple buyers simultaneously.
3. Supports configurable deterministic matching policies:
   - PRIORITY_ORDER (default): Deterministic matching based on documented priority order.
   - LARGEST_SURPLUS_FIRST: Greedy matching prioritizing largest surplus sellers and largest deficit buyers.
   - PRO_RATA: Proportional allocation across competing sellers/buyers when supply != demand.
4. Enforces strict physical energy conservation and non-double-counting.
5. Returns a granular transaction ledger with seller, buyer, quantity, and payment.
6. Reconciles with the central grid for residual unmatched surplus and unmet deficit.
7. Guarantees exact financial conservation (total buyer payments == total seller revenues).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from src.energy.battery import BatteryStorage
from src.energy.energy_balance import (
    BatteryAwareEnergyBalance,
    BatteryAwarePostTradeBalance,
    EnergyBalance,
    PostTradeEnergyBalance,
    compute_battery_aware_balance,
    compute_energy_balance,
    compute_post_trade_balance,
)
from src.game.utility import HouseholdPayoff, P2PTransaction, compute_household_payoff


class MarketClearingPolicy(str, Enum):
    """Supported deterministic market-clearing matching policies."""

    PRIORITY_ORDER = "priority_order"
    LARGEST_SURPLUS_FIRST = "largest_surplus_first"
    PRO_RATA = "pro_rata"


@dataclass
class HouseholdMarketBid:
    """Represents an individual household's market position post-battery dispatch.

    Attributes:
        house_id: Household identifier.
        surplus_kwh: Available electrical surplus (after self-consumption & battery charging).
        deficit_kwh: Remaining electrical deficit (after self-consumption & battery discharging).
        max_sell_kwh: Upper bound offered for sale (defaults to surplus_kwh, clamped <= surplus_kwh).
        max_buy_kwh: Upper bound requested for purchase (defaults to deficit_kwh, clamped <= deficit_kwh).
        p2p_price_aud: Optional custom P2P price for this household (defaults to market clearing price).
        energy_balance: Underlying pre-trade energy balance object if available.
    """

    house_id: str
    surplus_kwh: float
    deficit_kwh: float
    max_sell_kwh: Optional[float] = None
    max_buy_kwh: Optional[float] = None
    p2p_price_aud: Optional[float] = None
    energy_balance: Optional[Union[EnergyBalance, BatteryAwareEnergyBalance]] = None

    def __post_init__(self) -> None:
        for name, val in [("surplus_kwh", self.surplus_kwh), ("deficit_kwh", self.deficit_kwh)]:
            if not np.isfinite(val):
                raise ValueError(f"Non-finite input for {name}: {val}")
            if float(val) < -1e-6:
                raise ValueError(f"Negative input for {name}: {val}")

        self.surplus_kwh = max(0.0, float(self.surplus_kwh))
        self.deficit_kwh = max(0.0, float(self.deficit_kwh))

        # Enforce complementarity
        if self.surplus_kwh > 1e-6 and self.deficit_kwh > 1e-6:
            raise ValueError(
                f"Household {self.house_id} cannot simultaneously have surplus ({self.surplus_kwh:.4f} kWh) "
                f"and deficit ({self.deficit_kwh:.4f} kWh)."
            )

        # Set default offer/bid quantities
        if self.max_sell_kwh is None:
            self.max_sell_kwh = self.surplus_kwh
        else:
            if not np.isfinite(self.max_sell_kwh):
                raise ValueError(f"max_sell_kwh must be finite, got {self.max_sell_kwh}")
            if float(self.max_sell_kwh) < -1e-6:
                raise ValueError(f"max_sell_kwh must be nonnegative, got {self.max_sell_kwh}")
            if self.max_sell_kwh > self.surplus_kwh + 1e-6:
                raise ValueError(
                    f"max_sell_kwh ({self.max_sell_kwh:.4f}) cannot exceed available surplus ({self.surplus_kwh:.4f})."
                )
            self.max_sell_kwh = max(0.0, min(float(self.max_sell_kwh), self.surplus_kwh))

        if self.max_buy_kwh is None:
            self.max_buy_kwh = self.deficit_kwh
        else:
            if not np.isfinite(self.max_buy_kwh):
                raise ValueError(f"max_buy_kwh must be finite, got {self.max_buy_kwh}")
            if float(self.max_buy_kwh) < -1e-6:
                raise ValueError(f"max_buy_kwh must be nonnegative, got {self.max_buy_kwh}")
            if self.max_buy_kwh > self.deficit_kwh + 1e-6:
                raise ValueError(
                    f"max_buy_kwh ({self.max_buy_kwh:.4f}) cannot exceed remaining deficit ({self.deficit_kwh:.4f})."
                )
            self.max_buy_kwh = max(0.0, min(float(self.max_buy_kwh), self.deficit_kwh))

    @property
    def is_seller(self) -> bool:
        return self.max_sell_kwh > 1e-6

    @property
    def is_buyer(self) -> bool:
        return self.max_buy_kwh > 1e-6

    @classmethod
    def from_energy_balance(
        cls,
        balance: Union[EnergyBalance, BatteryAwareEnergyBalance],
        max_sell_kwh: Optional[float] = None,
        max_buy_kwh: Optional[float] = None,
        p2p_price_aud: Optional[float] = None,
    ) -> HouseholdMarketBid:
        """Construct a market bid directly from an EnergyBalance or BatteryAwareEnergyBalance."""
        return cls(
            house_id=balance.house_id,
            surplus_kwh=balance.surplus_kwh,
            deficit_kwh=balance.deficit_kwh,
            max_sell_kwh=max_sell_kwh,
            max_buy_kwh=max_buy_kwh,
            p2p_price_aud=p2p_price_aud,
            energy_balance=balance,
        )


@dataclass(frozen=True)
class MarketTransaction:
    """Individual cleared bilateral transaction in the microgrid."""

    transaction_id: str
    seller_id: str
    buyer_id: str
    traded_energy_kwh: float
    price_aud_per_kwh: float

    def __post_init__(self) -> None:
        if not np.isfinite(self.traded_energy_kwh):
            raise ValueError(f"Traded energy must be finite, got {self.traded_energy_kwh}")
        if not np.isfinite(self.price_aud_per_kwh):
            raise ValueError(f"Price must be finite, got {self.price_aud_per_kwh}")
        if self.traded_energy_kwh < -1e-6:
            raise ValueError(f"Traded energy must be nonnegative, got {self.traded_energy_kwh}")
        if self.price_aud_per_kwh < -1e-6:
            raise ValueError(f"Price must be nonnegative, got {self.price_aud_per_kwh}")
        if self.seller_id == self.buyer_id:
            raise ValueError(f"Self-trading is prohibited: seller={self.seller_id}, buyer={self.buyer_id}")

    @property
    def total_value_aud(self) -> float:
        """Buyer payment == Seller revenue."""
        return self.traded_energy_kwh * self.price_aud_per_kwh

    def to_p2p_transaction(self) -> P2PTransaction:
        return P2PTransaction(
            seller_id=self.seller_id,
            buyer_id=self.buyer_id,
            traded_energy_kwh=self.traded_energy_kwh,
            price_aud_per_kwh=self.price_aud_per_kwh,
        )


@dataclass
class CommunityEnergyBalanceSummary:
    """Community-wide aggregate energy and financial reconciliation."""

    total_demand_kwh: float
    total_solar_generation_kwh: float
    total_direct_self_consumption_kwh: float
    total_battery_charged_kwh: float
    total_battery_discharged_kwh: float
    total_p2p_traded_kwh: float
    total_p2p_payments_aud: float
    total_p2p_revenues_aud: float
    total_grid_imported_kwh: float
    total_grid_exported_kwh: float
    total_grid_import_cost_aud: float
    total_grid_export_revenue_aud: float
    combined_household_utility_aud: float
    demand_conservation_residual_kwh: float
    solar_conservation_residual_kwh: float
    net_energy_residual_kwh: float
    payment_conservation_residual_aud: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "total_demand_kwh": round(self.total_demand_kwh, 4),
            "total_solar_generation_kwh": round(self.total_solar_generation_kwh, 4),
            "total_direct_self_consumption_kwh": round(self.total_direct_self_consumption_kwh, 4),
            "total_battery_charged_kwh": round(self.total_battery_charged_kwh, 4),
            "total_battery_discharged_kwh": round(self.total_battery_discharged_kwh, 4),
            "total_p2p_traded_kwh": round(self.total_p2p_traded_kwh, 4),
            "total_p2p_payments_aud": round(self.total_p2p_payments_aud, 4),
            "total_p2p_revenues_aud": round(self.total_p2p_revenues_aud, 4),
            "total_grid_imported_kwh": round(self.total_grid_imported_kwh, 4),
            "total_grid_exported_kwh": round(self.total_grid_exported_kwh, 4),
            "total_grid_import_cost_aud": round(self.total_grid_import_cost_aud, 4),
            "total_grid_export_revenue_aud": round(self.total_grid_export_revenue_aud, 4),
            "combined_household_utility_aud": round(self.combined_household_utility_aud, 4),
            "demand_conservation_residual_kwh": self.demand_conservation_residual_kwh,
            "solar_conservation_residual_kwh": self.solar_conservation_residual_kwh,
            "net_energy_residual_kwh": self.net_energy_residual_kwh,
            "payment_conservation_residual_aud": self.payment_conservation_residual_aud,
        }


@dataclass
class MarketClearingResult:
    """Comprehensive result of multi-household P2P market clearing."""

    policy: MarketClearingPolicy
    clearing_price_aud: float
    transactions: List[MarketTransaction]
    total_traded_kwh: float
    seller_allocations_kwh: Dict[str, float]
    buyer_allocations_kwh: Dict[str, float]
    unmatched_surplus_kwh: Dict[str, float]
    unmet_demand_kwh: Dict[str, float]
    post_trade_balances: Dict[str, Union[PostTradeEnergyBalance, BatteryAwarePostTradeBalance]]
    payoffs: Dict[str, HouseholdPayoff]
    community_summary: CommunityEnergyBalanceSummary
    timestamp: Optional[pd.Timestamp] = None

    def get_ledger_dataframe(self) -> pd.DataFrame:
        """Tabulate the transaction ledger."""
        if not self.transactions:
            return pd.DataFrame(
                columns=["Transaction_ID", "Seller_ID", "Buyer_ID", "Traded_kWh", "Price_AUD_per_kWh", "Total_AUD"]
            )
        return pd.DataFrame([
            {
                "Transaction_ID": tx.transaction_id,
                "Seller_ID": tx.seller_id,
                "Buyer_ID": tx.buyer_id,
                "Traded_kWh": round(tx.traded_energy_kwh, 4),
                "Price_AUD_per_kWh": round(tx.price_aud_per_kwh, 4),
                "Total_AUD": round(tx.total_value_aud, 4),
            }
            for tx in self.transactions
        ])

    def get_household_summary_dataframe(self) -> pd.DataFrame:
        """Tabulate per-household physical and financial outcomes."""
        rows = []
        for h_id in sorted(self.post_trade_balances.keys()):
            pt = self.post_trade_balances[h_id]
            pay = self.payoffs[h_id]
            rows.append({
                "Household": h_id,
                "Demand_kWh": round(pt.demand_kwh, 4),
                "Solar_kWh": round(pt.solar_generation_kwh, 4),
                "SelfCons_kWh": round(pt.self_consumption_kwh, 4),
                "BatCharge_kWh": round(getattr(pt, "solar_to_battery_kwh", 0.0), 4),
                "BatDischarge_kWh": round(getattr(pt, "battery_to_demand_kwh", 0.0), 4),
                "P2P_Sold_kWh": round(pt.p2p_sold_kwh, 4),
                "P2P_Bought_kWh": round(pt.p2p_bought_kwh, 4),
                "Grid_Export_kWh": round(pt.grid_exported_kwh, 4),
                "Grid_Import_kWh": round(pt.grid_imported_kwh, 4),
                "P2P_Rev_AUD": round(pay.p2p_revenue_aud, 4),
                "P2P_Pmt_AUD": round(pay.p2p_payment_aud, 4),
                "Grid_Credit_AUD": round(pay.grid_export_revenue_aud, 4),
                "Grid_Cost_AUD": round(pay.grid_import_cost_aud, 4),
                "Utility_AUD": round(pay.utility, 4),
            })
        return pd.DataFrame(rows)


def _prepare_market_bids(
    inputs: Union[
        Sequence[HouseholdMarketBid],
        Dict[str, HouseholdMarketBid],
        Sequence[Union[EnergyBalance, BatteryAwareEnergyBalance]],
        Dict[str, Union[EnergyBalance, BatteryAwareEnergyBalance]],
    ],
    default_price_aud: float,
) -> Dict[str, HouseholdMarketBid]:
    """Standardize input balances or bids into a dictionary of HouseholdMarketBid."""
    bids: Dict[str, HouseholdMarketBid] = {}

    if isinstance(inputs, dict):
        items = list(inputs.items())
    else:
        items = [(getattr(item, "house_id", f"H_{i:03d}"), item) for i, item in enumerate(inputs)]

    for h_id, item in items:
        if isinstance(item, HouseholdMarketBid):
            bids[item.house_id] = item
        elif isinstance(item, (EnergyBalance, BatteryAwareEnergyBalance)):
            bid = HouseholdMarketBid(
                house_id=item.house_id,
                surplus_kwh=item.surplus_kwh,
                deficit_kwh=item.deficit_kwh,
                p2p_price_aud=default_price_aud,
                energy_balance=item,
            )
            bids[item.house_id] = bid
        else:
            raise TypeError(f"Unsupported input type for market clearing: {type(item)}")

    return bids


def clear_multi_household_market(
    bids_or_balances: Union[
        Sequence[HouseholdMarketBid],
        Dict[str, HouseholdMarketBid],
        Sequence[Union[EnergyBalance, BatteryAwareEnergyBalance]],
        Dict[str, Union[EnergyBalance, BatteryAwareEnergyBalance]],
    ],
    p2p_price_aud: float = 0.19,
    grid_import_price_aud: float = 0.30,
    grid_export_credit_aud: float = 0.08,
    policy: Union[MarketClearingPolicy, str] = MarketClearingPolicy.PRIORITY_ORDER,
    priority_order: Optional[Sequence[str]] = None,
    degradation_cost_per_kwh: float = 0.0,
    timestamp: Optional[pd.Timestamp] = None,
) -> MarketClearingResult:
    """Execute multi-household peer-to-peer market clearing.

    Parameters:
        bids_or_balances: Collection of HouseholdMarketBid, EnergyBalance, or BatteryAwareEnergyBalance.
        p2p_price_aud: Default P2P trading price in AUD/kWh (mid-market 0.19 default).
        grid_import_price_aud: Retail grid purchase tariff in AUD/kWh (0.30 default).
        grid_export_credit_aud: Solar feed-in credit in AUD/kWh (0.08 default).
        policy: MarketClearingPolicy enum or string name.
        priority_order: Optional explicit ordering of house_ids for priority matching.
        degradation_cost_per_kwh: Battery cycle degradation cost in AUD/kWh throughput (default 0.0).
        timestamp: Optional observation timestamp.

    Returns:
        MarketClearingResult containing transactions, balances, payoffs, and community reconciliation.
    """
    if isinstance(policy, str):
        policy = MarketClearingPolicy(policy)

    bids = _prepare_market_bids(bids_or_balances, default_price_aud=p2p_price_aud)

    # Validate prices
    for p_name, p_val in [
        ("p2p_price_aud", p2p_price_aud),
        ("grid_import_price_aud", grid_import_price_aud),
        ("grid_export_credit_aud", grid_export_credit_aud),
    ]:
        if not np.isfinite(p_val) or float(p_val) < 0.0:
            raise ValueError(f"{p_name} must be finite and nonnegative, got {p_val}")

    # Determine sorting order
    all_house_ids = sorted(bids.keys())
    if priority_order is not None:
        # Prioritize specified order, append any remaining
        ordered_ids = [hid for hid in priority_order if hid in bids]
        ordered_ids.extend([hid for hid in all_house_ids if hid not in ordered_ids])
    else:
        ordered_ids = all_house_ids

    # Separate eligible sellers and buyers
    sellers: List[Tuple[str, float, float]] = []  # (house_id, remaining_sell_kwh, price)
    buyers: List[Tuple[str, float, float]] = []   # (house_id, remaining_buy_kwh, price)

    for hid in ordered_ids:
        bid = bids[hid]
        if bid.is_seller:
            price = bid.p2p_price_aud if bid.p2p_price_aud is not None else p2p_price_aud
            sellers.append((hid, float(bid.max_sell_kwh), price))
        elif bid.is_buyer:
            price = bid.p2p_price_aud if bid.p2p_price_aud is not None else p2p_price_aud
            buyers.append((hid, float(bid.max_buy_kwh), price))

    # Apply policy-specific ordering
    if policy == MarketClearingPolicy.LARGEST_SURPLUS_FIRST:
        # Sort sellers by surplus descending, tie-break by house_id
        sellers = sorted(sellers, key=lambda x: (-x[1], x[0]))
        # Sort buyers by deficit descending, tie-break by house_id
        buyers = sorted(buyers, key=lambda x: (-x[1], x[0]))
    elif policy == MarketClearingPolicy.PRIORITY_ORDER:
        # Kept in ordered_ids sequence
        pass
    elif policy == MarketClearingPolicy.PRO_RATA:
        # Pro-rata pre-allocation calculation
        pass

    transactions: List[MarketTransaction] = []
    seller_allocations: Dict[str, float] = {hid: 0.0 for hid in bids}
    buyer_allocations: Dict[str, float] = {hid: 0.0 for hid in bids}

    # Execute matching
    if policy in (MarketClearingPolicy.PRIORITY_ORDER, MarketClearingPolicy.LARGEST_SURPLUS_FIRST):
        tx_idx = 1
        # Convert to mutable lists
        s_list = [[hid, q, p] for hid, q, p in sellers]
        b_list = [[hid, q, p] for hid, q, p in buyers]

        for s in s_list:
            s_id, s_rem, s_price = s[0], s[1], s[2]
            if s_rem <= 1e-6:
                continue

            for b in b_list:
                b_id, b_rem, b_price = b[0], b[1], b[2]
                if b_rem <= 1e-6 or s_id == b_id:
                    continue

                trade_q = min(s[1], b[1])
                if trade_q > 1e-6:
                    tx_price = s_price if s_price == b_price else p2p_price_aud
                    tx = MarketTransaction(
                        transaction_id=f"TX_{tx_idx:04d}",
                        seller_id=s_id,
                        buyer_id=b_id,
                        traded_energy_kwh=trade_q,
                        price_aud_per_kwh=tx_price,
                    )
                    transactions.append(tx)
                    tx_idx += 1

                    s[1] -= trade_q
                    b[1] -= trade_q
                    seller_allocations[s_id] += trade_q
                    buyer_allocations[b_id] += trade_q

                if s[1] <= 1e-6:
                    break

    elif policy == MarketClearingPolicy.PRO_RATA:
        tx_idx = 1
        total_supply = sum(s[1] for s in sellers)
        total_demand = sum(b[1] for b in buyers)

        if total_supply > 1e-6 and total_demand > 1e-6:
            if total_supply <= total_demand:
                # Supply constrained: every seller sells 100%, buyers receive pro-rata share
                target_buyer_alloc = {b[0]: b[1] * (total_supply / total_demand) for b in buyers}
                s_list = [[hid, q, p] for hid, q, p in sellers]
                b_list = [[hid, target_buyer_alloc[hid], p] for hid, q, p in buyers]
            else:
                # Demand constrained: every buyer buys 100%, sellers sell pro-rata share
                target_seller_alloc = {s[0]: s[1] * (total_demand / total_supply) for s in sellers}
                s_list = [[hid, target_seller_alloc[hid], p] for hid, q, p in sellers]
                b_list = [[hid, q, p] for hid, q, p in buyers]

            for s in s_list:
                s_id = s[0]
                if s[1] <= 1e-6:
                    continue
                for b in b_list:
                    b_id = b[0]
                    if b[1] <= 1e-6 or s_id == b_id:
                        continue
                    trade_q = min(s[1], b[1])
                    if trade_q > 1e-6:
                        tx = MarketTransaction(
                            transaction_id=f"TX_{tx_idx:04d}",
                            seller_id=s_id,
                            buyer_id=b_id,
                            traded_energy_kwh=trade_q,
                            price_aud_per_kwh=p2p_price_aud,
                        )
                        transactions.append(tx)
                        tx_idx += 1
                        s[1] -= trade_q
                        b[1] -= trade_q
                        seller_allocations[s_id] += trade_q
                        buyer_allocations[b_id] += trade_q
                    if s[1] <= 1e-6:
                        break

    # Reconcile unmatched surplus and unmet demand
    unmatched_surplus: Dict[str, float] = {}
    unmet_demand: Dict[str, float] = {}
    for hid, bid in bids.items():
        unmatched_surplus[hid] = max(0.0, bid.surplus_kwh - seller_allocations[hid])
        unmet_demand[hid] = max(0.0, bid.deficit_kwh - buyer_allocations[hid])

    # Reconcile post-trade balances and financial payoffs
    post_trade_balances: Dict[str, Union[PostTradeEnergyBalance, BatteryAwarePostTradeBalance]] = {}
    payoffs: Dict[str, HouseholdPayoff] = {}

    for hid, bid in bids.items():
        sold_q = seller_allocations[hid]
        bought_q = buyer_allocations[hid]

        # Use pre-existing balance if provided, else construct one
        if bid.energy_balance is not None:
            base_balance = bid.energy_balance
        else:
            base_balance = compute_energy_balance(
                demand_kwh=bid.deficit_kwh,
                solar_generation_kwh=bid.surplus_kwh,
                house_id=hid,
                timestamp=timestamp,
            )

        pt_balance = compute_post_trade_balance(
            balance=base_balance,
            p2p_sold_kwh=sold_q,
            p2p_bought_kwh=bought_q,
        )
        post_trade_balances[hid] = pt_balance

        # Compute household financial payoff
        b_ch = getattr(base_balance, "solar_to_battery_kwh", 0.0)
        b_dis = getattr(base_balance, "battery_to_demand_kwh", 0.0)
        b_isoc = getattr(base_balance, "battery_initial_soc", 0.0)
        b_fsoc = getattr(base_balance, "battery_final_soc", 0.0)

        payoff = compute_household_payoff(
            house_id=hid,
            deficit_kwh=bid.deficit_kwh,
            surplus_kwh=bid.surplus_kwh,
            grid_import_price_aud=grid_import_price_aud,
            grid_export_credit_aud=grid_export_credit_aud,
            p2p_energy_sold_kwh=sold_q,
            p2p_energy_bought_kwh=bought_q,
            p2p_price_aud=p2p_price_aud,
            battery_charged_kwh=b_ch,
            battery_discharged_kwh=b_dis,
            battery_initial_soc=b_isoc,
            battery_final_soc=b_fsoc,
            battery_degradation_cost_per_kwh=degradation_cost_per_kwh,
        )
        payoffs[hid] = payoff

    # Community conservation & summary calculations
    total_traded = sum(tx.traded_energy_kwh for tx in transactions)
    tot_demand = sum(pt.demand_kwh for pt in post_trade_balances.values())
    tot_solar = sum(pt.solar_generation_kwh for pt in post_trade_balances.values())
    tot_self_cons = sum(pt.self_consumption_kwh for pt in post_trade_balances.values())
    tot_bat_ch = sum(getattr(pt, "solar_to_battery_kwh", 0.0) for pt in post_trade_balances.values())
    tot_bat_dis = sum(getattr(pt, "battery_to_demand_kwh", 0.0) for pt in post_trade_balances.values())
    tot_grid_imp = sum(pt.grid_imported_kwh for pt in post_trade_balances.values())
    tot_grid_exp = sum(pt.grid_exported_kwh for pt in post_trade_balances.values())

    tot_p2p_pmt = sum(pay.p2p_payment_aud for pay in payoffs.values())
    tot_p2p_rev = sum(pay.p2p_revenue_aud for pay in payoffs.values())
    tot_grid_cost = sum(pay.grid_import_cost_aud for pay in payoffs.values())
    tot_grid_credit = sum(pay.grid_export_revenue_aud for pay in payoffs.values())
    comb_utility = sum(pay.utility for pay in payoffs.values())

    # Residuals
    d_res = tot_demand - (tot_self_cons + tot_bat_dis + total_traded + tot_grid_imp)
    s_res = tot_solar - (tot_self_cons + tot_bat_ch + total_traded + tot_grid_exp)
    net_actual = tot_demand - tot_solar
    net_accounted = (tot_grid_imp - tot_grid_exp) + (tot_bat_dis - tot_bat_ch)
    net_res = net_actual - net_accounted
    pmt_res = tot_p2p_pmt - tot_p2p_rev

    if abs(pmt_res) > 1e-5:
        raise ValueError(f"Community P2P payment conservation violation: payments={tot_p2p_pmt} != revenues={tot_p2p_rev}")
    if abs(d_res) > 1e-4:
        raise ValueError(f"Community demand conservation violation: residual={d_res}")
    if abs(s_res) > 1e-4:
        raise ValueError(f"Community solar conservation violation: residual={s_res}")

    comm_summary = CommunityEnergyBalanceSummary(
        total_demand_kwh=tot_demand,
        total_solar_generation_kwh=tot_solar,
        total_direct_self_consumption_kwh=tot_self_cons,
        total_battery_charged_kwh=tot_bat_ch,
        total_battery_discharged_kwh=tot_bat_dis,
        total_p2p_traded_kwh=total_traded,
        total_p2p_payments_aud=tot_p2p_pmt,
        total_p2p_revenues_aud=tot_p2p_rev,
        total_grid_imported_kwh=tot_grid_imp,
        total_grid_exported_kwh=tot_grid_exp,
        total_grid_import_cost_aud=tot_grid_cost,
        total_grid_export_revenue_aud=tot_grid_credit,
        combined_household_utility_aud=comb_utility,
        demand_conservation_residual_kwh=d_res,
        solar_conservation_residual_kwh=s_res,
        net_energy_residual_kwh=net_res,
        payment_conservation_residual_aud=pmt_res,
    )

    return MarketClearingResult(
        policy=policy,
        clearing_price_aud=p2p_price_aud,
        transactions=transactions,
        total_traded_kwh=total_traded,
        seller_allocations_kwh=seller_allocations,
        buyer_allocations_kwh=buyer_allocations,
        unmatched_surplus_kwh=unmatched_surplus,
        unmet_demand_kwh=unmet_demand,
        post_trade_balances=post_trade_balances,
        payoffs=payoffs,
        community_summary=comm_summary,
        timestamp=timestamp,
    )
