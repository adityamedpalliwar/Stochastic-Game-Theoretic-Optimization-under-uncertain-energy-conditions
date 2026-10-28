"""Phase 6B.1: Comprehensive Benchmark Evaluation Script.

Evaluates and compares:
1. Realized Greedy Baseline (Oracle-Information Reference)
2. Forecast-Based Greedy Baseline (Equal-Information Baseline)
3. Realistic Deterministic MPC (Phase 6A)
4. Corrected Stochastic Scenario-Based MPC (Phase 6B.1)

Across all households (H001, H002, H003) on identical held-out test predictions
with identical initial battery conditions, physical constraints, and tariffs.
Saves machine-readable metrics to reports/phase6b_1_simulation_metrics.csv.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src.energy.battery import BatteryStorage
from src.optimization.constraints import (
    BatteryOptimizationParams,
    MPCConfig,
    TariffParams,
)
from src.optimization.mpc_battery import (
    RollingHorizonSimulator,
    SimulationResult,
    SimulationStepRecord,
)
from src.optimization.mpc_stochastic import (
    StochasticMPCConfig,
    StochasticRollingHorizonSimulator,
)


def run_forecast_greedy_baseline(
    df: pd.DataFrame,
    battery_params: Optional[BatteryOptimizationParams] = None,
    tariffs: Optional[TariffParams] = None,
    actual_demand_col: str = "actual_demand_kwh",
    actual_solar_col: str = "actual_solar_generation_kwh",
    predicted_demand_col: str = "predicted_demand_kwh",
    predicted_solar_col: str = "predicted_solar_generation_kwh",
    timestamp_col: Optional[str] = "forecast_timestamp",
    initial_soc: float = 0.50,
    max_steps: Optional[int] = None,
) -> SimulationResult:
    """Equal-Information Forecast Greedy Baseline:
    Commits charge/discharge using ONLY point predictions and current battery state.
    Evaluated against ground truth physical realization.
    """
    bat = battery_params or BatteryOptimizationParams()
    tar = tariffs or TariffParams()
    dt = 1.0
    p_import = tar.import_price_aud_per_kwh
    p_export = tar.solar_export_credit_aud_per_kwh
    c_max = bat.max_charge_rate_kw * dt
    d_max = bat.max_discharge_rate_kw * dt
    e_min = bat.min_energy_kwh
    e_max = bat.max_energy_kwh

    N = len(df) if max_steps is None else min(len(df), max_steps)
    battery = BatteryStorage(
        capacity_kwh=bat.capacity_kwh,
        max_charge_rate_kw=bat.max_charge_rate_kw,
        max_discharge_rate_kw=bat.max_discharge_rate_kw,
        charge_efficiency=bat.charge_efficiency,
        discharge_efficiency=bat.discharge_efficiency,
        min_soc=bat.min_soc,
        max_soc=bat.max_soc,
        initial_soc=initial_soc,
    )

    records: List[SimulationStepRecord] = []
    actual_d = df[actual_demand_col].to_numpy(dtype=float)
    actual_s = df[actual_solar_col].to_numpy(dtype=float)
    pred_d = df[predicted_demand_col].to_numpy(dtype=float)
    pred_s = df[predicted_solar_col].to_numpy(dtype=float)
    timestamps = df[timestamp_col].tolist() if timestamp_col in df.columns else [None] * len(df)

    init_kwh = battery.current_charge_kwh

    for k in range(N):
        d_pred_k = float(pred_d[k])
        s_pred_k = float(pred_s[k])
        d_act_k = float(actual_d[k])
        s_act_k = float(actual_s[k])
        curr_kwh = battery.current_charge_kwh
        init_soc = battery.soc

        net_pred = s_pred_k - d_pred_k
        if net_pred > 1e-6:
            avail_room = max(0.0, (e_max - curr_kwh) / bat.charge_efficiency)
            c_plan = min(net_pred, c_max, avail_room)
            d_plan = 0.0
        elif net_pred < -1e-6:
            needed_dis = -net_pred
            avail_stored = max(0.0, (curr_kwh - e_min) * bat.discharge_efficiency)
            d_plan = min(needed_dis, d_max, avail_stored)
            c_plan = 0.0
        else:
            c_plan = 0.0
            d_plan = 0.0

        if c_plan > 1e-6:
            state = battery.step(c_plan, 0.0, duration_hours=dt)
        elif d_plan > 1e-6:
            state = battery.step(0.0, d_plan, duration_hours=dt)
        else:
            state = battery.step(0.0, 0.0, duration_hours=dt)

        actual_c = state.charged_kwh
        actual_d_dis = state.discharged_kwh

        net_flow = d_act_k - s_act_k + actual_c - actual_d_dis
        grid_in = max(0.0, net_flow)
        grid_out = max(0.0, -net_flow)
        residual = abs((d_act_k + actual_c + grid_out) - (s_act_k + actual_d_dis + grid_in))

        imp_cost = grid_in * p_import
        exp_rev = grid_out * p_export
        net_step_cost = imp_cost - exp_rev

        records.append(
            SimulationStepRecord(
                step_index=k,
                timestamp=timestamps[k],
                actual_demand_kwh=d_act_k,
                actual_solar_kwh=s_act_k,
                forecast_demand_kwh=d_pred_k,
                forecast_solar_kwh=s_pred_k,
                battery_initial_soc=init_soc,
                battery_final_soc=battery.soc,
                battery_initial_kwh=curr_kwh,
                battery_final_kwh=battery.current_charge_kwh,
                charged_kwh=actual_c,
                discharged_kwh=actual_d_dis,
                grid_imported_kwh=grid_in,
                grid_exported_kwh=grid_out,
                import_cost_aud=imp_cost,
                export_credit_aud=exp_rev,
                net_cost_aud=net_step_cost,
                energy_balance_residual_kwh=residual,
                solver_success=True,
                solver_time_sec=0.0,
            )
        )

    total_imp = sum(r.import_cost_aud for r in records)
    total_exp = sum(r.export_credit_aud for r in records)
    net_c = total_imp - total_exp
    final_kwh = battery.current_charge_kwh
    chem_val = bat.discharge_efficiency * p_import
    adj_c = net_c - ((final_kwh - init_kwh) * chem_val)

    return SimulationResult(
        controller_type="Forecast_Greedy",
        total_hours=len(records),
        total_import_cost_aud=total_imp,
        total_export_revenue_aud=total_exp,
        net_electricity_cost_aud=net_c,
        total_imported_kwh=sum(r.grid_imported_kwh for r in records),
        total_exported_kwh=sum(r.grid_exported_kwh for r in records),
        total_charged_kwh=sum(r.charged_kwh for r in records),
        total_discharged_kwh=sum(r.discharged_kwh for r in records),
        initial_soc=initial_soc,
        final_soc=battery.soc,
        initial_stored_kwh=init_kwh,
        final_stored_kwh=final_kwh,
        net_stored_energy_change_kwh=final_kwh - init_kwh,
        adjusted_net_cost_aud=adj_c,
        min_soc_observed=min(r.battery_final_soc for r in records),
        max_soc_observed=max(r.battery_final_soc for r in records),
        soc_boundary_violations=sum(1 for r in records if r.battery_final_soc < bat.min_soc - 1e-5 or r.battery_final_soc > bat.max_soc + 1e-5),
        simultaneous_charge_discharge_violations=sum(1 for r in records if r.charged_kwh > 1e-5 and r.discharged_kwh > 1e-5),
        max_energy_balance_residual_kwh=max((r.energy_balance_residual_kwh for r in records), default=0.0),
        total_solver_failures=0,
        average_solve_time_sec=0.0,
        max_solve_time_sec=0.0,
        step_records=records,
    )


def run_phase6b_benchmark(
    data_path: str = "data/processed/test_predictions.csv",
    output_csv: str = "reports/phase6b_1_simulation_metrics.csv",
    num_scenarios: int = 3,
    max_hours: Optional[int] = None,
    households: Optional[List[str]] = None,
) -> pd.DataFrame:
    df_all = pd.read_csv(data_path)
    available_households = sorted(df_all["house_id"].unique())
    target_households = households or available_households

    battery_params = BatteryOptimizationParams(
        capacity_kwh=5.0,
        min_soc=0.10,
        max_soc=0.90,
        max_charge_rate_kw=2.5,
        max_discharge_rate_kw=2.5,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
    )
    tariffs = TariffParams(
        import_price_aud_per_kwh=0.30,
        solar_export_credit_aud_per_kwh=0.08,
    )
    det_mpc_config = MPCConfig(
        horizon_hours=24,
        time_step_hours=1.0,
        terminal_strategy="terminal_value",
        allow_grid_charging=True,
    )
    stoch_mpc_config = StochasticMPCConfig(
        horizon_hours=24,
        time_step_hours=1.0,
        num_scenarios=num_scenarios,
        terminal_strategy="terminal_value",
        allow_grid_charging=True,
    )

    det_simulator = RollingHorizonSimulator(
        battery_params=battery_params,
        tariff_params=tariffs,
        mpc_config=det_mpc_config,
    )
    stoch_simulator = StochasticRollingHorizonSimulator(
        battery_params=battery_params,
        tariff_params=tariffs,
        stochastic_config=stoch_mpc_config,
    )

    rows: List[Dict[str, object]] = []

    print("=" * 88)
    print("PHASE 6B.1: STOCHASTIC SCENARIO-BASED MPC BENCHMARK EVALUATION (CORRECTED)")
    print(f"Data: {data_path} | Households: {target_households} | Scenarios S = {num_scenarios}")
    print(f"Battery: 5.0 kWh (10%-90% SOC, max 2.5 kW, eta=95%) | Initial SOC: 50% (2.5 kWh)")
    print(f"Tariffs: Import = 0.30 AUD/kWh, Export = 0.08 AUD/kWh")
    if max_hours:
        print(f"Horizon limit: First {max_hours} hours per household")
    print("=" * 88)

    for h_id in target_households:
        df_h = df_all[df_all["house_id"] == h_id].copy().reset_index(drop=True)
        if max_hours is not None:
            df_h = df_h.iloc[:max_hours].copy().reset_index(drop=True)
        n_hours = len(df_h)
        print(f"\n>>> Household {h_id} ({n_hours} hours | {df_h['forecast_timestamp'].min()} to {df_h['forecast_timestamp'].max()})")

        # 1. Oracle Greedy Baseline (Realized Observations)
        print("  [1/4] Running Realized Greedy Baseline (Oracle Reference)...")
        t0 = time.perf_counter()
        res_oracle = det_simulator.run_greedy_baseline(df_h, initial_soc=0.50)
        t_oracle = time.perf_counter() - t0
        print(f"        Done in {t_oracle:.2f}s | Net Cost: ${res_oracle.net_electricity_cost_aud:.2f} AUD (Adj: ${res_oracle.adjusted_net_cost_aud:.2f})")

        # 2. Forecast-Based Greedy Baseline (Equal Information)
        print("  [2/4] Running Forecast-Based Greedy Baseline (Equal Information)...")
        t0 = time.perf_counter()
        res_fgreedy = run_forecast_greedy_baseline(df_h, initial_soc=0.50)
        t_fgreedy = time.perf_counter() - t0
        print(f"        Done in {t_fgreedy:.2f}s | Net Cost: ${res_fgreedy.net_electricity_cost_aud:.2f} AUD (Adj: ${res_fgreedy.adjusted_net_cost_aud:.2f})")

        # 3. Realistic Deterministic MPC
        print("  [3/4] Running Realistic Deterministic MPC (Phase 6A)...")
        t0 = time.perf_counter()
        res_det = det_simulator.run_mpc(
            df_h,
            actual_demand_col="actual_demand_kwh",
            actual_solar_col="actual_solar_generation_kwh",
            predicted_demand_col="predicted_demand_kwh",
            predicted_solar_col="predicted_solar_generation_kwh",
            initial_soc=0.50,
            shrink_horizon_at_end=True,
        )
        t_det = time.perf_counter() - t0
        print(f"        Done in {t_det:.2f}s | Net Cost: ${res_det.net_electricity_cost_aud:.2f} AUD (Adj: ${res_det.adjusted_net_cost_aud:.2f}) | Avg: {res_det.average_solve_time_sec*1000:.1f}ms")

        # 4. Corrected Stochastic MPC
        print(f"  [4/4] Running Corrected Stochastic Scenario-Based MPC (Phase 6B.1, S={num_scenarios})...")
        t0 = time.perf_counter()
        res_stoch = stoch_simulator.run_stochastic_mpc(
            df_h,
            house_id=h_id,
            actual_demand_col="actual_demand_kwh",
            actual_solar_col="actual_solar_generation_kwh",
            predicted_demand_col="predicted_demand_kwh",
            predicted_solar_col="predicted_solar_generation_kwh",
            timestamp_col="forecast_timestamp",
            initial_soc=0.50,
            shrink_horizon_at_end=True,
        )
        t_stoch = time.perf_counter() - t0
        print(f"        Done in {t_stoch:.2f}s | Net Cost: ${res_stoch.net_electricity_cost_aud:.2f} AUD (Adj: ${res_stoch.adjusted_net_cost_aud:.2f}) | Avg: {res_stoch.average_solve_time_sec*1000:.1f}ms")

        row = {
            "house_id": h_id,
            "hours": n_hours,
            "num_scenarios": num_scenarios,
            # Oracle Greedy
            "oracle_greedy_import_aud": res_oracle.total_import_cost_aud,
            "oracle_greedy_export_aud": res_oracle.total_export_revenue_aud,
            "oracle_greedy_net_cost_aud": res_oracle.net_electricity_cost_aud,
            "oracle_greedy_adjusted_cost_aud": res_oracle.adjusted_net_cost_aud,
            "oracle_greedy_charged_kwh": res_oracle.total_charged_kwh,
            "oracle_greedy_discharged_kwh": res_oracle.total_discharged_kwh,
            "oracle_greedy_final_soc": res_oracle.final_soc,
            # Forecast Greedy (Equal Info)
            "forecast_greedy_import_aud": res_fgreedy.total_import_cost_aud,
            "forecast_greedy_export_aud": res_fgreedy.total_export_revenue_aud,
            "forecast_greedy_net_cost_aud": res_fgreedy.net_electricity_cost_aud,
            "forecast_greedy_adjusted_cost_aud": res_fgreedy.adjusted_net_cost_aud,
            "forecast_greedy_charged_kwh": res_fgreedy.total_charged_kwh,
            "forecast_greedy_discharged_kwh": res_fgreedy.total_discharged_kwh,
            "forecast_greedy_final_soc": res_fgreedy.final_soc,
            # Deterministic MPC
            "det_import_aud": res_det.total_import_cost_aud,
            "det_export_aud": res_det.total_export_revenue_aud,
            "det_net_cost_aud": res_det.net_electricity_cost_aud,
            "det_adjusted_cost_aud": res_det.adjusted_net_cost_aud,
            "det_charged_kwh": res_det.total_charged_kwh,
            "det_discharged_kwh": res_det.total_discharged_kwh,
            "det_final_soc": res_det.final_soc,
            "det_avg_solve_ms": res_det.average_solve_time_sec * 1000.0,
            "det_solver_failures": res_det.total_solver_failures,
            # Corrected Stochastic MPC
            "stoch_import_aud": res_stoch.total_import_cost_aud,
            "stoch_export_aud": res_stoch.total_export_revenue_aud,
            "stoch_net_cost_aud": res_stoch.net_electricity_cost_aud,
            "stoch_adjusted_cost_aud": res_stoch.adjusted_net_cost_aud,
            "stoch_charged_kwh": res_stoch.total_charged_kwh,
            "stoch_discharged_kwh": res_stoch.total_discharged_kwh,
            "stoch_final_soc": res_stoch.final_soc,
            "stoch_avg_solve_ms": res_stoch.average_solve_time_sec * 1000.0,
            "stoch_solver_failures": res_stoch.total_solver_failures,
            # Integrity checks
            "soc_violations": res_stoch.soc_boundary_violations,
            "simul_violations": res_stoch.simultaneous_charge_discharge_violations,
            "max_residual": res_stoch.max_energy_balance_residual_kwh,
        }
        rows.append(row)

        print(f"\n  --- Summary for {h_id} ---")
        print(f"    * Realized Net Cost:  Oracle Greedy = ${res_oracle.net_electricity_cost_aud:8.2f} | Forecast Greedy = ${res_fgreedy.net_electricity_cost_aud:8.2f} | Det MPC = ${res_det.net_electricity_cost_aud:8.2f} | Stoch MPC = ${res_stoch.net_electricity_cost_aud:8.2f}")
        print(f"    * Adjusted Net Cost:  Oracle Greedy = ${res_oracle.adjusted_net_cost_aud:8.2f} | Forecast Greedy = ${res_fgreedy.adjusted_net_cost_aud:8.2f} | Det MPC = ${res_det.adjusted_net_cost_aud:8.2f} | Stoch MPC = ${res_stoch.adjusted_net_cost_aud:8.2f}")
        print(f"    * Stoch vs Forecast Greedy Diff: ${res_stoch.net_electricity_cost_aud - res_fgreedy.net_electricity_cost_aud:+8.2f} AUD")
        print(f"    * Stoch vs Det MPC Diff:         ${res_stoch.net_electricity_cost_aud - res_det.net_electricity_cost_aud:+8.2f} AUD")
        print(f"    * Battery Throughput (Chg):   Oracle Greedy = {res_oracle.total_charged_kwh:6.1f} | Forecast Greedy = {res_fgreedy.total_charged_kwh:6.1f} | Det MPC = {res_det.total_charged_kwh:6.1f} | Stoch MPC = {res_stoch.total_charged_kwh:6.1f} kWh")

        df_out = pd.DataFrame(rows)
        out_file = Path(output_csv)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        df_out.to_csv(out_file, index=False)

    print(f"\n{'='*88}\n[OK] Phase 6B.1 benchmark metrics successfully saved to {out_file}\n{'='*88}")
    return df_out


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Phase 6B.1 Benchmark Runner")
    parser.add_argument("--data", default="data/processed/test_predictions.csv", help="Path to test dataset")
    parser.add_argument("--output", default="reports/phase6b_1_simulation_metrics.csv", help="Output CSV path")
    parser.add_argument("--scenarios", type=int, default=3, help="Number of scenarios")
    parser.add_argument("--max-hours", type=int, default=None, help="Limit hours for testing")
    parser.add_argument("--households", nargs="+", default=None, help="Specific households to evaluate")
    args = parser.parse_args()

    run_phase6b_benchmark(
        data_path=args.data,
        output_csv=args.output,
        num_scenarios=args.scenarios,
        max_hours=args.max_hours,
        households=args.households,
    )
