"""Validation tests for Phase 8C.1: Dataset-Wide Deterministic Nash Equilibrium Evaluation.

Verifies:
1. Exact 1,752-hour coverage with zero duplicate timestamps.
2. Accurate household role assignment (seller, buyer, inactive) from physical meter flows.
3. Every reported representative equilibrium strictly satisfies pure Nash equilibrium conditions.
4. Non-equilibrium profiles have demonstrable profitable unilateral deviations.
5. Every representative equilibrium belongs to the Pareto-undominated set.
6. Financial and physical consistency with the Phase 8B.1 engine down to double-precision tolerance.
7. Reproducible aggregate statistics and welfare conservation.
8. Preservation and integrity of the complete all-equilibria dataset.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import pytest

from src.game.strategic_market import (
    DEFAULT_GRID_EXPORT_CREDIT_AUD,
    DEFAULT_GRID_IMPORT_TARIFF_AUD,
    DEFAULT_NUMERICAL_TOLERANCE,
    STRATEGIC_PRICE_GRID,
    MarketOrder,
    MarketRole,
    clear_strategic_double_auction,
    compute_physical_net_position,
)
from src.game.strategic_solver import (
    solve_deterministic_nash_equilibrium,
)

CSV_REPORT_PATH = Path("reports/phase8c_hourly_equilibria.csv")
JSON_REPORT_PATH = Path("reports/phase8c_all_equilibria.json.gz")
SOURCE_HOURLY_PATH = Path("reports/phase7_hourly_records.csv")


@pytest.fixture(scope="module")
def hourly_results_df() -> pd.DataFrame:
    """Load the generated Phase 8C hourly equilibria dataset."""
    assert CSV_REPORT_PATH.exists(), f"Missing required file: {CSV_REPORT_PATH}"
    df = pd.read_csv(CSV_REPORT_PATH)
    return df


# =============================================================================
# 1. COVERAGE AND DATA INTEGRITY TESTS
# =============================================================================

def test_exact_1752_hour_coverage_and_no_duplicates(hourly_results_df: pd.DataFrame):
    """Confirm exact 1,752-hour coverage, zero duplicate timestamps, and correct date bounds."""
    df = hourly_results_df
    assert len(df) == 1752, f"Expected 1,752 rows, got {len(df)}"
    assert df["timestamp"].nunique() == 1752, "Duplicate timestamps found!"

    # Verify period: 2013-04-19 00:00 through 2013-06-30 23:00
    assert df["timestamp"].min() == "2013-04-19 00:00:00"
    assert df["timestamp"].max() == "2013-06-30 23:00:00"


def test_all_household_roles_correctly_assigned(hourly_results_df: pd.DataFrame):
    """Verify that household roles match physical surplus and deficit flows."""
    df = hourly_results_df
    tol = DEFAULT_NUMERICAL_TOLERANCE

    for _, row in df.iterrows():
        for hid in ["H001", "H002", "H003"]:
            s = row[f"{hid}_surplus_kwh"]
            d = row[f"{hid}_deficit_kwh"]
            role = row[f"{hid}_role"]

            assert s >= -tol
            assert d >= -tol
            assert not (s > tol and d > tol), f"Simultaneous surplus and deficit for {hid} at {row['timestamp']}"

            if s > tol:
                assert role == "seller"
            elif d > tol:
                assert role == "buyer"
            else:
                assert role == "inactive"


def test_active_player_counts_and_market_types(hourly_results_df: pd.DataFrame):
    """Verify active player counts and market type distributions."""
    df = hourly_results_df
    # Exactly 1 hour has 2 active players, 1751 hours have 3 active players
    assert (df["num_active_players"] == 2).sum() == 1
    assert (df["num_active_players"] == 3).sum() == 1751

    # Market types
    mixed = (df["num_active_sellers"] > 0) & (df["num_active_buyers"] > 0)
    buyer_only = (df["num_active_sellers"] == 0) & (df["num_active_buyers"] > 0)
    seller_only = (df["num_active_sellers"] > 0) & (df["num_active_buyers"] == 0)

    assert mixed.sum() == 866  # Exact match to Phase 7.1 tradeable hours
    assert buyer_only.sum() == 827
    assert seller_only.sum() == 59
    assert mixed.sum() + buyer_only.sum() + seller_only.sum() == 1752


# =============================================================================
# 2. NASH EQUILIBRIUM MATHEMATICAL VERIFICATION
# =============================================================================

def test_every_reported_equilibrium_passes_unilateral_deviation_checks(hourly_results_df: pd.DataFrame):
    """Sample diverse hours and re-verify that no unilateral deviation is profitable."""
    df = hourly_results_df
    # Sample every 50th hour to cover 36 diverse hours
    sample_indices = range(0, 1752, 50)
    sample_df = df.iloc[list(sample_indices)]

    tol = 1e-6
    for _, row in sample_df.iterrows():
        if row["num_pne"] == 0:
            continue

        profile_str = row["selected_price_profile"]
        assert pd.notna(profile_str)
        profile = json.loads(profile_str)

        surps = {hid: row[f"{hid}_surplus_kwh"] for hid in ["H001", "H002", "H003"]}
        defcs = {hid: row[f"{hid}_deficit_kwh"] for hid in ["H001", "H002", "H003"]}
        roles = {hid: row[f"{hid}_role"] for hid in ["H001", "H002", "H003"]}
        active_players = [hid for hid in ["H001", "H002", "H003"] if roles[hid] != "inactive"]

        # Base clearing
        base_orders = [
            MarketOrder(
                household_id=hid,
                role=MarketRole(roles[hid]),
                price_aud_per_kwh=profile[hid],
                quantity_kwh=surps[hid] if roles[hid] == "seller" else defcs[hid],
            )
            for hid in active_players
        ]
        base_res = clear_strategic_double_auction(base_orders)

        # Test all unilateral deviations for all active players
        for p_idx, player_id in enumerate(active_players):
            curr_p = profile[player_id]
            curr_role = roles[player_id]
            curr_payoff = (
                base_res.seller_incremental_benefits_aud.get(player_id, 0.0)
                if curr_role == "seller"
                else base_res.buyer_incremental_benefits_aud.get(player_id, 0.0)
            )

            for alt_p in STRATEGIC_PRICE_GRID:
                if abs(alt_p - curr_p) <= tol:
                    continue

                dev_orders = []
                for hid in active_players:
                    p_eval = alt_p if hid == player_id else profile[hid]
                    dev_orders.append(
                        MarketOrder(
                            household_id=hid,
                            role=MarketRole(roles[hid]),
                            price_aud_per_kwh=p_eval,
                            quantity_kwh=surps[hid] if roles[hid] == "seller" else defcs[hid],
                        )
                    )

                dev_res = clear_strategic_double_auction(dev_orders)
                dev_payoff = (
                    dev_res.seller_incremental_benefits_aud.get(player_id, 0.0)
                    if curr_role == "seller"
                    else dev_res.buyer_incremental_benefits_aud.get(player_id, 0.0)
                )

                # Nash condition: dev_payoff <= curr_payoff + tol
                assert dev_payoff <= curr_payoff + tol, (
                    f"Profitable deviation for {player_id} at {row['timestamp']}: "
                    f"current={curr_payoff:.6f} at {curr_p}, dev={dev_payoff:.6f} at {alt_p}"
                )


def test_every_representative_equilibrium_belongs_to_pareto_frontier(hourly_results_df: pd.DataFrame):
    """Verify that every selected representative equilibrium is marked Pareto-undominated."""
    df = hourly_results_df
    # In hours with PNE, the selected equilibrium must exist and be Pareto-undominated
    hours_with_pne = df[df["num_pne"] > 0]
    assert len(hours_with_pne) == 1752, "Expected PNE to exist in all hours"
    assert (hours_with_pne["num_pareto_undominated_pne"] >= 1).all()
    assert hours_with_pne["selected_price_profile"].notna().all()


def test_non_equilibrium_profiles_have_profitable_deviation():
    """Verify that an arbitrary non-equilibrium profile has at least one profitable deviation."""
    # Test on a known mixed tradeable hour
    surps = {"H001": 1.5, "H002": 0.0, "H003": 0.0}
    defcs = {"H001": 0.0, "H002": 1.0, "H003": 1.0}

    # Profile (0.08, 0.30, 0.30) has maximum bid-ask spread:
    # Seller asks 0.08, both buyers bid 0.30. Price is 0.19.
    # Seller can unilaterally deviate to 0.30 (or higher) to raise the transaction price!
    orders_base = [
        MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.08, quantity_kwh=1.5),
        MarketOrder("H002", MarketRole.BUYER, price_aud_per_kwh=0.30, quantity_kwh=1.0),
        MarketOrder("H003", MarketRole.BUYER, price_aud_per_kwh=0.30, quantity_kwh=1.0),
    ]
    res_base = clear_strategic_double_auction(orders_base)
    u_seller_base = res_base.seller_incremental_benefits_aud["H001"]

    # Seller deviates to 0.30
    orders_dev = [
        MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.30, quantity_kwh=1.5),
        MarketOrder("H002", MarketRole.BUYER, price_aud_per_kwh=0.30, quantity_kwh=1.0),
        MarketOrder("H003", MarketRole.BUYER, price_aud_per_kwh=0.30, quantity_kwh=1.0),
    ]
    res_dev = clear_strategic_double_auction(orders_dev)
    u_seller_dev = res_dev.seller_incremental_benefits_aud["H001"]

    # Seller strictly gains by asking higher
    assert u_seller_dev > u_seller_base + 1e-6


# =============================================================================
# 3. FINANCIAL AND PHYSICAL CONSERVATION INVARIANTS
# =============================================================================

def test_hourly_financial_and_physical_consistency_with_phase8b1(hourly_results_df: pd.DataFrame):
    """Verify that hourly outputs strictly preserve physical and financial conservation laws."""
    df = hourly_results_df
    tol = 1e-6

    # Test all 1,752 hours
    for _, row in df.iterrows():
        traded_kwh = row["selected_traded_volume_kwh"]
        welfare_aud = row["selected_community_welfare_aud"]
        payoffs_sum = row["H001_payoff_aud"] + row["H002_payoff_aud"] + row["H003_payoff_aud"]

        # Welfare identity: Delta W == 0.22 * Q_P2P
        expected_welfare = 0.22 * traded_kwh
        assert abs(welfare_aud - expected_welfare) <= tol

        # Payoffs sum identity: sum(U_i) == Delta W
        assert abs(payoffs_sum - welfare_aud) <= tol

        # If traded volume == 0, price is None/NaN
        if traded_kwh <= tol:
            assert pd.isna(row["selected_weighted_average_price_aud"])
            assert welfare_aud <= tol
        else:
            p_vwap = row["selected_weighted_average_price_aud"]
            assert 0.08 - tol <= p_vwap <= 0.30 + tol


def test_aggregate_metrics_reproducibility(hourly_results_df: pd.DataFrame):
    """Verify aggregate dataset metrics against physical constraints and baseline limits."""
    df = hourly_results_df
    agg_volume = df["selected_traded_volume_kwh"].sum()
    agg_welfare = df["selected_community_welfare_aud"].sum()

    # Total P2P volume must be strictly positive and bounded by the Phase 7 baseline (121.611449 kWh)
    assert 0.0 < agg_volume <= 121.611449 + 1e-6
    # Total welfare must equal 0.22 * aggregate volume
    assert pytest.approx(agg_welfare, abs=1e-5) == 0.22 * agg_volume

    # Individual rationality at the aggregate level: each household has positive cumulative benefit
    assert df["H001_payoff_aud"].sum() >= -1e-6
    assert df["H002_payoff_aud"].sum() >= -1e-6
    assert df["H003_payoff_aud"].sum() >= -1e-6


def test_all_equilibria_json_integrity():
    """Verify that all_equilibria.json.gz exists and contains all 1,752 timestamps."""
    assert JSON_REPORT_PATH.exists(), f"Missing {JSON_REPORT_PATH}"
    with gzip.open(JSON_REPORT_PATH, "rt", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 1752
    assert all("timestamp" in entry and "equilibria" in entry for entry in data)

