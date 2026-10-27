"""Utility and payoff functions for game-theoretic energy trading.

Utility is defined as negative net energy expenditure:
U_i = -C_i^{net}

where net expenditure includes:
- Grid electricity purchases (cost)
- Grid solar export revenue (negative cost / gain)
- Peer-to-peer electricity purchase payments (cost)
- Peer-to-peer electricity sales revenue (gain)

Accounting invariants:
1. Buyer payment == Seller revenue (P2P transaction conservation).
2. Traded quantity <= Available surplus of seller.
3. Traded quantity <= Deficit of buyer.
4. No energy is created, duplicated, or unmetered.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Union

import numpy as np


@dataclass(frozen=True)
class P2PTransaction:
    """Represents a validated peer-to-peer electricity transfer."""

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
            raise ValueError(f"Seller and buyer cannot be the same household: {self.seller_id}")

    @property
    def total_transaction_value_aud(self) -> float:
        """Buyer payment == Seller revenue."""
        return self.traded_energy_kwh * self.price_aud_per_kwh

    def validate_feasibility(self, seller_surplus_kwh: float, buyer_deficit_kwh: float) -> bool:
        """Verify transaction feasibility against participants' available energy."""
        if not np.isfinite(seller_surplus_kwh) or not np.isfinite(buyer_deficit_kwh):
            raise ValueError("Seller surplus and buyer deficit must be finite.")
        if seller_surplus_kwh < -1e-6 or buyer_deficit_kwh < -1e-6:
            raise ValueError("Seller surplus and buyer deficit must be nonnegative.")
        if self.traded_energy_kwh > seller_surplus_kwh + 1e-6:
            raise ValueError(
                f"Transaction infeasible: traded {self.traded_energy_kwh:.4f} kWh exceeds "
                f"seller available surplus {seller_surplus_kwh:.4f} kWh."
            )
        if self.traded_energy_kwh > buyer_deficit_kwh + 1e-6:
            raise ValueError(
                f"Transaction infeasible: traded {self.traded_energy_kwh:.4f} kWh exceeds "
                f"buyer unmet deficit {buyer_deficit_kwh:.4f} kWh."
            )
        return True


@dataclass
class HouseholdPayoff:
    """Detailed financial breakdown and utility for a single player."""

    house_id: str
    grid_import_cost_aud: float
    grid_export_revenue_aud: float
    p2p_payment_aud: float
    p2p_revenue_aud: float
    net_expenditure_aud: float
    utility: float
    grid_imported_kwh: float
    grid_exported_kwh: float
    p2p_imported_kwh: float
    p2p_exported_kwh: float
    battery_charged_kwh: float = 0.0
    battery_discharged_kwh: float = 0.0
    battery_initial_soc: float = 0.0
    battery_final_soc: float = 0.0
    battery_degradation_cost_aud: float = 0.0

    def to_dict(self) -> Dict[str, Union[str, float]]:
        return {
            "house_id": self.house_id,
            "grid_import_cost_aud": round(self.grid_import_cost_aud, 4),
            "grid_export_revenue_aud": round(self.grid_export_revenue_aud, 4),
            "p2p_payment_aud": round(self.p2p_payment_aud, 4),
            "p2p_revenue_aud": round(self.p2p_revenue_aud, 4),
            "net_expenditure_aud": round(self.net_expenditure_aud, 4),
            "utility": round(self.utility, 4),
            "grid_imported_kwh": round(self.grid_imported_kwh, 4),
            "grid_exported_kwh": round(self.grid_exported_kwh, 4),
            "p2p_imported_kwh": round(self.p2p_imported_kwh, 4),
            "p2p_exported_kwh": round(self.p2p_exported_kwh, 4),
            "battery_charged_kwh": round(self.battery_charged_kwh, 4),
            "battery_discharged_kwh": round(self.battery_discharged_kwh, 4),
            "battery_initial_soc": round(self.battery_initial_soc, 4),
            "battery_final_soc": round(self.battery_final_soc, 4),
            "battery_degradation_cost_aud": round(self.battery_degradation_cost_aud, 4),
        }


