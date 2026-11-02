"""Monte Carlo 1,000-Scenario Simulation of 5-Household Energy Trading Game with Batteries.

This script executes a 1,000-day Monte Carlo simulation over the 5-household dataset
(`data/processed/five_house_hourly_demand.csv`), replicating the sequential 24-hour
game-theoretic optimization from `05_five_house_game.ipynb` with:
- 5 households: H001, H002, H003, H004, H005
- Battery Storage: 5.0 kWh capacity, 2.5 kW max charge/discharge, 95% efficiency,
  min SOC 0.10, max SOC 0.90, all batteries initialized half-full (SOC = 50%) at the start of each day.
- Tariffs: Retail Grid Import = $0.30/kWh, Feed-in Tariff = $0.08/kWh.
- Dynamic P2P Pricing Model: Uncapped selling price (clamp_ceiling=False).
- Grid-Only Counterfactual Comparisons:
  1. Pure Grid Baseline: 100% of energy demand bought from the grid (no solar, no battery).
  2. Solar + Grid-Only: Solar self-consumption without battery, buying all deficits from grid @ $0.30/kWh and exporting surpluses @ $0.08/kWh.
  3. Solar + Battery + Grid-Only: Solar with 5 kWh battery, but buying all net deficits from grid @ $0.30/kWh with NO P2P trading.
  4. P2P Game with Battery: Full proposed peer-to-peer trading game with battery storage.
- Pure numeric computation (no plotting/graphs), aggregating average profit/savings.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.energy.battery import create_default_batteries, BatteryStorage
from src.game.pricing import DynamicPricingModel
from src.game.game import run_n_player_game, NPlayerGameResult


def load_dataset(data_path: Path) -> Tuple[pd.DataFrame, pd.DataFrame, List]:
    """Load and pivot the 5-household demand and solar time series."""
    if not data_path.exists():
        alt_path = data_path.parent / "five_hourly_demand.csv"
        if alt_path.exists():
            data_path = alt_path
        else:
            raise FileNotFoundError(f"Dataset not found at {data_path} or {alt_path}")

    df_raw = pd.read_csv(data_path, parse_dates=["timestamp"])
    player_ids = ["H001", "H002", "H003", "H004", "H005"]

    df_filtered = df_raw[df_raw["house_id"].isin(player_ids)].copy()

    df_demand = df_filtered.pivot(index="timestamp", columns="house_id", values="total_demand_kwh").sort_index()
    df_solar = df_filtered.pivot(index="timestamp", columns="house_id", values="solar_kwh").sort_index()

    unique_dates = sorted(list(set(df_demand.index.date)))
    return df_demand, df_solar, unique_dates


def generate_monte_carlo_scenarios(
    df_demand: pd.DataFrame,
    df_solar: pd.DataFrame,
    unique_dates: List,
    num_scenarios: int = 1000,
    random_seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    """Generate 1,000 24-hour daily scenarios using Monte Carlo smoothed block bootstrap.

    Returns:
    --------
    scenarios_demand : np.ndarray of shape (num_scenarios, 24, 5)
    scenarios_solar  : np.ndarray of shape (num_scenarios, 24, 5)
    """
    rng = np.random.default_rng(random_seed)
    num_dates = len(unique_dates)

    sampled_date_indices = rng.choice(num_dates, size=num_scenarios, replace=True)

    std_demand = df_demand.groupby(df_demand.index.hour).std().to_numpy()
    std_solar = df_solar.groupby(df_solar.index.hour).std().to_numpy()

    scenarios_demand = np.zeros((num_scenarios, 24, 5), dtype=np.float64)
    scenarios_solar = np.zeros((num_scenarios, 24, 5), dtype=np.float64)

    date_blocks_d = {}
    date_blocks_s = {}
    for d in unique_dates:
        mask = df_demand.index.date == d
        date_blocks_d[d] = df_demand[mask].to_numpy()
        date_blocks_s[d] = df_solar[mask].to_numpy()

    for s_idx, d_idx in enumerate(sampled_date_indices):
        d = unique_dates[d_idx]
        base_d = date_blocks_d[d]
        base_s = date_blocks_s[d]

        noise_d = rng.normal(0, 0.15 * std_demand)
        noise_s = rng.normal(0, 0.15 * std_solar)

        sim_d = np.maximum(0.0, base_d + noise_d)
        sim_s = np.maximum(0.0, base_s + noise_s)

        # Enforce physical law: zero solar at night
        sim_s[base_s <= 1e-6] = 0.0

        scenarios_demand[s_idx] = sim_d
        scenarios_solar[s_idx] = sim_s

    return scenarios_demand, scenarios_solar


def run_simulation(
    num_scenarios: int = 1000,
    random_seed: int = 42,
    data_path_str: str = "data/processed/five_house_hourly_demand.csv",
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run full 1,000-scenario Monte Carlo simulation with comprehensive grid-only counterfactuals."""
    data_path = PROJECT_ROOT / data_path_str
    print(f"Loading data from: {data_path} ...")
    df_demand, df_solar, unique_dates = load_dataset(data_path)
    player_ids = ["H001", "H002", "H003", "H004", "H005"]
    print(f"Loaded {len(unique_dates)} unique historical days for 5 households: {player_ids}")

    print(f"\nGenerating {num_scenarios} Monte Carlo daily scenarios (seed={random_seed}) ...")
    sc_demand, sc_solar = generate_monte_carlo_scenarios(
        df_demand=df_demand,
        df_solar=df_solar,
        unique_dates=unique_dates,
        num_scenarios=num_scenarios,
        random_seed=random_seed,
    )
    print(f"Scenario tensors generated: Demand {sc_demand.shape}, Solar {sc_solar.shape}")

    # BESS parameters from 05 notebook
    BATTERY_CAPACITY_KWH = 5.0
    MAX_POWER_KW = 2.50
    EFFICIENCY = 0.95
    MIN_SOC = 0.10
    MAX_SOC = 0.90
    INITIAL_SOC = 0.50  # Half full

    GRID_IMPORT_PRICE = 0.30
    GRID_EXPORT_CREDIT = 0.08

    # Uncapped Dynamic Pricing Model
    pricing_model = DynamicPricingModel(max_pressure=2.0, sensitivity=1.0, clamp_ceiling=False)

    batteries = create_default_batteries(
        player_ids=player_ids,
        capacity_kwh=BATTERY_CAPACITY_KWH,
        max_charge_rate_kw=MAX_POWER_KW,
        max_discharge_rate_kw=MAX_POWER_KW,
        charge_efficiency=EFFICIENCY,
        discharge_efficiency=EFFICIENCY,
        min_soc=MIN_SOC,
        max_soc=MAX_SOC,
        initial_soc=INITIAL_SOC,
    )

    print("\n" + "=" * 80)
    print("STARTING MONTE CARLO GAME SIMULATION (1,000 SCENARIOS / 24,000 HOURLY ROUNDS)")
    print("=" * 80)
    print(f"Batteries: 5 kWh nominal capacity, 50% initial SOC (half full) each day.")
    print(f"Tariffs: Grid Import=${GRID_IMPORT_PRICE:.2f}/kWh, Feed-in Tariff=${GRID_EXPORT_CREDIT:.2f}/kWh.")
    print(f"Pricing Model: {pricing_model.name()} (selling price upper limit removed).")
    print(f"Counterfactuals evaluated:")
    print(f"  [1] Pure Grid: 100% Demand bought from grid @ ${GRID_IMPORT_PRICE:.2f}/kWh (no solar, no battery).")
    print(f"  [2] Solar + Grid: Solar self-consumption, deficit from grid, surplus to grid @ ${GRID_EXPORT_CREDIT:.2f}/kWh (no battery).")
    print(f"  [3] Battery + Grid: Solar + Battery storage, all unmet deficit bought from grid (NO P2P trading).")
    print(f"  [4] P2P Game: Proposed P2P energy trading game with battery storage.")
    print("-" * 80)

    t_start = time.time()

    scenario_records = []
    hourly_savings_sum = np.zeros(24, dtype=np.float64)

    for sc_idx in range(num_scenarios):
        # Reset all players' batteries to half-full at the start of each simulated day
        for b in batteries.values():
            b.reset(INITIAL_SOC)

        sc_demand_day = sc_demand[sc_idx]  # shape (24, 5)
        sc_solar_day = sc_solar[sc_idx]    # shape (24, 5)

        # ── 1. Counterfactual: Pure Grid (100% gross demand bought from grid) ──
        gross_grid_costs = {
            pid: float(np.sum(sc_demand_day[:, i]) * GRID_IMPORT_PRICE)
            for i, pid in enumerate(player_ids)
        }

        # ── 2. Counterfactual: Solar + Grid-Only (no battery, no P2P) ─────────
        raw_deficits_day = np.maximum(0.0, sc_demand_day - sc_solar_day)
        raw_surpluses_day = np.maximum(0.0, sc_solar_day - sc_demand_day)
        solar_grid_costs = {
            pid: float(
                np.sum(raw_deficits_day[:, i]) * GRID_IMPORT_PRICE -
                np.sum(raw_surpluses_day[:, i]) * GRID_EXPORT_CREDIT
            )
            for i, pid in enumerate(player_ids)
        }

        # ── 3 & 4. Battery + Grid-Only and P2P Game Execution ─────────────────
        day_batt_grid_cost = {pid: 0.0 for pid in player_ids}
        day_game_cost = {pid: 0.0 for pid in player_ids}
        day_p2p_profit = {pid: 0.0 for pid in player_ids}
        day_batt_ch = {pid: 0.0 for pid in player_ids}
        day_batt_dis = {pid: 0.0 for pid in player_ids}
        day_p2p_traded = 0.0
        day_demand_total = {pid: 0.0 for pid in player_ids}
        day_solar_total = {pid: 0.0 for pid in player_ids}

        for h in range(24):
            d_vals = sc_demand_day[h]
            s_vals = sc_solar_day[h]

            surpluses = [max(0.0, float(s_vals[i] - d_vals[i])) for i in range(5)]
            deficits = [max(0.0, float(d_vals[i] - s_vals[i])) for i in range(5)]

            for i, pid in enumerate(player_ids):
                day_demand_total[pid] += d_vals[i]
                day_solar_total[pid] += s_vals[i]

            res: NPlayerGameResult = run_n_player_game(
                player_ids=player_ids,
                surpluses_kwh=surpluses,
                deficits_kwh=deficits,
                grid_import_price_aud=GRID_IMPORT_PRICE,
                grid_export_credit_aud=GRID_EXPORT_CREDIT,
                pricing_model=pricing_model,
                batteries=batteries,
            )

            hourly_savings_sum[h] += res.total_community_savings_aud

            for pid in player_ids:
                day_batt_grid_cost[pid] += res.baseline_costs_aud.get(pid, 0.0)
                day_game_cost[pid] += res.game_costs_aud.get(pid, 0.0)
                day_p2p_profit[pid] += res.savings_aud.get(pid, 0.0)
                day_batt_ch[pid] += res.battery_charged_kwh.get(pid, 0.0)
                day_batt_dis[pid] += res.battery_discharged_kwh.get(pid, 0.0)

            if res.matrix is not None and res.equilibrium_result is not None:
                eq = res.equilibrium_result.selected_equilibrium
                if eq:
                    eq_idx = tuple(eq.action_indices[pid] for pid in player_ids)
                    day_p2p_traded += float(res.matrix.traded_quantities[eq_idx])

        # Aggregate community totals
        comm_gross = sum(gross_grid_costs.values())
        comm_solar_grid = sum(solar_grid_costs.values())
        comm_batt_grid = sum(day_batt_grid_cost.values())
        comm_game = sum(day_game_cost.values())

        comm_profit_vs_pure_grid = comm_gross - comm_game
        comm_profit_vs_solar_grid = comm_solar_grid - comm_game
        comm_profit_vs_batt_grid = sum(day_p2p_profit.values())

        rec = {
            "scenario_id": sc_idx + 1,
            # Community metrics
            "community_gross_grid_cost_aud": comm_gross,
            "community_solar_grid_cost_aud": comm_solar_grid,
            "community_batt_grid_cost_aud": comm_batt_grid,
            "community_game_cost_aud": comm_game,
            "community_profit_vs_pure_grid_aud": comm_profit_vs_pure_grid,
            "community_profit_vs_solar_grid_aud": comm_profit_vs_solar_grid,
            "community_profit_vs_batt_grid_aud": comm_profit_vs_batt_grid,
            "community_p2p_traded_kwh": day_p2p_traded,
        }
        for pid in player_ids:
            rec[f"{pid}_demand_kwh"] = day_demand_total[pid]
            rec[f"{pid}_solar_kwh"] = day_solar_total[pid]
            rec[f"{pid}_batt_charged_kwh"] = day_batt_ch[pid]
            rec[f"{pid}_batt_discharged_kwh"] = day_batt_dis[pid]
            rec[f"{pid}_gross_grid_cost_aud"] = gross_grid_costs[pid]
            rec[f"{pid}_solar_grid_cost_aud"] = solar_grid_costs[pid]
            rec[f"{pid}_batt_grid_cost_aud"] = day_batt_grid_cost[pid]
            rec[f"{pid}_game_cost_aud"] = day_game_cost[pid]
            rec[f"{pid}_profit_vs_pure_grid_aud"] = gross_grid_costs[pid] - day_game_cost[pid]
            rec[f"{pid}_profit_vs_solar_grid_aud"] = solar_grid_costs[pid] - day_game_cost[pid]
            rec[f"{pid}_profit_vs_batt_grid_aud"] = day_p2p_profit[pid]

        scenario_records.append(rec)

        if (sc_idx + 1) % 100 == 0 or (sc_idx + 1) == num_scenarios:
            elapsed = time.time() - t_start
            print(f"  Processed {sc_idx + 1:>4}/{num_scenarios} scenarios ({((sc_idx + 1)/num_scenarios)*100:>5.1f}%) | "
                  f"Elapsed: {elapsed:>5.1f}s | Current Avg Community Profit (P2P): ${np.mean([r['community_profit_vs_batt_grid_aud'] for r in scenario_records]):.4f}/day")

    total_time = time.time() - t_start
    print("-" * 80)
    print(f"Simulation completed in {total_time:.2f} seconds ({total_time / num_scenarios * 1000:.1f} ms per 24h scenario).")

    df_scenarios = pd.DataFrame(scenario_records)

    # ── Compute Summary Distribution Statistics ────────────────────────────────
    stat_rows = []
    entities = player_ids + ["COMMUNITY_TOTAL"]

    for ent in entities:
        if ent == "COMMUNITY_TOTAL":
            gross_cost = df_scenarios["community_gross_grid_cost_aud"].mean()
            solar_grid_cost = df_scenarios["community_solar_grid_cost_aud"].mean()
            batt_grid_cost = df_scenarios["community_batt_grid_cost_aud"].mean()
            game_cost = df_scenarios["community_game_cost_aud"].mean()

            profit_pure_series = df_scenarios["community_profit_vs_pure_grid_aud"]
            profit_solar_series = df_scenarios["community_profit_vs_solar_grid_aud"]
            profit_p2p_series = df_scenarios["community_profit_vs_batt_grid_aud"]

            mean_demand = sum(df_scenarios[f"{pid}_demand_kwh"].mean() for pid in player_ids)
            mean_solar = sum(df_scenarios[f"{pid}_solar_kwh"].mean() for pid in player_ids)
            mean_ch = sum(df_scenarios[f"{pid}_batt_charged_kwh"].mean() for pid in player_ids)
            mean_dis = sum(df_scenarios[f"{pid}_batt_discharged_kwh"].mean() for pid in player_ids)
        else:
            gross_cost = df_scenarios[f"{ent}_gross_grid_cost_aud"].mean()
            solar_grid_cost = df_scenarios[f"{ent}_solar_grid_cost_aud"].mean()
            batt_grid_cost = df_scenarios[f"{ent}_batt_grid_cost_aud"].mean()
            game_cost = df_scenarios[f"{ent}_game_cost_aud"].mean()

            profit_pure_series = df_scenarios[f"{ent}_profit_vs_pure_grid_aud"]
            profit_solar_series = df_scenarios[f"{ent}_profit_vs_solar_grid_aud"]
            profit_p2p_series = df_scenarios[f"{ent}_profit_vs_batt_grid_aud"]

            mean_demand = df_scenarios[f"{ent}_demand_kwh"].mean()
            mean_solar = df_scenarios[f"{ent}_solar_kwh"].mean()
            mean_ch = df_scenarios[f"{ent}_batt_charged_kwh"].mean()
            mean_dis = df_scenarios[f"{ent}_batt_discharged_kwh"].mean()

        stat_rows.append({
            "Entity": ent,
            # Cost Comparisons ($/day)
            "Pure_Grid_Cost_AUD": gross_cost,
            "Solar_Grid_Cost_AUD": solar_grid_cost,
            "Batt_Grid_Cost_AUD": batt_grid_cost,
            "Game_Cost_AUD": game_cost,
            # Financial Savings / Profit vs Baselines ($/day & $/yr)
            "Savings_over_Pure_Grid_AUD": profit_pure_series.mean(),
            "Annual_Savings_over_Pure_Grid_AUD": profit_pure_series.mean() * 365.25,
            "Savings_over_Solar_Grid_AUD": profit_solar_series.mean(),
            "Annual_Savings_over_Solar_Grid_AUD": profit_solar_series.mean() * 365.25,
            "P2P_Trading_Profit_AUD": profit_p2p_series.mean(),
            "Annual_P2P_Trading_Profit_AUD": profit_p2p_series.mean() * 365.25,
            # Distribution of P2P game profit
            "Std_Dev_P2P_AUD": profit_p2p_series.std(),
            "Median_P2P_AUD": profit_p2p_series.median(),
            "Q05_P2P_AUD": profit_p2p_series.quantile(0.05),
            "Q95_P2P_AUD": profit_p2p_series.quantile(0.95),
            "Min_P2P_AUD": profit_p2p_series.min(),
            "Max_P2P_AUD": profit_p2p_series.max(),
            # Energy flows
            "Avg_Demand_kWh": mean_demand,
            "Avg_Solar_kWh": mean_solar,
            "Avg_Batt_Charge_kWh": mean_ch,
            "Avg_Batt_Discharge_kWh": mean_dis,
        })

    df_summary = pd.DataFrame(stat_rows)

    hourly_avg_savings = hourly_savings_sum / num_scenarios
    df_hourly = pd.DataFrame({
        "Hour": range(24),
        "Avg_Community_Profit_AUD": hourly_avg_savings,
    })

    return df_scenarios, df_summary, df_hourly


