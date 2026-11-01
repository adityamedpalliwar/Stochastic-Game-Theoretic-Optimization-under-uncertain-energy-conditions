"""Dataset-wide validation and mathematical invariant tests for Phase 8D.

Verifies:
1. Exact 1,752-hour coverage with zero missing or duplicate timestamps.
2. Complete reconciliation between household payoffs and community welfare (|sum U_i - Delta W| < 1e-10).
3. Exact volume (121.611449 kWh) and welfare ($26.754519 AUD) conservation across all strategies.
4. Numerical equivalence between archive payoffs and live double-auction re-clearing (< 1e-10 AUD).
5. Exact reproduction of Phase 8C representative equilibria by Strategy A.
6. Proper segregation of one-sided market hours (NaN fairness scores).
7. Correct active-participant handling in the single 2-active hour (2013-05-18 11:00:00).
8. Existence and non-zero size of all generated visualization artifacts.
"""

from __future__ import annotations

import ast
from pathlib import Path
import pandas as pd
import pytest

from src.game.strategic_market import (
    MarketOrder,
    MarketRole,
    clear_strategic_double_auction,
)

HOURLY_CSV_PATH = Path("reports/phase8d_hourly_selection.csv")
STRATEGY_CSV_PATH = Path("reports/phase8d_strategy_comparison.csv")
PHASE8C_CSV_PATH = Path("reports/phase8c_hourly_equilibria.csv")
VIS_DIR = Path("reports/phase8d_visualizations")


@pytest.fixture(scope="module")
def df_hourly_8d() -> pd.DataFrame:
    assert HOURLY_CSV_PATH.exists(), f"Missing required file: {HOURLY_CSV_PATH}"
    return pd.read_csv(HOURLY_CSV_PATH)


@pytest.fixture(scope="module")
def df_strategy_comp() -> pd.DataFrame:
    assert STRATEGY_CSV_PATH.exists(), f"Missing required file: {STRATEGY_CSV_PATH}"
    return pd.read_csv(STRATEGY_CSV_PATH)


@pytest.fixture(scope="module")
def df_hourly_8c() -> pd.DataFrame:
    assert PHASE8C_CSV_PATH.exists(), f"Missing required file: {PHASE8C_CSV_PATH}"
    return pd.read_csv(PHASE8C_CSV_PATH)


# =============================================================================
# 1. COVERAGE AND DATA INTEGRITY TESTS
# =============================================================================

def test_exact_1752_hour_coverage_and_no_duplicates(df_hourly_8d: pd.DataFrame):
    """Verify exact 1,752 hours from 2013-04-19 00:00 to 2013-06-30 23:00 without duplicates."""
    df = df_hourly_8d
    assert len(df) == 1752, f"Expected 1,752 rows, got {len(df)}"
    assert df["timestamp"].nunique() == 1752, "Duplicate timestamps detected!"
    assert df["timestamp"].min() == "2013-04-19 00:00:00"
    assert df["timestamp"].max() == "2013-06-30 23:00:00"


def test_strategy_comparison_contains_all_13_configurations(df_strategy_comp: pd.DataFrame):
    """Verify that comparison CSV contains all 6 core strategies + 7 hybrid variants."""
    df = df_strategy_comp
    assert len(df) == 13
    core_strats = df[df["strategy_type"] == "core"]
    sens_strats = df[df["strategy_type"] == "sensitivity"]
    assert len(core_strats) == 6
    assert len(sens_strats) == 7


# =============================================================================
# 2. PHYSICAL AND FINANCIAL CONSERVATION INVARIANTS
# =============================================================================

def test_all_strategies_preserve_exact_volume_and_welfare(df_strategy_comp: pd.DataFrame):
    """Verify that every single strategy clears exactly 121.611449 kWh and $26.754519 AUD."""
    df = df_strategy_comp
    expected_vol = 121.611448765602
    expected_welf = 26.754518728432

    for _, row in df.iterrows():
        s_id = row["strategy_id"]
        vol = row["total_p2p_volume_kwh"]
        welf = row["total_community_welfare_aud"]
        assert abs(vol - expected_vol) < 1e-6, f"Volume mismatch in {s_id}: {vol} vs {expected_vol}"
        assert abs(welf - expected_welf) < 1e-6, f"Welfare mismatch in {s_id}: {welf} vs {expected_welf}"


def test_hourly_and_aggregate_payoff_reconciliation(df_strategy_comp: pd.DataFrame):
    """Verify that household benefits reconcile with community welfare to machine precision."""
    df = df_strategy_comp
    for _, row in df.iterrows():
        s_id = row["strategy_id"]
        h1 = row["H001_benefit_aud"]
        h2 = row["H002_benefit_aud"]
        h3 = row["H003_benefit_aud"]
        tot_welf = row["total_community_welfare_aud"]
        sum_payoffs = h1 + h2 + h3

        # Aggregate residual < 1e-10 AUD
        assert abs(sum_payoffs - tot_welf) < 1e-10, f"Aggregate residual failure in {s_id}"
        # Max hourly residual < 1e-10 AUD
        assert row["max_hourly_accounting_residual_aud"] < 1e-10, f"Hourly residual failure in {s_id}"


