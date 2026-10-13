"""Unit tests for energy balance and grid cost calculations."""

import pytest
import numpy as np
import pandas as pd

from src.energy.energy_balance import compute_energy_balance, compute_energy_balance_series
from src.energy.grid import GridCostCalculator, TariffScenario


def test_energy_balance_surplus():
    """Solar exceeds demand -> surplus > 0, deficit == 0."""
    balance = compute_energy_balance(demand_kwh=0.5, solar_generation_kwh=1.8, house_id="H001")
    assert balance.demand_kwh == 0.5
    assert balance.solar_generation_kwh == 1.8
    assert balance.self_consumption_kwh == 0.5
    assert balance.deficit_kwh == 0.0
    assert balance.surplus_kwh == pytest.approx(1.3)
    assert balance.has_surplus is True
    assert balance.has_deficit is False


def test_energy_balance_deficit():
    """Demand exceeds solar -> deficit > 0, surplus == 0."""
    balance = compute_energy_balance(demand_kwh=2.4, solar_generation_kwh=0.8, house_id="H002")
    assert balance.self_consumption_kwh == 0.8
    assert balance.deficit_kwh == pytest.approx(1.6)
    assert balance.surplus_kwh == 0.0
    assert balance.has_surplus is False
    assert balance.has_deficit is True


def test_energy_balance_conservation():
    """Check exact energy conservation: Demand - Solar == Deficit - Surplus."""
    rng = np.random.default_rng(123)
    demands = rng.uniform(0.0, 5.0, size=20)
    solars = rng.uniform(0.0, 5.0, size=20)
    for d, s in zip(demands, solars):
        b = compute_energy_balance(d, s)
        net_actual = b.demand_kwh - b.solar_generation_kwh
        net_computed = b.deficit_kwh - b.surplus_kwh
        assert net_actual == pytest.approx(net_computed, abs=1e-6)
        assert b.demand_kwh == pytest.approx(b.self_consumption_kwh + b.deficit_kwh, abs=1e-6)
        assert b.solar_generation_kwh == pytest.approx(b.self_consumption_kwh + b.surplus_kwh, abs=1e-6)


def test_negative_energy_rejected():
    """Energy inputs must be physically nonnegative."""
    with pytest.raises(ValueError):
        compute_energy_balance(demand_kwh=-0.5, solar_generation_kwh=1.0)
    with pytest.raises(ValueError):
        compute_energy_balance(demand_kwh=1.0, solar_generation_kwh=-0.2)


def test_grid_cost_calculator():
    """Test grid import cost and export revenue under HYPOTHETICAL_BASE."""
    calc = GridCostCalculator()
    scenario = calc.get_scenario("HYPOTHETICAL_BASE")
    assert scenario.import_price_aud_per_kwh == 0.30
    assert scenario.solar_export_credit_aud_per_kwh == 0.08

    # Case 1: Household with deficit
    b_def = compute_energy_balance(demand_kwh=2.0, solar_generation_kwh=0.5, house_id="H002")
    res_def = calc.calculate_cost(b_def, scenario_id="HYPOTHETICAL_BASE")
    assert res_def.energy_imported_kwh == pytest.approx(1.5)
    assert res_def.energy_exported_kwh == 0.0
    assert res_def.import_cost_aud == pytest.approx(1.5 * 0.30)
    assert res_def.export_credit_aud == 0.0
    assert res_def.net_cost_aud == pytest.approx(0.45)

    # Case 2: Household with surplus
    b_sur = compute_energy_balance(demand_kwh=0.2, solar_generation_kwh=1.2, house_id="H001")
    res_sur = calc.calculate_cost(b_sur, scenario_id="HYPOTHETICAL_BASE", allow_export=True)
    assert res_sur.energy_imported_kwh == 0.0
    assert res_sur.energy_exported_kwh == pytest.approx(1.0)
    assert res_sur.export_credit_aud == pytest.approx(1.0 * 0.08)
    assert res_sur.net_cost_aud == pytest.approx(-0.08)
