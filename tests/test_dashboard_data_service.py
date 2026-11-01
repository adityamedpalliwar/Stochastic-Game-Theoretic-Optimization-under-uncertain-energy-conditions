"""Unit tests for dashboard data service layer (Deliverable 2, Step 1).

Validates:
1. In-memory data loading and caching.
2. JSON serialization safety (no NaN/Inf leaks).
3. Query accuracy across all 8 functional domains.
4. Data consistency with authoritative Deliverable 1 baseline outputs.
5. Sub-millisecond query performance.
"""

import time
import pytest
import numpy as np

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


def test_system_status(data_service: DashboardDataService) -> None:
    """Validate system status overview and 250 test pass verification."""
    status = data_service.get_system_status()
    assert status["regression_test_status"]["tests_passing"] == 250
    assert status["regression_test_status"]["tests_total"] == 250
    assert status["regression_test_status"]["pass_rate_pct"] == 100.0
    assert status["households"] == ["H001", "H002", "H003"]
    assert status["dataset_horizons"]["test_period_hours"] == 1752
    assert status["dataset_horizons"]["test_period_total_evaluations"] == 5256
    assert abs(status["p2p_economic_summary"]["total_p2p_traded_kwh"] - 121.611449) < 1e-4
    assert abs(status["p2p_economic_summary"]["total_community_welfare_aud"] - 26.754519) < 1e-4


def test_customer_profiles(data_service: DashboardDataService) -> None:
    """Validate customer profiles, generator capacities, and battery parameters."""
    profiles = data_service.get_customer_profiles()
    assert len(profiles) == 3
    p_map = {p["house_id"]: p for p in profiles}

    assert p_map["H001"]["generator_capacity_kwp"] == 3.78
    assert p_map["H002"]["generator_capacity_kwp"] == 1.00
    assert p_map["H003"]["generator_capacity_kwp"] == 1.00

    for p in profiles:
        assert p["battery_capacity_kwh"] == 5.0
        assert p["battery_power_kw"] == 2.5
        assert p["soc_limits"] == [0.10, 0.90]
        assert p["tariff_scenario"]["grid_import_price_aud"] == 0.30
        assert p["tariff_scenario"]["grid_export_credit_aud"] == 0.08


def test_forecast_data_queries(data_service: DashboardDataService) -> None:
    """Validate test predictions and prediction intervals retrieval."""
    # Test specific household
    h1 = data_service.get_forecast_data(house_id="H001")
    assert h1["total_records"] == 1752
    first = h1["records"][0]
    assert "demand" in first and "solar" in first
    assert "actual" in first["demand"]
    assert "predicted" in first["demand"]
    assert "pi_lower" in first["demand"]
    assert "pi_upper" in first["demand"]
    assert "is_covered" in first["demand"]

    # Test filtering by date and limit
    filtered = data_service.get_forecast_data(
        house_id="H001",
        start_date="2013-05-01 00:00:00",
        end_date="2013-05-01 23:00:00",
        limit=10,
    )
    assert filtered["total_records"] == 10
    assert filtered["records"][0]["timestamp"] == "2013-05-01 00:00:00"


def test_forecast_scorecard(data_service: DashboardDataService) -> None:
    """Validate baseline point metrics and interval coverage calibration."""
    scorecard = data_service.get_forecast_scorecard()
    p_metrics = scorecard["point_metrics"]
    i_metrics = scorecard["interval_metrics"]

    assert len(p_metrics) == 16
    assert len(i_metrics) == 8

    # Check overall Solar MAE: shared_lstm_24h (0.0814) < persistence_last_hour (0.0864)
    lstm_solar = next(m for m in p_metrics if m["scope"] == "overall" and m["model"] == "shared_lstm_24h" and m["target"] == "solar_generation_kwh")
    pers_solar = next(m for m in p_metrics if m["scope"] == "overall" and m["model"] == "persistence_last_hour" and m["target"] == "solar_generation_kwh")
    assert lstm_solar["mae_kwh"] < pers_solar["mae_kwh"]

    # Check overall Demand MAE: persistence_last_hour (0.4310) < shared_lstm_24h (0.4660)
    lstm_demand = next(m for m in p_metrics if m["scope"] == "overall" and m["model"] == "shared_lstm_24h" and m["target"] == "total_demand_kwh")
    pers_demand = next(m for m in p_metrics if m["scope"] == "overall" and m["model"] == "persistence_last_hour" and m["target"] == "total_demand_kwh")
    assert pers_demand["mae_kwh"] < lstm_demand["mae_kwh"]

    # Check interval coverage for ALL
    solar_cov = next(m for m in i_metrics if m["household"] == "ALL" and m["target_variable"] == "solar_generation_kwh")
    demand_cov = next(m for m in i_metrics if m["household"] == "ALL" and m["target_variable"] == "total_demand_kwh")
    assert abs(solar_cov["empirical_coverage_pct"] - 89.42) < 0.1
    assert abs(demand_cov["empirical_coverage_pct"] - 81.91) < 0.1


def test_battery_dispatch(data_service: DashboardDataService) -> None:
    """Validate battery operation, SOC boundaries, and energy balance residuals."""
    res = data_service.get_battery_dispatch(
        controller="Stochastic_MPC",
        house_id="H001",
        enable_p2p=True,
    )
    assert res["total_records"] == 1752
    for r in res["records"]:
        # SOC within [0.10, 0.90]
        assert 0.0999 <= r["battery_final_soc"] <= 0.9001
        # Mutual exclusion: cannot charge and discharge simultaneously
        assert not (r["charged_kwh"] > 1e-4 and r["discharged_kwh"] > 1e-4)
        # Residual within tolerance
        assert abs(r["energy_balance_residual_kwh"]) < 1e-5


