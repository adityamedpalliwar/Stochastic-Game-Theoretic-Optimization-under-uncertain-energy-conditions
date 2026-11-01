"""Phase 8E Dashboard and Backend API Integration Tests.

Validates:
1. GET /api/strategic-market/stochastic-hourly endpoint handling (200, 400, 404).
2. JSON structure, required fields, and mathematical identities.
3. In-memory timestamp caching for performance.
4. Deterministic (Phase 8C) vs Stochastic (Phase 8E) side-by-side comparison payload.
5. Zero-trade hour graceful handling.
6. Frontend HTML template and static assets verification.
"""

import time
import pytest
from dashboard.app import create_app


@pytest.fixture(scope="module")
def client():
    """Create test client with initialized Flask application."""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_stochastic_endpoint_missing_timestamp(client):
    """Missing timestamp query parameter should return HTTP 400."""
    res = client.get("/api/strategic-market/stochastic-hourly")
    assert res.status_code == 400
    data = res.get_json()
    assert data["status"] == "error"
    assert "Parameter 'timestamp' is required" in data["message"]


def test_stochastic_endpoint_invalid_timestamp_format(client):
    """Invalid timestamp format should return HTTP 400."""
    res = client.get("/api/strategic-market/stochastic-hourly?timestamp=not-a-timestamp")
    assert res.status_code == 400
    data = res.get_json()
    assert data["status"] == "error"
    assert "Invalid timestamp format" in data["message"]


def test_stochastic_endpoint_out_of_range_timestamp(client):
    """Timestamp outside dataset range should return HTTP 404."""
    res = client.get("/api/strategic-market/stochastic-hourly?timestamp=2025-01-01T00:00:00")
    assert res.status_code == 404
    data = res.get_json()
    assert data["status"] == "error"
    assert "No data found for timestamp" in data["message"]


def test_stochastic_endpoint_success_and_payload_structure(client):
    """Valid timestamp (2013-05-15 11:00:00) returns 200 with complete Phase 8E schema."""
    ts = "2013-05-15 11:00:00"
    res = client.get(f"/api/strategic-market/stochastic-hourly?timestamp={ts}")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["status"] == "success"

    data = json_data["data"]
    assert data["timestamp"] == ts
    assert data["engine"] == "Phase 8E Stochastic Expected-Payoff Nash Equilibrium Engine"
    assert data["num_scenarios"] == 1000
    assert "num_tradeable_scenarios" in data
    assert "tradeable_scenario_percentage" in data

    # Roles and positions
    assert set(data["ex_ante_roles"].keys()) == {"H001", "H002", "H003"}
    assert set(data["expected_net_positions_kwh"].keys()) == {"H001", "H002", "H003"}
    assert set(data["scenario_role_flip_counts"].keys()) == {"H001", "H002", "H003"}

    # Battery dispatch
    assert "battery_dispatch" in data
    assert set(data["battery_dispatch"]["charge_kwh"].keys()) == {"H001", "H002", "H003"}
    assert set(data["battery_dispatch"]["discharge_kwh"].keys()) == {"H001", "H002", "H003"}

    # Market summary & welfare conservation
    summary = data["market_summary"]
    assert "expected_traded_energy_kwh" in summary
    assert "expected_community_welfare_aud" in summary
    assert "expected_vwap_aud_per_kwh" in summary
    assert summary["welfare_conservation_verified"] is True

    exp_q = summary["expected_traded_energy_kwh"]
    exp_w = summary["expected_community_welfare_aud"]
    assert abs(exp_w - (0.22 * exp_q)) < 1e-6

    # Household payoffs sum to community welfare
    payoffs = summary["expected_household_payoffs_aud"]
    assert abs(sum(payoffs.values()) - exp_w) < 1e-6

    # Nash equilibrium counts
    assert data["num_stochastic_pne"] >= 0
    assert data["strict_pne_count"] >= 0
    assert data["weak_pne_count"] >= 0
    assert data["pareto_undominated_pne_count"] >= 0
    assert data["num_stochastic_pne"] == data["strict_pne_count"] + data["weak_pne_count"]

    # Equilibrium selection
    assert "selected_equilibrium" in data
    if data["num_stochastic_pne"] > 0:
        sel = data["selected_equilibrium"]
        assert sel["profile"] is not None
        assert "selection_rationale" in sel
        assert len(data["pareto_undominated_equilibria"]) >= 1

    # Expected payoff table (343 profiles evaluated)
    assert len(data["expected_payoff_table"]) == 343

    # Modeling metadata
    meta = data["modeling_metadata"]
    assert "Option 1A" in meta["action_space"]
    assert "Option 2A" in meta["scenario_sampling"]
    assert "Option 3A" in meta["battery_dispatch"]
    assert "role-conditioned" in meta["disclaimer"].lower()


