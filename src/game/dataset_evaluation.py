"""Phase 8C.1: Dataset-Wide Deterministic Nash Equilibrium Evaluation.

Executes exhaustive deterministic price-only Nash equilibrium solving across all
1,752 hourly observations of the accepted Phase 7.1 held-out test dataset
(Stochastic MPC physical battery dispatch baseline).
"""

from __future__ import annotations

import gzip
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.game.strategic_market import (
    DEFAULT_GRID_EXPORT_CREDIT_AUD,
    DEFAULT_GRID_IMPORT_TARIFF_AUD,
    DEFAULT_NUMERICAL_TOLERANCE,
    STRATEGIC_PRICE_GRID,
    MarketRole,
)
from src.game.strategic_solver import (
    NashEquilibriumRecord,
    SolverStatus,
    StrategicGameResult,
    solve_deterministic_nash_equilibrium,
)


def load_phase7_hourly_data(
    csv_path: Union[str, Path] = "reports/phase7_hourly_records.csv",
    controller: str = "Stochastic_MPC",
    enable_p2p: bool = True,
) -> pd.DataFrame:
    """Load and validate authoritative Phase 7.1 hourly test dataset.

    Parameters
    ----------
    csv_path : Union[str, Path]
        Path to Phase 7 hourly records CSV.
    controller : str
        Controller name to filter (default 'Stochastic_MPC').
    enable_p2p : bool
        Whether to select P2P-enabled simulation records (default True).

    Returns
    -------
    pd.DataFrame
        Filtered DataFrame with 5,256 records (1,752 hours * 3 households).
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Phase 7 records not found at {path}")

    df = pd.read_csv(path)
    sub = df[(df["controller"] == controller) & (df["enable_p2p"] == enable_p2p)].copy()

    # Validate 1,752 timestamps and 3 households
    unique_ts = sub["timestamp"].nunique()
    if unique_ts != 1752:
        raise ValueError(f"Expected exactly 1,752 timestamps, got {unique_ts}")

    if len(sub) != 5256:
        raise ValueError(f"Expected exactly 5,256 rows, got {len(sub)}")

    # Sort deterministically
    sub.sort_values(by=["timestamp", "house_id"], inplace=True)
    return sub


def run_phase8c_dataset_evaluation(
    source_df: pd.DataFrame,
    all_households: Sequence[str] = ("H001", "H002", "H003"),
    grid_import_tariff_aud: float = DEFAULT_GRID_IMPORT_TARIFF_AUD,
    grid_export_credit_aud: float = DEFAULT_GRID_EXPORT_CREDIT_AUD,
    price_grid: Sequence[float] = STRATEGIC_PRICE_GRID,
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
    reference_price_aud: float = 0.19,
    verbose_interval: Optional[int] = 250,
) -> Tuple[pd.DataFrame, List[Dict[str, Any]], Dict[str, Any]]:
    """Execute Phase 8C Nash equilibrium solver across all 1,752 hourly timestamps.

    Parameters
    ----------
    source_df : pd.DataFrame
        Authoritative Phase 7.1 dataset records.
    all_households : Sequence[str]
        Universe of households.
    grid_import_tariff_aud : float
        Grid retail import tariff ($0.30/kWh).
    grid_export_credit_aud : float
        Solar export feed-in credit ($0.08/kWh).
    price_grid : Sequence[float]
        Admissible strategic price grid.
    tolerance : float
        Numerical tolerance.
    reference_price_aud : float
        Reference price for representative selection ($0.19/kWh).
    verbose_interval : Optional[int]
        Print progress every N timestamps (if not None).

    Returns
    -------
    Tuple[pd.DataFrame, List[Dict[str, Any]], Dict[str, Any]]
        (hourly_results_df, all_equilibria_list, aggregate_metrics_dict)
    """
    # Pre-pivot surplus and deficit for fast dictionary extraction
    piv_s = source_df.pivot(index="timestamp", columns="house_id", values="post_battery_surplus_kwh")
    piv_d = source_df.pivot(index="timestamp", columns="house_id", values="post_battery_deficit_kwh")

    s_dicts = piv_s.to_dict(orient="index")
    d_dicts = piv_d.to_dict(orient="index")
    timestamps = list(piv_s.index)

    rows: List[Dict[str, Any]] = []
    all_equilibria_data: List[Dict[str, Any]] = []

    t0 = time.time()
    for idx, ts in enumerate(timestamps):
        surps = s_dicts[ts]
        defcs = d_dicts[ts]

        # Determine roles for output record
        roles = {}
        for hid in all_households:
            s_val = surps.get(hid, 0.0)
            d_val = defcs.get(hid, 0.0)
            if s_val > tolerance:
                roles[hid] = "seller"
            elif d_val > tolerance:
                roles[hid] = "buyer"
            else:
                roles[hid] = "inactive"

        # Solve Nash equilibrium
        res: StrategicGameResult = solve_deterministic_nash_equilibrium(
            surpluses_kwh=surps,
            deficits_kwh=defcs,
            all_households=all_households,
            grid_import_tariff_aud=grid_import_tariff_aud,
            grid_export_credit_aud=grid_export_credit_aud,
            price_grid=price_grid,
            tolerance=tolerance,
            reference_price_aud=reference_price_aud,
        )

        sel = res.selected_equilibrium
        sel_profile = sel.profile if sel else None
        sel_payoffs = sel.payoffs if sel else {hid: 0.0 for hid in all_households}

        row: Dict[str, Any] = {
            "timestamp": ts,
            "H001_surplus_kwh": surps.get("H001", 0.0),
            "H002_surplus_kwh": surps.get("H002", 0.0),
            "H003_surplus_kwh": surps.get("H003", 0.0),
            "H001_deficit_kwh": defcs.get("H001", 0.0),
            "H002_deficit_kwh": defcs.get("H002", 0.0),
            "H003_deficit_kwh": defcs.get("H003", 0.0),
            "H001_role": roles.get("H001", "inactive"),
            "H002_role": roles.get("H002", "inactive"),
            "H003_role": roles.get("H003", "inactive"),
            "num_active_players": len(res.active_sellers) + len(res.active_buyers),
            "num_active_sellers": len(res.active_sellers),
            "num_active_buyers": len(res.active_buyers),
            "num_inactive_households": len(res.inactive_households),
            "num_profiles_evaluated": res.num_profiles_evaluated,
            "num_deviations_evaluated": res.num_deviations_evaluated,
            "num_pne": res.num_equilibria,
            "num_strict_pne": res.num_strict,
            "num_weak_pne": res.num_weak,
            "num_pareto_undominated_pne": res.num_pareto_undominated,
            "no_pne_status": (res.num_equilibria == 0),
            "selected_price_profile": json.dumps(sel_profile) if sel_profile else None,
            "H001_selected_price_aud": sel_profile.get("H001") if sel_profile else None,
            "H002_selected_price_aud": sel_profile.get("H002") if sel_profile else None,
            "H003_selected_price_aud": sel_profile.get("H003") if sel_profile else None,
            "selected_payoff_vector": json.dumps(sel_payoffs),
            "H001_payoff_aud": sel_payoffs.get("H001", 0.0),
            "H002_payoff_aud": sel_payoffs.get("H002", 0.0),
            "H003_payoff_aud": sel_payoffs.get("H003", 0.0),
            "selected_traded_volume_kwh": sel.total_traded_kwh if sel else 0.0,
            "selected_weighted_average_price_aud": sel.weighted_average_price_aud if sel else None,
            "selected_community_welfare_aud": sel.community_welfare_aud if sel else 0.0,
            "selected_num_transactions": sel.num_transactions if sel else 0,
        }
        rows.append(row)

        # Store complete equilibrium details for hour
        hour_eqs = [eq.to_dict() for eq in res.equilibria]
        all_equilibria_data.append({
            "timestamp": ts,
            "status": res.status,
            "num_equilibria": res.num_equilibria,
            "equilibria": hour_eqs,
        })

        if verbose_interval and (idx + 1) % verbose_interval == 0:
            elapsed = time.time() - t0
            print(f"[{idx + 1}/{len(timestamps)}] Evaluated in {elapsed:.1f}s")

    df_out = pd.DataFrame(rows)

    # Compute aggregate metrics
    agg_metrics = compute_dataset_aggregate_metrics(df_out)
    return df_out, all_equilibria_data, agg_metrics


def compute_dataset_aggregate_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute comprehensive statistical and economic summary across all evaluated hours.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame of hourly equilibrium results.

    Returns
    -------
    Dict[str, Any]
        Aggregated participation, equilibrium, and welfare metrics.
    """
    total_hours = len(df)
    trading_hours_mask = df["selected_traded_volume_kwh"] > 1e-6
    num_trading_hours = int(trading_hours_mask.sum())

    # Participation breakdowns
    active_player_counts = df["num_active_players"].value_counts().to_dict()
    hours_0_active = int(active_player_counts.get(0, 0))
    hours_1_active = int(active_player_counts.get(1, 0))
    hours_2_active = int(active_player_counts.get(2, 0))
    hours_3_active = int(active_player_counts.get(3, 0))

    mixed_mask = (df["num_active_sellers"] > 0) & (df["num_active_buyers"] > 0)
    seller_only_mask = (df["num_active_sellers"] > 0) & (df["num_active_buyers"] == 0)
    buyer_only_mask = (df["num_active_sellers"] == 0) & (df["num_active_buyers"] > 0)
    no_active_mask = (df["num_active_sellers"] == 0) & (df["num_active_buyers"] == 0)

    num_mixed_hours = int(mixed_mask.sum())
    num_seller_only_hours = int(seller_only_mask.sum())
    num_buyer_only_hours = int(buyer_only_mask.sum())
    num_no_active_hours = int(no_active_mask.sum())

    # Equilibrium counts
    hours_with_pne = int((df["num_pne"] > 0).sum())
    hours_with_no_pne = int((df["num_pne"] == 0).sum())
    hours_multiple_pareto = int((df["num_pareto_undominated_pne"] > 1).sum())

    total_pne_found = int(df["num_pne"].sum())
    total_strict_pne = int(df["num_strict_pne"].sum())
    total_weak_pne = int(df["num_weak_pne"].sum())

    pne_per_hour = df["num_pne"]
    pne_min = int(pne_per_hour.min())
    pne_median = float(pne_per_hour.median())
    pne_max = int(pne_per_hour.max())
    pne_mean = float(pne_per_hour.mean())

    # Strategic Market Outcomes
    agg_traded_volume_kwh = float(df["selected_traded_volume_kwh"].sum())
    avg_volume_per_trading_hour_kwh = (
        agg_traded_volume_kwh / num_trading_hours if num_trading_hours > 0 else 0.0
    )
    avg_volume_per_calendar_hour_kwh = agg_traded_volume_kwh / total_hours

    # Volume-weighted average transaction price
    valid_price_mask = trading_hours_mask & df["selected_weighted_average_price_aud"].notna()
    if agg_traded_volume_kwh > 1e-6:
        vwap_aud = float(
            (
                df.loc[valid_price_mask, "selected_traded_volume_kwh"]
                * df.loc[valid_price_mask, "selected_weighted_average_price_aud"]
            ).sum()
            / agg_traded_volume_kwh
        )
    else:
        vwap_aud = None

    agg_community_welfare_aud = float(df["selected_community_welfare_aud"].sum())

    h001_benefit_aud = float(df["H001_payoff_aud"].sum())
    h002_benefit_aud = float(df["H002_payoff_aud"].sum())
    h003_benefit_aud = float(df["H003_payoff_aud"].sum())

    # Distribution of representative equilibrium prices across trading hours
    price_series = df.loc[trading_hours_mask, "selected_weighted_average_price_aud"].dropna()
    price_stats = {
        "mean": float(price_series.mean()) if not price_series.empty else None,
        "std": float(price_series.std()) if not price_series.empty else None,
        "min": float(price_series.min()) if not price_series.empty else None,
        "q25": float(price_series.quantile(0.25)) if not price_series.empty else None,
        "median": float(price_series.median()) if not price_series.empty else None,
        "q75": float(price_series.quantile(0.75)) if not price_series.empty else None,
        "max": float(price_series.max()) if not price_series.empty else None,
    }

    return {
        "total_hours": total_hours,
        "hours_0_active": hours_0_active,
        "hours_1_active": hours_1_active,
        "hours_2_active": hours_2_active,
        "hours_3_active": hours_3_active,
        "mixed_market_hours": num_mixed_hours,
        "seller_only_hours": num_seller_only_hours,
        "buyer_only_hours": num_buyer_only_hours,
        "no_active_hours": num_no_active_hours,
        "hours_with_pne": hours_with_pne,
        "hours_with_no_pne": hours_with_no_pne,
        "hours_multiple_pareto": hours_multiple_pareto,
        "total_pne_found": total_pne_found,
        "total_strict_pne": total_strict_pne,
        "total_weak_pne": total_weak_pne,
        "pne_per_hour_min": pne_min,
        "pne_per_hour_median": pne_median,
        "pne_per_hour_mean": pne_mean,
        "pne_per_hour_max": pne_max,
        "num_trading_hours": num_trading_hours,
        "agg_traded_volume_kwh": agg_traded_volume_kwh,
        "avg_volume_per_trading_hour_kwh": avg_volume_per_trading_hour_kwh,
        "avg_volume_per_calendar_hour_kwh": avg_volume_per_calendar_hour_kwh,
        "volume_weighted_average_price_aud": vwap_aud,
        "agg_community_welfare_aud": agg_community_welfare_aud,
        "h001_benefit_aud": h001_benefit_aud,
        "h002_benefit_aud": h002_benefit_aud,
        "h003_benefit_aud": h003_benefit_aud,
        "representative_price_distribution": price_stats,
    }


