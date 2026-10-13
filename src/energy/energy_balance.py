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
        # Enforce physical nonnegativity
        if self.demand_kwh < -1e-6 or self.solar_generation_kwh < -1e-6:
            raise ValueError(
                f"Negative energy input detected: Demand={self.demand_kwh}, Solar={self.solar_generation_kwh}"
            )
        # Numerical tolerance adjustment
        self.demand_kwh = max(0.0, float(self.demand_kwh))
        self.solar_generation_kwh = max(0.0, float(self.solar_generation_kwh))
        self.self_consumption_kwh = max(0.0, float(self.self_consumption_kwh))
        self.deficit_kwh = max(0.0, float(self.deficit_kwh))
        self.surplus_kwh = max(0.0, float(self.surplus_kwh))

        # Check conservation law
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
        Electricity consumption in kWh (must be >= 0).
    solar_generation_kwh : float
        Solar generation in kWh (must be >= 0).
    house_id : str
        Household identifier.
    timestamp : Optional[pd.Timestamp]
        Timestamp of the observation.

    Returns
    -------
    EnergyBalance
        Validated energy balance object.
    """
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


def compute_energy_balance_series(
    df: pd.DataFrame,
    demand_col: str = "total_demand_kwh",
    solar_col: str = "solar_generation_kwh",
    house_col: str = "house_id",
    timestamp_col: str = "timestamp",
) -> pd.DataFrame:
    """Compute energy balance across a DataFrame of observations."""
    out = df.copy()
    d = np.maximum(0.0, out[demand_col].to_numpy(dtype=float))
    s = np.maximum(0.0, out[solar_col].to_numpy(dtype=float))

    out["self_consumption_kwh"] = np.minimum(d, s)
    out["deficit_kwh"] = np.maximum(0.0, d - s)
    out["surplus_kwh"] = np.maximum(0.0, s - d)
    return out
