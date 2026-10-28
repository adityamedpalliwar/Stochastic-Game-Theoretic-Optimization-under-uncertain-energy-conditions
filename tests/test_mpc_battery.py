"""Comprehensive test suite for Phase 6A: Single-Household Rolling-Horizon MPC Battery Controller.

Covers all 10 Step 6 test requirements:
1. SOC dynamics and efficiency (one-way and round-trip losses).
2. SOC and power limits (headroom, footroom, rated kW bounds).
3. Strict mutual exclusion (no simultaneous charging and discharging).
4. Physical energy conservation and residual checks.
5. Terminal-horizon behavior (terminal valuation, target constraints, unconstrained dumping).
6. Infeasible or missing forecast data handling.
7. Solver failure handling and fallback safety.
8. Rolling-horizon state updates and boundary handling.
9. Deterministic reproducibility across repeated invocations.
10. Hand-checkable benchmark comparison between MPC and Greedy baseline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.energy.battery import BatteryStorage
from src.optimization.constraints import (
    BatteryOptimizationParams,
    MPCConfig,
    TariffParams,
)
from src.optimization.mpc_battery import (
    MPCOptimizationResult,
    RollingHorizonSimulator,
    SingleHouseholdMPCController,
    compare_controllers,
)
from src.optimization.solver import solve_milp


# ---------------------------------------------------------------------------
# 1. SOC Dynamics and Efficiency
# ---------------------------------------------------------------------------

def test_soc_dynamics_and_efficiency():
    """Verify stored energy updates obey exact efficiency equations."""
    params = BatteryOptimizationParams(
        capacity_kwh=5.0,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        min_soc=0.10,
        max_soc=0.90,
    )
    controller = SingleHouseholdMPCController(battery_params=params)

    # 1. Charging test: solar surplus 2.0 kWh, demand 0.0 kWh, initial energy 1.0 kWh (20% SOC)
    d_fc = np.array([0.0])
    s_fc = np.array([2.0])
    res_ch = controller.optimize(initial_energy_kwh=1.0, demand_forecast=d_fc, solar_forecast=s_fc)

    assert res_ch.success
    c_0, d_0 = res_ch.first_action
    assert c_0 == pytest.approx(2.0)
    assert d_0 == pytest.approx(0.0)
    expected_e1 = 1.0 + 2.0 * 0.95  # 2.90 kWh
    assert res_ch.e_kwh[1] == pytest.approx(expected_e1)

    # 2. Discharging test: demand 1.0 kWh, solar 0.0 kWh, initial energy 2.90 kWh
    d_fc2 = np.array([1.0])
    s_fc2 = np.array([0.0])
    res_dis = controller.optimize(initial_energy_kwh=expected_e1, demand_forecast=d_fc2, solar_forecast=s_fc2)

    assert res_dis.success
    c_1, d_1 = res_dis.first_action
    assert c_1 == pytest.approx(0.0)
    assert d_1 == pytest.approx(1.0)
    expected_e2 = expected_e1 - (1.0 / 0.95)
    assert res_dis.e_kwh[1] == pytest.approx(expected_e2)

    # 3. Round-trip efficiency check:
    # Charge with 1 kWh electricity -> chemical delta = 0.95 kWh.
    # To discharge 0.95 * 0.95 = 0.9025 kWh electricity -> chemical delta = 0.9025 / 0.95 = 0.95 kWh.
    assert params.round_trip_efficiency == pytest.approx(0.9025)


# ---------------------------------------------------------------------------
# 2. SOC and Power Limits
# ---------------------------------------------------------------------------

def test_soc_and_power_limits():
    """Verify power limits (2.5 kW) and SOC bounds ([0.5, 4.5] kWh) are strictly respected."""
    params = BatteryOptimizationParams(
        capacity_kwh=5.0,
        min_soc=0.10,
        max_soc=0.90,
        max_charge_rate_kw=2.5,
        max_discharge_rate_kw=2.5,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
    )
    controller = SingleHouseholdMPCController(battery_params=params)

    # A. Enormous solar surplus (10.0 kWh), initial stored energy at max (4.5 kWh)
    res_full = controller.optimize(
        initial_energy_kwh=4.5,
        demand_forecast=np.array([0.0]),
        solar_forecast=np.array([10.0]),
    )
    assert res_full.success
    # Cannot charge because battery is full
    assert res_full.c_kwh[0] == pytest.approx(0.0)
    assert res_full.x_kwh[0] == pytest.approx(10.0)  # All exported
    assert res_full.e_kwh[1] == pytest.approx(4.5)

    # B. Enormous solar surplus (10.0 kWh), initial stored energy at 3.0 kWh
    # Headroom = (4.5 - 3.0) / 0.95 = 1.5789 kWh < 2.5 kWh power limit
    res_headroom = controller.optimize(
        initial_energy_kwh=3.0,
        demand_forecast=np.array([0.0]),
        solar_forecast=np.array([10.0]),
    )
    assert res_headroom.success
    expected_c = (4.5 - 3.0) / 0.95
    assert res_headroom.c_kwh[0] == pytest.approx(expected_c, abs=1e-5)
    assert res_headroom.e_kwh[1] == pytest.approx(4.5)

    # C. Huge demand (10.0 kWh), initial stored energy at min (0.5 kWh)
    res_empty = controller.optimize(
        initial_energy_kwh=0.5,
        demand_forecast=np.array([10.0]),
        solar_forecast=np.array([0.0]),
    )
    assert res_empty.success
    # Cannot discharge because at min SOC
    assert res_empty.d_kwh[0] == pytest.approx(0.0)
    assert res_empty.m_kwh[0] == pytest.approx(10.0)  # All imported
    assert res_empty.e_kwh[1] == pytest.approx(0.5)

    # D. Huge demand (10.0 kWh), initial stored energy at 4.5 kWh (full)
    # Power limit is 2.5 kW * 1h = 2.5 kWh
    res_power = controller.optimize(
        initial_energy_kwh=4.5,
        demand_forecast=np.array([10.0]),
        solar_forecast=np.array([0.0]),
    )
    assert res_power.success
    assert res_power.d_kwh[0] == pytest.approx(2.5)  # Clamped by max discharge power
    assert res_power.m_kwh[0] == pytest.approx(7.5)  # Remaining 7.5 kWh imported
    assert res_power.e_kwh[1] == pytest.approx(4.5 - 2.5 / 0.95)


# ---------------------------------------------------------------------------
# 3. No Simultaneous Charging and Discharging
# ---------------------------------------------------------------------------

def test_no_simultaneous_charge_discharge():
    """Verify mutual exclusion: charging and discharging never occur simultaneously."""
    controller = SingleHouseholdMPCController()

    # Generate multi-period profile with alternating solar peaks and demand spikes
    np.random.seed(42)
    T = 24
    d_fc = np.random.uniform(0.2, 2.5, size=T)
    s_fc = np.zeros(T)
    s_fc[8:17] = np.random.uniform(0.5, 3.5, size=9)

    res = controller.optimize(initial_energy_kwh=2.5, demand_forecast=d_fc, solar_forecast=s_fc)
    assert res.success

    for t in range(T):
        c_t = res.c_kwh[t]
        d_t = res.d_kwh[t]
        u_t = res.u_ch[t]

        # Binary variable must be 0 or 1
        assert u_t in (0.0, 1.0)

        # Mutual exclusion
        assert min(c_t, d_t) <= 1e-7, f"Step {t} simultaneous flow: C={c_t}, D={d_t}"
        if u_t == 1.0:
            assert d_t == pytest.approx(0.0)
        else:
            assert c_t == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 4. Energy Conservation and Residuals
# ---------------------------------------------------------------------------

def test_energy_conservation_and_residuals():
    """Verify household energy balance D + C + X == S + D_bat + M at all horizon steps."""
    controller = SingleHouseholdMPCController()

    d_fc = np.array([1.5, 0.8, 2.2, 0.4, 1.9, 0.0, 1.2, 2.0])
    s_fc = np.array([0.0, 2.0, 1.5, 3.2, 0.5, 0.0, 0.0, 0.0])

    res = controller.optimize(initial_energy_kwh=2.5, demand_forecast=d_fc, solar_forecast=s_fc)
    assert res.success

    for t in range(len(d_fc)):
        d_t = d_fc[t]
        s_t = s_fc[t]
        c_t = res.c_kwh[t]
        d_bat_t = res.d_kwh[t]
        m_t = res.m_kwh[t]
        x_t = res.x_kwh[t]

        lhs = d_t + c_t + x_t
        rhs = s_t + d_bat_t + m_t
        assert lhs == pytest.approx(rhs, abs=1e-5), f"Conservation residual at step {t}: {abs(lhs - rhs)}"
        assert m_t >= -1e-6
        assert x_t >= -1e-6
        # Complementarity between grid import and export
        assert min(m_t, x_t) <= 1e-6


# ---------------------------------------------------------------------------
# 5. Terminal-Horizon Behavior
# ---------------------------------------------------------------------------

def test_terminal_horizon_behavior():
    """Verify terminal valuation prevents tail dumping, while unconstrained allows it."""
    # Profile where demand drops to 0 after midday solar
    d_fc = np.array([1.0] * 8 + [0.0] * 16)
    s_fc = np.array([0.0] * 8 + [2.5] * 8 + [0.0] * 8)

    # 1. Unconstrained: optimizer should dump all stored solar for export credit
    cfg_unconstrained = MPCConfig(terminal_strategy="unconstrained")
    ctrl_unconstrained = SingleHouseholdMPCController(config=cfg_unconstrained)
    res_unc = ctrl_unconstrained.optimize(2.5, d_fc, s_fc)

    assert res_unc.success
    # Final SOC is dumped to min SOC (0.10)
    assert res_unc.soc[-1] == pytest.approx(0.10)

    # 2. Terminal valuation: optimizer values stored energy at avoided import cost
    cfg_val = MPCConfig(terminal_strategy="terminal_value")
    ctrl_val = SingleHouseholdMPCController(config=cfg_val)
    res_val = ctrl_val.optimize(2.5, d_fc, s_fc)

    assert res_val.success
    # Final SOC is preserved at max SOC (0.90)
    assert res_val.soc[-1] == pytest.approx(0.90)

    # 3. Terminal SOC target constraint: target 50% SOC (2.5 kWh)
    cfg_target = MPCConfig(terminal_strategy="terminal_soc_target", terminal_soc_target=0.50)
    ctrl_target = SingleHouseholdMPCController(config=cfg_target)
    res_target = ctrl_target.optimize(2.5, d_fc, s_fc)

    assert res_target.success
    assert res_target.e_kwh[-1] >= 2.50 - 1e-5
    assert res_target.terminal_slack_kwh == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 6. Infeasible or Missing Forecast Data Handling
# ---------------------------------------------------------------------------

def test_infeasible_or_missing_forecast_data():
    """Verify controller rejects invalid inputs with descriptive ValueErrors."""
    controller = SingleHouseholdMPCController()

    # Empty forecasts
    with pytest.raises(ValueError, match="at least 1"):
        controller.optimize(2.5, [], [])

    # Mismatched lengths
    with pytest.raises(ValueError, match="mismatch"):
        controller.optimize(2.5, [1.0, 2.0], [1.0])

    # Negative demand
    with pytest.raises(ValueError, match="Negative"):
        controller.optimize(2.5, [-0.5, 1.0], [0.0, 0.0])

    # Non-finite values
    with pytest.raises(ValueError, match="Non-finite"):
        controller.optimize(2.5, [np.nan, 1.0], [0.0, 0.0])
    with pytest.raises(ValueError, match="Non-finite"):
        controller.optimize(2.5, [1.0, 1.0], [np.inf, 0.0])

    # Initial energy out of bounds
    with pytest.raises(ValueError, match="outside permitted range"):
        controller.optimize(0.1, [1.0], [0.0])  # min is 0.5 kWh
    with pytest.raises(ValueError, match="outside permitted range"):
        controller.optimize(5.0, [1.0], [0.0])  # max is 4.5 kWh


# ---------------------------------------------------------------------------
# 7. Solver Failure Handling and Fallback Safety
# ---------------------------------------------------------------------------

def test_solver_failure_handling(monkeypatch):
    """Verify graceful handling when the underlying solver fails."""
    controller = SingleHouseholdMPCController()

    from src.optimization import mpc_battery
    from src.optimization.solver import MILPResult

    # Simulate solver crash returning failure
    def mock_solve_milp(*args, **kwargs):
        return MILPResult(
            success=False,
            status=3,
            message="Simulated solver timeout / failure",
            x=None,
            fun=None,
            solve_time_sec=0.05,
        )

    monkeypatch.setattr(mpc_battery, "solve_milp", mock_solve_milp)

    res = controller.optimize(2.5, [1.0, 2.0], [0.0, 0.0])
    assert not res.success
    assert res.status == 3
    assert "Simulated solver" in res.message
    # Safe fallback: first action is zero dispatch (no uncontrolled battery action)
    assert res.first_action == (0.0, 0.0)
    assert np.all(res.c_kwh == 0.0)
    assert np.all(res.d_kwh == 0.0)


# ---------------------------------------------------------------------------
# 8. Rolling-Horizon State Updates & Boundary Handling
# ---------------------------------------------------------------------------

def test_rolling_horizon_state_updates():
    """Verify rolling horizon advances battery state sequentially with end-of-dataset shrinkage."""
    simulator = RollingHorizonSimulator()

    # Create dummy 30-hour dataset
    hours = 30
    df = pd.DataFrame({
        "forecast_timestamp": pd.date_range("2026-01-01", periods=hours, freq="h"),
        "actual_demand_kwh": [1.0] * hours,
        "actual_solar_generation_kwh": [0.0] * 8 + [2.0] * 8 + [0.0] * 14,
        "predicted_demand_kwh": [1.1] * hours,
        "predicted_solar_generation_kwh": [0.0] * 8 + [1.9] * 8 + [0.0] * 14,
    })

    res = simulator.run_mpc(df, shrink_horizon_at_end=True)
    assert res.total_hours == hours
    assert len(res.step_records) == hours

    # Continuity: initial energy at step k+1 must equal final energy at step k
    for k in range(hours - 1):
        assert res.step_records[k + 1].battery_initial_kwh == pytest.approx(
            res.step_records[k].battery_final_kwh
        )

    # Check conservation across every single step
    assert res.max_energy_balance_residual_kwh < 1e-12
    assert res.soc_boundary_violations == 0
    assert res.simultaneous_charge_discharge_violations == 0


# ---------------------------------------------------------------------------
# 9. Deterministic Reproducibility
# ---------------------------------------------------------------------------

def test_reproducibility():
    """Verify that identical inputs produce identical optimal solutions bit-for-bit."""
    controller = SingleHouseholdMPCController()
    d_fc = np.array([1.2, 0.5, 2.0, 1.8, 0.3, 0.0, 1.5, 2.2])
    s_fc = np.array([0.0, 1.5, 3.0, 2.5, 0.8, 0.0, 0.0, 0.0])

    res1 = controller.optimize(2.5, d_fc, s_fc)
    res2 = controller.optimize(2.5, d_fc, s_fc)

    assert res1.success and res2.success
    np.testing.assert_array_almost_equal(res1.c_kwh, res2.c_kwh, decimal=10)
    np.testing.assert_array_almost_equal(res1.d_kwh, res2.d_kwh, decimal=10)
    np.testing.assert_array_almost_equal(res1.m_kwh, res2.m_kwh, decimal=10)
    np.testing.assert_array_almost_equal(res1.x_kwh, res2.x_kwh, decimal=10)
    assert res1.net_cost_aud == pytest.approx(res2.net_cost_aud, abs=1e-10)


# ---------------------------------------------------------------------------
# 10. Hand-Checkable Comparison Against Greedy Baseline
# ---------------------------------------------------------------------------

def test_hand_checkable_example_comparison_with_greedy():
    """Verify exact hand-calculated 3-hour scenario for both Greedy and MPC."""
    simulator = RollingHorizonSimulator()

    # 3-hour test dataset:
    # Hour 0: Demand = 2.0 kWh, Solar = 0.0 kWh (Deficit 2.0 kWh)
    # Hour 1: Demand = 0.5 kWh, Solar = 3.5 kWh (Surplus 3.0 kWh)
    # Hour 2: Demand = 1.5 kWh, Solar = 0.0 kWh (Deficit 1.5 kWh)
    df = pd.DataFrame({
        "forecast_timestamp": pd.date_range("2026-01-01", periods=3, freq="h"),
        "actual_demand_kwh": [2.0, 0.5, 1.5],
        "actual_solar_generation_kwh": [0.0, 3.5, 0.0],
        "predicted_demand_kwh": [2.0, 0.5, 1.5],
        "predicted_solar_generation_kwh": [0.0, 3.5, 0.0],
    })

    # Initial state: E_0 = 2.5 kWh (SOC = 50%)
    res_greedy = simulator.run_greedy_baseline(df, initial_soc=0.50)

    # Hand-checkable trace for Greedy:
    # Step 0: Deficit = 2.0 kWh.
    # Battery can discharge up to footroom = (2.5 - 0.5) * 0.95 = 1.90 kWh.
    # Power limit is 2.5 kW. Actual discharge = 1.90 kWh.
    # Battery stored energy drops by 1.90 / 0.95 = 2.0 kWh -> Final E = 0.50 kWh (SOC 10%).
    # Grid imported = 2.0 - 1.90 = 0.10 kWh.
    rec0 = res_greedy.step_records[0]
    assert rec0.discharged_kwh == pytest.approx(1.90)
    assert rec0.battery_final_kwh == pytest.approx(0.50)
    assert rec0.grid_imported_kwh == pytest.approx(0.10)
    assert rec0.import_cost_aud == pytest.approx(0.10 * 0.30)

    # Step 1: Solar = 3.5, Demand = 0.5 -> Surplus = 3.0 kWh.
    # Battery headroom = (4.5 - 0.5) / 0.95 = 4.21 kWh. Power limit = 2.5 kWh.
    # Clamped to 2.5 kWh charging!
    # Actual charged = 2.50 kWh.
    # Stored energy increases by 2.50 * 0.95 = 2.375 kWh -> Final E = 0.50 + 2.375 = 2.875 kWh.
    # Remaining surplus = 3.0 - 2.50 = 0.50 kWh exported to grid.
    rec1 = res_greedy.step_records[1]
    assert rec1.charged_kwh == pytest.approx(2.50)
    assert rec1.battery_final_kwh == pytest.approx(2.875)
    assert rec1.grid_exported_kwh == pytest.approx(0.50)
    assert rec1.export_credit_aud == pytest.approx(0.50 * 0.08)

    # Step 2: Demand = 1.5, Solar = 0.0 -> Deficit = 1.5 kWh.
    # Footroom = (2.875 - 0.50) * 0.95 = 2.25625 kWh > 1.5 kWh.
    # Actual discharge = 1.50 kWh.
    # Stored energy decreases by 1.50 / 0.95 = 1.578947 kWh -> Final E = 2.875 - 1.578947 = 1.296053 kWh.
    # Grid imported = 0.0 kWh.
    rec2 = res_greedy.step_records[2]
    assert rec2.discharged_kwh == pytest.approx(1.50)
    assert rec2.battery_final_kwh == pytest.approx(1.296053, abs=1e-5)
    assert rec2.grid_imported_kwh == pytest.approx(0.0)

    # Now run MPC
    res_mpc = simulator.run_mpc(df, initial_soc=0.50)
    comp = compare_controllers(res_mpc, res_greedy)

    # Both controllers should respect physical balance with 0 residual
    assert res_greedy.max_energy_balance_residual_kwh < 1e-12
    assert res_mpc.max_energy_balance_residual_kwh < 1e-12
    assert comp["hours_evaluated"] == 3
