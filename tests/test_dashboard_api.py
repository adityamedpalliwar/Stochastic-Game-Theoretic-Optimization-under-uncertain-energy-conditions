"""Integration tests for Flagship 5-Household Flask API (`dashboard/app.py`).

Validates:
1. Root UI and Health endpoints.
2. Static publication figure serving.
3. System overview & customer profiles endpoints.
4. Diurnal trajectory queries and household validation.
5. 4 Counterfactual modes comparison endpoint.
6. Scenario generation demo endpoint.
7. Figures catalog endpoint.
8. Error handling and CORS headers.
"""

from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient

from dashboard.app import create_app
from dashboard.data_service import get_data_service


@pytest.fixture(scope="module")
def app() -> Flask:
    """Fixture providing initialized Flask app."""
    service = get_data_service()
    app = create_app(data_service=service)
    app.config["TESTING"] = True
    return app


@pytest.fixture(scope="module")
def client(app: Flask) -> FlaskClient:
    """Fixture providing test client."""
    return app.test_client()


def test_root_endpoint(client: FlaskClient) -> None:
    """Validate root endpoint returns 200 HTML."""
    res = client.get("/")
    assert res.status_code == 200
    assert b"Stochastic Game-Theoretic Renewable Energy Optimization" in res.data


def test_dashboard_ui_endpoint(client: FlaskClient) -> None:
    """Validate /dashboard returns 200 HTML."""
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert b"5-Household" in res.data


def test_health_endpoint(client: FlaskClient) -> None:
    """Validate health check JSON."""
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "success"
    assert body["data"]["status"] == "healthy"
    assert body["data"]["scenarios_evaluated"] == 1000


def test_system_overview_endpoint(client: FlaskClient) -> None:
    """Validate system overview JSON response."""
    res = client.get("/api/system_overview")
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "success"
    assert body["data"]["households_count"] == 5
    assert abs(body["data"]["financial_outcomes"]["total_profit_1000d"] - 10559.67) < 1.0


def test_customer_profiles_endpoint(client: FlaskClient) -> None:
    """Validate customer profiles endpoint returns all 5 houses."""
    res = client.get("/api/customer_profiles")
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "success"
    assert len(body["data"]) == 5


def test_diurnal_trajectories_endpoint(client: FlaskClient) -> None:
    """Validate diurnal trajectories endpoint."""
    res = client.get("/api/diurnal_trajectories?house_id=H001")
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "success"
    assert body["data"]["house_id"] == "H001"
    assert len(body["data"]["hours"]) == 24


def test_diurnal_trajectories_invalid_house(client: FlaskClient) -> None:
    """Validate invalid household ID error handling."""
    res = client.get("/api/diurnal_trajectories?house_id=INVALID")
    assert res.status_code == 400
    body = res.get_json()
    assert body["status"] == "error"


def test_modes_comparison_endpoint(client: FlaskClient) -> None:
    """Validate 4 counterfactual modes endpoint."""
    res = client.get("/api/modes_comparison")
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "success"
    assert len(body["data"]) == 6


def test_scenario_generation_demo_endpoint(client: FlaskClient) -> None:
    """Validate scenario generator demo endpoint."""
    res = client.get("/api/scenario_generation_demo?house_id=H001&seed=42")
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "success"
    assert len(body["data"]["synthetic_scenarios"]) == 3


def test_figures_catalog_endpoint(client: FlaskClient) -> None:
    """Validate publication figures catalog endpoint."""
    res = client.get("/api/figures_catalog")
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "success"
    assert len(body["data"]) == 7


def test_serve_figure_endpoint(client: FlaskClient) -> None:
    """Validate static publication figure serving."""
    res = client.get("/figures/01_daily_cost_comparison_across_modes.png")
    assert res.status_code == 200
    assert res.content_type.startswith("image/png")


def test_serve_figure_not_found(client: FlaskClient) -> None:
    """Validate 404 for nonexistent figure."""
    res = client.get("/figures/nonexistent_plot.png")
    assert res.status_code == 404


def test_cors_headers(client: FlaskClient) -> None:
    """Validate CORS headers are present on API responses."""
    res = client.get("/api/health")
    assert res.headers.get("Access-Control-Allow-Origin") == "*"


def test_method_not_allowed(client: FlaskClient) -> None:
    """Validate POST method rejection on read-only endpoints."""
    res = client.post("/api/system_overview")
    assert res.status_code == 405
