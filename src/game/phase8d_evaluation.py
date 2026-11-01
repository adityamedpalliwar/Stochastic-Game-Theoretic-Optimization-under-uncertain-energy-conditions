"""Phase 8D dataset-wide equilibrium selection evaluation and analysis engine.

Evaluates all six selection strategies (A-F) plus seven sensitivity weight variants
for Strategy F across the complete 1,752-hour held-out test period.

Generates:
1. Hourly selection records: `reports/phase8d_hourly_selection.csv`
2. Aggregate comparative summary: `reports/phase8d_strategy_comparison.csv`
3. Publication-grade visualizations: `reports/phase8d_visualizations/`
"""

from __future__ import annotations

import gzip
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.game.equilibrium_selection import (
    SelectionStrategy,
    select_equilibrium,
    select_strategy_a_reference,
    select_strategy_b_seller_favouring,
    select_strategy_c_buyer_favouring,
    select_strategy_d_maxmin_fair,
    select_strategy_e_nash_social_welfare,
    select_strategy_f_hybrid,
)
from src.game.fairness_metrics import (
    DEFAULT_NSW_EPSILON,
    DEFAULT_NUMERICAL_TOLERANCE,
    compute_fairness_summary,
    compute_household_benefit_shares,
    compute_normalized_gini,
    compute_standard_gini,
)

DEFAULT_ARCHIVE_JSON_PATH = Path("reports/phase8c_all_equilibria.json.gz")
DEFAULT_HOURLY_CSV_PATH = Path("reports/phase8c_hourly_equilibria.csv")
DEFAULT_OUTPUT_HOURLY_PATH = Path("reports/phase8d_hourly_selection.csv")
DEFAULT_OUTPUT_STRATEGY_PATH = Path("reports/phase8d_strategy_comparison.csv")
DEFAULT_VIS_DIR = Path("reports/phase8d_visualizations")

HYBRID_SENSITIVITY_WEIGHTS: Tuple[float, ...] = (0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0)


def load_evaluation_data(
    json_path: Path = DEFAULT_ARCHIVE_JSON_PATH,
    csv_path: Path = DEFAULT_HOURLY_CSV_PATH,
) -> Tuple[List[Dict[str, Any]], pd.DataFrame]:
    """Load the complete all-equilibria JSON archive and hourly meter dataset."""
    if not json_path.exists():
        raise FileNotFoundError(f"Equilibrium archive not found: {json_path}")
    if not csv_path.exists():
        raise FileNotFoundError(f"Hourly dataset not found: {csv_path}")

    with gzip.open(json_path, "rt", encoding="utf-8") as f:
        all_eq_data = json.load(f)

    df_hourly = pd.read_csv(csv_path)
    df_hourly.set_index("timestamp", inplace=True)

    return all_eq_data, df_hourly


