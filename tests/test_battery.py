"""Unit tests for battery storage model."""

import pytest
from src.energy.battery import BatteryStorage


def test_battery_initialization():
    bat = BatteryStorage(capacity_kwh=5.0, initial_soc=0.50, min_soc=0.10, max_soc=0.90)
    assert bat.capacity_kwh == 5.0
    assert bat.soc == pytest.approx(0.50)
    assert bat.current_charge_kwh == pytest.approx(2.50)


def test_battery_charging():
    bat = BatteryStorage(capacity_kwh=5.0, initial_soc=0.20, charge_efficiency=0.90)
    # Charge with 1.0 kWh surplus
    state = bat.step(energy_available_to_charge_kwh=1.0)
    assert state.charged_kwh == pytest.approx(1.0)
    assert bat.current_charge_kwh == pytest.approx(1.0 + 1.0 * 0.90)
    assert state.discharged_kwh == 0.0


def test_battery_discharging():
    bat = BatteryStorage(capacity_kwh=5.0, initial_soc=0.80, discharge_efficiency=0.90)
    # Request 1.0 kWh deficit
    state = bat.step(energy_requested_to_discharge_kwh=1.0)
    assert state.discharged_kwh == pytest.approx(1.0)
    # Stored energy decreased by 1.0 / 0.90
    assert bat.current_charge_kwh == pytest.approx(4.0 - (1.0 / 0.90))


def test_battery_soc_limits():
    bat = BatteryStorage(capacity_kwh=5.0, initial_soc=0.85, max_soc=0.90)
    # Try charging huge amount
    state = bat.step(energy_available_to_charge_kwh=10.0)
    assert bat.soc <= 0.90001
    assert bat.current_charge_kwh <= 4.50001


def test_simultaneous_charge_discharge_forbidden():
    bat = BatteryStorage()
    with pytest.raises(ValueError):
        bat.step(energy_available_to_charge_kwh=1.0, energy_requested_to_discharge_kwh=1.0)
