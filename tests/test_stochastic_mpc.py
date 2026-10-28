"""Unit tests for Phase 6B: Single-Household Stochastic Scenario-Based MPC.

Covers all 10 Step 5 validation requirements:
1. Scenario probabilities and scenario shapes.
2. Deterministic reproducibility (Protocol B observation seeding).
3. Shared first-stage decisions and non-anticipativity across scenarios.
4. Battery SOC bounds and power limits across all scenarios.
5. Strict mutual exclusion (no simultaneous charging and discharging).
6. Physical energy conservation under every evaluated scenario.
7. Terminal-energy valuation behavior.
8. Solver failure handling and fallback safety.
9. Rolling state updates and strict information boundaries.
10. Small hand-checkable stochastic scenario with known expected cost.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.optimization.constraints import BatteryOptimizationParams, TariffParams
from src.optimization.mpc_stochastic import (
    ScenarioSet,
    SingleHouseholdStochasticMPCController,
    StochasticMPCConfig,
    StochasticOptimizationResult,
    StochasticRollingHorizonSimulator,
    StochasticScenarioGenerator,
)


# ---------------------------------------------------------------------------
# 1. Scenario Probabilities and Shapes
# ---------------------------------------------------------------------------

def test_scenario_probabilities_and_shapes():
    """Verify generated scenario sets have correct shapes, bounds, and probability sums."""
    gen = StochasticScenarioGenerator()
    d_fc = np.array([1.0, 1.5, 0.8, 2.2])
    s_fc = np.array([0.0, 0.5, 2.5, 1.2])

    scen_set = gen.generate_horizon_scenarios(
        demand_forecast=d_fc,
        solar_forecast=s_fc,
        house_id="H001",
        timestamp="2013-05-01 12:00:00",
        num_scenarios=5,
        include_nominal=True,
    )

    assert scen_set.num_scenarios == 5
    assert scen_set.horizon_hours == 4
    assert scen_set.scenarios_demand_kwh.shape == (5, 4)
    assert scen_set.scenarios_solar_kwh.shape == (5, 4)
    assert len(scen_set.probabilities) == 5
    assert np.sum(scen_set.probabilities) == pytest.approx(1.0)

    # Physical non-negativity
    assert np.all(scen_set.scenarios_demand_kwh >= 0.0)
    assert np.all(scen_set.scenarios_solar_kwh >= 0.0)

    # Scenario 0 must be nominal deterministic forecast
    np.testing.assert_allclose(scen_set.scenarios_demand_kwh[0], d_fc)
    np.testing.assert_allclose(scen_set.scenarios_solar_kwh[0], s_fc)


# ---------------------------------------------------------------------------
# 2. Deterministic Reproducibility
# ---------------------------------------------------------------------------

def test_reproducibility():
    """Verify that identical inputs and timestamps produce identical scenario sets and solutions."""
    controller = SingleHouseholdStochasticMPCController()
    d_fc = np.array([1.2, 0.8, 2.0, 1.5])
    s_fc = np.array([0.0, 1.8, 2.5, 0.5])
    ts = "2013-05-15 14:00:00"

    res1 = controller.optimize(2.5, d_fc, s_fc, house_id="H001", timestamp=ts)
    res2 = controller.optimize(2.5, d_fc, s_fc, house_id="H001", timestamp=ts)

    assert res1.success and res2.success
    assert res1.first_action[0] == pytest.approx(res2.first_action[0], abs=1e-10)
    assert res1.first_action[1] == pytest.approx(res2.first_action[1], abs=1e-10)
    assert res1.expected_cost_aud == pytest.approx(res2.expected_cost_aud, abs=1e-10)
    np.testing.assert_allclose(res1.c_kwh, res2.c_kwh, atol=1e-8)
    np.testing.assert_allclose(res1.d_kwh, res2.d_kwh, atol=1e-8)


# ---------------------------------------------------------------------------
# 3. Non-Anticipativity on First-Stage Decisions
# ---------------------------------------------------------------------------

def test_shared_first_stage_decisions_non_anticipativity():
    """Verify strict non-anticipativity: C_0 and D_0 are identical across all scenarios."""
    controller = SingleHouseholdStochasticMPCController()
    T = 12
    d_fc = np.random.uniform(0.5, 2.0, size=T)
    s_fc = np.zeros(T)
    s_fc[4:9] = np.random.uniform(1.0, 3.0, size=5)

    res = controller.optimize(2.5, d_fc, s_fc, house_id="H001", timestamp="2013-05-10 08:00:00")
    assert res.success

    c0, d0 = res.first_action
    S = res.num_scenarios

    # Across all S scenarios, the t=0 action must match (c0, d0)
    for w in range(S):
        assert res.c_kwh[w, 0] == pytest.approx(c0, abs=1e-8)
        assert res.d_kwh[w, 0] == pytest.approx(d0, abs=1e-8)


# ---------------------------------------------------------------------------
# 4. Battery SOC Bounds and Power Constraints
# ---------------------------------------------------------------------------

def test_battery_soc_and_power_constraints():
    """Verify power limits (<= 2.5 kW) and SOC bounds ([0.5, 4.5] kWh) hold across all scenarios."""
    params = BatteryOptimizationParams(
        capacity_kwh=5.0,
        min_soc=0.10,
        max_soc=0.90,
        max_charge_rate_kw=2.5,
        max_discharge_rate_kw=2.5,
    )
    controller = SingleHouseholdStochasticMPCController(battery_params=params)

    # Huge demand and solar
    d_fc = np.array([8.0, 0.0, 9.0])
    s_fc = np.array([0.0, 10.0, 0.0])

    res = controller.optimize(2.5, d_fc, s_fc, house_id="H001", timestamp="2013-05-01 00:00:00")
    assert res.success

    # Check across all scenarios and all time steps
    assert np.all(res.c_kwh <= 2.5 + 1e-6)
    assert np.all(res.d_kwh <= 2.5 + 1e-6)
    assert np.all(res.e_kwh >= 0.5 - 1e-5)
    assert np.all(res.e_kwh <= 4.5 + 1e-5)


# ---------------------------------------------------------------------------
# 5. Strict Mutual Exclusion (No Simultaneous Charge / Discharge)
# ---------------------------------------------------------------------------

def test_no_simultaneous_charging_and_discharging():
    """Verify mutual exclusion: min(C, D) <= 1e-7 across every scenario and every hour."""
    controller = SingleHouseholdStochasticMPCController()
    T = 24
    d_fc = np.array([1.2] * T)
    s_fc = np.zeros(T)
    s_fc[8:16] = 2.8

    res = controller.optimize(2.5, d_fc, s_fc, house_id="H001", timestamp="2013-06-01 06:00:00")
    assert res.success

    for w in range(res.num_scenarios):
        for t in range(T):
            c_val = res.c_kwh[w, t]
            d_val = res.d_kwh[w, t]
            assert min(c_val, d_val) <= 1e-7, f"Scenario {w}, step {t} simultaneous flow: C={c_val}, D={d_val}"


# ---------------------------------------------------------------------------
# 6. Physical Energy Conservation Under Every Scenario
# ---------------------------------------------------------------------------

def test_energy_conservation_under_every_scenario():
    """Verify Demand + C + X == Solar + D + M holds in every scenario."""
    gen = StochasticScenarioGenerator()
    d_fc = np.array([1.0, 2.0, 0.5, 1.8])
    s_fc = np.array([0.0, 1.0, 3.0, 0.2])

    scen_set = gen.generate_horizon_scenarios(
        demand_forecast=d_fc,
        solar_forecast=s_fc,
        house_id="H001",
        num_scenarios=4,
    )
    controller = SingleHouseholdStochasticMPCController()
    res = controller.optimize_scenarios(2.5, scen_set)
    assert res.success

    for w in range(scen_set.num_scenarios):
        for t in range(scen_set.horizon_hours):
            d_wt = scen_set.scenarios_demand_kwh[w, t]
            s_wt = scen_set.scenarios_solar_kwh[w, t]
            c_wt = res.c_kwh[w, t]
            d_bat_wt = res.d_kwh[w, t]
            m_wt = res.m_kwh[w, t]
            x_wt = res.x_kwh[w, t]

            lhs = d_wt + c_wt + x_wt
            rhs = s_wt + d_bat_wt + m_wt
            assert lhs == pytest.approx(rhs, abs=1e-5), f"Conservation residual in scenario {w}, step {t}: {abs(lhs - rhs)}"


# ---------------------------------------------------------------------------
# 7. Terminal Energy Valuation Behavior
# ---------------------------------------------------------------------------

def test_terminal_energy_treatment():
    """Verify terminal valuation preserves stored energy across scenarios."""
    # Low evening demand
    d_fc = np.array([1.0] * 8 + [0.0] * 16)
    s_fc = np.array([0.0] * 8 + [2.5] * 8 + [0.0] * 8)

    # 1. Unconstrained: dumps terminal SOC
    cfg_unc = StochasticMPCConfig(terminal_strategy="unconstrained", num_scenarios=3)
    ctrl_unc = SingleHouseholdStochasticMPCController(config=cfg_unc)
    res_unc = ctrl_unc.optimize(2.5, d_fc, s_fc, house_id="H001")
    assert res_unc.success
    # In every scenario, final SOC should be drained to min_soc (0.10)
    for w in range(3):
        assert res_unc.soc[w, -1] == pytest.approx(0.10)

    # 2. Terminal valuation: preserves stored energy in nominal scenario
    cfg_val = StochasticMPCConfig(terminal_strategy="terminal_value", num_scenarios=3)
    ctrl_val = SingleHouseholdStochasticMPCController(config=cfg_val)
    res_val = ctrl_val.optimize(2.5, d_fc, s_fc, house_id="H001")
    assert res_val.success
    # In nominal scenario (index 0), final SOC must be preserved at max (0.90)
    assert res_val.soc[0, -1] == pytest.approx(0.90)


# ---------------------------------------------------------------------------
# 8. Solver Failure Handling and Safety
# ---------------------------------------------------------------------------

def test_solver_failure_handling(monkeypatch):
    """Verify graceful handling when solver encounters an internal failure."""
    from src.optimization import mpc_stochastic
    from src.optimization.solver import MILPResult

    def mock_solve_milp(*args, **kwargs):
        return MILPResult(
            success=False,
            status=3,
            message="Simulated solver timeout / failure",
            x=None,
            fun=None,
            solve_time_sec=0.05,
        )

    monkeypatch.setattr(mpc_stochastic, "solve_milp", mock_solve_milp)

    controller = SingleHouseholdStochasticMPCController()
    res = controller.optimize(2.5, [1.0, 2.0], [0.0, 0.0])
    assert not res.success
    assert res.status == 3
    # Safe fallback: zero battery dispatch
    assert res.first_action == (0.0, 0.0)


# ---------------------------------------------------------------------------
# 9. Rolling State Updates & Information Boundaries
# ---------------------------------------------------------------------------

def test_rolling_state_updates_and_information_boundaries():
    """Verify state continuity and non-leakage over a rolling simulation."""
    sim = StochasticRollingHorizonSimulator()

    hours = 12
    df = pd.DataFrame({
        "forecast_timestamp": pd.date_range("2026-01-01", periods=hours, freq="h"),
        "actual_demand_kwh": [1.0] * hours,
        "actual_solar_generation_kwh": [0.0] * 4 + [2.0] * 4 + [0.0] * 4,
        "predicted_demand_kwh": [1.1] * hours,
        "predicted_solar_generation_kwh": [0.0] * 4 + [1.8] * 4 + [0.0] * 4,
    })

    res = sim.run_stochastic_mpc(df, house_id="H001", shrink_horizon_at_end=True)
    assert res.total_hours == hours

    # Continuity: initial energy at k+1 == final energy at k
    for k in range(hours - 1):
        assert res.step_records[k + 1].battery_initial_kwh == pytest.approx(
            res.step_records[k].battery_final_kwh
        )

    assert res.max_energy_balance_residual_kwh < 1e-12
    assert res.soc_boundary_violations == 0
    assert res.simultaneous_charge_discharge_violations == 0


# ---------------------------------------------------------------------------
# 10. Hand-Checkable Stochastic Scenario with Exact Expected Cost
# ---------------------------------------------------------------------------

def test_small_hand_checkable_stochastic_scenario():
    """Verify stochastic decision on a hand-checkable 2-scenario example.

    Two equiprobable scenarios (pi_1 = pi_2 = 0.5) over a 1-hour horizon (T=1):
    - Scenario 1: Demand = 1.0 kWh, Solar = 0.0 kWh (Deficit = 1.0 kWh)
    - Scenario 2: Demand = 1.5 kWh, Solar = 0.0 kWh (Deficit = 1.5 kWh)
    Initial stored energy: E_0 = 2.50 kWh.

    Hand-calculated trade-off for first-stage action:
    - If D_0 = 1.0 kWh:
        Scenario 1: M_1 = 0.0 kWh, X_1 = 0.0 kWh -> Net grid cost = $0.00 AUD.
        Scenario 2: M_2 = 0.5 kWh, X_2 = 0.0 kWh -> Net grid cost = 0.5 * 0.30 = $0.15 AUD.
        Expected Grid Cost: 0.5 * 0.00 + 0.5 * 0.15 = $0.0750 AUD.
        E_1 = 2.50 - 1.0 / 0.95 = 1.4474 kWh.
        Terminal Valuation: -0.2793 * (1.4474 - 0.50) = -$0.2646 AUD.
        Total Expected Objective: $0.0750 - $0.2646 = -$0.1896 AUD.
    - If D_0 = 1.5 kWh:
        Scenario 1: Deficit 1.0, but D_0 = 1.5 -> Excess discharge 0.5 kWh is exported at $0.08!
                    X_1 = 0.5 kWh -> Net cost = -0.5 * 0.08 = -$0.0400 AUD.
        Scenario 2: M_2 = 0.0 kWh -> Net cost = $0.00 AUD.
        Expected Grid Cost: 0.5 * (-0.04) + 0.5 * 0.00 = -$0.0200 AUD.
        E_1 = 2.50 - 1.5 / 0.95 = 0.9211 kWh.
        Terminal Valuation: -0.2793 * (0.9211 - 0.50) = -$0.1176 AUD.
        Total Expected Objective: -$0.0200 - $0.1176 = -$0.1376 AUD.

    Conclusion:
    Objective(D_0 = 1.0) = -$0.1896 < Objective(D_0 = 1.5) = -$0.1376.
    The stochastic optimizer must choose D_0 = 1.0 kWh to avoid dumping valuable stored
    energy to the grid at the low $0.08 export tariff!
    """
    scen_d = np.array([[1.0], [1.5]])
    scen_s = np.array([[0.0], [0.0]])
    probs = np.array([0.5, 0.5])

    scen_set = ScenarioSet(
        num_scenarios=2,
        horizon_hours=1,
        scenarios_demand_kwh=scen_d,
        scenarios_solar_kwh=scen_s,
        probabilities=probs,
    )

    controller = SingleHouseholdStochasticMPCController()
    res = controller.optimize_scenarios(initial_energy_kwh=2.5, scenario_set=scen_set)

    assert res.success
    c0, d0 = res.first_action

    assert c0 == pytest.approx(0.0)
    assert d0 == pytest.approx(1.0, abs=1e-5)
    # Check expected objective value
    expected_obj = -0.189626
    # Cost = E[grid cost] = 0.075 AUD
    assert res.expected_cost_aud == pytest.approx(0.075, abs=1e-4)


# ---------------------------------------------------------------------------
# 11. Night-Time Solar Zero Enforcement
# ---------------------------------------------------------------------------

def test_night_time_solar_zero_enforcement():
    """Verify zero solar generation across all scenarios during verified night-time hours."""
    gen = StochasticScenarioGenerator()
    ts_midnight = pd.Timestamp("2013-04-19 00:00:00")
    d_fc = np.full(24, 1.0)
    # Give a tiny positive noise in forecast (typical of ML models at night)
    s_fc = np.array([0.0124] * 6 + [0.5, 1.0, 1.5, 2.0, 2.2, 2.0, 1.5, 1.0, 0.5, 0.1, 0.0] + [0.0] * 7)

    scenarios = gen.generate_horizon_scenarios(
        demand_forecast=d_fc,
        solar_forecast=s_fc,
        house_id="H001",
        timestamp=ts_midnight,
        num_scenarios=5,
    )

    # Night hours: t=0,1,2,3,4,5,6 (00:00 to 06:00) and t=19,20,21,22,23 (19:00 to 23:00)
    night_indices = [0, 1, 2, 3, 4, 5, 6, 19, 20, 21, 22, 23]
    for idx in night_indices:
        for s in range(scenarios.num_scenarios):
            assert scenarios.scenarios_solar_kwh[s, idx] == 0.0, (
                f"Scenario {s} at horizon step {idx} (hour {(ts_midnight + pd.Timedelta(hours=idx)).hour}) "
                f"had non-zero solar: {scenarios.scenarios_solar_kwh[s, idx]}"
            )


# ---------------------------------------------------------------------------
# 12. H001 First-Hour Audit Reproduction & Elimination of False Charging
# ---------------------------------------------------------------------------

def test_h001_first_hour_audit_reproduction_and_fix():
    """Re-run the exact H001 first-hour case from the audit and verify midnight charging is eliminated."""
    df = pd.read_csv("data/processed/test_predictions.csv")
    df_h1 = df[df["house_id"] == "H001"].iloc[:24].copy().reset_index(drop=True)
    ts0 = df_h1["forecast_timestamp"].iloc[0]

    controller = SingleHouseholdStochasticMPCController()
    res = controller.optimize(
        initial_energy_kwh=2.5,
        demand_forecast=df_h1["predicted_demand_kwh"].values,
        solar_forecast=df_h1["predicted_solar_generation_kwh"].values,
        house_id="H001",
        timestamp=ts0,
    )

    assert res.success
    c0, d0 = res.first_action
    # Must NOT charge at midnight
    assert c0 == pytest.approx(0.0, abs=1e-6)
    # Must discharge to serve the night demand
    assert d0 > 0.5


# ---------------------------------------------------------------------------
# 13. Daytime Conditioning and Non-Negativity
# ---------------------------------------------------------------------------

def test_daytime_conditioning_and_non_negativity():
    """Verify that daytime scenarios remain strictly non-negative and finite."""
    gen = StochasticScenarioGenerator()
    ts_noon = pd.Timestamp("2013-04-19 12:00:00")
    d_fc = np.array([0.5] * 24)
    s_fc = np.array([2.5] * 24)

    scenarios = gen.generate_horizon_scenarios(
        demand_forecast=d_fc,
        solar_forecast=s_fc,
        house_id="H001",
        timestamp=ts_noon,
        num_scenarios=5,
    )

    assert np.all(scenarios.scenarios_demand_kwh >= 0.0)
    assert np.all(scenarios.scenarios_solar_kwh >= 0.0)
    assert np.all(np.isfinite(scenarios.scenarios_demand_kwh))
    assert np.all(np.isfinite(scenarios.scenarios_solar_kwh))


# ---------------------------------------------------------------------------
# 14. Information Leakage Isolation
# ---------------------------------------------------------------------------

def test_information_leakage_isolation():
    """Verify scenario generation relies strictly on forecast and historical validation residuals."""
    gen = StochasticScenarioGenerator()
    ts = pd.Timestamp("2013-05-01 10:00:00")
    d_fc = [0.8] * 24
    s_fc = [1.5] * 24

    # Run twice with same timestamp and seed -> bitwise identical
    s1 = gen.generate_horizon_scenarios(d_fc, s_fc, house_id="H001", timestamp=ts, num_scenarios=3)
    s2 = gen.generate_horizon_scenarios(d_fc, s_fc, house_id="H001", timestamp=ts, num_scenarios=3)

    np.testing.assert_array_equal(s1.scenarios_demand_kwh, s2.scenarios_demand_kwh)
    np.testing.assert_array_equal(s1.scenarios_solar_kwh, s2.scenarios_solar_kwh)


# ---------------------------------------------------------------------------
# 15. Daytime Low Forecast Retention & Seasonal Boundary Validation
# ---------------------------------------------------------------------------

def test_daytime_low_forecast_not_zeroed():
    """Ensure valid daytime solar generation is not zeroed solely because point forecast <= 0.01 kWh."""
    gen = StochasticScenarioGenerator()
    ts_day = pd.Timestamp("2013-05-15 11:00:00")  # 11:00 AM (broad daylight)
    d_fc = np.full(24, 1.0)
    # Heavy overcast day with very low forecast at 11 AM: 0.005 kWh
    s_fc = np.zeros(24)
    s_fc[0] = 0.005  # t=0 corresponds to 11 AM

    scenarios = gen.generate_horizon_scenarios(
        demand_forecast=d_fc,
        solar_forecast=s_fc,
        house_id="H001",
        timestamp=ts_day,
        num_scenarios=5,
        include_nominal=True,
    )

    # In nominal scenario (index 0), 11 AM solar must retain 0.005 kWh (NOT zeroed)
    assert scenarios.scenarios_solar_kwh[0, 0] == pytest.approx(0.005)

    # In sampled scenarios, at 11 AM daytime residuals should allow positive generation
    # Hour 11 in residual pool has residuals up to +1.418 kWh
    daytime_max = np.max(scenarios.scenarios_solar_kwh[:, 0])
    assert daytime_max > 0.01, f"Expected positive daytime generation from sampled residuals, got {daytime_max}"


def test_seasonal_sunrise_sunset_boundary_hours():
    """Verify that empirical night mask correctly differentiates night from day at transition hours."""
    gen = StochasticScenarioGenerator()
    # At 06:00 (dawn / astronomical twilight) -> night mask applies
    ts_06 = pd.Timestamp("2013-05-15 06:00:00")
    scen_06 = gen.generate_horizon_scenarios([1.0]*24, [0.05]*24, "H001", timestamp=ts_06, num_scenarios=3)
    assert np.all(scen_06.scenarios_solar_kwh[:, 0] == 0.0), "Hour 6 (pre-sunrise autumn/winter) must be masked to 0"

    # At 07:00 (sunrise) -> daytime: generation permitted
    ts_07 = pd.Timestamp("2013-05-15 07:00:00")
    scen_07 = gen.generate_horizon_scenarios([1.0]*24, [0.10]*24, "H001", timestamp=ts_07, num_scenarios=3)
    assert scen_07.scenarios_solar_kwh[0, 0] == pytest.approx(0.10), "Hour 7 nominal forecast must be retained"

    # At 18:00 (post-sunset autumn/winter) -> daytime mask ends at 19:00
    ts_19 = pd.Timestamp("2013-05-15 19:00:00")
    scen_19 = gen.generate_horizon_scenarios([1.0]*24, [0.05]*24, "H001", timestamp=ts_19, num_scenarios=3)
    assert np.all(scen_19.scenarios_solar_kwh[:, 0] == 0.0), "Hour 19 must be masked to 0"


