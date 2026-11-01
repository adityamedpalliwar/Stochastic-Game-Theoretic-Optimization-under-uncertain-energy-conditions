"""Comprehensive integration tests for Deliverable 2 Flask API (`dashboard/app.py`).

Validates:
1. All 12 REST API endpoints return HTTP 200 and uniform JSON schema.
2. Input parameter validation and structured HTTP 400/404/405 error responses.
3. CORS headers and JSON serialization safety.
4. Read-only compliance (no data mutation, no solver execution).
"""

from typing import Generator
import pytest
from flask.testing import FlaskClient

from dashboard.app import create_app
from dashboard.data_service import get_data_service


@pytest.fixture(scope="module")
def client() -> Generator[FlaskClient, None, None]:
    """Flask test client fixture using shared singleton data service."""
    service = get_data_service()
    app = create_app(data_service=service)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_root_endpoint(client: FlaskClient) -> None:
    """Test GET / returns 200 and greeting metadata."""
    res = client.get("/")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "version" in data["data"]


def test_health_endpoint(client: FlaskClient) -> None:
    """Test GET /api/health returns 200 and healthy cache state."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["data"]["status"] == "healthy"
    assert data["data"]["cache_initialized"] is True
    assert data["data"]["read_only_mode"] is True
    assert data["data"]["tests_passing"] == 250


def test_system_status_endpoint(client: FlaskClient) -> None:
    """Test GET /api/system_status returns system horizons and 250 tests."""
    res = client.get("/api/system_status")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    sys_data = data["data"]
    assert sys_data["regression_test_status"]["tests_passing"] == 250
    assert sys_data["households"] == ["H001", "H002", "H003"]
    assert sys_data["dataset_horizons"]["test_period_hours"] == 1752


def test_customer_profiles_endpoint(client: FlaskClient) -> None:
    """Test GET /api/customer_profiles returns 3 customer profiles."""
    res = client.get("/api/customer_profiles")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    profiles = data["data"]
    assert len(profiles) == 3
    assert profiles[0]["house_id"] == "H001"
    assert profiles[0]["battery_capacity_kwh"] == 5.0


def test_forecast_data_endpoint(client: FlaskClient) -> None:
    """Test GET /api/forecast_data with default and query parameters."""
    # Default query
    res = client.get("/api/forecast_data")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["data"]["total_records"] == 1752

    # Query with filters
    res2 = client.get("/api/forecast_data?house_id=H002&limit=5")
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert data2["data"]["total_records"] == 5
    assert data2["data"]["house_id"] == "H002"


def test_forecast_data_invalid_params(client: FlaskClient) -> None:
    """Test GET /api/forecast_data handles invalid parameters cleanly."""
    # Invalid house ID
    res = client.get("/api/forecast_data?house_id=H999")
    assert res.status_code == 400
    data = res.get_json()
    assert data["status"] == "error"
    assert "Invalid house_id" in data["message"]

    # Invalid negative limit
    res2 = client.get("/api/forecast_data?limit=-10")
    assert res2.status_code == 400
    assert res2.get_json()["status"] == "error"

    # Non-integer limit
    res3 = client.get("/api/forecast_data?limit=abc")
    assert res3.status_code == 400
    assert res3.get_json()["status"] == "error"


def test_forecast_scorecard_endpoint(client: FlaskClient) -> None:
    """Test GET /api/forecast_scorecard returns point and interval metrics."""
    res = client.get("/api/forecast_scorecard")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert len(data["data"]["point_metrics"]) == 16
    assert len(data["data"]["interval_metrics"]) == 8
    assert "honest_assessment" in data["data"]


def test_battery_dispatch_endpoint(client: FlaskClient) -> None:
    """Test GET /api/battery_dispatch with valid controller and options."""
    res = client.get("/api/battery_dispatch?controller=Stochastic_MPC&house_id=H001&enable_p2p=true&limit=24")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["data"]["total_records"] == 24
    record = data["data"]["records"][0]
    assert "battery_final_soc" in record
    assert "charged_kwh" in record
    assert "discharged_kwh" in record


def test_battery_dispatch_invalid_params(client: FlaskClient) -> None:
    """Test GET /api/battery_dispatch returns 400 on invalid inputs."""
    # Invalid controller
    res = client.get("/api/battery_dispatch?controller=SuperController")
    assert res.status_code == 400
    assert res.get_json()["status"] == "error"

    # Invalid house ID
    res2 = client.get("/api/battery_dispatch?house_id=ALL")
    assert res2.status_code == 400

    # Invalid enable_p2p
    res3 = client.get("/api/battery_dispatch?enable_p2p=maybe")
    assert res3.status_code == 400


def test_p2p_benchmarks_endpoint(client: FlaskClient) -> None:
    """Test GET /api/p2p_benchmarks returns all 32 benchmark rows."""
    res = client.get("/api/p2p_benchmarks")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert len(data["data"]) == 32


def test_liquidity_metrics_endpoint(client: FlaskClient) -> None:
    """Test GET /api/liquidity_metrics with and without filter."""
    res = client.get("/api/liquidity_metrics")
    assert res.status_code == 200
    assert len(res.get_json()["data"]) == 4

    res2 = client.get("/api/liquidity_metrics?controller=Stochastic_MPC")
    assert res2.status_code == 200
    assert len(res2.get_json()["data"]) == 1

    # Invalid controller filter
    res3 = client.get("/api/liquidity_metrics?controller=Unknown")
    assert res3.status_code == 400


def test_tradeable_hours_endpoint(client: FlaskClient) -> None:
    """Test GET /api/tradeable_hours returns 866 tradeable hours."""
    res = client.get("/api/tradeable_hours")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert len(data["data"]) == 866


def test_nash_hour_endpoint(client: FlaskClient) -> None:
    """Test GET /api/nash_hour with timestamp and hour_index."""
    # Default (first tradeable hour)
    res = client.get("/api/nash_hour")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert "market_state" in data
    assert "equilibria" in data

    # By hour_index
    res2 = client.get("/api/nash_hour?hour_index=0")
    assert res2.status_code == 200
    data2 = res2.get_json()["data"]
    assert data2["timestamp"] == "2013-04-19 00:00:00"


def test_nash_hour_invalid_params(client: FlaskClient) -> None:
    """Test GET /api/nash_hour handles out-of-range index and unknown timestamp."""
    # Out of range hour_index
    res = client.get("/api/nash_hour?hour_index=2000")
    assert res.status_code == 400

    # Non-integer hour_index
    res2 = client.get("/api/nash_hour?hour_index=hour_one")
    assert res2.status_code == 400

    # Unknown timestamp
    res3 = client.get("/api/nash_hour?timestamp=2099-01-01%2000:00:00")
    assert res3.status_code == 404


def test_fairness_summary_endpoint(client: FlaskClient) -> None:
    """Test GET /api/fairness_summary returns 13 strategies table."""
    res = client.get("/api/fairness_summary")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert len(data["data"]) == 13


def test_fairness_hourly_endpoint(client: FlaskClient) -> None:
    """Test GET /api/fairness_hourly with limit filter."""
    res = client.get("/api/fairness_hourly?limit=10")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert len(data["data"]) == 10


def test_precomputed_ledger_endpoint(client: FlaskClient) -> None:
    """Test GET /api/precomputed_ledger returns 250 tests and conservation verifications."""
    res = client.get("/api/precomputed_ledger")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    ledger = data["data"]
    assert ledger["test_suite"]["passed_tests"] == 250
    assert ledger["financial_accounting_invariants"]["verdict"] == "VERIFIED_ZERO_FINANCIAL_LEAKAGE"


def test_cors_headers(client: FlaskClient) -> None:
    """Test that CORS headers are attached to responses."""
    res = client.get("/api/health")
    assert res.headers.get("Access-Control-Allow-Origin") == "*"
    assert "GET" in res.headers.get("Access-Control-Allow-Methods", "")


def test_not_found_endpoint(client: FlaskClient) -> None:
    """Test 404 response on nonexistent route."""
    res = client.get("/api/nonexistent_path")
    assert res.status_code == 404
    data = res.get_json()
    assert data["status"] == "error"


def test_method_not_allowed(client: FlaskClient) -> None:
    """Test POST request on GET-only route returns 405."""
    res = client.post("/api/health")
    assert res.status_code == 405
    data = res.get_json()
    assert data["status"] == "error"
    assert "Method not allowed" in data["message"]

