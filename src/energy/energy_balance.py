"""Hourly energy balance calculations for solar-equipped households.

Calculates:
- Self-consumed solar: E_{self} = min(Demand, Solar)
- Deficit: E_{deficit} = max(0, Demand - Solar)
- Surplus: E_{surplus} = max(0, Solar - Demand)

Enforces physical energy balance conservation:
Demand = E_{self} + E_{deficit}
Solar  = E_{self} + E_{surplus}
Demand - Solar = E_{deficit} - E_{surplus}
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Union

import numpy as np
import pandas as pd

from src.energy.battery import BatteryStorage


@dataclass
class EnergyBalance:
    """Energy balance result for one household over an interval."""

    house_id: str
    demand_kwh: float
    solar_generation_kwh: float
    self_consumption_kwh: float
    deficit_kwh: float
    surplus_kwh: float
    timestamp: Optional[pd.Timestamp] = None

    def __post_init__(self) -> None:
        # Enforce finite inputs
        for name, val in [
            ("demand_kwh", self.demand_kwh),
            ("solar_generation_kwh", self.solar_generation_kwh),
            ("self_consumption_kwh", self.self_consumption_kwh),
            ("deficit_kwh", self.deficit_kwh),
            ("surplus_kwh", self.surplus_kwh),
        ]:
            if not np.isfinite(val):
                raise ValueError(f"Non-finite value detected for {name}: {val}")

        # Enforce physical nonnegativity
        if self.demand_kwh < -1e-6 or self.solar_generation_kwh < -1e-6:
            raise ValueError(
                f"Negative energy input detected: Demand={self.demand_kwh}, Solar={self.solar_generation_kwh}"
            )
        if self.self_consumption_kwh < -1e-6 or self.deficit_kwh < -1e-6 or self.surplus_kwh < -1e-6:
            raise ValueError("Energy balance components must be nonnegative.")

        # Numerical tolerance adjustment
        self.demand_kwh = max(0.0, float(self.demand_kwh))
        self.solar_generation_kwh = max(0.0, float(self.solar_generation_kwh))
        self.self_consumption_kwh = max(0.0, float(self.self_consumption_kwh))
        self.deficit_kwh = max(0.0, float(self.deficit_kwh))
        self.surplus_kwh = max(0.0, float(self.surplus_kwh))

        # Enforce complementarity: household cannot simultaneously have surplus and deficit
        if self.surplus_kwh > 1e-6 and self.deficit_kwh > 1e-6:
            raise ValueError(
                f"Complementarity violation: household cannot simultaneously have surplus ({self.surplus_kwh:.4f} kWh) "
                f"and deficit ({self.deficit_kwh:.4f} kWh)"
            )

        # Enforce component conservation laws
        demand_diff = abs(self.demand_kwh - (self.self_consumption_kwh + self.deficit_kwh))
        if demand_diff > 1e-5:
            raise ValueError(f"Demand conservation violation: Demand != Self-consumption + Deficit (diff: {demand_diff})")

        solar_diff = abs(self.solar_generation_kwh - (self.self_consumption_kwh + self.surplus_kwh))
        if solar_diff > 1e-5:
            raise ValueError(f"Solar conservation violation: Solar != Self-consumption + Surplus (diff: {solar_diff})")

        # Check net conservation law: Demand - Solar == Deficit - Surplus
        net_diff = (self.demand_kwh - self.solar_generation_kwh) - (self.deficit_kwh - self.surplus_kwh)
        if abs(net_diff) > 1e-5:
            raise ValueError(f"Energy conservation violation: difference is {net_diff}")

    @property
    def has_surplus(self) -> bool:
        return self.surplus_kwh > 1e-6

    @property
    def has_deficit(self) -> bool:
        return self.deficit_kwh > 1e-6

    def to_dict(self) -> Dict[str, Union[str, float, None]]:
        return {
            "house_id": self.house_id,
            "timestamp": str(self.timestamp) if self.timestamp is not None else None,
            "demand_kwh": round(self.demand_kwh, 4),
            "solar_generation_kwh": round(self.solar_generation_kwh, 4),
            "self_consumption_kwh": round(self.self_consumption_kwh, 4),
            "deficit_kwh": round(self.deficit_kwh, 4),
            "surplus_kwh": round(self.surplus_kwh, 4),
        }


@dataclass
class PostTradeEnergyBalance:
    """Post-trade energy balance accounting for local solar, P2P exchange, and grid."""

    house_id: str
    demand_kwh: float
    solar_generation_kwh: float
    self_consumption_kwh: float
    initial_deficit_kwh: float
    initial_surplus_kwh: float
    p2p_bought_kwh: float
    p2p_sold_kwh: float
    grid_imported_kwh: float
    grid_exported_kwh: float
    timestamp: Optional[pd.Timestamp] = None

    def __post_init__(self) -> None:
        for name, val in [
            ("demand_kwh", self.demand_kwh),
            ("solar_generation_kwh", self.solar_generation_kwh),
            ("self_consumption_kwh", self.self_consumption_kwh),
            ("initial_deficit_kwh", self.initial_deficit_kwh),
            ("initial_surplus_kwh", self.initial_surplus_kwh),
            ("p2p_bought_kwh", self.p2p_bought_kwh),
            ("p2p_sold_kwh", self.p2p_sold_kwh),
            ("grid_imported_kwh", self.grid_imported_kwh),
            ("grid_exported_kwh", self.grid_exported_kwh),
        ]:
            if not np.isfinite(val):
                raise ValueError(f"Non-finite value detected for {name}: {val}")
            if float(val) < -1e-6:
                raise ValueError(f"Negative value detected for {name}: {val}")

        # Numerical tolerance adjustment
        self.demand_kwh = max(0.0, float(self.demand_kwh))
        self.solar_generation_kwh = max(0.0, float(self.solar_generation_kwh))
        self.self_consumption_kwh = max(0.0, float(self.self_consumption_kwh))
        self.initial_deficit_kwh = max(0.0, float(self.initial_deficit_kwh))
        self.initial_surplus_kwh = max(0.0, float(self.initial_surplus_kwh))
        self.p2p_bought_kwh = max(0.0, float(self.p2p_bought_kwh))
        self.p2p_sold_kwh = max(0.0, float(self.p2p_sold_kwh))
        self.grid_imported_kwh = max(0.0, float(self.grid_imported_kwh))
        self.grid_exported_kwh = max(0.0, float(self.grid_exported_kwh))

        # Complementarity checks
        if self.initial_surplus_kwh > 1e-6 and self.initial_deficit_kwh > 1e-6:
            raise ValueError("Household cannot have simultaneous initial surplus and deficit.")
        if self.p2p_bought_kwh > 1e-6 and self.p2p_sold_kwh > 1e-6:
            raise ValueError("Household cannot simultaneously buy and sell P2P energy in the same interval.")
        if self.grid_imported_kwh > 1e-6 and self.grid_exported_kwh > 1e-6:
            raise ValueError("Household cannot simultaneously import from and export to the grid.")

        # Conservation of demand: D = self_consumption + p2p_bought + grid_imported
        d_served = self.self_consumption_kwh + self.p2p_bought_kwh + self.grid_imported_kwh
        if abs(self.demand_kwh - d_served) > 1e-5:
            raise ValueError(f"Post-trade demand conservation violation: {self.demand_kwh} != {d_served}")

        # Conservation of solar: G = self_consumption + p2p_sold + grid_exported
        g_allocated = self.self_consumption_kwh + self.p2p_sold_kwh + self.grid_exported_kwh
        if abs(self.solar_generation_kwh - g_allocated) > 1e-5:
            raise ValueError(f"Post-trade solar conservation violation: {self.solar_generation_kwh} != {g_allocated}")

    def to_dict(self) -> Dict[str, Union[str, float, None]]:
        return {
            "house_id": self.house_id,
            "timestamp": str(self.timestamp) if self.timestamp is not None else None,
            "demand_kwh": round(self.demand_kwh, 4),
            "solar_generation_kwh": round(self.solar_generation_kwh, 4),
            "self_consumption_kwh": round(self.self_consumption_kwh, 4),
            "initial_deficit_kwh": round(self.initial_deficit_kwh, 4),
            "initial_surplus_kwh": round(self.initial_surplus_kwh, 4),
            "p2p_bought_kwh": round(self.p2p_bought_kwh, 4),
            "p2p_sold_kwh": round(self.p2p_sold_kwh, 4),
            "grid_imported_kwh": round(self.grid_imported_kwh, 4),
            "grid_exported_kwh": round(self.grid_exported_kwh, 4),
        }


def compute_energy_balance(
    demand_kwh: float,
    solar_generation_kwh: float,
    house_id: str = "H001",
    timestamp: Optional[pd.Timestamp] = None,
) -> EnergyBalance:
    """Calculate hourly energy balance components for a household.

    Parameters
    ----------
    demand_kwh : float
        Electricity consumption in kWh (must be finite and >= 0).
    solar_generation_kwh : float
        Solar generation in kWh (must be finite and >= 0).
    house_id : str
        Household identifier.
    timestamp : Optional[pd.Timestamp]
        Timestamp of the observation.

    Returns
    -------
    EnergyBalance
        Validated energy balance object.
    """
    if not np.isfinite(demand_kwh):
        raise ValueError(f"demand_kwh must be a finite number, got {demand_kwh}")
    if not np.isfinite(solar_generation_kwh):
        raise ValueError(f"solar_generation_kwh must be a finite number, got {solar_generation_kwh}")
    if float(demand_kwh) < -1e-6:
        raise ValueError(f"demand_kwh must be >= 0, got {demand_kwh}")
    if float(solar_generation_kwh) < -1e-6:
        raise ValueError(f"solar_generation_kwh must be >= 0, got {solar_generation_kwh}")
    d = max(0.0, float(demand_kwh))
    s = max(0.0, float(solar_generation_kwh))

    self_consumption = min(d, s)
    deficit = max(0.0, d - s)
    surplus = max(0.0, s - d)

    return EnergyBalance(
        house_id=house_id,
        demand_kwh=d,
        solar_generation_kwh=s,
        self_consumption_kwh=self_consumption,
        deficit_kwh=deficit,
        surplus_kwh=surplus,
        timestamp=timestamp,
    )


def compute_post_trade_balance(
    balance: EnergyBalance,
    p2p_sold_kwh: float = 0.0,
    p2p_bought_kwh: float = 0.0,
) -> PostTradeEnergyBalance:
    """Calculate post-trade physical flows and remaining grid interactions.

    Parameters
    ----------
    balance : EnergyBalance
        Pre-trade household energy balance.
    p2p_sold_kwh : float
        Quantity of surplus solar sold to peer (must be <= surplus_kwh).
    p2p_bought_kwh : float
        Quantity of energy purchased from peer (must be <= deficit_kwh).

    Returns
    -------
    PostTradeEnergyBalance
        Validated post-trade energy balance.
    """
    for val, name in [(p2p_sold_kwh, "p2p_sold_kwh"), (p2p_bought_kwh, "p2p_bought_kwh")]:
        if not np.isfinite(val):
            raise ValueError(f"{name} must be a finite number, got {val}")
        if float(val) < -1e-6:
            raise ValueError(f"{name} must be nonnegative, got {val}")

    sold = max(0.0, float(p2p_sold_kwh))
    bought = max(0.0, float(p2p_bought_kwh))

    if sold > 1e-6 and bought > 1e-6:
        raise ValueError("Household cannot simultaneously sell and buy P2P energy in the same interval.")

    if sold > balance.surplus_kwh + 1e-6:
        raise ValueError(
            f"Cannot sell {sold:.4f} kWh: only {balance.surplus_kwh:.4f} kWh surplus available."
        )
    if bought > balance.deficit_kwh + 1e-6:
        raise ValueError(
            f"Cannot buy {bought:.4f} kWh: only {balance.deficit_kwh:.4f} kWh deficit needed."
        )

    grid_imported = max(0.0, balance.deficit_kwh - bought)
    grid_exported = max(0.0, balance.surplus_kwh - sold)

    if isinstance(balance, BatteryAwareEnergyBalance):
        return compute_battery_post_trade_balance(
            balance=balance,
            p2p_sold_kwh=p2p_sold_kwh,
            p2p_bought_kwh=p2p_bought_kwh,
        )

    return PostTradeEnergyBalance(
        house_id=balance.house_id,
        demand_kwh=balance.demand_kwh,
        solar_generation_kwh=balance.solar_generation_kwh,
        self_consumption_kwh=balance.self_consumption_kwh,
        initial_deficit_kwh=balance.deficit_kwh,
        initial_surplus_kwh=balance.surplus_kwh,
        p2p_bought_kwh=bought,
        p2p_sold_kwh=sold,
        grid_imported_kwh=grid_imported,
        grid_exported_kwh=grid_exported,
        timestamp=balance.timestamp,
    )


@dataclass
class BatteryAwareEnergyBalance:
    """Hourly energy balance for a household with integrated battery storage.

    Enforces physical energy balance conservation:
    Demand = E_{self} + D_{battery} + E_{deficit}^{post}
    Solar  = E_{self} + C_{battery} + E_{surplus}^{post}
    Net    = (Demand - Solar) == (E_{deficit}^{post} - E_{surplus}^{post}) + (D_{battery} - C_{battery})
    """

    house_id: str
    demand_kwh: float
    solar_generation_kwh: float
    self_consumption_kwh: float
    solar_to_battery_kwh: float  # C[t]: energy entering battery terminals
    battery_to_demand_kwh: float  # D[t]: energy delivered from battery terminals to demand
    battery_initial_soc: float
    battery_final_soc: float
    battery_initial_kwh: float
    battery_final_kwh: float
    battery_losses_kwh: float
    raw_deficit_kwh: float
    raw_surplus_kwh: float
    deficit_kwh: float  # remaining post-battery deficit
    surplus_kwh: float  # remaining post-battery surplus
    timestamp: Optional[pd.Timestamp] = None

    def __post_init__(self) -> None:
        for name, val in [
            ("demand_kwh", self.demand_kwh),
            ("solar_generation_kwh", self.solar_generation_kwh),
            ("self_consumption_kwh", self.self_consumption_kwh),
            ("solar_to_battery_kwh", self.solar_to_battery_kwh),
            ("battery_to_demand_kwh", self.battery_to_demand_kwh),
            ("battery_initial_soc", self.battery_initial_soc),
            ("battery_final_soc", self.battery_final_soc),
            ("battery_initial_kwh", self.battery_initial_kwh),
            ("battery_final_kwh", self.battery_final_kwh),
            ("battery_losses_kwh", self.battery_losses_kwh),
            ("raw_deficit_kwh", self.raw_deficit_kwh),
            ("raw_surplus_kwh", self.raw_surplus_kwh),
            ("deficit_kwh", self.deficit_kwh),
            ("surplus_kwh", self.surplus_kwh),
        ]:
            if not np.isfinite(val):
                raise ValueError(f"Non-finite value detected for {name}: {val}")
            if float(val) < -1e-6:
                raise ValueError(f"Negative value detected for {name}: {val}")

        self.demand_kwh = max(0.0, float(self.demand_kwh))
        self.solar_generation_kwh = max(0.0, float(self.solar_generation_kwh))
        self.self_consumption_kwh = max(0.0, float(self.self_consumption_kwh))
        self.solar_to_battery_kwh = max(0.0, float(self.solar_to_battery_kwh))
        self.battery_to_demand_kwh = max(0.0, float(self.battery_to_demand_kwh))
        self.battery_initial_soc = max(0.0, float(self.battery_initial_soc))
        self.battery_final_soc = max(0.0, float(self.battery_final_soc))
        self.battery_initial_kwh = max(0.0, float(self.battery_initial_kwh))
        self.battery_final_kwh = max(0.0, float(self.battery_final_kwh))
        self.battery_losses_kwh = max(0.0, float(self.battery_losses_kwh))
        self.raw_deficit_kwh = max(0.0, float(self.raw_deficit_kwh))
        self.raw_surplus_kwh = max(0.0, float(self.raw_surplus_kwh))
        self.deficit_kwh = max(0.0, float(self.deficit_kwh))
        self.surplus_kwh = max(0.0, float(self.surplus_kwh))

        # Complementarity checks
        if self.surplus_kwh > 1e-6 and self.deficit_kwh > 1e-6:
            raise ValueError(
                f"Complementarity violation: cannot have simultaneous post-battery surplus "
                f"({self.surplus_kwh:.4f}) and deficit ({self.deficit_kwh:.4f})"
            )
        if self.solar_to_battery_kwh > 1e-6 and self.battery_to_demand_kwh > 1e-6:
            raise ValueError(
                f"Mutual exclusion violation: cannot simultaneously charge ({self.solar_to_battery_kwh:.4f}) "
                f"and discharge ({self.battery_to_demand_kwh:.4f}) in the same interval"
            )

        # Demand conservation: D = self_consumption + battery_to_demand + deficit
        d_diff = abs(self.demand_kwh - (self.self_consumption_kwh + self.battery_to_demand_kwh + self.deficit_kwh))
        if d_diff > 1e-5:
            raise ValueError(f"Demand conservation violation: diff {d_diff:.6f}")

        # Solar conservation: G = self_consumption + solar_to_battery + surplus
        s_diff = abs(self.solar_generation_kwh - (self.self_consumption_kwh + self.solar_to_battery_kwh + self.surplus_kwh))
        if s_diff > 1e-5:
            raise ValueError(f"Solar conservation violation: diff {s_diff:.6f}")

        # Net balance conservation: (D - G) == (deficit - surplus) + (D_bat - C_bat)
        net_actual = self.demand_kwh - self.solar_generation_kwh
        net_accounted = (self.deficit_kwh - self.surplus_kwh) + (self.battery_to_demand_kwh - self.solar_to_battery_kwh)
        if abs(net_actual - net_accounted) > 1e-5:
            raise ValueError(f"Net conservation violation: {net_actual:.6f} != {net_accounted:.6f}")

    @property
    def has_surplus(self) -> bool:
        return self.surplus_kwh > 1e-6

    @property
    def has_deficit(self) -> bool:
        return self.deficit_kwh > 1e-6

    @property
    def net_stored_energy_change_kwh(self) -> float:
        """Net change in stored chemical energy: positive = net charge, negative = net drain."""
        return self.battery_final_kwh - self.battery_initial_kwh

    def to_dict(self) -> Dict[str, Union[str, float, None]]:
        return {
            "house_id": self.house_id,
            "timestamp": str(self.timestamp) if self.timestamp is not None else None,
            "demand_kwh": round(self.demand_kwh, 4),
            "solar_generation_kwh": round(self.solar_generation_kwh, 4),
            "self_consumption_kwh": round(self.self_consumption_kwh, 4),
            "solar_to_battery_kwh": round(self.solar_to_battery_kwh, 4),
            "battery_to_demand_kwh": round(self.battery_to_demand_kwh, 4),
            "battery_initial_soc": round(self.battery_initial_soc, 4),
            "battery_final_soc": round(self.battery_final_soc, 4),
            "battery_initial_kwh": round(self.battery_initial_kwh, 4),
            "battery_final_kwh": round(self.battery_final_kwh, 4),
            "battery_losses_kwh": round(self.battery_losses_kwh, 4),
            "raw_deficit_kwh": round(self.raw_deficit_kwh, 4),
            "raw_surplus_kwh": round(self.raw_surplus_kwh, 4),
            "deficit_kwh": round(self.deficit_kwh, 4),
            "surplus_kwh": round(self.surplus_kwh, 4),
        }


@dataclass
class BatteryAwarePostTradeBalance:
    """Post-trade energy balance accounting for local solar, battery storage, P2P exchange, and grid."""

    house_id: str
    demand_kwh: float
    solar_generation_kwh: float
    self_consumption_kwh: float
    solar_to_battery_kwh: float
    battery_to_demand_kwh: float
    battery_initial_soc: float
    battery_final_soc: float
    battery_initial_kwh: float
    battery_final_kwh: float
    battery_losses_kwh: float
    post_battery_deficit_kwh: float
    post_battery_surplus_kwh: float
    p2p_bought_kwh: float
    p2p_sold_kwh: float
    grid_imported_kwh: float
    grid_exported_kwh: float
    timestamp: Optional[pd.Timestamp] = None

    def __post_init__(self) -> None:
        for name, val in [
            ("demand_kwh", self.demand_kwh),
            ("solar_generation_kwh", self.solar_generation_kwh),
            ("self_consumption_kwh", self.self_consumption_kwh),
            ("solar_to_battery_kwh", self.solar_to_battery_kwh),
            ("battery_to_demand_kwh", self.battery_to_demand_kwh),
            ("battery_initial_soc", self.battery_initial_soc),
            ("battery_final_soc", self.battery_final_soc),
            ("battery_initial_kwh", self.battery_initial_kwh),
            ("battery_final_kwh", self.battery_final_kwh),
            ("battery_losses_kwh", self.battery_losses_kwh),
            ("post_battery_deficit_kwh", self.post_battery_deficit_kwh),
            ("post_battery_surplus_kwh", self.post_battery_surplus_kwh),
            ("p2p_bought_kwh", self.p2p_bought_kwh),
            ("p2p_sold_kwh", self.p2p_sold_kwh),
            ("grid_imported_kwh", self.grid_imported_kwh),
            ("grid_exported_kwh", self.grid_exported_kwh),
        ]:
            if not np.isfinite(val):
                raise ValueError(f"Non-finite value detected for {name}: {val}")
            if float(val) < -1e-6:
                raise ValueError(f"Negative value detected for {name}: {val}")

        self.demand_kwh = max(0.0, float(self.demand_kwh))
        self.solar_generation_kwh = max(0.0, float(self.solar_generation_kwh))
        self.self_consumption_kwh = max(0.0, float(self.self_consumption_kwh))
        self.solar_to_battery_kwh = max(0.0, float(self.solar_to_battery_kwh))
        self.battery_to_demand_kwh = max(0.0, float(self.battery_to_demand_kwh))
        self.battery_initial_soc = max(0.0, float(self.battery_initial_soc))
        self.battery_final_soc = max(0.0, float(self.battery_final_soc))
        self.battery_initial_kwh = max(0.0, float(self.battery_initial_kwh))
        self.battery_final_kwh = max(0.0, float(self.battery_final_kwh))
        self.battery_losses_kwh = max(0.0, float(self.battery_losses_kwh))
        self.post_battery_deficit_kwh = max(0.0, float(self.post_battery_deficit_kwh))
        self.post_battery_surplus_kwh = max(0.0, float(self.post_battery_surplus_kwh))
        self.p2p_bought_kwh = max(0.0, float(self.p2p_bought_kwh))
        self.p2p_sold_kwh = max(0.0, float(self.p2p_sold_kwh))
        self.grid_imported_kwh = max(0.0, float(self.grid_imported_kwh))
        self.grid_exported_kwh = max(0.0, float(self.grid_exported_kwh))

        # Complementarity checks
        if self.p2p_bought_kwh > 1e-6 and self.p2p_sold_kwh > 1e-6:
            raise ValueError("Household cannot simultaneously buy and sell P2P energy in the same interval.")
        if self.grid_imported_kwh > 1e-6 and self.grid_exported_kwh > 1e-6:
            raise ValueError("Household cannot simultaneously import from and export to the grid.")
        if self.solar_to_battery_kwh > 1e-6 and self.battery_to_demand_kwh > 1e-6:
            raise ValueError("Household cannot simultaneously charge and discharge battery.")

        # Demand conservation: D = self_consumption + battery_to_demand + p2p_bought + grid_imported
        d_served = self.self_consumption_kwh + self.battery_to_demand_kwh + self.p2p_bought_kwh + self.grid_imported_kwh
        if abs(self.demand_kwh - d_served) > 1e-5:
            raise ValueError(f"Post-trade demand conservation violation: {self.demand_kwh} != {d_served}")

        # Solar conservation: G = self_consumption + solar_to_battery + p2p_sold + grid_exported
        g_allocated = self.self_consumption_kwh + self.solar_to_battery_kwh + self.p2p_sold_kwh + self.grid_exported_kwh
        if abs(self.solar_generation_kwh - g_allocated) > 1e-5:
            raise ValueError(f"Post-trade solar conservation violation: {self.solar_generation_kwh} != {g_allocated}")

    @property
    def initial_deficit_kwh(self) -> float:
        """Alias for post-battery deficit available before P2P trade."""
        return self.post_battery_deficit_kwh

    @property
    def initial_surplus_kwh(self) -> float:
        """Alias for post-battery surplus available before P2P trade."""
        return self.post_battery_surplus_kwh

    @property
    def net_stored_energy_change_kwh(self) -> float:
        return self.battery_final_kwh - self.battery_initial_kwh

    def to_dict(self) -> Dict[str, Union[str, float, None]]:
        return {
            "house_id": self.house_id,
            "timestamp": str(self.timestamp) if self.timestamp is not None else None,
            "demand_kwh": round(self.demand_kwh, 4),
            "solar_generation_kwh": round(self.solar_generation_kwh, 4),
            "self_consumption_kwh": round(self.self_consumption_kwh, 4),
            "solar_to_battery_kwh": round(self.solar_to_battery_kwh, 4),
            "battery_to_demand_kwh": round(self.battery_to_demand_kwh, 4),
            "battery_initial_soc": round(self.battery_initial_soc, 4),
            "battery_final_soc": round(self.battery_final_soc, 4),
            "battery_initial_kwh": round(self.battery_initial_kwh, 4),
            "battery_final_kwh": round(self.battery_final_kwh, 4),
            "battery_losses_kwh": round(self.battery_losses_kwh, 4),
            "post_battery_deficit_kwh": round(self.post_battery_deficit_kwh, 4),
            "post_battery_surplus_kwh": round(self.post_battery_surplus_kwh, 4),
            "p2p_bought_kwh": round(self.p2p_bought_kwh, 4),
            "p2p_sold_kwh": round(self.p2p_sold_kwh, 4),
            "grid_imported_kwh": round(self.grid_imported_kwh, 4),
            "grid_exported_kwh": round(self.grid_exported_kwh, 4),
        }


def compute_battery_aware_balance(
    demand_kwh: float,
    solar_generation_kwh: float,
    battery: Optional[BatteryStorage] = None,
    house_id: str = "H001",
    timestamp: Optional[pd.Timestamp] = None,
    duration_hours: float = 1.0,
    inplace: bool = True,
) -> BatteryAwareEnergyBalance:
    """Compute physical energy balance incorporating residential battery dispatch.

    Transparent Baseline Policy:
    1. Direct self-consumption: E_{self} = min(Demand, Solar).
    2. Battery dispatch:
       - If Solar > Demand: charge battery from surplus solar up to power/headroom limits.
       - If Demand > Solar: discharge battery to meet unmet demand up to power/footroom limits.
    3. Residual surplus/deficit is made available for subsequent P2P trading or grid exchange.

    Parameters
    ----------
    demand_kwh : float
        Gross electricity consumption.
    solar_generation_kwh : float
        Gross solar generation.
    battery : Optional[BatteryStorage]
        Battery storage instance. If None, battery dispatch is zero.
    house_id : str
        Household identifier.
    timestamp : Optional[pd.Timestamp]
        Interval timestamp.
    duration_hours : float
        Timestep duration in hours (default 1.0).
    inplace : bool
        If True, modifies battery state in-place. If False, operates on an independent copy.

    Returns
    -------
    BatteryAwareEnergyBalance
        Validated balance record with complete initial/final SOC and flow accounting.
    """
    for name, val in [
        ("demand_kwh", demand_kwh),
        ("solar_generation_kwh", solar_generation_kwh),
        ("duration_hours", duration_hours),
    ]:
        if not np.isfinite(val):
            raise ValueError(f"{name} must be a finite number, got {val}")
        if float(val) < -1e-6:
            raise ValueError(f"{name} must be >= 0, got {val}")

    if duration_hours <= 0.0:
        raise ValueError(f"duration_hours must be positive, got {duration_hours}")

    d = max(0.0, float(demand_kwh))
    s = max(0.0, float(solar_generation_kwh))

    self_consumption = min(d, s)
    raw_deficit = max(0.0, d - s)
    raw_surplus = max(0.0, s - d)

    if battery is None:
        return BatteryAwareEnergyBalance(
            house_id=house_id,
            demand_kwh=d,
            solar_generation_kwh=s,
            self_consumption_kwh=self_consumption,
            solar_to_battery_kwh=0.0,
            battery_to_demand_kwh=0.0,
            battery_initial_soc=0.0,
            battery_final_soc=0.0,
            battery_initial_kwh=0.0,
            battery_final_kwh=0.0,
            battery_losses_kwh=0.0,
            raw_deficit_kwh=raw_deficit,
            raw_surplus_kwh=raw_surplus,
            deficit_kwh=raw_deficit,
            surplus_kwh=raw_surplus,
            timestamp=timestamp,
        )

    bat = battery if inplace else battery.copy()
    init_kwh = float(bat.current_charge_kwh)
    init_soc = float(bat.soc)

    solar_to_bat = 0.0
    bat_to_demand = 0.0

    if raw_surplus > 1e-6:
        # Step 2A: Charge from surplus solar
        state = bat.step(
            energy_available_to_charge_kwh=raw_surplus,
            energy_requested_to_discharge_kwh=0.0,
            duration_hours=duration_hours,
        )
        solar_to_bat = state.charged_kwh
        rem_surplus = max(0.0, raw_surplus - solar_to_bat)
        rem_deficit = 0.0
    elif raw_deficit > 1e-6:
        # Step 2B: Discharge to serve unmet demand
        state = bat.step(
            energy_available_to_charge_kwh=0.0,
            energy_requested_to_discharge_kwh=raw_deficit,
            duration_hours=duration_hours,
        )
        bat_to_demand = state.discharged_kwh
        rem_surplus = 0.0
        rem_deficit = max(0.0, raw_deficit - bat_to_demand)
    else:
        state = bat.step(0.0, 0.0, duration_hours=duration_hours)
        rem_surplus = 0.0
        rem_deficit = 0.0

    final_kwh = float(state.current_charge_kwh)
    final_soc = float(state.soc)

    if solar_to_bat > 0.0:
        losses = max(0.0, solar_to_bat - (final_kwh - init_kwh))
    elif bat_to_demand > 0.0:
        losses = max(0.0, (init_kwh - final_kwh) - bat_to_demand)
    else:
        losses = 0.0

    return BatteryAwareEnergyBalance(
        house_id=house_id,
        demand_kwh=d,
        solar_generation_kwh=s,
        self_consumption_kwh=self_consumption,
        solar_to_battery_kwh=solar_to_bat,
        battery_to_demand_kwh=bat_to_demand,
        battery_initial_soc=init_soc,
        battery_final_soc=final_soc,
        battery_initial_kwh=init_kwh,
        battery_final_kwh=final_kwh,
        battery_losses_kwh=losses,
        raw_deficit_kwh=raw_deficit,
        raw_surplus_kwh=raw_surplus,
        deficit_kwh=rem_deficit,
        surplus_kwh=rem_surplus,
        timestamp=timestamp,
    )


def compute_battery_post_trade_balance(
    balance: Union[BatteryAwareEnergyBalance, EnergyBalance],
    p2p_sold_kwh: float = 0.0,
    p2p_bought_kwh: float = 0.0,
) -> BatteryAwarePostTradeBalance:
    """Calculate post-trade physical flows and remaining grid interactions for battery-aware household.

    Parameters
    ----------
    balance : Union[BatteryAwareEnergyBalance, EnergyBalance]
        Pre-trade household energy balance.
    p2p_sold_kwh : float
        Quantity of post-battery surplus solar sold to peer (must be <= surplus_kwh).
    p2p_bought_kwh : float
        Quantity of energy purchased from peer (must be <= deficit_kwh).

    Returns
    -------
    BatteryAwarePostTradeBalance
        Validated post-trade balance with battery and grid flows.
    """
    for val, name in [(p2p_sold_kwh, "p2p_sold_kwh"), (p2p_bought_kwh, "p2p_bought_kwh")]:
        if not np.isfinite(val):
            raise ValueError(f"{name} must be a finite number, got {val}")
        if float(val) < -1e-6:
            raise ValueError(f"{name} must be nonnegative, got {val}")

    sold = max(0.0, float(p2p_sold_kwh))
    bought = max(0.0, float(p2p_bought_kwh))

    if sold > 1e-6 and bought > 1e-6:
        raise ValueError("Household cannot simultaneously sell and buy P2P energy in the same interval.")

    if sold > balance.surplus_kwh + 1e-6:
        raise ValueError(
            f"Cannot sell {sold:.4f} kWh: only {balance.surplus_kwh:.4f} kWh post-battery surplus available."
        )
    if bought > balance.deficit_kwh + 1e-6:
        raise ValueError(
            f"Cannot buy {bought:.4f} kWh: only {balance.deficit_kwh:.4f} kWh post-battery deficit needed."
        )

    grid_imported = max(0.0, balance.deficit_kwh - bought)
    grid_exported = max(0.0, balance.surplus_kwh - sold)

    solar_to_bat = getattr(balance, "solar_to_battery_kwh", 0.0)
    bat_to_demand = getattr(balance, "battery_to_demand_kwh", 0.0)
    init_soc = getattr(balance, "battery_initial_soc", 0.0)
    final_soc = getattr(balance, "battery_final_soc", 0.0)
    init_kwh = getattr(balance, "battery_initial_kwh", 0.0)
    final_kwh = getattr(balance, "battery_final_kwh", 0.0)
    losses = getattr(balance, "battery_losses_kwh", 0.0)

    return BatteryAwarePostTradeBalance(
        house_id=balance.house_id,
        demand_kwh=balance.demand_kwh,
        solar_generation_kwh=balance.solar_generation_kwh,
        self_consumption_kwh=balance.self_consumption_kwh,
        solar_to_battery_kwh=solar_to_bat,
        battery_to_demand_kwh=bat_to_demand,
        battery_initial_soc=init_soc,
        battery_final_soc=final_soc,
        battery_initial_kwh=init_kwh,
        battery_final_kwh=final_kwh,
        battery_losses_kwh=losses,
        post_battery_deficit_kwh=balance.deficit_kwh,
        post_battery_surplus_kwh=balance.surplus_kwh,
        p2p_bought_kwh=bought,
        p2p_sold_kwh=sold,
        grid_imported_kwh=grid_imported,
        grid_exported_kwh=grid_exported,
        timestamp=balance.timestamp,
    )


def compute_energy_balance_series(
    df: pd.DataFrame,
    demand_col: str = "total_demand_kwh",
    solar_col: str = "solar_generation_kwh",
    house_col: str = "house_id",
    timestamp_col: str = "timestamp",
) -> pd.DataFrame:
    """Compute energy balance across a DataFrame of observations."""
    out = df.copy()
    d_raw = out[demand_col].to_numpy(dtype=float)
    s_raw = out[solar_col].to_numpy(dtype=float)

    if not np.all(np.isfinite(d_raw)):
        raise ValueError(f"Non-finite values found in {demand_col}")
    if not np.all(np.isfinite(s_raw)):
        raise ValueError(f"Non-finite values found in {solar_col}")
    if np.any(d_raw < -1e-6):
        raise ValueError(f"Negative values found in {demand_col}")
    if np.any(s_raw < -1e-6):
        raise ValueError(f"Negative values found in {solar_col}")

    d = np.maximum(0.0, d_raw)
    s = np.maximum(0.0, s_raw)

    out["self_consumption_kwh"] = np.minimum(d, s)
    out["deficit_kwh"] = np.maximum(0.0, d - s)
    out["surplus_kwh"] = np.maximum(0.0, s - d)
    return out