def save_dataset_evaluation_outputs(
    df: pd.DataFrame,
    all_equilibria: List[Dict[str, Any]],
    csv_path: Union[str, Path] = "reports/phase8c_hourly_equilibria.csv",
    json_path: Union[str, Path] = "reports/phase8c_all_equilibria.json.gz",
) -> None:
    """Save hourly equilibrium CSV and compressed JSON of all equilibrium details."""
    csv_p = Path(csv_path)
    csv_p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_p, index=False)

    json_p = Path(json_path)
    json_p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(json_p, "wt", encoding="utf-8") as f:
        json.dump(all_equilibria, f)


if __name__ == "__main__":
    print("Loading Phase 7.1 hourly dataset (Stochastic MPC)...")
    source_df = load_phase7_hourly_data()
    print(f"Loaded {len(source_df)} records across {source_df['timestamp'].nunique()} timestamps.")

    print("\nExecuting Phase 8C Dataset-Wide Nash Equilibrium Evaluation...")
    t0 = time.time()
    df_results, all_eqs, agg_metrics = run_phase8c_dataset_evaluation(
        source_df=source_df,
        verbose_interval=250,
    )
    t1 = time.time()
    print(f"\nExecution complete in {t1 - t0:.1f}s.")

    csv_out = "reports/phase8c_hourly_equilibria.csv"
    json_out = "reports/phase8c_all_equilibria.json.gz"
    print(f"Saving outputs to {csv_out} and {json_out}...")
    save_dataset_evaluation_outputs(df_results, all_eqs, csv_out, json_out)
    print("Saved successfully.")

    print("\nAggregate Evaluation Summary:")
    for k, v in agg_metrics.items():
        print(f"  {k}: {v}")

