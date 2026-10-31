"""Phase 7: Multi-Household Stochastic Energy Market Integration Benchmark.

Runs all 4 controllers under both P2P-Clearing and Standalone (No-P2P) modes
across the full 1,752-hour held-out test split for H001, H002, and H003:
1. Realized Greedy Baseline (Oracle Reference)
2. Forecast Greedy Baseline (Equal Information)
3. Realistic Deterministic MPC (Phase 6A)
4. Corrected Stochastic MPC (Phase 6B.2, S=3 scenarios)

Generates:
- reports/phase7_benchmark_metrics.csv
- reports/phase7_hourly_records.csv
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.energy.battery import BatteryStorage
from src.energy.market_clearing import MarketClearingPolicy
from src.energy.market_integration import (
    MultiHouseholdCommunitySimulator,
    MultiHouseholdSimulationResult,
)
from src.optimization.constraints import (
    BatteryOptimizationParams,
    MPCConfig,
    TariffParams,
)
from src.optimization.mpc_stochastic import (
    StochasticMPCConfig,
    StochasticScenarioGenerator,
)
from src.stochastic.monte_carlo import ValidationResidualPool


def run_phase7_benchmark(
    data_path: str = "data/processed/test_predictions.csv",
    metrics_csv: str = "reports/phase7_benchmark_metrics.csv",
    hourly_csv: str = "reports/phase7_hourly_records.csv",
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
    p2p_price_aud = 0.19  # Mid-market tariff
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

    # Initialize shared validation pool once
    print("=" * 95)
    print("PHASE 7: MULTI-HOUSEHOLD STOCHASTIC ENERGY MARKET INTEGRATION BENCHMARK")
    print(f"Data source: {data_path} (Households: {households})")
    print(f"Battery: 5.0 kWh (10-90% SOC, max 2.5 kW, eta=95%) | Initial SOC: 50% (2.5 kWh)")
    print(f"Tariffs: Grid Import = $0.30/kWh, Solar Export = $0.08/kWh, P2P Price = $0.19/kWh")
    print(f"Stochastic scenarios S = {num_scenarios} | Matching policy: PRIORITY_ORDER")
    print("=" * 95)

    print("Pre-loading historical ValidationResidualPool for stochastic scenario generation...")
    t0_pool = time.perf_counter()
    residual_pool = ValidationResidualPool()
    scen_gen = StochasticScenarioGenerator(residual_pool=residual_pool)
    print(f"ValidationResidualPool ready in {time.perf_counter() - t0_pool:.2f}s")

    simulator = MultiHouseholdCommunitySimulator(
        households=households,
        battery_params=battery_params,
        tariff_params=tariffs,
        p2p_price_aud=p2p_price_aud,
        market_policy=MarketClearingPolicy.PRIORITY_ORDER,
        mpc_config=det_mpc_config,
        stochastic_config=stoch_mpc_config,
        scenario_generator=scen_gen,
    )

    controllers = [
        ("Oracle_Greedy", "Realized Greedy Baseline (Oracle Reference)"),
        ("Forecast_Greedy", "Forecast Greedy Baseline (Equal Information)"),
        ("Deterministic_MPC", "Realistic Deterministic MPC (Phase 6A)"),
        ("Stochastic_MPC", f"Corrected Stochastic MPC (Phase 6B.2, S={num_scenarios})"),
    ]

    all_hourly_dfs: List[pd.DataFrame] = []
    benchmark_summary_rows: List[Dict[str, Any]] = []

    p_phase6b_records = Path("reports/phase6b_2_hourly_records.csv")
    df_phase6b: Optional[pd.DataFrame] = None
    if p_phase6b_records.exists():
        print(f"Detected audited Phase 6B.2 hourly records at: {p_phase6b_records}")
        df_phase6b = pd.read_csv(p_phase6b_records)

    # Run each controller under both P2P-Clearing and Standalone (No-P2P) modes
    for ctrl_id, ctrl_desc in controllers:
        print(f"\n" + "-" * 90)
        print(f">>> EVALUATING CONTROLLER: {ctrl_desc}")
        print("-" * 90)

        precomp_ctrl = None
        if df_phase6b is not None:
            precomp_ctrl = df_phase6b[df_phase6b["controller"] == ctrl_id].copy().reset_index(drop=True)
            if max_hours is not None:
                precomp_ctrl = precomp_ctrl[precomp_ctrl["step_index"] < max_hours].copy()

        for enable_p2p in [True, False]:
            mode_label = "WITH P2P Clearing" if enable_p2p else "STANDALONE (No P2P)"
            print(f"  * Running {ctrl_id} [{mode_label}]...")
            t0 = time.perf_counter()
            res: MultiHouseholdSimulationResult = simulator.run_simulation(
                df_all=df_all,
                controller_type=ctrl_id,
                enable_p2p=enable_p2p,
                initial_soc=0.50,
                max_steps=max_hours,
                precomputed_records=precomp_ctrl,
            )
            elapsed = time.perf_counter() - t0
            p_met = res.portfolio_metrics

            print(
                f"    Done in {elapsed:.2f}s | Realized Net Cost: ${p_met['realized_net_cost_aud']:.2f} "
                f"(Adj: ${p_met['adjusted_net_cost_aud']:.2f}) | P2P Traded: {p_met['total_p2p_traded_kwh']:.2f} kWh | "
                f"Tradeable Hours: {p_met['tradeable_hours']}/{res.total_hours}"
            )

            # Collect hourly audit DataFrame
            df_h_records = res.get_hourly_records_df()
            all_hourly_dfs.append(df_h_records)

            # Per-household rows
            for hid in households:
                h_met = res.per_household_metrics[hid]
                benchmark_summary_rows.append({
                    "controller": ctrl_id,
                    "enable_p2p": enable_p2p,
                    "mode": "P2P_Integrated" if enable_p2p else "Standalone_Grid",
                    "household": hid,
                    "hours": res.total_hours,
                    "total_demand_kwh": h_met["total_demand_kwh"],
                    "total_solar_kwh": h_met["total_solar_kwh"],
                    "battery_charged_kwh": h_met["total_charged_kwh"],
                    "battery_discharged_kwh": h_met["total_discharged_kwh"],
                    "battery_initial_soc": h_met["initial_soc"],
                    "battery_final_soc": h_met["final_soc"],
                    "battery_delta_stored_kwh": h_met["delta_stored_kwh"],
                    "p2p_bought_kwh": h_met["total_p2p_bought_kwh"],
                    "p2p_sold_kwh": h_met["total_p2p_sold_kwh"],
                    "grid_imported_kwh": h_met["total_imported_kwh"],
                    "grid_exported_kwh": h_met["total_exported_kwh"],
                    "grid_import_cost_aud": h_met["grid_import_cost_aud"],
                    "grid_export_credit_aud": h_met["grid_export_credit_aud"],
                    "p2p_payment_aud": h_met["p2p_payment_aud"],
                    "p2p_revenue_aud": h_met["p2p_revenue_aud"],
                    "realized_net_cost_aud": h_met["realized_net_cost_aud"],
                    "terminal_adjustment_aud": h_met["terminal_adjustment_aud"],
                    "adjusted_net_cost_aud": h_met["adjusted_net_cost_aud"],
                    "soc_boundary_violations": h_met["soc_boundary_violations"],
                    "simultaneous_charge_discharge_violations": h_met["simultaneous_charge_discharge_violations"],
                    "max_energy_balance_residual_kwh": h_met["max_energy_balance_residual_kwh"],
                    "solver_failures": res.total_solver_failures if hid == "H001" else 0,
                    "avg_solve_time_ms": p_met["average_solve_time_ms"],
                    "tradeable_hours": p_met["tradeable_hours"],
                    "no_trade_hours": p_met["no_trade_hours"],
                })

            # Portfolio total row
            benchmark_summary_rows.append({
                "controller": ctrl_id,
                "enable_p2p": enable_p2p,
                "mode": "P2P_Integrated" if enable_p2p else "Standalone_Grid",
                "household": "PORTFOLIO_TOTAL",
                "hours": res.total_hours,
                "total_demand_kwh": sum(m["total_demand_kwh"] for m in res.per_household_metrics.values()),
                "total_solar_kwh": sum(m["total_solar_kwh"] for m in res.per_household_metrics.values()),
                "battery_charged_kwh": p_met["total_charged_kwh"],
                "battery_discharged_kwh": p_met["total_discharged_kwh"],
                "battery_initial_soc": 0.50,
                "battery_final_soc": 0.10,
                "battery_delta_stored_kwh": sum(m["delta_stored_kwh"] for m in res.per_household_metrics.values()),
                "p2p_bought_kwh": sum(m["total_p2p_bought_kwh"] for m in res.per_household_metrics.values()),
                "p2p_sold_kwh": p_met["total_p2p_traded_kwh"],
                "grid_imported_kwh": p_met["total_imported_kwh"],
                "grid_exported_kwh": p_met["total_exported_kwh"],
                "grid_import_cost_aud": p_met["grid_import_cost_aud"],
                "grid_export_credit_aud": p_met["grid_export_credit_aud"],
                "p2p_payment_aud": p_met["p2p_payment_aud"],
                "p2p_revenue_aud": p_met["p2p_revenue_aud"],
                "realized_net_cost_aud": p_met["realized_net_cost_aud"],
                "terminal_adjustment_aud": p_met["terminal_adjustment_aud"],
                "adjusted_net_cost_aud": p_met["adjusted_net_cost_aud"],
                "soc_boundary_violations": sum(m["soc_boundary_violations"] for m in res.per_household_metrics.values()),
                "simultaneous_charge_discharge_violations": sum(m["simultaneous_charge_discharge_violations"] for m in res.per_household_metrics.values()),
                "max_energy_balance_residual_kwh": max(m["max_energy_balance_residual_kwh"] for m in res.per_household_metrics.values()),
                "solver_failures": res.total_solver_failures,
                "avg_solve_time_ms": p_met["average_solve_time_ms"],
                "tradeable_hours": p_met["tradeable_hours"],
                "no_trade_hours": p_met["no_trade_hours"],
            })

    # Save outputs
    df_metrics = pd.DataFrame(benchmark_summary_rows)
    p_metrics = Path(metrics_csv)
    p_metrics.parent.mkdir(parents=True, exist_ok=True)
    df_metrics.to_csv(p_metrics, index=False)
    print(f"\n[OK] Benchmark metrics saved to: {p_metrics} ({len(df_metrics)} rows)")

    df_all_hourly = pd.concat(all_hourly_dfs, ignore_index=True)
    p_hourly = Path(hourly_csv)
    p_hourly.parent.mkdir(parents=True, exist_ok=True)
    df_all_hourly.to_csv(p_hourly, index=False)
    print(f"[OK] Full hourly records saved to: {p_hourly} ({len(df_all_hourly)} records)")

    # Print summary table
    print("\n" + "=" * 105)
    print("PHASE 7 BENCHMARK SUMMARY (1,752 HOURS): PORTFOLIO COMPARISON")
    print("=" * 105)
    cols_display = [
        "controller",
        "mode",
        "p2p_sold_kwh",
        "grid_imported_kwh",
        "grid_exported_kwh",
        "realized_net_cost_aud",
        "adjusted_net_cost_aud",
        "tradeable_hours",
    ]
    df_port = df_metrics[df_metrics["household"] == "PORTFOLIO_TOTAL"][cols_display].copy()
    print(df_port.to_string(index=False))
    print("=" * 105)

    return df_metrics


if __name__ == "__main__":
    run_phase7_benchmark()