def print_results(df_summary: pd.DataFrame, df_hourly: pd.DataFrame, num_scenarios: int) -> None:
    """Print comprehensive numeric tables to stdout."""
    print("\n" + "=" * 98)
    print(f"   MONTE CARLO 1,000-SCENARIO RESULTS: GRID-ONLY COMPARISON & PROFIT SUMMARY")
    print("=" * 98)
    print(f"Evaluated over {num_scenarios} independent stochastic days (24 hours each).\n")

    # Table 1: Cost Comparison across Operational Modes
    cost_table = df_summary[[
        "Entity", "Pure_Grid_Cost_AUD", "Solar_Grid_Cost_AUD",
        "Batt_Grid_Cost_AUD", "Game_Cost_AUD",
    ]].copy()
    cost_table.columns = [
        "Participant", "Pure Grid ($/day)", "Solar + Grid ($/day)",
        "Battery + Grid ($/day)", "P2P Game ($/day)"
    ]
    for col in cost_table.columns[1:]:
        cost_table[col] = cost_table[col].map(lambda x: f"${x:7.4f}")

    print("TABLE 1: AVERAGE DAILY COST COMPARISON ACROSS OPERATIONAL MODES")
    print("  [1] Pure Grid:       100% Demand bought from grid @ $0.30/kWh (no solar, no battery)")
    print("  [2] Solar + Grid:    Rooftop solar self-consumption, deficit from grid, surplus to grid @ $0.08/kWh")
    print("  [3] Battery + Grid:  Solar + 5 kWh battery, all unmet deficit from grid (NO P2P trading)")
    print("  [4] P2P Game:        Proposed P2P energy trading game with battery storage")
    print("-" * 98)
    print(cost_table.to_string(index=False))
    print("-" * 98)

    # Table 2: Financial Savings & P2P Profit vs Grid-Only Baselines
    profit_comp_table = df_summary[[
        "Entity", "Savings_over_Pure_Grid_AUD", "Annual_Savings_over_Pure_Grid_AUD",
        "Savings_over_Solar_Grid_AUD", "Annual_Savings_over_Solar_Grid_AUD",
        "P2P_Trading_Profit_AUD", "Annual_P2P_Trading_Profit_AUD",
    ]].copy()
    profit_comp_table.columns = [
        "Participant",
        "Savings over Pure Grid ($/d)",
        "Savings over Pure Grid ($/yr)",
        "Savings over Solar Grid ($/d)",
        "Savings over Solar Grid ($/yr)",
        "P2P Trading Profit ($/d)",
        "P2P Trading Profit ($/yr)",
    ]
    for col in profit_comp_table.columns[1:]:
        if "/yr" in col:
            profit_comp_table[col] = profit_comp_table[col].map(lambda x: f"${x:9.2f}")
        else:
            profit_comp_table[col] = profit_comp_table[col].map(lambda x: f"${x:7.4f}")

    print("\nTABLE 2: FINANCIAL SAVINGS & P2P PROFIT COMPARED TO GRID-ONLY BASELINES")
    print("  - Savings over Pure Grid:  Money saved by (Solar + Battery + P2P) instead of buying 100% from grid")
    print("  - Savings over Solar Grid: Extra money saved by adding (Battery + P2P) over solar-only grid imports")
    print("  - P2P Trading Profit:      Extra profit earned specifically from neighbor P2P trading vs isolated battery")
    print("-" * 98)
    print(profit_comp_table.to_string(index=False))
    print("-" * 98)

    # Table 3: P2P Game Profit Distribution
    dist_table = df_summary[[
        "Entity", "P2P_Trading_Profit_AUD", "Std_Dev_P2P_AUD", "Median_P2P_AUD",
        "Q05_P2P_AUD", "Q95_P2P_AUD", "Min_P2P_AUD", "Max_P2P_AUD"
    ]].copy()
    dist_table.columns = [
        "Participant", "Mean P2P Profit ($/d)", "Std Dev ($)", "Median ($)",
        "Q05 ($)", "Q95 ($)", "Min ($)", "Max ($)"
    ]
    for col in dist_table.columns[1:]:
        dist_table[col] = dist_table[col].map(lambda x: f"${x:7.4f}")

    print("\nTABLE 3: P2P GAME DAILY PROFIT DISTRIBUTION (UNCAPPED DYNAMIC PRICING)")
    print("-" * 98)
    print("-" * 98)

    # Table 4: Hourly breakdown of community profit
    print("\nTABLE 4: HOURLY AVERAGE COMMUNITY PROFIT (24-HOUR PROFILE)")
    print("-" * 55)
    print(" Hour   | Avg Community Profit ($) | Peak Trading Hours")
    print("-" * 55)
    for _, row in df_hourly.iterrows():
        h = int(row["Hour"])
        val = row["Avg_Community_Profit_AUD"]
        tag = "<-- Peak Solar/P2P Trade" if 11 <= h <= 15 and val > 0.01 else ""
        print(f" {h:02d}:00  |         ${val:7.4f}         | {tag}")
    print("-" * 55)

    pure_cost = df_summary.loc[df_summary["Entity"] == "COMMUNITY_TOTAL", "Pure_Grid_Cost_AUD"].values[0]
    game_cost = df_summary.loc[df_summary["Entity"] == "COMMUNITY_TOTAL", "Game_Cost_AUD"].values[0]
    p_pure = df_summary.loc[df_summary["Entity"] == "COMMUNITY_TOTAL", "Savings_over_Pure_Grid_AUD"].values[0]
    p_pure_ann = df_summary.loc[df_summary["Entity"] == "COMMUNITY_TOTAL", "Annual_Savings_over_Pure_Grid_AUD"].values[0]
    p_p2p = df_summary.loc[df_summary["Entity"] == "COMMUNITY_TOTAL", "P2P_Trading_Profit_AUD"].values[0]
    p_p2p_ann = df_summary.loc[df_summary["Entity"] == "COMMUNITY_TOTAL", "Annual_P2P_Trading_Profit_AUD"].values[0]

    print("\nKEY FINDINGS & GRID-ONLY COMPARISON:")
    print(f"  1. Pure Grid Baseline (100% Demand from Grid):")
    print(f"     Community would pay ${pure_cost:.4f} AUD/day (${pure_cost*365.25:.2f} AUD/year) with no DERs.")
    print(f"     By deploying Solar + Batteries + P2P Trading, the community cost drops to ${game_cost:.4f} AUD/day,")
    print(f"     yielding an average profit/savings of ${p_pure:.4f} AUD/day (${p_pure_ann:.2f} AUD/year) -- a {((pure_cost-game_cost)/pure_cost)*100:.1f}% reduction in electricity expenditure.")
    print(f"  2. Incremental Value of P2P Market Trading (over Battery Grid-Only):")
    print(f"     Even with solar and batteries fully installed, operating under grid-only rules costs ${df_summary.loc[df_summary['Entity'] == 'COMMUNITY_TOTAL', 'Batt_Grid_Cost_AUD'].values[0]:.4f} AUD/day.")
    print(f"     Enabling peer-to-peer dynamic trading unlocks an extra ${p_p2p:.4f} AUD/day (${p_p2p_ann:.2f} AUD/year)")
    print(f"     of direct financial surplus across all 1,000 Monte Carlo scenarios.\n")
    print("=" * 98)


if __name__ == "__main__":
    df_scenarios, df_summary, df_hourly = run_simulation(
        num_scenarios=1000,
        random_seed=42,
        data_path_str="data/processed/five_house_hourly_demand.csv",
    )
    print_results(df_summary, df_hourly, num_scenarios=1000)

    # Save detailed numeric scenario results to CSV
    output_dir = PROJECT_ROOT / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = output_dir / "monte_carlo_1000_scenarios_summary.csv"
    df_summary.to_csv(summary_csv, index=False)
    print(f"Summary table saved to: {summary_csv}")

    # Generate and save comparison plots
    fig_dir = output_dir / "figures" / "simulate_five_house_monte_carlo"
    from generate_monte_carlo_plots import plot_comparisons
    saved_plots = plot_comparisons(df_scenarios, df_summary, df_hourly, fig_dir)
    print(f"Generated {len(saved_plots)} comparison plots in: {fig_dir}")