def run_phase8d_evaluation(
    all_eq_data: Optional[List[Dict[str, Any]]] = None,
    df_hourly: Optional[pd.DataFrame] = None,
    hybrid_weights: Sequence[float] = HYBRID_SENSITIVITY_WEIGHTS,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
    epsilon: float = DEFAULT_NSW_EPSILON,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """Execute complete dataset-wide evaluation across all 1,752 hours.

    Parameters
    ----------
    all_eq_data : Optional[List[Dict[str, Any]]]
        Loaded JSON archive data.
    df_hourly : Optional[pd.DataFrame]
        Loaded hourly physical positions.
    hybrid_weights : Sequence[float]
        Fairness weights w_fair to sweep for Strategy F.
    tolerance : float
        Numerical zero threshold.
    epsilon : float
        Regularization for log-NSW.

    Returns
    -------
    Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]
        (df_hourly_selection, df_strategy_comparison, summary_dict)
    """
    if all_eq_data is None or df_hourly is None:
        all_eq_data, df_hourly = load_evaluation_data()

    total_hours = len(all_eq_data)

    # Define core strategies and hybrid variants
    strategy_definitions: List[Dict[str, Any]] = [
        {"id": "Strategy_A_Reference", "name": "Strategy A: Reference (Phase 8C)", "type": "core", "key": "strat_a"},
        {"id": "Strategy_B_Seller", "name": "Strategy B: Seller-Favouring", "type": "core", "key": "strat_b"},
        {"id": "Strategy_C_Buyer", "name": "Strategy C: Buyer-Favouring", "type": "core", "key": "strat_c"},
        {"id": "Strategy_D_MaxMin", "name": "Strategy D: Max-Min Fair", "type": "core", "key": "strat_d"},
        {"id": "Strategy_E_NSW", "name": "Strategy E: Nash Social Welfare", "type": "core", "key": "strat_e"},
        {"id": "Strategy_F_Hybrid_w0.5", "name": "Strategy F: Hybrid (w_fair=0.5)", "type": "core", "key": "strat_f_05"},
    ]

    # Add sensitivity variants
    for w in hybrid_weights:
        w_str = f"{w:.1f}"
        s_id = f"Hybrid_w_fair_{w_str}"
        s_name = f"Hybrid (w_fair={w_str}, w_ref={1.0 - w:.1f})"
        if not any(d["id"] == s_id for d in strategy_definitions):
            strategy_definitions.append({
                "id": s_id,
                "name": s_name,
                "type": "sensitivity",
                "key": f"hybrid_{w_str.replace('.', '_')}",
                "w_fair": w,
            })

    # Prepare tracking containers
    hourly_rows: List[Dict[str, Any]] = []

    strategy_stats: Dict[str, Dict[str, Any]] = {
        s["id"]: {
            "name": s["name"],
            "type": s["type"],
            "total_volume_kwh": 0.0,
            "total_welfare_aud": 0.0,
            "total_seller_benefit_aud": 0.0,
            "total_buyer_benefit_aud": 0.0,
            "H001_benefit_aud": 0.0,
            "H002_benefit_aud": 0.0,
            "H003_benefit_aud": 0.0,
            "price_volume_numerator": 0.0,
            "max_hourly_accounting_residual": 0.0,
            "hours_match_strategy_a": 0,
            "mixed_gini_std_list": [],
            "mixed_gini_norm_list": [],
            "mixed_min_benefit_list": [],
            "mixed_max_benefit_list": [],
            "mixed_range_list": [],
            "execution_time_ms": 0.0,
        }
        for s in strategy_definitions
    }

    t0_all = time.time()

    for idx, entry in enumerate(all_eq_data):
        ts = entry["timestamp"]
        eqs = entry["equilibria"]
        pareto_eqs = [eq for eq in eqs if eq.get("is_pareto_undominated", False)]
        h_row = df_hourly.loc[ts]

        # Extract active players and roles
        active_players = []
        sellers = []
        buyers = []
        for hid in ["H001", "H002", "H003"]:
            s_val = float(h_row[f"{hid}_surplus_kwh"])
            d_val = float(h_row[f"{hid}_deficit_kwh"])
            if s_val > tolerance:
                active_players.append(hid)
                sellers.append(hid)
            elif d_val > tolerance:
                active_players.append(hid)
                buyers.append(hid)

        active_players.sort()
        sellers.sort()
        buyers.sort()
        is_mixed = (len(sellers) > 0) and (len(buyers) > 0)

        row: Dict[str, Any] = {
            "timestamp": ts,
            "num_active_players": len(active_players),
            "num_active_sellers": len(sellers),
            "num_active_buyers": len(buyers),
            "is_mixed_market": is_mixed,
            "num_pareto_undominated": len(pareto_eqs),
        }

        # Track Strategy A profile for concordance comparison
        strat_a_profile = None

        for s_def in strategy_definitions:
            s_id = s_def["id"]
            t0_strat = time.time()

            if s_id == "Strategy_A_Reference":
                sel_eq = select_strategy_a_reference(pareto_eqs, active_players, tolerance=tolerance)
                strat_a_profile = sel_eq.get("profile") if sel_eq else None
            elif s_id == "Strategy_B_Seller":
                sel_eq = select_strategy_b_seller_favouring(pareto_eqs, active_players, sellers, tolerance=tolerance)
            elif s_id == "Strategy_C_Buyer":
                sel_eq = select_strategy_c_buyer_favouring(pareto_eqs, active_players, buyers, tolerance=tolerance)
            elif s_id == "Strategy_D_MaxMin":
                sel_eq = select_strategy_d_maxmin_fair(pareto_eqs, active_players, tolerance=tolerance)
            elif s_id == "Strategy_E_NSW":
                sel_eq = select_strategy_e_nash_social_welfare(pareto_eqs, active_players, epsilon=epsilon, tolerance=tolerance)
            elif s_id == "Strategy_F_Hybrid_w0.5":
                sel_eq = select_strategy_f_hybrid(pareto_eqs, active_players, weight_reference=0.5, weight_fairness=0.5, tolerance=tolerance)
            else:
                # Sensitivity weight
                w_f = float(s_def["w_fair"])
                sel_eq = select_strategy_f_hybrid(pareto_eqs, active_players, weight_reference=1.0 - w_f, weight_fairness=w_f, tolerance=tolerance)

            elapsed_ms = (time.time() - t0_strat) * 1000.0
            strategy_stats[s_id]["execution_time_ms"] += elapsed_ms

            if sel_eq is not None:
                vol = float(sel_eq["total_traded_kwh"])
                welf = float(sel_eq["community_welfare_aud"])
                p_vwap = sel_eq.get("weighted_average_price_aud")
                payoffs = sel_eq.get("payoffs", {})
                profile = sel_eq.get("profile", {})

                p1 = float(payoffs.get("H001", 0.0))
                p2 = float(payoffs.get("H002", 0.0))
                p3 = float(payoffs.get("H003", 0.0))
                p_sum = p1 + p2 + p3

                # Accounting residual
                residual = abs(p_sum - welf)
                strategy_stats[s_id]["max_hourly_accounting_residual"] = max(
                    strategy_stats[s_id]["max_hourly_accounting_residual"], residual
                )

                strategy_stats[s_id]["total_volume_kwh"] += vol
                strategy_stats[s_id]["total_welfare_aud"] += welf
                strategy_stats[s_id]["H001_benefit_aud"] += p1
                strategy_stats[s_id]["H002_benefit_aud"] += p2
                strategy_stats[s_id]["H003_benefit_aud"] += p3

                seller_benefit = sum(float(payoffs.get(s, 0.0)) for s in sellers)
                buyer_benefit = sum(float(payoffs.get(b, 0.0)) for b in buyers)
                strategy_stats[s_id]["total_seller_benefit_aud"] += seller_benefit
                strategy_stats[s_id]["total_buyer_benefit_aud"] += buyer_benefit

                if p_vwap is not None and vol > tolerance:
                    strategy_stats[s_id]["price_volume_numerator"] += float(p_vwap) * vol

                # Concordance with Strategy A
                if strat_a_profile is not None and profile == strat_a_profile:
                    strategy_stats[s_id]["hours_match_strategy_a"] += 1

                # Fairness metrics
                if is_mixed:
                    summary = compute_fairness_summary(payoffs, active_players, tolerance=tolerance, epsilon=epsilon)
                    g_std = summary["standard_gini"]
                    g_norm = summary["normalized_gini"]
                    u_min = summary["max_min_benefit_aud"]
                    u_max = summary["max_benefit_aud"]
                    u_range = summary["benefit_range_aud"]

                    if g_std is not None:
                        strategy_stats[s_id]["mixed_gini_std_list"].append(g_std)
                        strategy_stats[s_id]["mixed_gini_norm_list"].append(g_norm)
                    if u_min is not None:
                        strategy_stats[s_id]["mixed_min_benefit_list"].append(u_min)
                        strategy_stats[s_id]["mixed_max_benefit_list"].append(u_max)
                        strategy_stats[s_id]["mixed_range_list"].append(u_range)
                else:
                    g_std, g_norm, u_min, u_max, u_range = None, None, None, None, None

                # Record in hourly export dataframe (only for core strategies to keep CSV concise)
                if s_def["type"] == "core":
                    k = s_def["key"]
                    row[f"{k}_price_profile"] = str(profile)
                    row[f"{k}_vwap_aud"] = p_vwap
                    row[f"{k}_volume_kwh"] = vol
                    row[f"{k}_welfare_aud"] = welf
                    row[f"{k}_H001_payoff"] = p1
                    row[f"{k}_H002_payoff"] = p2
                    row[f"{k}_H003_payoff"] = p3
                    row[f"{k}_standard_gini"] = g_std
                    row[f"{k}_normalized_gini"] = g_norm
                    row[f"{k}_min_benefit"] = u_min

        hourly_rows.append(row)

    df_hourly_selection = pd.DataFrame(hourly_rows)

    # Build comparison summary table
    comp_rows: List[Dict[str, Any]] = []
    for s_def in strategy_definitions:
        s_id = s_def["id"]
        stat = strategy_stats[s_id]

        tot_vol = stat["total_volume_kwh"]
        tot_welf = stat["total_welfare_aud"]
        vwap = (stat["price_volume_numerator"] / tot_vol) if tot_vol > tolerance else None

        h1 = stat["H001_benefit_aud"]
        h2 = stat["H002_benefit_aud"]
        h3 = stat["H003_benefit_aud"]
        sum_payoffs = h1 + h2 + h3

        h1_share = (h1 / tot_welf * 100.0) if tot_welf > tolerance else 0.0
        h2_share = (h2 / tot_welf * 100.0) if tot_welf > tolerance else 0.0
        h3_share = (h3 / tot_welf * 100.0) if tot_welf > tolerance else 0.0

        mean_g_std = float(np.mean(stat["mixed_gini_std_list"])) if stat["mixed_gini_std_list"] else None
        mean_g_norm = float(np.mean(stat["mixed_gini_norm_list"])) if stat["mixed_gini_norm_list"] else None
        mean_min_u = float(np.mean(stat["mixed_min_benefit_list"])) if stat["mixed_min_benefit_list"] else None
        mean_max_u = float(np.mean(stat["mixed_max_benefit_list"])) if stat["mixed_max_benefit_list"] else None
        mean_range = float(np.mean(stat["mixed_range_list"])) if stat["mixed_range_list"] else None

        match_pct = (stat["hours_match_strategy_a"] / total_hours) * 100.0
        agg_residual = abs(sum_payoffs - tot_welf)

        comp_rows.append({
            "strategy_id": s_id,
            "strategy_name": stat["name"],
            "strategy_type": stat["type"],
            "total_p2p_volume_kwh": tot_vol,
            "total_community_welfare_aud": tot_welf,
            "volume_weighted_price_aud_per_kwh": vwap,
            "total_seller_benefit_aud": stat["total_seller_benefit_aud"],
            "total_buyer_benefit_aud": stat["total_buyer_benefit_aud"],
            "H001_benefit_aud": h1,
            "H002_benefit_aud": h2,
            "H003_benefit_aud": h3,
            "H001_benefit_share_pct": h1_share,
            "H002_benefit_share_pct": h2_share,
            "H003_benefit_share_pct": h3_share,
            "mean_standard_gini_mixed": mean_g_std,
            "mean_normalized_gini_mixed": mean_g_norm,
            "mean_min_active_benefit_aud": mean_min_u,
            "mean_max_active_benefit_aud": mean_max_u,
            "mean_benefit_range_aud": mean_range,
            "concordance_with_strategy_a_pct": match_pct,
            "hours_identical_to_strategy_a": stat["hours_match_strategy_a"],
            "max_hourly_accounting_residual_aud": stat["max_hourly_accounting_residual"],
            "aggregate_welfare_residual_aud": agg_residual,
            "runtime_ms": stat["execution_time_ms"],
        })

    df_strategy_comparison = pd.DataFrame(comp_rows)

    summary_dict = {
        "total_evaluated_hours": total_hours,
        "total_runtime_sec": time.time() - t0_all,
        "strategies_evaluated": len(strategy_definitions),
    }

    return df_hourly_selection, df_strategy_comparison, summary_dict


def generate_phase8d_visualizations(
    df_hourly: pd.DataFrame,
    df_comp: pd.DataFrame,
    output_dir: Path = DEFAULT_VIS_DIR,
) -> List[Path]:
    """Generate all seven required publication-grade visual charts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_charts: List[Path] = []

    # Filter to core strategies for main plots
    core_comp = df_comp[df_comp["strategy_type"] == "core"].copy()

    # 1. Household Benefit Comparison Across Strategies
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(core_comp))
    width = 0.25

    ax.bar(x - width, core_comp["H001_benefit_aud"], width, label="H001 Benefit ($ AUD)", color="#1f77b4")
    ax.bar(x, core_comp["H002_benefit_aud"], width, label="H002 Benefit ($ AUD)", color="#ff7f0e")
    ax.bar(x + width, core_comp["H003_benefit_aud"], width, label="H003 Benefit ($ AUD)", color="#2ca02c")

    ax.set_ylabel("Total Realized Benefit (AUD)")
    ax.set_title("Household Economic Benefit Allocation Across Selection Strategies (1,752 Hours)")
    ax.set_xticks(x)
    ax.set_xticklabels([name.split(":")[0] for name in core_comp["strategy_name"]], rotation=15)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()
    chart1 = output_dir / "household_benefit_comparison.png"
    plt.savefig(chart1, dpi=300)
    plt.close()
    generated_charts.append(chart1)

    # 2. Gini Coefficient Comparison (Standard vs Normalized)
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(core_comp))
    width = 0.35

    ax.bar(x - width/2, core_comp["mean_standard_gini_mixed"], width, label="Standard Gini G in [0, 2/3]", color="#4a7ebb")
    ax.bar(x + width/2, core_comp["mean_normalized_gini_mixed"], width, label="Normalized Gini G_norm in [0, 1]", color="#d95f02")

    ax.set_ylabel("Inequality Metric")
    ax.set_title("Mean Gini Inequality Coefficient (Across 866 Mixed-Market Trading Hours)")
    ax.set_xticks(x)
    ax.set_xticklabels([name.split(":")[0] for name in core_comp["strategy_name"]], rotation=15)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()
    chart2 = output_dir / "gini_coefficient_comparison.png"
    plt.savefig(chart2, dpi=300)
    plt.close()
    generated_charts.append(chart2)

    # 3. Total Welfare vs Fairness Trade-off
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(core_comp["mean_normalized_gini_mixed"], core_comp["total_community_welfare_aud"], color="#2b83ba", s=120, zorder=5)

    for _, r in core_comp.iterrows():
        ax.annotate(
            r["strategy_name"].split(":")[0],
            (r["mean_normalized_gini_mixed"], r["total_community_welfare_aud"]),
            xytext=(5, 5), textcoords="offset points", fontsize=9, weight="bold"
        )

    ax.set_xlabel("Mean Normalized Gini Inequality (G_norm)")
    ax.set_ylabel("Total Community Welfare (AUD)")
    ax.set_title("Community Welfare Invariance vs. Distributional Fairness Trade-off")
    ax.set_ylim(26.7540, 26.7550)
    ax.grid(True, linestyle="--", alpha=0.7)
    plt.tight_layout()
    chart3 = output_dir / "welfare_vs_fairness_tradeoff.png"
    plt.savefig(chart3, dpi=300)
    plt.close()
    generated_charts.append(chart3)

    # 4. Volume-Weighted Average Transaction Price (VWAP)
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(
        [name.split(":")[0] for name in core_comp["strategy_name"]],
        core_comp["volume_weighted_price_aud_per_kwh"],
        color=["#2b83ba", "#d7191c", "#1a9641", "#fdae61", "#abd9e9", "#7570b3"]
    )
    ax.axhline(0.19, color="black", linestyle="--", label="Mid-market Reference ($0.19/kWh)")
    ax.axhline(0.30, color="gray", linestyle=":", label="Import Tariff Ceiling ($0.30/kWh)")
    ax.axhline(0.08, color="gray", linestyle=":", label="Export Credit Floor ($0.08/kWh)")
    ax.set_ylabel("VWAP (AUD/kWh)")
    ax.set_title("Volume-Weighted Average Transaction Price Across Selection Strategies")
    ax.legend(loc="lower right")
    ax.grid(axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()
    chart4 = output_dir / "transaction_price_distributions.png"
    plt.savefig(chart4, dpi=300)
    plt.close()
    generated_charts.append(chart4)

    # 5. Household Benefit-Share Distributions (Stacked Bar)
    fig, ax = plt.subplots(figsize=(9, 5))
    names = [name.split(":")[0] for name in core_comp["strategy_name"]]
    s1 = core_comp["H001_benefit_share_pct"].values
    s2 = core_comp["H002_benefit_share_pct"].values
    s3 = core_comp["H003_benefit_share_pct"].values

    ax.bar(names, s1, label="H001 Share (%)", color="#1f77b4")
    ax.bar(names, s2, bottom=s1, label="H002 Share (%)", color="#ff7f0e")
    ax.bar(names, s3, bottom=s1 + s2, label="H003 Share (%)", color="#2ca02c")

    ax.set_ylabel("Share of Total Community Welfare (%)")
    ax.set_title("Community Surplus Allocation Shares by Household")
    ax.set_ylim(0, 100)
    ax.legend(loc="upper right")
    ax.grid(axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()
    chart5 = output_dir / "benefit_share_distributions.png"
    plt.savefig(chart5, dpi=300)
    plt.close()
    generated_charts.append(chart5)

    # 6. Hourly Fairness vs Welfare Scatter (Mixed Trading Hours)
    mixed_df = df_hourly[df_hourly["is_mixed_market"]].copy()
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(
        mixed_df["strat_a_normalized_gini"],
        mixed_df["strat_a_welfare_aud"],
        alpha=0.4, color="#1f77b4", label="Strategy A (Reference)"
    )
    ax.scatter(
        mixed_df["strat_d_normalized_gini"] if "strat_d_normalized_gini" in mixed_df.columns else mixed_df["strat_a_normalized_gini"],
        mixed_df["strat_a_welfare_aud"],
        alpha=0.4, color="#2ca02c", label="Strategy D (Max-Min)"
    )
    ax.set_xlabel("Hourly Normalized Gini (G_norm)")
    ax.set_ylabel("Hourly Community Welfare (AUD)")
    ax.set_title("Distribution of Hourly Welfare vs Normalized Inequality in Mixed Hours")
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.7)
    plt.tight_layout()
    chart6 = output_dir / "fairness_vs_welfare_scatter.png"
    plt.savefig(chart6, dpi=300)
    plt.close()
    generated_charts.append(chart6)

    # 7. Hourly Price Comparison for Representative Mixed-Market Day
    # Sample a representative active day (e.g. 24 hours of 2013-05-01)
    day_df = df_hourly[df_hourly["timestamp"].str.startswith("2013-05-01")].copy()
    if not day_df.empty:
        fig, ax = plt.subplots(figsize=(10, 5))
        hours = np.arange(len(day_df))
        ax.plot(hours, day_df["strat_a_vwap_aud"], marker="o", label="Strategy A (Reference)", color="#1f77b4")
        ax.plot(hours, day_df["strat_b_vwap_aud"], marker="s", label="Strategy B (Seller+)", color="#d7191c", linestyle=":")
        ax.plot(hours, day_df["strat_c_vwap_aud"], marker="^", label="Strategy C (Buyer+)", color="#1a9641", linestyle=":")
        ax.axhline(0.19, color="black", linestyle="--", alpha=0.5, label="Benchmark ($0.19)")
        ax.set_xlabel("Hour of Day (2013-05-01)")
        ax.set_ylabel("Transaction Price (AUD/kWh)")
        ax.set_title("Hourly Cleared Transaction Prices Across Strategies (Sample Day)")
        ax.set_xticks(hours[::2])
        ax.set_xticklabels([f"{h}:00" for h in hours[::2]])
        ax.legend()
        ax.grid(True, linestyle="--", alpha=0.7)
        plt.tight_layout()
        chart7 = output_dir / "hourly_price_comparison.png"
        plt.savefig(chart7, dpi=300)
        plt.close()
        generated_charts.append(chart7)

    # 8. Hybrid Sensitivity Curve (w_fair sweep)
    sens_comp = df_comp[df_comp["strategy_id"].str.startswith("Hybrid_w_fair_")].copy()
    if not sens_comp.empty:
        # Extract weight float
        sens_comp["w_fair"] = sens_comp["strategy_id"].apply(lambda s: float(s.replace("Hybrid_w_fair_", "")))
        sens_comp.sort_values("w_fair", inplace=True)

        fig, ax1 = plt.subplots(figsize=(9, 5))
        color1 = "#1f77b4"
        ax1.set_xlabel("Fairness Weight (w_fair in Loss Function)")
        ax1.set_ylabel("Mean Normalized Gini (G_norm)", color=color1)
        ax1.plot(sens_comp["w_fair"], sens_comp["mean_normalized_gini_mixed"], marker="o", color=color1, linewidth=2)
        ax1.tick_params(axis="y", labelcolor=color1)

        ax2 = ax1.twinx()
        color2 = "#d95f02"
        ax2.set_ylabel("VWAP (AUD/kWh)", color=color2)
        ax2.plot(sens_comp["w_fair"], sens_comp["volume_weighted_price_aud_per_kwh"], marker="s", color=color2, linewidth=2, linestyle="--")
        ax2.tick_params(axis="y", labelcolor=color2)

        plt.title("Sensitivity of Market Fairness and VWAP to Hybrid Fairness Weight (w_fair)")
        ax1.grid(True, linestyle="--", alpha=0.7)
        plt.tight_layout()
        chart8 = output_dir / "hybrid_weight_sensitivity.png"
        plt.savefig(chart8, dpi=300)
        plt.close()
        generated_charts.append(chart8)

    return generated_charts


def save_phase8d_evaluation_outputs(
    df_hourly: pd.DataFrame,
    df_comp: pd.DataFrame,
    hourly_path: Path = DEFAULT_OUTPUT_HOURLY_PATH,
    comp_path: Path = DEFAULT_OUTPUT_STRATEGY_PATH,
    vis_dir: Path = DEFAULT_VIS_DIR,
) -> None:
    """Save all CSV evaluation outputs and generate visualization figures."""
    hourly_path.parent.mkdir(parents=True, exist_ok=True)
    comp_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Saving hourly selection data to {hourly_path}...")
    df_hourly.to_csv(hourly_path, index=False)

    print(f"Saving strategy comparison metrics to {comp_path}...")
    df_comp.to_csv(comp_path, index=False)

    print(f"Generating publication figures in {vis_dir}...")
    charts = generate_phase8d_visualizations(df_hourly, df_comp, output_dir=vis_dir)
    print(f"Generated {len(charts)} figures successfully.")


if __name__ == "__main__":
    print("=" * 80)
    print("Executing Phase 8D Dataset-Wide Equilibrium Selection Evaluation")
    print("=" * 80)
    df_h, df_c, summary = run_phase8d_evaluation()
    save_phase8d_evaluation_outputs(df_h, df_c)
    print("\nPhase 8D Evaluation Complete.")
    print(f"Evaluated {summary['total_evaluated_hours']} hours across {summary['strategies_evaluated']} strategy configurations in {summary['total_runtime_sec']:.2f}s.")

