"""Phase 6B.2 Benchmark Evaluation & Hourly Reconciliation Script.

Runs all 4 controllers on the 1,752-hour held-out test split:
1. Realized Greedy Baseline (Oracle Reference)
2. Forecast Greedy Baseline (Equal Information)
3. Realistic Deterministic MPC (Phase 6A)
4. Corrected Stochastic MPC (Phase 6B.2, with daylight forecast retention)

Outputs:
- reports/phase6b_2_simulation_metrics.csv
- reports/phase6b_2_hourly_records.csv
"""

from __future__ import annotations

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
from evaluate_phase6b_benchmark import run_forecast_greedy_baseline


def run_benchmark_6b2(
    data_path: str = "data/processed/test_predictions.csv",
    metrics_csv: str = "reports/phase6b_2_simulation_metrics.csv",
    hourly_csv: str = "reports/phase6b_2_hourly_records.csv",
    num_scenarios: int = 3,
    max_hours: Optional[int] = None,
) -> pd.DataFrame:
    sys.stdout.reconfigure(encoding="utf-8")
    df_all = pd.read_csv(data_path)
    households = sorted(df_all["house_id"].unique())

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

    summary_rows: List[Dict[str, object]] = []
    all_hourly_records: List[Dict[str, object]] = []

    print("=" * 90)
    print("PHASE 6B.2: RE-RUNNING FULL BENCHMARK (1,752 HOURS ACROSS H001, H002, H003)")
    print(f"Data source: {data_path}")
    print(f"Scenarios S = {num_scenarios} | Battery: 5.0 kWh (10-90% SOC, max 2.5 kW, eta=95%)")
    print(f"Tariffs: Import = 0.30 AUD/kWh, Export = 0.08 AUD/kWh | Initial SOC: 50% (2.5 kWh)")
    print("=" * 90)

    for h_id in households:
        df_h = df_all[df_all["house_id"] == h_id].copy().reset_index(drop=True)
        if max_hours is not None:
            df_h = df_h.iloc[:max_hours].copy().reset_index(drop=True)
        n_hours = len(df_h)
        print(f"\n>>> Household {h_id} ({n_hours} hours | {df_h['forecast_timestamp'].min()} to {df_h['forecast_timestamp'].max()})")

        # 1. Oracle Greedy
        print("  [1/4] Running Realized Greedy Baseline (Oracle Reference)...")
        t0 = time.perf_counter()
        res_oracle = det_simulator.run_greedy_baseline(df_h, initial_soc=0.50)
        t_oracle = time.perf_counter() - t0
        print(f"        Done in {t_oracle:.2f}s | Net Cost: ${res_oracle.net_electricity_cost_aud:.2f} (Adj: ${res_oracle.adjusted_net_cost_aud:.2f})")

        # 2. Forecast Greedy
        print("  [2/4] Running Forecast Greedy Baseline (Equal Information)...")
        t0 = time.perf_counter()
        res_fgreedy = run_forecast_greedy_baseline(df_h, initial_soc=0.50)
        t_fgreedy = time.perf_counter() - t0
        print(f"        Done in {t_fgreedy:.2f}s | Net Cost: ${res_fgreedy.net_electricity_cost_aud:.2f} (Adj: ${res_fgreedy.adjusted_net_cost_aud:.2f})")

        # 3. Deterministic MPC
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
        print(f"        Done in {t_det:.2f}s | Net Cost: ${res_det.net_electricity_cost_aud:.2f} (Adj: ${res_det.adjusted_net_cost_aud:.2f}) | Avg solve: {res_det.average_solve_time_sec*1000:.1f}ms")

        # 4. Corrected Stochastic MPC
        print(f"  [4/4] Running Corrected Stochastic MPC (Phase 6B.2, S={num_scenarios})...")
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
        print(f"        Done in {t_stoch:.2f}s | Net Cost: ${res_stoch.net_electricity_cost_aud:.2f} (Adj: ${res_stoch.adjusted_net_cost_aud:.2f}) | Avg solve: {res_stoch.average_solve_time_sec*1000:.1f}ms")

        # Record hourly steps for all controllers
        controllers = [
            ("Oracle_Greedy", res_oracle),
            ("Forecast_Greedy", res_fgreedy),
            ("Deterministic_MPC", res_det),
            ("Stochastic_MPC", res_stoch),
        ]
        for ctrl_name, res in controllers:
            for rec in res.step_records:
                all_hourly_records.append({
                    "house_id": h_id,
                    "controller": ctrl_name,
                    "step_index": rec.step_index,
                    "timestamp": rec.timestamp,
                    "actual_demand_kwh": rec.actual_demand_kwh,
                    "actual_solar_kwh": rec.actual_solar_kwh,
                    "forecast_demand_kwh": rec.forecast_demand_kwh,
                    "forecast_solar_kwh": rec.forecast_solar_kwh,
                    "battery_initial_soc": rec.battery_initial_soc,
                    "battery_final_soc": rec.battery_final_soc,
                    "battery_initial_kwh": rec.battery_initial_kwh,
                    "battery_final_kwh": rec.battery_final_kwh,
                    "charged_kwh": rec.charged_kwh,
                    "discharged_kwh": rec.discharged_kwh,
                    "grid_imported_kwh": rec.grid_imported_kwh,
                    "grid_exported_kwh": rec.grid_exported_kwh,
                    "import_cost_aud": rec.import_cost_aud,
                    "export_credit_aud": rec.export_credit_aud,
                    "net_cost_aud": rec.net_cost_aud,
                    "residual_kwh": rec.energy_balance_residual_kwh,
                    "solver_success": rec.solver_success,
                    "solver_time_sec": rec.solver_time_sec,
                })

        summary_rows.append({
            "house_id": h_id,
            "hours": n_hours,
            "num_scenarios": num_scenarios,
            # Oracle Greedy
            "oracle_greedy_import_aud": res_oracle.total_import_cost_aud,
            "oracle_greedy_export_aud": res_oracle.total_export_revenue_aud,
            "oracle_greedy_net_cost_aud": res_oracle.net_electricity_cost_aud,
            "oracle_greedy_adjusted_cost_aud": res_oracle.adjusted_net_cost_aud,
            "oracle_greedy_imported_kwh": res_oracle.total_imported_kwh,
            "oracle_greedy_exported_kwh": res_oracle.total_exported_kwh,
            "oracle_greedy_charged_kwh": res_oracle.total_charged_kwh,
            "oracle_greedy_discharged_kwh": res_oracle.total_discharged_kwh,
            "oracle_greedy_final_soc": res_oracle.final_soc,
            # Forecast Greedy
            "forecast_greedy_import_aud": res_fgreedy.total_import_cost_aud,
            "forecast_greedy_export_aud": res_fgreedy.total_export_revenue_aud,
            "forecast_greedy_net_cost_aud": res_fgreedy.net_electricity_cost_aud,
            "forecast_greedy_adjusted_cost_aud": res_fgreedy.adjusted_net_cost_aud,
            "forecast_greedy_imported_kwh": res_fgreedy.total_imported_kwh,
            "forecast_greedy_exported_kwh": res_fgreedy.total_exported_kwh,
            "forecast_greedy_charged_kwh": res_fgreedy.total_charged_kwh,
            "forecast_greedy_discharged_kwh": res_fgreedy.total_discharged_kwh,
            "forecast_greedy_final_soc": res_fgreedy.final_soc,
            # Deterministic MPC
            "det_import_aud": res_det.total_import_cost_aud,
            "det_export_aud": res_det.total_export_revenue_aud,
            "det_net_cost_aud": res_det.net_electricity_cost_aud,
            "det_adjusted_cost_aud": res_det.adjusted_net_cost_aud,
            "det_imported_kwh": res_det.total_imported_kwh,
            "det_exported_kwh": res_det.total_exported_kwh,
            "det_charged_kwh": res_det.total_charged_kwh,
            "det_discharged_kwh": res_det.total_discharged_kwh,
            "det_final_soc": res_det.final_soc,
            "det_avg_solve_ms": res_det.average_solve_time_sec * 1000.0,
            "det_solver_failures": res_det.total_solver_failures,
            # Stochastic MPC
            "stoch_import_aud": res_stoch.total_import_cost_aud,
            "stoch_export_aud": res_stoch.total_export_revenue_aud,
            "stoch_net_cost_aud": res_stoch.net_electricity_cost_aud,
            "stoch_adjusted_cost_aud": res_stoch.adjusted_net_cost_aud,
            "stoch_imported_kwh": res_stoch.total_imported_kwh,
            "stoch_exported_kwh": res_stoch.total_exported_kwh,
            "stoch_charged_kwh": res_stoch.total_charged_kwh,
            "stoch_discharged_kwh": res_stoch.total_discharged_kwh,
            "stoch_final_soc": res_stoch.final_soc,
            "stoch_avg_solve_ms": res_stoch.average_solve_time_sec * 1000.0,
            "stoch_solver_failures": res_stoch.total_solver_failures,
            # Constraints
            "soc_violations": res_stoch.soc_boundary_violations,
            "simul_violations": res_stoch.simultaneous_charge_discharge_violations,
            "max_residual": res_stoch.max_energy_balance_residual_kwh,
        })

    df_summary = pd.DataFrame(summary_rows)
    df_hourly = pd.DataFrame(all_hourly_records)

    p_summary = Path(metrics_csv)
    p_summary.parent.mkdir(parents=True, exist_ok=True)
    df_summary.to_csv(p_summary, index=False)

    p_hourly = Path(hourly_csv)
    p_hourly.parent.mkdir(parents=True, exist_ok=True)
    df_hourly.to_csv(p_hourly, index=False)

    print("\n" + "=" * 90)
    print(f"[OK] Summary metrics saved to: {p_summary}")
    print(f"[OK] Hourly step records ({len(df_hourly)} rows) saved to: {p_hourly}")
    print("=" * 90)
    return df_summary


if __name__ == "__main__":
    run_benchmark_6b2()
