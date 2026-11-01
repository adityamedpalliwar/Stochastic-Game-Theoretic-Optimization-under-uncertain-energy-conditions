"""Phase 9 Publication-Quality Visualizations.

Generates 7 publication-standard figures with explicit units, labels, titles,
and data source annotations:
1. Forecast Performance & Uncertainty Calibration (Demand & Solar)
2. Full-Horizon Hourly P2P Trading Volume (Deterministic vs. Stochastic)
3. Cumulative and Monthly Community Welfare Comparison
4. Household-Wise Incremental Payoff Distribution & Surplus Allocation
5. Pure Nash Equilibrium Multiplicity Distribution (Strict vs. Weak)
6. Zero-Trade Frequency & Market Participation by Hour-of-Day
7. Financial Accounting Verification & Exact Welfare Identity Validation
"""

from __future__ import annotations

from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path("D:/5thSem/GT project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions")
PHASE9_DIR = PROJECT_ROOT / "reports" / "phase9"

plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.titlesize": 14,
    "figure.dpi": 300,
})


def generate_all_plots() -> None:
    print("Generating Phase 9 publication-quality figures...")
    
    # Load generated datasets
    df_market = pd.read_csv(PHASE9_DIR / "full_horizon_market_metrics.csv")
    df_comp = pd.read_csv(PHASE9_DIR / "deterministic_vs_stochastic_comparison.csv")
    df_audit = pd.read_csv(PHASE9_DIR / "financial_consistency_audit.csv")
    df_intervals = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "test_interval_evaluations_row_level.csv")
    
    df_market["timestamp"] = pd.to_datetime(df_market["timestamp"])
    df_comp["timestamp"] = pd.to_datetime(df_comp["timestamp"])
    df_market["hour"] = df_market["timestamp"].dt.hour
    df_market["month"] = df_market["timestamp"].dt.month
    
    # -------------------------------------------------------------------------
    # PLOT 1: FORECAST ACCURACY & UNCERTAINTY CALIBRATION
    # -------------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    
    # Subplot 1: Demand Actual vs Predicted
    ax = axes[0]
    ax.scatter(df_intervals["actual_demand_kwh"], df_intervals["predicted_demand_kwh"], 
               alpha=0.25, color="#1f77b4", s=12, label="Hourly Predictions")
    max_d = max(df_intervals["actual_demand_kwh"].max(), df_intervals["predicted_demand_kwh"].max())
    ax.plot([0, max_d], [0, max_d], "r--", linewidth=1.8, label="Ideal 1:1 Parity")
    ax.set_title("Demand Forecasting Performance (Overall MAE = 0.466 kWh)")
    ax.set_xlabel("Actual Total Demand (kWh)")
    ax.set_ylabel("Predicted Total Demand (kWh)")
    ax.legend(loc="upper left")
    ax.set_xlim(0, max_d * 1.05)
    ax.set_ylim(0, max_d * 1.05)
    
    # Subplot 2: Solar Actual vs Predicted
    ax = axes[1]
    ax.scatter(df_intervals["actual_solar_kwh"], df_intervals["predicted_solar_kwh"], 
               alpha=0.25, color="#ff7f0e", s=12, label="Hourly Predictions")
    max_s = max(df_intervals["actual_solar_kwh"].max(), df_intervals["predicted_solar_kwh"].max())
    ax.plot([0, max_s], [0, max_s], "r--", linewidth=1.8, label="Ideal 1:1 Parity")
    ax.set_title("Solar Generation Forecasting Performance (Overall MAE = 0.081 kWh)")
    ax.set_xlabel("Actual Solar Generation (kWh)")
    ax.set_ylabel("Predicted Solar Generation (kWh)")
    ax.legend(loc="upper left")
    ax.set_xlim(0, max_s * 1.05)
    ax.set_ylim(0, max_s * 1.05)
    
    fig.suptitle("Deliverable 1: LSTM Energy Forecast Validation Across 5,256 Observations", y=1.02)
    fig.tight_layout()
    fig.savefig(PHASE9_DIR / "plot1_forecast_validation.png", bbox_inches="tight")
    plt.close(fig)
    print("Saved plot1_forecast_validation.png")

    # -------------------------------------------------------------------------
    # PLOT 2: HOURLY P2P TRADING VOLUME (DETERMINISTIC VS STOCHASTIC)
    # -------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(df_comp["timestamp"], df_comp["deterministic_volume_kwh"], 
            color="#2ca02c", alpha=0.7, linewidth=1.2, label="Phase 8C Deterministic Ex-Post Volume (kWh)")
    ax.plot(df_comp["timestamp"], df_comp["stochastic_volume_kwh"], 
            color="#d62728", alpha=0.85, linewidth=1.2, linestyle="--", label="Phase 8E Stochastic Expected Volume (kWh)")
    ax.set_title("Full-Horizon Hourly P2P Trading Volume Comparison (1,752 Hours)")
    ax.set_xlabel("Evaluation Timestamp (2013-04-19 to 2013-06-30)")
    ax.set_ylabel("Cleared Trading Volume (kWh / hour)")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(PHASE9_DIR / "plot2_hourly_volume_comparison.png", bbox_inches="tight")
    plt.close(fig)
    print("Saved plot2_hourly_volume_comparison.png")

    # -------------------------------------------------------------------------
    # PLOT 3: COMMUNITY WELFARE COMPARISON
    # -------------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Cumulative welfare
    ax = axes[0]
    cum_w_det = np.cumsum(df_comp["deterministic_welfare_aud"])
    cum_w_stoch = np.cumsum(df_comp["stochastic_welfare_aud"])
    ax.plot(df_comp["timestamp"], cum_w_det, color="#2ca02c", linewidth=2.0, label="Phase 8C Deterministic ($26.75 AUD)")
    ax.plot(df_comp["timestamp"], cum_w_stoch, color="#1f77b4", linewidth=2.0, linestyle="--", label="Phase 8E Stochastic Expected")
    ax.set_title("Cumulative Community Economic Welfare (AUD)")
    ax.set_xlabel("Evaluation Date")
    ax.set_ylabel("Cumulative Welfare (AUD)")
    ax.legend(loc="upper left")
    
    # Monthly welfare bars
    ax = axes[1]
    months = ["April", "May", "June"]
    m_det = [df_comp[df_comp["timestamp"].dt.month == m]["deterministic_welfare_aud"].sum() for m in [4, 5, 6]]
    m_stoch = [df_comp[df_comp["timestamp"].dt.month == m]["stochastic_welfare_aud"].sum() for m in [4, 5, 6]]
    x = np.arange(len(months))
    width = 0.35
    ax.bar(x - width/2, m_det, width, label="Deterministic Ex-Post", color="#2ca02c", alpha=0.85)
    ax.bar(x + width/2, m_stoch, width, label="Stochastic Expected", color="#1f77b4", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(months)
    ax.set_title("Monthly Community Welfare Breakdown")
    ax.set_ylabel("Community Welfare (AUD)")
    ax.legend(loc="upper right")
    
    fig.suptitle("Community Economic Welfare Gain (P2P Spread: $0.22/kWh)", y=1.02)
    fig.tight_layout()
    fig.savefig(PHASE9_DIR / "plot3_welfare_comparison.png", bbox_inches="tight")
    plt.close(fig)
    print("Saved plot3_welfare_comparison.png")

    # -------------------------------------------------------------------------
    # PLOT 4: HOUSEHOLD-WISE INCREMENTAL BENEFITS
    # -------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 5.5))
    h_labels = ["H001", "H002", "H003"]
    det_payoffs = [
        float(pd.read_csv(PROJECT_ROOT / "reports" / "phase8c_hourly_equilibria.csv")["H001_payoff_aud"].sum()),
        float(pd.read_csv(PROJECT_ROOT / "reports" / "phase8c_hourly_equilibria.csv")["H002_payoff_aud"].sum()),
        float(pd.read_csv(PROJECT_ROOT / "reports" / "phase8c_hourly_equilibria.csv")["H003_payoff_aud"].sum()),
    ]
    stoch_payoffs = [
        float(df_market["stochastic_H001_payoff_aud"].sum()),
        float(df_market["stochastic_H002_payoff_aud"].sum()),
        float(df_market["stochastic_H003_payoff_aud"].sum()),
    ]
    x = np.arange(len(h_labels))
    width = 0.35
    b1 = ax.bar(x - width/2, det_payoffs, width, label="Deterministic Ex-Post (Phase 8C)", color="#2ca02c", alpha=0.85)
    b2 = ax.bar(x + width/2, stoch_payoffs, width, label="Stochastic Expected (Phase 8E)", color="#1f77b4", alpha=0.85)
    
    for bar in b1:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.15, f"${yval:.2f}", ha="center", va="bottom", fontsize=9)
    for bar in b2:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.15, f"${yval:.2f}", ha="center", va="bottom", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(h_labels)
    ax.set_ylabel("Total Incremental Payoff (AUD)")
    ax.set_title("Household Incremental Benefits Allocation Across Full Evaluation Horizon")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(PHASE9_DIR / "plot4_household_benefits.png", bbox_inches="tight")
    plt.close(fig)
    print("Saved plot4_household_benefits.png")

    # -------------------------------------------------------------------------
    # PLOT 5: PNE MULTIPLICITY DISTRIBUTION
    # -------------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Subplot 1: Distribution in Active Trading Hours
    ax = axes[0]
    active_mask = (df_market["stochastic_expected_volume_kwh"] > 1e-6)
    pne_active = df_market[active_mask]["stochastic_num_pne"]
    ax.hist(pne_active, bins=np.arange(0, 30, 1) - 0.5, color="#1f77b4", edgecolor="black", alpha=0.8)
    ax.set_title(f"PNE Multiplicity in Tradeable Hours (N={active_mask.sum()})")
    ax.set_xlabel("Number of Pure Nash Equilibria per Hour")
    ax.set_ylabel("Frequency (Hours)")
    
    # Subplot 2: Strict vs Weak PNE
    ax = axes[1]
    strict_tot = int(df_market["stochastic_strict_pne"].sum())
    weak_tot = int(df_market["stochastic_weak_pne"].sum())
    ax.bar(["Strict PNE\n(Unilateral Deviation Strictly Worse)", "Weak PNE\n(Supported by Indifference)"], 
           [strict_tot, weak_tot], color=["#2ca02c", "#ff7f0e"], width=0.5, edgecolor="black", alpha=0.85)
    for i, v in enumerate([strict_tot, weak_tot]):
        ax.text(i, v + max(strict_tot, weak_tot) * 0.02, f"{v:,} ({v/(strict_tot+weak_tot)*100:.1f}%)", 
                ha="center", fontsize=10, weight="bold")
    ax.set_title("Stochastic Pure Nash Equilibrium Classification")
    ax.set_ylabel("Total Equilibria Detected")
    
    fig.suptitle("Strategic Equilibrium Structure Across Full 1,752 Hours", y=1.02)
    fig.tight_layout()
    fig.savefig(PHASE9_DIR / "plot5_equilibrium_multiplicity.png", bbox_inches="tight")
    plt.close(fig)
    print("Saved plot5_equilibrium_multiplicity.png")

    # -------------------------------------------------------------------------
    # PLOT 6: ZERO-TRADE FREQUENCY BY HOUR-OF-DAY
    # -------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(12, 5))
    hourly_zero = []
    hourly_det_zero = []
    hours = list(range(24))
    
    for h in hours:
        sub_h = df_market[df_market["hour"] == h]
        hourly_zero.append((sub_h["stochastic_expected_volume_kwh"] <= 1e-6).mean() * 100.0)
        hourly_det_zero.append((sub_h["deterministic_traded_volume_kwh"] <= 1e-6).mean() * 100.0)
        
    x = np.arange(24)
    width = 0.4
    ax.bar(x - width/2, hourly_det_zero, width, label="Deterministic Ex-Post Zero-Trade %", color="#2ca02c", alpha=0.75)
    ax.bar(x + width/2, hourly_zero, width, label="Stochastic Ex-Ante Zero-Trade %", color="#d62728", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{h:02d}:00" for h in hours], rotation=45)
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Zero-Trade Frequency (%)")
    ax.set_title("Zero-Trade Frequency Across the Diurnal Cycle (Deterministic vs. Stochastic)")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(PHASE9_DIR / "plot6_diurnal_zero_trade.png", bbox_inches="tight")
    plt.close(fig)
    print("Saved plot6_diurnal_zero_trade.png")

    # -------------------------------------------------------------------------
    # PLOT 7: FINANCIAL AUDIT IDENTITY VERIFICATION
    # -------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.scatter(df_audit["stochastic_traded_volume_kwh"], df_audit["cleared_community_welfare_aud"], 
               color="#1f77b4", alpha=0.6, s=16, label="Cleared Market Outcomes")
    v_max = df_audit["stochastic_traded_volume_kwh"].max()
    ax.plot([0, v_max], [0, 0.22 * v_max], "r--", linewidth=2.0, label="Exact Identity: Welfare = $0.22 × Volume")
    ax.set_title("Financial Identity Verification: Community Welfare vs. Traded Volume")
    ax.set_xlabel("Stochastic Expected Traded Volume (kWh)")
    ax.set_ylabel("Stochastic Expected Community Welfare (AUD)")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(PHASE9_DIR / "plot7_financial_identity.png", bbox_inches="tight")
    plt.close(fig)
    print("Saved plot7_financial_identity.png")

    print("All 7 publication-quality figures successfully generated!")

if __name__ == "__main__":
    generate_all_plots()

