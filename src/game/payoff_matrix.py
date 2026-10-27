"""Normal-form payoff matrix builder for two-household peer-to-peer trading.

Players:
- Player 1: Seller (surplus household, e.g., H001)
  Actions: ['OFFER_P2P', 'EXPORT_GRID']
- Player 2: Buyer (deficit household, e.g., H002)
  Actions: ['ACCEPT_P2P', 'GRID_IMPORT']

Conserves energy balance and accounting cash flows across every strategy profile.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

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