def test_stochastic_cache_hit_performance(client):
    """Repeated call to same timestamp should hit the in-memory cache in sub-50ms."""
    ts = "2013-05-15 11:00:00"
    t0 = time.perf_counter()
    res = client.get(f"/api/strategic-market/stochastic-hourly?timestamp={ts}")
    t_cache = (time.perf_counter() - t0) * 1000.0

    assert res.status_code == 200
    assert t_cache < 50.0  # Cache hit should be fast


def test_deterministic_vs_stochastic_comparison(client):
    """Side-by-side deterministic (Phase 8C) vs stochastic (Phase 8E) comparison."""
    ts = "2013-05-15 11:00:00"
    res = client.get(f"/api/strategic-market/stochastic-hourly?timestamp={ts}")
    assert res.status_code == 200
    comp = res.get_json()["data"]["deterministic_comparison"]

    assert "traded_volume_kwh" in comp
    assert "community_welfare_aud" in comp
    assert "vwap_aud_per_kwh" in comp
    assert "household_payoffs" in comp
    assert "roles" in comp
    assert "equilibrium_counts" in comp

    vol_comp = comp["traded_volume_kwh"]
    assert "deterministic_ex_post" in vol_comp
    assert "stochastic_expected" in vol_comp
    assert "absolute_diff_kwh" in vol_comp
    assert "percentage_diff" in vol_comp
    assert "jensen_effect_observed" in vol_comp

    # Verify Jensen effect definition: diff < 0 indicates E[min(S,D)] <= min(E[S],E[D])
    if vol_comp["absolute_diff_kwh"] < -1e-6:
        assert vol_comp["jensen_effect_observed"] is True


def test_zero_trade_hour_stochastic_handling(client):
    """Nighttime zero-trade hour should yield 0.0 trade, 0.0 welfare, and 343 weak PNE."""
    ts = "2013-05-15 02:00:00"
    res = client.get(f"/api/strategic-market/stochastic-hourly?timestamp={ts}")
    assert res.status_code == 200
    data = res.get_json()["data"]

    assert data["num_tradeable_scenarios"] == 0
    assert data["market_summary"]["expected_traded_energy_kwh"] == 0.0
    assert data["market_summary"]["expected_community_welfare_aud"] == 0.0
    assert data["num_stochastic_pne"] == 343
    assert data["weak_pne_count"] == 343
    assert data["strict_pne_count"] == 0


def test_dashboard_html_and_js_elements(client):
    """Dashboard HTML should contain Phase 8E tab, KPI containers, and static JS hooks."""
    res = client.get("/dashboard")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Tab navigation and pane
    assert 'data-target="pane-stochastic"' in html
    assert 'id="pane-stochastic"' in html

    # KPIs and components
    assert 'id="stoch-kpi-traded"' in html
    assert 'id="stoch-kpi-welfare"' in html
    assert 'id="stoch-kpi-vwap"' in html
    assert 'id="stoch-kpi-tradeable"' in html
    assert 'id="stoch-prosumer-cards-container"' in html
    assert 'id="stoch-comp-cards-grid"' in html
    assert 'id="stoch-comparison-table-body"' in html
    assert 'id="stoch-pareto-table-body"' in html
    assert 'id="stoch-payoff-table-body"' in html

    # Jump button from Phase 8D
    assert 'id="btn-jump-to-stochastic"' in html

    # JS file contains Phase 8E handlers
    js_res = client.get("/static/js/strategic_market.js")
    assert js_res.status_code == 200
    js = js_res.get_data(as_text=True)
    assert "initStochasticControls" in js
    assert "loadStochasticMarketData" in js
    assert "renderStochasticKPIs" in js
    assert "renderStochasticComparison" in js