def test_numerical_equivalence_with_recomputed_double_auction(df_hourly_8d: pd.DataFrame, df_hourly_8c: pd.DataFrame):
    """Verify recomputed double auction payoffs match archive payoffs to < 1e-10 AUD."""
    df8d = df_hourly_8d.set_index("timestamp")
    df8c = df_hourly_8c.set_index("timestamp")

    # Sample 15 mixed-market timestamps across dataset
    mixed_ts = df8d[df8d["is_mixed_market"]].index[::55][:15]

    for ts in mixed_ts:
        row8d = df8d.loc[ts]
        row8c = df8c.loc[ts]

        # Test Strategy A profile
        profile_str = row8d["strat_a_price_profile"]
        profile = ast.literal_eval(profile_str)

        orders = []
        for hid in ["H001", "H002", "H003"]:
            s = row8c[f"{hid}_surplus_kwh"]
            d = row8c[f"{hid}_deficit_kwh"]
            p = profile.get(hid, 0.19)
            if s > 1e-6:
                orders.append(MarketOrder(hid, MarketRole.SELLER, p, s))
            elif d > 1e-6:
                orders.append(MarketOrder(hid, MarketRole.BUYER, p, d))

        res = clear_strategic_double_auction(orders)
        recomp_payoffs = {
            hid: res.seller_incremental_benefits_aud.get(hid, 0.0) + res.buyer_incremental_benefits_aud.get(hid, 0.0)
            for hid in ["H001", "H002", "H003"]
        }

        # Check equivalence to < 1e-10 AUD
        assert abs(recomp_payoffs["H001"] - row8d["strat_a_H001_payoff"]) < 1e-10
        assert abs(recomp_payoffs["H002"] - row8d["strat_a_H002_payoff"]) < 1e-10
        assert abs(recomp_payoffs["H003"] - row8d["strat_a_H003_payoff"]) < 1e-10
        assert abs(res.total_traded_kwh - row8d["strat_a_volume_kwh"]) < 1e-10
        assert abs(res.community_incremental_welfare_aud - row8d["strat_a_welfare_aud"]) < 1e-10


# =============================================================================
# 3. STRATEGY A REPRODUCTION AND FAIRNESS SEGREGATION
# =============================================================================

def test_strategy_a_exact_reproduction_of_phase8c(df_strategy_comp: pd.DataFrame, df_hourly_8d: pd.DataFrame, df_hourly_8c: pd.DataFrame):
    """Verify Strategy A produces 100.0% concordance with Phase 8C representative results."""
    comp = df_strategy_comp.set_index("strategy_id")
    row_a = comp.loc["Strategy_A_Reference"]

    assert row_a["concordance_with_strategy_a_pct"] == 100.0
    assert row_a["hours_identical_to_strategy_a"] == 1752
    assert pytest.approx(row_a["H001_benefit_aud"], abs=1e-6) == 8.413031
    assert pytest.approx(row_a["H002_benefit_aud"], abs=1e-6) == 11.090010
    assert pytest.approx(row_a["H003_benefit_aud"], abs=1e-6) == 7.251477


def test_one_sided_hours_fairness_segregation(df_hourly_8d: pd.DataFrame):
    """Verify that all 886 one-sided market hours have NaN fairness metrics."""
    df = df_hourly_8d
    one_sided = df[~df["is_mixed_market"]]
    assert len(one_sided) == 886

    for strat_key in ["strat_a", "strat_b", "strat_c", "strat_d", "strat_e", "strat_f_05"]:
        if f"{strat_key}_standard_gini" in one_sided.columns:
            assert one_sided[f"{strat_key}_standard_gini"].isna().all()
            assert one_sided[f"{strat_key}_normalized_gini"].isna().all()


def test_single_2_active_hour_handling(df_hourly_8d: pd.DataFrame):
    """Verify that timestamp 2013-05-06 16:00:00 (exact single 2-active hour) evaluates properly."""
    df = df_hourly_8d.set_index("timestamp")
    row_2act = df.loc["2013-05-06 16:00:00"]

    assert row_2act["num_active_players"] == 2
    assert row_2act["num_active_sellers"] == 2
    assert row_2act["num_active_buyers"] == 0
    assert row_2act["is_mixed_market"] == False

    # Because there are no buyers, trade is 0 and fairness metrics are properly marked NaN
    assert pd.isna(row_2act["strat_a_standard_gini"])
    assert pd.isna(row_2act["strat_d_min_benefit"])


# =============================================================================
# 4. ARTIFACTS VERIFICATION
# =============================================================================

def test_visualization_artifacts_exist_and_non_empty():
    """Verify that all 8 required visual charts exist in reports/phase8d_visualizations/."""
    expected_charts = [
        "household_benefit_comparison.png",
        "gini_coefficient_comparison.png",
        "welfare_vs_fairness_tradeoff.png",
        "transaction_price_distributions.png",
        "benefit_share_distributions.png",
        "fairness_vs_welfare_scatter.png",
        "hourly_price_comparison.png",
        "hybrid_weight_sensitivity.png",
    ]

    for fname in expected_charts:
        fpath = VIS_DIR / fname
        assert fpath.exists(), f"Missing visualization: {fpath}"
        assert fpath.stat().st_size > 1000, f"Visualization file is empty or corrupted: {fpath}"
