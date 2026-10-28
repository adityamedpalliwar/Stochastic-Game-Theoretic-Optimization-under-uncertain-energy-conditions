"""Script to evaluate Single-Household Rolling-Horizon MPC vs Greedy Baseline.

Evaluates on the held-out test predictions dataset (1,752 hours per household).
Compares:
1. Greedy Heuristic Baseline (instantaneous self-consumption priority)
2. Realistic Rolling-Horizon MPC (optimizing over LSTM forecasts, executed against actuals)
3. Perfect-Foresight Rolling-Horizon MPC (optimizing over realized actuals, theoretical upper bound)
"""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import numpy as np

from src.optimization.constraints import (
    BatteryOptimizationParams,
    MPCConfig,
    TariffParams,
)
from src.optimization.mpc_battery import (
    RollingHorizonSimulator,
    compare_controllers,
)


def run_comprehensive_evaluation(data_path: str = "data/processed/test_predictions.csv") -> None:
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
    # Default MPC config: 24h horizon, terminal value discounting
    mpc_config = MPCConfig(
        horizon_hours=24,
        time_step_hours=1.0,
        terminal_strategy="terminal_value",
        allow_grid_charging=True,
    )

    simulator = RollingHorizonSimulator(
        battery_params=battery_params,
        tariff_params=tariffs,
        mpc_config=mpc_config,
    )

    all_summaries = []

    print("=" * 80)
    print("PHASE 6A: ROLLING-HORIZON MPC VS GREEDY BASELINE EMPIRICAL EVALUATION")
    print(f"Dataset: {data_path} | Households: {households} | Initial SOC: 50% (2.5 kWh)")
    print(f"Tariffs: Import = 0.30 AUD/kWh, Export = 0.08 AUD/kWh")
    print("=" * 80)

    for h_id in households:
        df_h = df_all[df_all["house_id"] == h_id].copy().reset_index(drop=True)
        n_hours = len(df_h)
        print(f"\n>>> Evaluating Household {h_id} ({n_hours} hours: {df_h['forecast_timestamp'].min()} to {df_h['forecast_timestamp'].max()})")

        # 1. Greedy Baseline
        print("  • Running Greedy Baseline...")
        res_greedy = simulator.run_greedy_baseline(df_h, initial_soc=0.50)

        # 2. Realistic MPC (Forecast-driven)
        print("  • Running Realistic Rolling-Horizon MPC (Forecasts -> Actuals)...")
        res_mpc_realistic = simulator.run_mpc(
            df_h,
            actual_demand_col="actual_demand_kwh",
            actual_solar_col="actual_solar_generation_kwh",
            predicted_demand_col="predicted_demand_kwh",
            predicted_solar_col="predicted_solar_generation_kwh",
            initial_soc=0.50,
            shrink_horizon_at_end=True,
        )

        # 3. Perfect Foresight MPC (Actuals -> Actuals)
        print("  • Running Perfect-Foresight MPC (Actuals -> Actuals Benchmark)...")
        res_mpc_perfect = simulator.run_mpc(
            df_h,
            actual_demand_col="actual_demand_kwh",
            actual_solar_col="actual_solar_generation_kwh",
            predicted_demand_col="actual_demand_kwh",
            predicted_solar_col="actual_solar_generation_kwh",
            initial_soc=0.50,
            shrink_horizon_at_end=True,
        )

        # Summaries
        comp_realistic = compare_controllers(res_mpc_realistic, res_greedy)
        comp_perfect = compare_controllers(res_mpc_perfect, res_greedy)

        summary_row = {
            "house_id": h_id,
            "hours": n_hours,
            "greedy_net_cost": res_greedy.net_electricity_cost_aud,
            "greedy_adjusted_cost": res_greedy.adjusted_net_cost_aud,
            "greedy_import_kwh": res_greedy.total_imported_kwh,
            "greedy_export_kwh": res_greedy.total_exported_kwh,
            "greedy_charged_kwh": res_greedy.total_charged_kwh,
            "greedy_discharged_kwh": res_greedy.total_discharged_kwh,
            "greedy_final_soc": res_greedy.final_soc,
            "mpc_realistic_net_cost": res_mpc_realistic.net_electricity_cost_aud,
            "mpc_realistic_adjusted_cost": res_mpc_realistic.adjusted_net_cost_aud,
            "mpc_realistic_cost_diff": comp_realistic["net_cost_difference_aud"],
            "mpc_realistic_adj_diff": comp_realistic["adjusted_cost_diff_aud"],
            "mpc_realistic_import_kwh": res_mpc_realistic.total_imported_kwh,
            "mpc_realistic_export_kwh": res_mpc_realistic.total_exported_kwh,
            "mpc_realistic_charged_kwh": res_mpc_realistic.total_charged_kwh,
            "mpc_realistic_discharged_kwh": res_mpc_realistic.total_discharged_kwh,
            "mpc_realistic_final_soc": res_mpc_realistic.final_soc,
            "mpc_realistic_avg_ms": res_mpc_realistic.average_solve_time_sec * 1000.0,
            "mpc_realistic_max_ms": res_mpc_realistic.max_solve_time_sec * 1000.0,
            "mpc_perfect_net_cost": res_mpc_perfect.net_electricity_cost_aud,
            "mpc_perfect_adjusted_cost": res_mpc_perfect.adjusted_net_cost_aud,
            "mpc_perfect_cost_diff": comp_perfect["net_cost_difference_aud"],
            "mpc_perfect_adj_diff": comp_perfect["adjusted_cost_diff_aud"],
            "mpc_perfect_import_kwh": res_mpc_perfect.total_imported_kwh,
            "mpc_perfect_export_kwh": res_mpc_perfect.total_exported_kwh,
            "mpc_perfect_charged_kwh": res_mpc_perfect.total_charged_kwh,
            "mpc_perfect_discharged_kwh": res_mpc_perfect.total_discharged_kwh,
            "mpc_perfect_final_soc": res_mpc_perfect.final_soc,
            "soc_violations_greedy": res_greedy.soc_boundary_violations,
            "soc_violations_mpc": res_mpc_realistic.soc_boundary_violations,
            "simultaneous_violations_greedy": res_greedy.simultaneous_charge_discharge_violations,
            "simultaneous_violations_mpc": res_mpc_realistic.simultaneous_charge_discharge_violations,
            "max_residual_greedy": res_greedy.max_energy_balance_residual_kwh,
            "max_residual_mpc": res_mpc_realistic.max_energy_balance_residual_kwh,
            "solver_failures": res_mpc_realistic.total_solver_failures,
        }
        all_summaries.append(summary_row)

        print(f"  Results for {h_id}:")
        print(f"    • Greedy Net Cost:               ${res_greedy.net_electricity_cost_aud:8.2f} AUD (Adjusted: ${res_greedy.adjusted_net_cost_aud:8.2f} AUD)")
        print(f"    • Realistic MPC Net Cost:        ${res_mpc_realistic.net_electricity_cost_aud:8.2f} AUD (Adjusted: ${res_mpc_realistic.adjusted_net_cost_aud:8.2f} AUD)")
        print(f"    • Perfect-Foresight MPC Cost:    ${res_mpc_perfect.net_electricity_cost_aud:8.2f} AUD (Adjusted: ${res_mpc_perfect.adjusted_net_cost_aud:8.2f} AUD)")
        print(f"    • Net Cost Difference (MPC-Greedy): ${comp_realistic['net_cost_difference_aud']:+8.2f} AUD ({comp_realistic['net_cost_diff_pct']:+5.2f}%)")
        print(f"    • Adjusted Cost Diff (MPC-Greedy):  ${comp_realistic['adjusted_cost_diff_aud']:+8.2f} AUD ({comp_realistic['adjusted_cost_diff_pct']:+5.2f}%)")
        print(f"    • Battery Throughput (Greedy):   Charged {res_greedy.total_charged_kwh:.1f} kWh | Discharged {res_greedy.total_discharged_kwh:.1f} kWh | Final SOC {res_greedy.final_soc*100:.1f}%")
        print(f"    • Battery Throughput (Real MPC): Charged {res_mpc_realistic.total_charged_kwh:.1f} kWh | Discharged {res_mpc_realistic.total_discharged_kwh:.1f} kWh | Final SOC {res_mpc_realistic.final_soc*100:.1f}%")
        print(f"    • Solver Runtime per step:       Avg {res_mpc_realistic.average_solve_time_sec*1000.0:.2f} ms | Max {res_mpc_realistic.max_solve_time_sec*1000.0:.2f} ms")
        print(f"    • Solver Failures:               {res_mpc_realistic.total_solver_failures} / {n_hours}")
        print(f"    • Max Conservation Residual:     {res_mpc_realistic.max_energy_balance_residual_kwh:.2e} kWh")

    # Save summary dataframe
    df_summary = pd.DataFrame(all_summaries)
    out_path = Path("reports/phase6a_simulation_metrics.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_summary.to_csv(out_path, index=False)
    print(f"\n[OK] Evaluation metrics successfully saved to {out_path}")


if __name__ == "__main__":
    run_comprehensive_evaluation()
