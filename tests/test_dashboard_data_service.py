"""Unit tests for dashboard data service layer (Flagship 5-Household Platform).

Validates:
1. In-memory data loading and caching.
2. JSON sanitization safety (no NaN/Inf leaks).
3. 5-Household customer profiles and capacities.
4. Diurnal trajectory statistics and uncertainty percentiles.
5. 4 Operational counterfactual modes and factor decomposition.
6. Publication figures catalog metadata.
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from dashboard.data_service import DashboardDataService, get_data_service, sanitize_value


@pytest.fixture(scope="module")
def data_service() -> DashboardDataService:
    """Fixture providing initialized data service."""
    return get_data_service()


def test_sanitize_value() -> None:
    """Validate JSON sanitization handles numpy types, NaNs, and infinities."""
    test_dict = {
        "nan_float": float("nan"),
        "inf_float": float("inf"),
        "neg_inf": float("-inf"),
        "np_nan": np.nan,
        "np_float": np.float64(3.14159),
        "np_int": np.int64(42),
        "np_bool": np.bool_(True),
        "nested": {
            "arr": np.array([1.0, 2.0, np.nan]),
            "val": 100,
        },
    }
    sanitized = sanitize_value(test_dict)
    assert sanitized["nan_float"] is None
    assert sanitized["inf_float"] is None
    assert sanitized["neg_inf"] is None
    assert sanitized["np_nan"] is None
    assert abs(sanitized["np_float"] - 3.14159) < 1e-5
    assert sanitized["np_int"] == 42
    assert sanitized["np_bool"] is True
    assert sanitized["nested"]["arr"] == [1.0, 2.0, None]


def test_system_overview(data_service: DashboardDataService) -> None:
    """Validate system overview macroeconomic findings."""
    overview = data_service.get_system_overview()
    assert overview["scenarios_evaluated"] == 1000
    assert overview["game_rounds_total"] == 24000
    assert overview["households_count"] == 5
    assert overview["household_ids"] == ["H001", "H002", "H003", "H004", "H005"]

    fin = overview["financial_outcomes"]
    assert abs(fin["total_profit_1000d"] - 10559.67) < 1.0
    assert abs(fin["bill_reduction_pct"] - 40.07) < 0.5
    assert abs(fin["daily_baseline_cost"] - 26.36) < 0.5
    assert abs(fin["daily_p2p_game_cost"] - 15.80) < 0.5

    decomp = overview["profit_decomposition"]
    assert abs(decomp["solar_self_consumption_aud"] - 5522.87) < 1.0
    assert abs(decomp["battery_arbitrage_aud"] - 4496.47) < 1.0
    assert abs(decomp["p2p_game_coordination_aud"] - 540.34) < 1.0


def test_customer_profiles(data_service: DashboardDataService) -> None:
    """Validate 5-household specifications, archetypes, and capacities."""
    profiles = data_service.get_customer_profiles()
    assert len(profiles) == 5
    p_map = {p["house_id"]: p for p in profiles}

    assert p_map["H001"]["pv_capacity_kwp"] == 3.78
    assert p_map["H002"]["pv_capacity_kwp"] == 1.00
    assert p_map["H003"]["pv_capacity_kwp"] == 1.00
    assert p_map["H004"]["pv_capacity_kwp"] == 2.00
    assert p_map["H005"]["pv_capacity_kwp"] == 2.16

    # Archetype verification
    assert "Seller" in p_map["H001"]["archetype"]
    assert "Buyer" in p_map["H004"]["archetype"]


def test_diurnal_trajectories(data_service: DashboardDataService) -> None:
    """Validate 24-hour diurnal trajectory statistics."""
    res_h001 = data_service.get_diurnal_trajectories("H001")
    assert res_h001["house_id"] == "H001"
    assert len(res_h001["hours"]) == 24
    assert len(res_h001["demand"]["mean"]) == 24
    assert len(res_h001["solar"]["mean"]) == 24
    assert len(res_h001["demand"]["p10"]) == 24
    assert len(res_h001["demand"]["p90"]) == 24

    # Peak solar occurs midday (e.g. 11 to 14)
    midday_solar = res_h001["solar"]["mean"][12]
    assert midday_solar > 1.5

    # Battery trajectory verification
    assert "battery" in res_h001
    assert len(res_h001["battery"]["soc"]) == 24
    assert all(0.09 <= s <= 0.91 for s in res_h001["battery"]["soc"])


def test_modes_comparison(data_service: DashboardDataService) -> None:
    """Validate 4 counterfactual modes summary table."""
    modes = data_service.get_modes_comparison()
    assert len(modes) == 6  # 5 houses + COMMUNITY_TOTAL

    comm = next(m for m in modes if m["entity"] == "COMMUNITY_TOTAL")
    # Pure Grid > Solar > Battery > P2P Game
    assert comm["mode1_pure_grid_aud_day"] > comm["mode2_solar_grid_aud_day"]
    assert comm["mode2_solar_grid_aud_day"] > comm["mode3_battery_grid_aud_day"]
    assert comm["mode3_battery_grid_aud_day"] > comm["mode4_p2p_game_aud_day"]


def test_scenario_generation_demo(data_service: DashboardDataService) -> None:
    """Validate interactive scenario generator demo."""
    demo = data_service.get_scenario_generation_demo("H001", seed=42)
    assert demo["house_id"] == "H001"
    assert len(demo["base_demand"]) == 24
    assert len(demo["base_solar"]) == 24
    assert len(demo["synthetic_scenarios"]) == 3

    # Physical constraint: night solar must be zero
    for sc in demo["synthetic_scenarios"]:
        assert sc["solar"][0] == 0.0
        assert sc["solar"][1] == 0.0
        assert sc["solar"][23] == 0.0


def test_figures_catalog(data_service: DashboardDataService) -> None:
    """Validate publication figures catalog."""
    catalog = data_service.get_figures_catalog()
    assert len(catalog) == 6
    ids = [f["id"] for f in catalog]
    assert "plot_01" in ids
    assert "plot_06" in ids