def test_p2p_benchmarks(data_service: DashboardDataService) -> None:
    """Validate 32 benchmark rows and savings from P2P trading."""
    benchmarks = data_service.get_p2p_benchmarks()
    assert len(benchmarks) == 32

    # Check Stochastic MPC Portfolio Total row
    stoch_p2p = next(
        b for b in benchmarks
        if b["controller"] == "Stochastic_MPC" and b["enable_p2p"] is True and b["household"] == "PORTFOLIO_TOTAL"
    )
    stoch_standalone = next(
        b for b in benchmarks
        if b["controller"] == "Stochastic_MPC" and b["enable_p2p"] is False and b["household"] == "PORTFOLIO_TOTAL"
    )

    # Cost savings from P2P
    savings = stoch_standalone["adjusted_net_cost_aud"] - stoch_p2p["adjusted_net_cost_aud"]
    assert abs(savings - 26.75) < 0.1
    assert stoch_p2p["soc_violations"] == 0
    assert stoch_p2p["simultaneous_violations"] == 0


def test_liquidity_metrics(data_service: DashboardDataService) -> None:
    """Validate microgrid liquidity metrics across controllers."""
    liq = data_service.get_liquidity_metrics(controller="Stochastic_MPC")
    assert len(liq) == 1
    s_liq = liq[0]
    assert s_liq["total_hours"] == 1752
    assert s_liq["tradeable_hours"] == 866
    assert abs(s_liq["total_p2p_traded_kwh"] - 121.611449) < 1e-4
    assert s_liq["seller_traded_hours"]["H001"] == 366
    assert s_liq["buyer_traded_hours"]["H001"] == 500


def test_tradeable_hours_list(data_service: DashboardDataService) -> None:
    """Validate list of tradeable hours."""
    t_list = data_service.get_tradeable_hours_list()
    assert len(t_list) == 866
    first = t_list[0]
    assert first["active_players"] >= 2
    assert first["traded_volume_kwh"] > 0


def test_nash_hour(data_service: DashboardDataService) -> None:
    """Validate single-hour pure Nash equilibrium inspection and Pareto invariance."""
    hour_data = data_service.get_nash_hour(timestamp="2013-04-19 00:00:00")
    assert hour_data is not None
    assert hour_data["market_state"]["is_mixed_market"] is True
    assert hour_data["pure_nash_counts"]["total_pne"] >= 10
    assert hour_data["pareto_invariance_proof"]["invariance_holds"] is True

    # Check strategy selections
    assert "strat_a" in hour_data["strategy_selections"]
    assert "strat_b" in hour_data["strategy_selections"]
    assert "strat_c" in hour_data["strategy_selections"]
    assert "strat_d" in hour_data["strategy_selections"]
    assert "strat_e" in hour_data["strategy_selections"]

    # Verify Pareto and dominated equilibria lists
    assert len(hour_data["equilibria"]["pareto_undominated"]) > 0
    assert len(hour_data["equilibria"]["dominated_or_submaximal"]) > 0


def test_fairness_summary(data_service: DashboardDataService) -> None:
    """Validate 13-row Phase 8D strategy comparison table."""
    summary = data_service.get_fairness_summary()
    assert len(summary) == 13

    # All configurations clear exactly 121.611449 kWh and $26.754519 AUD welfare
    for s in summary:
        assert abs(s["total_p2p_volume_kwh"] - 121.611449) < 1e-5
        assert abs(s["total_community_welfare_aud"] - 26.754519) < 1e-5
        assert s["max_hourly_accounting_residual_aud"] < 1e-15
        assert s["aggregate_welfare_residual_aud"] < 1e-13

    # Check Strategy B vs C benefit distribution
    strat_b = next(s for s in summary if s["strategy_id"] == "Strategy_B_Seller")
    strat_c = next(s for s in summary if s["strategy_id"] == "Strategy_C_Buyer")
    strat_e = next(s for s in summary if s["strategy_id"] == "Strategy_E_NSW")

    assert strat_b["household_benefits"]["H001"] > strat_c["household_benefits"]["H001"]
    assert strat_c["household_benefits"]["H003"] > strat_b["household_benefits"]["H003"]
    # Strategy E achieves lowest inequality among core strategies
    assert strat_e["mean_normalized_gini"] < strat_b["mean_normalized_gini"]


def test_precomputed_verification_ledger(data_service: DashboardDataService) -> None:
    """Validate precomputed verification ledger values."""
    ledger = data_service.get_precomputed_verification_ledger()
    assert ledger["test_suite"]["passed_tests"] == 250
    assert ledger["test_suite"]["pass_rate_pct"] == 100.0
    assert ledger["financial_accounting_invariants"]["bilateral_payment_equality_residual_aud"] == 0.0
    assert ledger["financial_accounting_invariants"]["seller_payoff_formula_residual_max_aud"] < 1e-15
    assert ledger["physical_conservation_invariants"]["tolerance_threshold_kwh"] == 1e-05


def test_sub_millisecond_query_performance(data_service: DashboardDataService) -> None:
    """Benchmark in-memory queries execute in sub-millisecond to low millisecond time."""
    t0 = time.perf_counter()
    for _ in range(50):
        _ = data_service.get_system_status()
        _ = data_service.get_fairness_summary()
        _ = data_service.get_p2p_benchmarks()
        _ = data_service.get_precomputed_verification_ledger()
    t1 = time.perf_counter()
    avg_ms = ((t1 - t0) / 200) * 1000
    assert avg_ms < 5.0, f"Average query took {avg_ms:.2f} ms (expected < 5.0 ms)"