def compute_household_payoff(
    house_id: str,
    deficit_kwh: float,
    surplus_kwh: float,
    grid_import_price_aud: float,
    grid_export_credit_aud: float,
    p2p_energy_sold_kwh: float = 0.0,
    p2p_energy_bought_kwh: float = 0.0,
    p2p_price_aud: float = 0.0,
    battery_charged_kwh: float = 0.0,
    battery_discharged_kwh: float = 0.0,
    battery_initial_soc: float = 0.0,
    battery_final_soc: float = 0.0,
    battery_degradation_cost_per_kwh: float = 0.0,
) -> HouseholdPayoff:
    """Compute financial payoff and utility for one household.

    Parameters
    ----------
    house_id : str
        Household ID.
    deficit_kwh : float
        Energy deficit requiring external supply.
    surplus_kwh : float
        Excess solar generation available.
    grid_import_price_aud : float
        Grid buy tariff in AUD/kWh.
    grid_export_credit_aud : float
        Grid feed-in tariff in AUD/kWh.
    p2p_energy_sold_kwh : float
        Quantity of surplus sold to peer.
    p2p_energy_bought_kwh : float
        Quantity of energy bought from peer to meet deficit.
    p2p_price_aud : float
        Trading price in AUD/kWh.
    battery_charged_kwh : float
        Energy charged into battery during interval in kWh.
    battery_discharged_kwh : float
        Energy discharged from battery during interval in kWh.
    battery_initial_soc : float
        State of charge at start of interval in [0, 1].
    battery_final_soc : float
        State of charge at end of interval in [0, 1].
    battery_degradation_cost_per_kwh : float
        Degradation cost per unit battery throughput in AUD/kWh (default 0.0).

    Returns
    -------
    HouseholdPayoff
        Fully resolved payoff with conservation guarantees.
    """
    for name, val in [
        ("deficit_kwh", deficit_kwh),
        ("surplus_kwh", surplus_kwh),
        ("grid_import_price_aud", grid_import_price_aud),
        ("grid_export_credit_aud", grid_export_credit_aud),
        ("p2p_energy_sold_kwh", p2p_energy_sold_kwh),
        ("p2p_energy_bought_kwh", p2p_energy_bought_kwh),
        ("p2p_price_aud", p2p_price_aud),
        ("battery_charged_kwh", battery_charged_kwh),
        ("battery_discharged_kwh", battery_discharged_kwh),
        ("battery_initial_soc", battery_initial_soc),
        ("battery_final_soc", battery_final_soc),
        ("battery_degradation_cost_per_kwh", battery_degradation_cost_per_kwh),
    ]:
        if not np.isfinite(val):
            raise ValueError(f"Non-finite input detected for {name}: {val}")
        if float(val) < -1e-6:
            raise ValueError(f"{name} must be nonnegative, got {val}")

    deficit = max(0.0, float(deficit_kwh))
    surplus = max(0.0, float(surplus_kwh))
    p2p_sold = max(0.0, float(p2p_energy_sold_kwh))
    p2p_bought = max(0.0, float(p2p_energy_bought_kwh))

    # Physical complementarity & mutual exclusion checks
    if surplus > 1e-6 and deficit > 1e-6:
        raise ValueError(
            f"Household {house_id} cannot have simultaneous surplus ({surplus:.4f}) and deficit ({deficit:.4f})."
        )
    if p2p_sold > 1e-6 and p2p_bought > 1e-6:
        raise ValueError(
            f"Household {house_id} cannot simultaneously sell ({p2p_sold:.4f}) and buy ({p2p_bought:.4f}) P2P energy."
        )

    # Conservation checks
    if p2p_sold > surplus + 1e-6:
        raise ValueError(
            f"Household {house_id} cannot sell {p2p_sold:.4f} kWh: only {surplus:.4f} kWh surplus available."
        )
    if p2p_bought > deficit + 1e-6:
        raise ValueError(
            f"Household {house_id} cannot buy {p2p_bought:.4f} kWh: only {deficit:.4f} kWh deficit needed."
        )

    # Net energy to/from grid after P2P
    grid_exported = max(0.0, surplus - p2p_sold)
    grid_imported = max(0.0, deficit - p2p_bought)

    # Cash flows
    grid_import_cost = grid_imported * grid_import_price_aud
    grid_export_revenue = grid_exported * grid_export_credit_aud
    p2p_payment = p2p_bought * p2p_price_aud
    p2p_revenue = p2p_sold * p2p_price_aud

    # Battery degradation cost (if modeled)
    degradation_cost = (battery_charged_kwh + battery_discharged_kwh) * battery_degradation_cost_per_kwh

    # Net expenditure: expenses minus earnings
    net_expenditure = (grid_import_cost + p2p_payment + degradation_cost) - (grid_export_revenue + p2p_revenue)

    # Utility: negative net expenditure (higher is better)
    utility = -net_expenditure

    return HouseholdPayoff(
        house_id=house_id,
        grid_import_cost_aud=grid_import_cost,
        grid_export_revenue_aud=grid_export_revenue,
        p2p_payment_aud=p2p_payment,
        p2p_revenue_aud=p2p_revenue,
        net_expenditure_aud=net_expenditure,
        utility=utility,
        grid_imported_kwh=grid_imported,
        grid_exported_kwh=grid_exported,
        p2p_imported_kwh=p2p_bought,
        p2p_exported_kwh=p2p_sold,
        battery_charged_kwh=battery_charged_kwh,
        battery_discharged_kwh=battery_discharged_kwh,
        battery_initial_soc=battery_initial_soc,
        battery_final_soc=battery_final_soc,
        battery_degradation_cost_aud=degradation_cost,
    )
