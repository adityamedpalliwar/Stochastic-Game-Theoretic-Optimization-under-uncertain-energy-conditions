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


@dataclass(frozen=True)
class P2PTransaction:
    """Represents a validated peer-to-peer electricity transfer."""

    seller_id: str
    buyer_id: str
    traded_energy_kwh: float
    price_aud_per_kwh: float

    def __post_init__(self) -> None:
        if self.traded_energy_kwh < 0.0:
            raise ValueError(f"Traded energy must be nonnegative, got {self.traded_energy_kwh}")
        if self.price_aud_per_kwh < 0.0:
            raise ValueError(f"Price must be nonnegative, got {self.price_aud_per_kwh}")

    @property
    def total_transaction_value_aud(self) -> float:
        """Buyer payment == Seller revenue."""
        return self.traded_energy_kwh * self.price_aud_per_kwh


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

    Returns
    -------
    HouseholdPayoff
        Fully resolved payoff with conservation guarantees.
    """
    deficit = max(0.0, float(deficit_kwh))
    surplus = max(0.0, float(surplus_kwh))
    p2p_sold = max(0.0, float(p2p_energy_sold_kwh))
    p2p_bought = max(0.0, float(p2p_energy_bought_kwh))

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

    # Net expenditure: expenses minus earnings
    net_expenditure = (grid_import_cost + p2p_payment) - (grid_export_revenue + p2p_revenue)

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
    )
