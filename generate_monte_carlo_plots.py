"""Generate high-resolution comparison plots for the 1,000-scenario Monte Carlo simulation.

Saves figures directly into:
    results/figures/simulate_five_house_monte_carlo/
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for clean headless rendering
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from simulate_five_house_monte_carlo import run_simulation


def plot_comparisons(
    df_scenarios: pd.DataFrame,
    df_summary: pd.DataFrame,
    df_hourly: pd.DataFrame,
    fig_dir: Path,
) -> List[Path]:
    """Generate and save 7 comprehensive publication-grade comparison plots."""
    fig_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: List[Path] = []

    # Clean styling parameters
    plt.rcParams.update({
        "figure.dpi": 150,
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 11,
        "legend.fontsize": 9.5,
        "figure.titlesize": 14,
    })

    player_ids = ["H001", "H002", "H003", "H004", "H005"]
    entities = player_ids + ["COMMUNITY_TOTAL"]
    display_names = [f"House {p[-3:]}" for p in player_ids] + ["Community Total"]
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
    num_scenarios = len(df_scenarios)

    # =========================================================================
    # PLOT 1: Daily Cost Comparison Across Operational Modes
    # =========================================================================
    fig, ax = plt.subplots(figsize=(13, 6.5))

    x = np.arange(len(entities))
    width = 0.20

    pure_costs = df_summary["Pure_Grid_Cost_AUD"].to_numpy()
    solar_costs = df_summary["Solar_Grid_Cost_AUD"].to_numpy()
    batt_costs = df_summary["Batt_Grid_Cost_AUD"].to_numpy()
    game_costs = df_summary["Game_Cost_AUD"].to_numpy()

    b1 = ax.bar(x - 1.5 * width, pure_costs, width, label="1. Pure Grid (100% Demand from Grid)", color="#d62728", alpha=0.9, edgecolor="black", linewidth=0.7)
    b2 = ax.bar(x - 0.5 * width, solar_costs, width, label="2. Solar + Grid Only (No Battery)", color="#ff7f0e", alpha=0.9, edgecolor="black", linewidth=0.7)
    b3 = ax.bar(x + 0.5 * width, batt_costs, width, label="3. Battery + Grid Only (No P2P)", color="#1f77b4", alpha=0.9, edgecolor="black", linewidth=0.7)
    b4 = ax.bar(x + 1.5 * width, game_costs, width, label="4. Proposed P2P Game + Battery", color="#2ca02c", alpha=0.9, edgecolor="black", linewidth=0.7)

    for bars in [b1, b2, b3, b4]:
        for bar in bars:
            height = bar.get_height()
            if height > 0.05:
                ax.annotate(
                    f"${height:.2f}",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    rotation=0,
                )

    ax.set_title(f"Average Daily Electricity Cost Comparison Across 4 Operational Modes ({num_scenarios:,} Scenarios)", fontweight="bold", pad=12)
    ax.set_xlabel("Market Participant")
    ax.set_ylabel("Average Cost (AUD / day)")
    ax.set_xticks(x)
    ax.set_xticklabels(display_names, fontweight="semibold")
    ax.grid(True, alpha=0.25, axis="y")
    ax.legend(loc="upper left", framealpha=0.95)
    ax.set_ylim(0, max(pure_costs) * 1.15)

    p1_path = fig_dir / "01_daily_cost_comparison_across_modes.png"
    plt.tight_layout()
    plt.savefig(p1_path, bbox_inches="tight")
    plt.close()
    saved_paths.append(p1_path)

    # =========================================================================
    # PLOT 2: Cost Difference Bar Plot (Baseline vs Optimized)
    # =========================================================================
    fig, ax1 = plt.subplots(figsize=(10, 6.2))

    pure_totals = df_summary["Pure_Grid_Cost_AUD"].to_numpy() * num_scenarios
    game_totals = df_summary["Game_Cost_AUD"].to_numpy() * num_scenarios
    diff_profit_totals = pure_totals - game_totals

    pure_daily = df_summary["Pure_Grid_Cost_AUD"].to_numpy()
    game_daily = df_summary["Game_Cost_AUD"].to_numpy()
    diff_profit_daily = pure_daily - game_daily

    # Cost Difference Bar Plot (Baseline vs P2P Game & Difference = Total Profit)
    x_sub = np.arange(len(entities))
    w_sub = 0.27

    b_pure = ax1.bar(
        x_sub - w_sub,
        pure_totals,
        w_sub,
        label="1. Baseline Cost (Pure Grid @ $0.30/kWh)",
        color="#d62728",
        alpha=0.85,
        edgecolor="black",
        linewidth=0.7,
    )
    b_game = ax1.bar(
        x_sub,
        game_totals,
        w_sub,
        label="2. Optimized Cost (Solar + BESS + P2P)",
        color="#1f77b4",
        alpha=0.85,
        edgecolor="black",
        linewidth=0.7,
    )
    b_diff = ax1.bar(
        x_sub + w_sub,
        diff_profit_totals,
        w_sub,
        label="3. Difference = TOTAL PROFIT EARNED",
        color="#2ca02c",
        alpha=0.92,
        edgecolor="black",
        linewidth=1.0,
    )

    for bar, d_val, pct in zip(b_diff, diff_profit_daily, (diff_profit_totals / pure_totals) * 100):
        h = bar.get_height()
        ax1.annotate(
            f"+${h:,.0f}\n(+${d_val:.2f}/d)\n[-{pct:.0f}%]",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8.0,
            fontweight="bold",
            color="darkgreen",
        )

    for bar in b_pure:
        h = bar.get_height()
        ax1.annotate(
            f"${h:,.0f}",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=7.8,
        )

    for bar in b_game:
        h = bar.get_height()
        ax1.annotate(
            f"${h:,.0f}",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=7.8,
        )

    ax1.set_title(f"Cost Difference: Baseline vs Optimized ({num_scenarios:,} Days)\nDifference = Total Profit Earned", fontweight="bold")
    ax1.set_xlabel("Market Participant")
    ax1.set_ylabel("Total Expenditure / Profit (AUD)")
    ax1.set_xticks(x_sub)
    ax1.set_xticklabels(display_names, rotation=15, ha="right", fontweight="semibold")
    ax1.grid(True, alpha=0.25, axis="y")
    ax1.legend(loc="upper left", framealpha=0.95)
    ax1.set_ylim(0, max(pure_totals) * 1.25)

    p2_path = fig_dir / "02_total_profit_and_cost_difference.png"
    plt.tight_layout()
    plt.savefig(p2_path, bbox_inches="tight")
    plt.savefig(fig_dir / "02_financial_savings_and_p2p_profit.png", bbox_inches="tight")
    plt.close()
    saved_paths.append(p2_path)

    # =========================================================================
    # PLOT 3: P2P Game Profit Distribution (1,000 Scenarios)
    # =========================================================================
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    p2p_data = [df_scenarios[f"{pid}_profit_vs_batt_grid_aud"].to_numpy() for pid in player_ids]
    p2p_data.append(df_scenarios["community_profit_vs_batt_grid_aud"].to_numpy())

    bp = ax1.boxplot(
        p2p_data,
        tick_labels=display_names,
        patch_artist=True,
        showmeans=True,
        meanline=True,
        medianprops={"color": "black", "linewidth": 1.5},
        meanprops={"color": "red", "linestyle": "--", "linewidth": 1.5},
    )

    for patch, c in zip(bp["boxes"], colors):
        patch.set_facecolor(c)
        patch.set_alpha(0.7)

    ax1.set_title(f"Daily P2P Profit Distribution ({num_scenarios:,} Scenarios Boxplot)", fontweight="bold")
    ax1.set_xlabel("Market Participant")
    ax1.set_ylabel("Daily P2P Profit (AUD)")
    ax1.set_xticklabels(display_names, rotation=15, ha="right", fontweight="semibold")
    ax1.grid(True, alpha=0.25, axis="y")

    ax1.plot([], [], color="black", label="Median", linewidth=1.5)
    ax1.plot([], [], color="red", linestyle="--", label="Mean", linewidth=1.5)
    ax1.legend(loc="upper left")

    comm_profits = df_scenarios["community_profit_vs_batt_grid_aud"].to_numpy()
    mean_val = np.mean(comm_profits)
    med_val = np.median(comm_profits)
    q05_val = np.percentile(comm_profits, 5)
    q95_val = np.percentile(comm_profits, 95)

    n, bins, patches = ax2.hist(comm_profits, bins=40, density=True, color="#2ca02c", alpha=0.65, edgecolor="black")

    from scipy.stats import gaussian_kde
    kde = gaussian_kde(comm_profits)
    x_grid = np.linspace(0, max(comm_profits), 200)
    ax2.plot(x_grid, kde(x_grid), color="darkgreen", linewidth=2.5, label="Kernel Density Estimate")

    ax2.axvline(mean_val, color="red", linestyle="--", linewidth=1.8, label=f"Mean: ${mean_val:.4f}/d")
    ax2.axvline(med_val, color="black", linestyle="-", linewidth=1.8, label=f"Median: ${med_val:.4f}/d")
    ax2.axvline(q05_val, color="purple", linestyle=":", linewidth=1.5, label=f"5th Pct: ${q05_val:.4f}/d")
    ax2.axvline(q95_val, color="navy", linestyle=":", linewidth=1.5, label=f"95th Pct: ${q95_val:.4f}/d")

    ax2.set_title("Community Daily P2P Profit Probability Density", fontweight="bold")
    ax2.set_xlabel("Community Daily P2P Profit (AUD)")
    ax2.set_ylabel("Probability Density")
    ax2.grid(True, alpha=0.25)
    ax2.legend(loc="upper right", fontsize=8.5)

    p3_path = fig_dir / "03_p2p_profit_distribution_1000_scenarios.png"
    plt.tight_layout()
    plt.savefig(p3_path, bbox_inches="tight")
    plt.close()
    saved_paths.append(p3_path)

    # =========================================================================
    # PLOT 4: Hourly Average Community Profit (24-Hour Profile)
    # =========================================================================
    fig, ax = plt.subplots(figsize=(12, 5.5))

    hours = df_hourly["Hour"].to_numpy()
    h_profits = df_hourly["Avg_Community_Profit_AUD"].to_numpy()

    bars = ax.bar(hours, h_profits, color="#1f77b4", alpha=0.7, edgecolor="black", label="Hourly Average Profit")
    ax.plot(hours, h_profits, color="navy", marker="o", markersize=5, linewidth=2.2, label="Trend Profile")

    ax.axvspan(10.5, 15.5, color="gold", alpha=0.18, label="Active Solar P2P Trading Window (11:00-15:00)")

    peak_h = int(np.argmax(h_profits))
    peak_val = h_profits[peak_h]
    ax.annotate(
        f"Peak Hour {peak_h:02d}:00\n${peak_val:.4f}/hr",
        xy=(peak_h, peak_val),
        xytext=(peak_h - 2.5, peak_val + 0.015),
        arrowprops=dict(facecolor="black", shrink=0.08, width=1, headwidth=6),
        fontsize=9,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="grey"),
    )

    ax.set_title(f"Average Hourly Community Profit from P2P Energy Trading ({num_scenarios:,} Scenarios)", fontweight="bold", pad=12)
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Average Community Profit (AUD / hr)")
    ax.set_xticks(hours)
    ax.set_ylim(0, max(h_profits) * 1.30)
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left")

    p4_path = fig_dir / "04_hourly_average_community_profit.png"
    plt.tight_layout()
    plt.savefig(p4_path, bbox_inches="tight")
    plt.close()
    saved_paths.append(p4_path)

    # =========================================================================
    # PLOT 5: Cumulative Community Savings Trajectory over 1,000 Simulated Days
    # =========================================================================
    fig, ax = plt.subplots(figsize=(13, 6))

    sc_indices = np.arange(1, len(df_scenarios) + 1)
    cum_pure = np.cumsum(df_scenarios["community_profit_vs_pure_grid_aud"].to_numpy())
    cum_solar = np.cumsum(df_scenarios["community_profit_vs_solar_grid_aud"].to_numpy())
    cum_p2p = np.cumsum(df_scenarios["community_profit_vs_batt_grid_aud"].to_numpy())

    ax.plot(sc_indices, cum_pure, label=f"Cumulative Savings vs Pure Grid (Final: ${cum_pure[-1]:,.2f} AUD)", color="#2ca02c", linewidth=2.5)
    ax.fill_between(sc_indices, 0, cum_pure, color="#2ca02c", alpha=0.10)

    ax.plot(sc_indices, cum_solar, label=f"Cumulative Savings vs Solar Grid (Final: ${cum_solar[-1]:,.2f} AUD)", color="#1f77b4", linewidth=2.0)
    ax.fill_between(sc_indices, 0, cum_solar, color="#1f77b4", alpha=0.08)

    ax.plot(sc_indices, cum_p2p, label=f"Cumulative P2P Market Profit (Final: ${cum_p2p[-1]:,.2f} AUD)", color="#d62728", linewidth=2.0, linestyle="--")

    ax.set_title(f"Cumulative Community Financial Benefits Over {num_scenarios:,} Monte Carlo Simulated Days", fontweight="bold", pad=12)
    ax.set_xlabel("Simulated Day (Scenario Number)")
    ax.set_ylabel("Cumulative Financial Benefit (AUD)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left", framealpha=0.95)

    p5_path = fig_dir / "05_cumulative_community_savings_over_1000_days.png"
    plt.tight_layout()
    plt.savefig(p5_path, bbox_inches="tight")
    plt.close()
    saved_paths.append(p5_path)

    # =========================================================================
    # PLOT 6: Total Profit Breakdown by Contributing Source (Difference Decomposition)
    # =========================================================================
    fig, ax = plt.subplots(figsize=(13, 6.5))

    solar_totals = (df_summary["Pure_Grid_Cost_AUD"].to_numpy() - df_summary["Solar_Grid_Cost_AUD"].to_numpy()) * num_scenarios
    batt_totals = (df_summary["Solar_Grid_Cost_AUD"].to_numpy() - df_summary["Batt_Grid_Cost_AUD"].to_numpy()) * num_scenarios
    p2p_totals = (df_summary["Batt_Grid_Cost_AUD"].to_numpy() - df_summary["Game_Cost_AUD"].to_numpy()) * num_scenarios
    total_diff = solar_totals + batt_totals + p2p_totals

    b_sol = ax.bar(display_names, solar_totals, label="1. Solar Self-Consumption Profit", color="#ff7f0e", alpha=0.85, edgecolor="black", linewidth=0.7)
    b_bat = ax.bar(display_names, batt_totals, bottom=solar_totals, label="2. Battery Storage Arbitrage Profit", color="#1f77b4", alpha=0.85, edgecolor="black", linewidth=0.7)
    b_p2p = ax.bar(display_names, p2p_totals, bottom=solar_totals + batt_totals, label="3. P2P Market Trading Profit", color="#2ca02c", alpha=0.90, edgecolor="black", linewidth=0.7)

    for i in range(len(entities)):
        total_h = total_diff[i]
        ax.annotate(
            f"Total Profit:\n${total_h:,.2f}",
            xy=(i, total_h),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
        )

    ax.set_title(f"Difference Decomposition: Sources Contributing to Total Profit ({num_scenarios:,} Days)\nShowing Differences in Energy Component Contributions", fontweight="bold", pad=12)
    ax.set_xlabel("Market Participant")
    ax.set_ylabel("Total Profit Contribution (AUD)")
    ax.grid(True, alpha=0.25, axis="y")
    ax.legend(loc="upper left", framealpha=0.95)
    ax.set_ylim(0, max(total_diff) * 1.20)

    p6_path = fig_dir / "06_total_profit_difference_decomposition.png"
    plt.tight_layout()
    plt.savefig(p6_path, bbox_inches="tight")
    plt.close()
    saved_paths.append(p6_path)

    # =========================================================================
    # PLOT 7: Portion of Each Factor in Total Financial Savings (Solar, Battery, P2P)
    # =========================================================================
    fig, (ax_donut, ax_bar) = plt.subplots(1, 2, figsize=(16, 7.5), gridspec_kw={"width_ratios": [1, 1.4]})

    comm_solar = solar_totals[-1]
    comm_batt = batt_totals[-1]
    comm_p2p = p2p_totals[-1]
    comm_total = total_diff[-1]

    factor_colors = ["#ff7f0e", "#1f77b4", "#2ca02c"]
    factor_labels = [
        f"Rooftop Solar PV\nSelf-Consumption\n${comm_solar:,.2f} ({comm_solar/comm_total*100:.1f}%)",
        f"Battery Storage (BESS)\nPeak Arbitrage\n${comm_batt:,.2f} ({comm_batt/comm_total*100:.1f}%)",
        f"P2P Market Trading\nCollaborative Surplus\n${comm_p2p:,.2f} ({comm_p2p/comm_total*100:.1f}%)",
    ]

    # Panel 1: Donut Chart of Community Total Portions
    wedges, texts, autotexts = ax_donut.pie(
        [comm_solar, comm_batt, comm_p2p],
        explode=[0.02, 0.02, 0.08],
        labels=factor_labels,
        autopct="%1.1f%%",
        pctdistance=0.72,
        startangle=140,
        colors=factor_colors,
        wedgeprops=dict(width=0.45, edgecolor="black", linewidth=1.2),
        textprops=dict(fontsize=9.5, fontweight="semibold"),
    )
    for at in autotexts:
        at.set_fontsize(11)
        at.set_fontweight("bold")
        at.set_color("white")

    # Center circle annotation in donut hole
    ax_donut.text(
        0, 0,
        f"Total Community\nSavings:\n${comm_total:,.2f}\n(100%)",
        ha="center",
        va="center",
        fontsize=11,
        fontweight="bold",
        color="#333333",
    )
    ax_donut.set_title(f"A. Community Total Savings Portion by Factor\n(Over {num_scenarios:,} Simulated Days)", fontweight="bold", pad=15)

    # Panel 2: 100% Normalized Stacked Bar Chart across Households
    solar_pct = (solar_totals / total_diff) * 100
    batt_pct = (batt_totals / total_diff) * 100
    p2p_pct = (p2p_totals / total_diff) * 100

    bar_width = 0.55
    indices = np.arange(len(entities))

    b1 = ax_bar.bar(indices, solar_pct, bar_width, label="1. Rooftop Solar PV Self-Consumption", color="#ff7f0e", alpha=0.90, edgecolor="black", linewidth=0.8)
    b2 = ax_bar.bar(indices, batt_pct, bar_width, bottom=solar_pct, label="2. Battery Storage Arbitrage (BESS)", color="#1f77b4", alpha=0.90, edgecolor="black", linewidth=0.8)
    b3 = ax_bar.bar(indices, p2p_pct, bar_width, bottom=solar_pct + batt_pct, label="3. P2P Market Trading Surplus", color="#2ca02c", alpha=0.92, edgecolor="black", linewidth=0.8)

    # Add text labels inside bars
    for i in range(len(entities)):
        # Solar label
        sp = solar_pct[i]
        sv = solar_totals[i]
        if sp > 10:
            ax_bar.text(i, sp / 2, f"{sp:.1f}%\n(${sv:,.0f})", ha="center", va="center", fontsize=8, fontweight="bold", color="white")
        
        # Battery label
        bp = batt_pct[i]
        bv = batt_totals[i]
        if bp > 10:
            ax_bar.text(i, sp + bp / 2, f"{bp:.1f}%\n(${bv:,.0f})", ha="center", va="center", fontsize=8, fontweight="bold", color="white")
        
        # P2P label
        pp = p2p_pct[i]
        pv = p2p_totals[i]
        if pp >= 3.0:
            ax_bar.text(i, sp + bp + pp / 2, f"{pp:.1f}%\n(${pv:,.0f})", ha="center", va="center", fontsize=8, fontweight="bold", color="white")
        elif pp > 0.4:
            ax_bar.annotate(
                f"{pp:.1f}% (${pv:,.0f})",
                xy=(i, 100),
                xytext=(0, 6),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7.5,
                fontweight="bold",
                color="darkgreen",
            )

    ax_bar.set_title(f"B. Percentage Portion of Each Factor per Household (100% Normalized)\n(Highlighting How Energy Profiles Determine Factor Importance)", fontweight="bold", pad=15)
    ax_bar.set_xlabel("Market Participant")
    ax_bar.set_ylabel("Portion of Total Savings (%)")
    ax_bar.set_xticks(indices)
    ax_bar.set_xticklabels(display_names, rotation=15, ha="right", fontweight="semibold")
    ax_bar.set_ylim(0, 112)
    ax_bar.grid(True, alpha=0.25, axis="y")
    ax_bar.legend(loc="upper right", framealpha=0.95, fontsize=9)

    p7_path = fig_dir / "07_savings_portion_by_factor.png"
    plt.tight_layout()
    plt.savefig(p7_path, bbox_inches="tight")
    plt.close()
    saved_paths.append(p7_path)

    return saved_paths


if __name__ == "__main__":
    print("Running 1,000-scenario Monte Carlo simulation to generate plots...")
    df_scenarios, df_summary, df_hourly = run_simulation(
        num_scenarios=1000,
        random_seed=42,
        data_path_str="data/processed/five_house_hourly_demand.csv",
    )

    fig_dir = PROJECT_ROOT / "results" / "figures" / "simulate_five_house_monte_carlo"
    print(f"\nGenerating and saving plots to: {fig_dir} ...")
    saved_plots = plot_comparisons(df_scenarios, df_summary, df_hourly, fig_dir)

    print("\nSuccessfully generated the following plots:")
    for p in saved_plots:
        print(f"  - {p.name} ({p.stat().st_size / 1024:.1f} KB)")
