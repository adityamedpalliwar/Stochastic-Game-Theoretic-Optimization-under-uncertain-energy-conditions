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
    initial_charge_kwh: float = 0.0
    initial_soc: float = 0.0

    @property
    def net_stored_energy_change_kwh(self) -> float:
        """Net change in stored energy: positive = charged, negative = depleted."""
        return self.current_charge_kwh - self.initial_charge_kwh


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
        self.default_initial_soc = float(initial_soc)

        self.min_charge_kwh = self.min_soc * self.capacity_kwh
        self.max_charge_kwh = self.max_soc * self.capacity_kwh
        self.current_charge_kwh = float(initial_soc * self.capacity_kwh)

    @property
    def soc(self) -> float:
        """Current State of Charge in [0, 1]."""
        return self.current_charge_kwh / self.capacity_kwh

    def reset(self, initial_soc: Optional[float] = None) -> None:
        """Reset battery state of charge."""
        target_soc = self.default_initial_soc if initial_soc is None else float(initial_soc)
        if not (self.min_soc <= target_soc <= self.max_soc):
            raise ValueError(
                f"Cannot reset: target SOC {target_soc:.4f} outside [{self.min_soc}, {self.max_soc}]."
            )
        self.current_charge_kwh = target_soc * self.capacity_kwh

    def copy(self) -> BatteryStorage:
        """Create an independent copy with the current state."""
        b = BatteryStorage(
            capacity_kwh=self.capacity_kwh,
            max_charge_rate_kw=self.max_charge_rate_kw,
            max_discharge_rate_kw=self.max_discharge_rate_kw,
            charge_efficiency=self.charge_efficiency,
            discharge_efficiency=self.discharge_efficiency,
            min_soc=self.min_soc,
            max_soc=self.max_soc,
            initial_soc=self.default_initial_soc,
        )
        b.current_charge_kwh = float(self.current_charge_kwh)
        return b

    def available_charge_headroom_kwh(self, duration_hours: float = 1.0) -> float:
        """Maximum energy that can enter battery during this interval given power and SOC limits."""
        max_from_power = self.max_charge_rate_kw * duration_hours
        headroom_kwh = (self.max_charge_kwh - self.current_charge_kwh) / self.charge_efficiency
        return max(0.0, min(max_from_power, headroom_kwh))

    def available_discharge_capacity_kwh(self, duration_hours: float = 1.0) -> float:
        """Maximum energy that can be delivered from battery during this interval given power and SOC limits."""
        max_from_power = self.max_discharge_rate_kw * duration_hours
        available_stored = (self.current_charge_kwh - self.min_charge_kwh) * self.discharge_efficiency
        return max(0.0, min(max_from_power, available_stored))

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
        for name, val in [
            ("energy_available_to_charge_kwh", energy_available_to_charge_kwh),
            ("energy_requested_to_discharge_kwh", energy_requested_to_discharge_kwh),
            ("duration_hours", duration_hours),
        ]:
            if not np.isfinite(val):
                raise ValueError(f"{name} must be a finite number, got {val}")
            if float(val) < -1e-6:
                raise ValueError(f"{name} must be nonnegative, got {val}")

        if duration_hours <= 0.0:
            raise ValueError(f"duration_hours must be positive, got {duration_hours}")

        # Mutual exclusion: cannot charge and discharge simultaneously
        if energy_available_to_charge_kwh > 0.0 and energy_requested_to_discharge_kwh > 0.0:
            raise ValueError("Cannot charge and discharge simultaneously in the same step.")

        initial_charge = float(self.current_charge_kwh)
        initial_soc = float(self.soc)

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
            initial_charge_kwh=initial_charge,
            initial_soc=initial_soc,
        )
