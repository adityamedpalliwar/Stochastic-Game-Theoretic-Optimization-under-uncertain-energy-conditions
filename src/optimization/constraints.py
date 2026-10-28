"""Configuration and parameter definitions for battery and MPC optimization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BatteryOptimizationParams:
    """Physical specifications and operational limits of the residential battery."""

    capacity_kwh: float = 5.0
    min_soc: float = 0.10
    max_soc: float = 0.90
    max_charge_rate_kw: float = 2.5
    max_discharge_rate_kw: float = 2.5
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.95

    def __post_init__(self) -> None:
        if self.capacity_kwh <= 0:
            raise ValueError("capacity_kwh must be strictly positive.")
        if not (0.0 <= self.min_soc < self.max_soc <= 1.0):
            raise ValueError("Require 0 <= min_soc < max_soc <= 1.")
        if self.max_charge_rate_kw <= 0 or self.max_discharge_rate_kw <= 0:
            raise ValueError("Max charge and discharge rates must be positive.")
        if not (0.0 < self.charge_efficiency <= 1.0):
            raise ValueError("charge_efficiency must be in (0, 1].")
        if not (0.0 < self.discharge_efficiency <= 1.0):
            raise ValueError("discharge_efficiency must be in (0, 1].")

    @property
    def min_energy_kwh(self) -> float:
        """Minimum permissible stored chemical energy in kWh."""
        return self.min_soc * self.capacity_kwh

    @property
    def max_energy_kwh(self) -> float:
        """Maximum permissible stored chemical energy in kWh."""
        return self.max_soc * self.capacity_kwh

    @property
    def usable_capacity_kwh(self) -> float:
        """Usable capacity between min_soc and max_soc."""
        return self.max_energy_kwh - self.min_energy_kwh

    @property
    def round_trip_efficiency(self) -> float:
        """Implied AC-to-AC round-trip efficiency."""
        return self.charge_efficiency * self.discharge_efficiency


@dataclass(frozen=True)
class TariffParams:
    """Tariff structure for electricity import and solar export."""

    import_price_aud_per_kwh: float = 0.30
    solar_export_credit_aud_per_kwh: float = 0.08

    def __post_init__(self) -> None:
        if self.import_price_aud_per_kwh < 0.0:
            raise ValueError("import_price_aud_per_kwh must be nonnegative.")
        if self.solar_export_credit_aud_per_kwh < 0.0:
            raise ValueError("solar_export_credit_aud_per_kwh must be nonnegative.")


@dataclass(frozen=True)
class MPCConfig:
    """Configuration for Model Predictive Control optimization and simulation."""

    horizon_hours: int = 24
    time_step_hours: float = 1.0
    terminal_strategy: str = "terminal_value"  # 'terminal_value', 'terminal_soc_target', 'unconstrained'
    terminal_soc_target: float = 0.50
    terminal_value_aud_per_kwh: Optional[float] = None
    allow_grid_charging: bool = True
    slack_penalty: float = 1000.0
    time_limit_sec: float = 10.0

    def __post_init__(self) -> None:
        if self.horizon_hours < 1:
            raise ValueError("horizon_hours must be at least 1.")
        if self.time_step_hours <= 0:
            raise ValueError("time_step_hours must be strictly positive.")
        valid_strategies = {"terminal_value", "terminal_soc_target", "unconstrained"}
        if self.terminal_strategy not in valid_strategies:
            raise ValueError(f"terminal_strategy must be one of {valid_strategies}, got '{self.terminal_strategy}'")
        if not (0.0 <= self.terminal_soc_target <= 1.0):
            raise ValueError("terminal_soc_target must be between 0.0 and 1.0.")
