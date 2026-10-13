"""Battery Energy Storage System (BESS) model with physical constraints.

Implements:
- Capacity limits: SOC_min <= SOC_t <= SOC_max
- Charge/discharge power limits: 0 <= P_ch <= P_ch_max, 0 <= P_dis <= P_dis_max
- Charging efficiency eta_ch and discharging efficiency eta_dis
- Exact state-of-charge energy balance update
- Mutual exclusion between charging and discharging
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Union

import numpy as np


@dataclass
class BatteryState:
    """Snapshot of battery operational status."""

    capacity_kwh: float
    current_charge_kwh: float
    soc: float
    charged_kwh: float
    discharged_kwh: float


class BatteryStorage:
    """Models a physical residential battery system."""

    def __init__(
        self,
        capacity_kwh: float = 5.0,
        max_charge_rate_kw: float = 2.5,
        max_discharge_rate_kw: float = 2.5,
        charge_efficiency: float = 0.95,
        discharge_efficiency: float = 0.95,
        min_soc: float = 0.10,
        max_soc: float = 0.90,
        initial_soc: float = 0.50,
    ) -> None:
        if capacity_kwh <= 0:
            raise ValueError("Battery capacity must be positive.")
        if not (0.0 <= min_soc < max_soc <= 1.0):
            raise ValueError("Invalid SOC limits: require 0 <= min_soc < max_soc <= 1.")
        if not (min_soc <= initial_soc <= max_soc):
            raise ValueError("Initial SOC must be within [min_soc, max_soc].")

        self.capacity_kwh = float(capacity_kwh)
        self.max_charge_rate_kw = float(max_charge_rate_kw)
        self.max_discharge_rate_kw = float(max_discharge_rate_kw)
        self.charge_efficiency = float(charge_efficiency)
        self.discharge_efficiency = float(discharge_efficiency)
        self.min_soc = float(min_soc)
        self.max_soc = float(max_soc)

        self.min_charge_kwh = self.min_soc * self.capacity_kwh
        self.max_charge_kwh = self.max_soc * self.capacity_kwh
        self.current_charge_kwh = float(initial_soc * self.capacity_kwh)

    @property
    def soc(self) -> float:
        """Current State of Charge in [0, 1]."""
        return self.current_charge_kwh / self.capacity_kwh

    def step(
        self,
        energy_available_to_charge_kwh: float = 0.0,
        energy_requested_to_discharge_kwh: float = 0.0,
        duration_hours: float = 1.0,
    ) -> BatteryState:
        """Simulate one operational time step.

        Parameters
        ----------
        energy_available_to_charge_kwh : float
            Surplus energy available to store (e.g. from solar).
        energy_requested_to_discharge_kwh : float
            Deficit energy requested to draw (e.g. for demand).
        duration_hours : float
            Timestep length (default 1.0 hour).

        Returns
        -------
        BatteryState
            Resulting state with actual charged and discharged kWh.
        """
        # Mutual exclusion: cannot charge and discharge simultaneously
        if energy_available_to_charge_kwh > 0.0 and energy_requested_to_discharge_kwh > 0.0:
            raise ValueError("Cannot charge and discharge simultaneously in the same step.")

        actual_charged = 0.0
        actual_discharged = 0.0

        if energy_available_to_charge_kwh > 0.0:
            # Power limit
            max_from_power = self.max_charge_rate_kw * duration_hours
            # Headroom limit
            headroom_kwh = (self.max_charge_kwh - self.current_charge_kwh) / self.charge_efficiency
            actual_charged = max(0.0, min(energy_available_to_charge_kwh, max_from_power, headroom_kwh))
            self.current_charge_kwh += actual_charged * self.charge_efficiency

        elif energy_requested_to_discharge_kwh > 0.0:
            # Power limit
            max_from_power = self.max_discharge_rate_kw * duration_hours
            # Footroom limit
            available_stored = (self.current_charge_kwh - self.min_charge_kwh) * self.discharge_efficiency
            actual_discharged = max(0.0, min(energy_requested_to_discharge_kwh, max_from_power, available_stored))
            self.current_charge_kwh -= actual_discharged / self.discharge_efficiency

        # Numerical cleanup within limits
        self.current_charge_kwh = np.clip(self.current_charge_kwh, self.min_charge_kwh, self.max_charge_kwh)

        return BatteryState(
            capacity_kwh=self.capacity_kwh,
            current_charge_kwh=self.current_charge_kwh,
            soc=self.soc,
            charged_kwh=actual_charged,
            discharged_kwh=actual_discharged,
        )
