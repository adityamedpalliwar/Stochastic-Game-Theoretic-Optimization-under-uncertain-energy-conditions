"""Tests for Step 4: Strategic Ask-Bid Integration for Dashboard Visualization.

Verifies the complete connected workflow:
  Physical roles/quantities → Selected Phase 8D ASK/BID prices
  → Existing double-auction clearing → Bilateral transaction prices and quantities
  → Household incremental benefits → Community welfare.

Phase 8E (stochastic strategic bidding) is NOT implemented and must not appear.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import ast

import numpy as np
import pandas as pd
import pytest

# Project root for file path resolution
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="module")
def phase8c_hourly():
    path = PROJECT_ROOT / "reports" / "phase8c_hourly_equilibria.csv"
    df = pd.read_csv(path)
    return df


@pytest.fixture(scope="module")
def phase8d_hourly():
    path = PROJECT_ROOT / "reports" / "phase8d_hourly_selection.csv"
    df = pd.read_csv(path)
    return df


@pytest.fixture(scope="module")
def first_tradeable_ts(phase8c_hourly):
    """Return the first timestamp where trading occurred (selected_traded_volume_kwh > 0)."""
    tradeable = phase8c_hourly[phase8c_hourly["selected_traded_volume_kwh"] > 0]
    return str(tradeable.iloc[0]["timestamp"])


@pytest.fixture(scope="module")
def data_service():
    from dashboard.data_service import DashboardDataService
    return DashboardDataService(project_root=PROJECT_ROOT)


@pytest.fixture(scope="module")
def flask_client(data_service):
    from dashboard.app import create_app
    app = create_app(data_service=data_service)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

# ============================================================================
# 1. Role Exposure Tests
# ============================================================================

def test_seller_price_exposed_as_ask(data_service, first_tradeable_ts, phase8c_hourly):
    """Selected Phase 8D seller price must be exposed as ASK order."""
    result = data_service.get_strategic_market_hourly(timestamp=first_tradeable_ts, strategy="strat_a")
    assert result is not None

    row_c = phase8c_hourly[phase8c_hourly["timestamp"] == first_tradeable_ts].iloc[0]
    for order in result["household_orders"]:
        hid = order["household_id"]
        role = str(row_c[f"{hid}_role"]).lower()
        if role == "seller":
            assert order["order_type"] == "ASK", f"{hid} is a seller but order_type is not ASK"
            assert order["selected_action_price_aud"] is not None
        elif role == "buyer":
            assert order["order_type"] == "BID", f"{hid} is a buyer but order_type is not BID"
            assert order["selected_action_price_aud"] is not None
        else:
            assert order["order_type"] == "NONE", f"{hid} is inactive but order_type is not NONE"
            assert order["selected_action_price_aud"] is None


def test_buyer_price_exposed_as_bid(data_service, first_tradeable_ts):
    """Selected Phase 8D buyer price must be exposed as BID order."""
    result = data_service.get_strategic_market_hourly(timestamp=first_tradeable_ts, strategy="strat_a")
    assert result is not None
    for order in result["household_orders"]:
        if order["physical_role"] == "buyer":
            assert order["order_type"] == "BID"


def test_inactive_households_have_no_order(data_service, phase8c_hourly):
    """Inactive households must return order_type NONE and null ask/bid price."""
    # Find an hour where at least one household is inactive
    inactive_rows = phase8c_hourly[phase8c_hourly["num_inactive_households"] > 0]
    if inactive_rows.empty:
        pytest.skip("No hours with inactive households in dataset")

    ts = str(inactive_rows.iloc[0]["timestamp"])
    result = data_service.get_strategic_market_hourly(timestamp=ts, strategy="strat_a")
    assert result is not None

    row_c = inactive_rows.iloc[0]
    for order in result["household_orders"]:
        hid = order["household_id"]
        if str(row_c[f"{hid}_role"]).lower() == "inactive":
            assert order["order_type"] == "NONE"
            assert order["selected_action_price_aud"] is None


def test_seller_ask_not_assigned_to_buyer(data_service, first_tradeable_ts, phase8c_hourly):
    """Seller asks must not be assigned to buyers and vice versa."""
    result = data_service.get_strategic_market_hourly(timestamp=first_tradeable_ts, strategy="strat_a")
    assert result is not None
    row_c = phase8c_hourly[phase8c_hourly["timestamp"] == first_tradeable_ts].iloc[0]
    for order in result["household_orders"]:
        hid = order["household_id"]
        role = str(row_c[f"{hid}_role"]).lower()
        order_type = order["order_type"]
        if role == "seller":
            assert order_type != "BID", f"Seller {hid} incorrectly assigned BID"
        elif role == "buyer":
            assert order_type != "ASK", f"Buyer {hid} incorrectly assigned ASK"


# ============================================================================
# 2. Clearing Function Integration Tests
# ============================================================================

def test_clearing_function_receives_correct_prices(data_service, first_tradeable_ts, phase8d_hourly):
    """Clearing function must receive the selected Phase 8D price profile."""
    from src.game.strategic_market import (
        clear_strategic_double_auction, MarketOrder, MarketRole
    )

    row_d = phase8d_hourly[phase8d_hourly["timestamp"] == first_tradeable_ts].iloc[0]
    raw = str(row_d["strat_a_price_profile"])
    try:
        profile = ast.literal_eval(raw)
    except Exception:
        profile = json.loads(raw.replace("'", '"'))

    result = data_service.get_strategic_market_hourly(timestamp=first_tradeable_ts, strategy="strat_a")
    assert result is not None

    # Verify price profile in result matches stored profile
    displayed_profile = result["selected_strategy"]["price_profile"]
    for hid, expected_price in profile.items():
        assert abs(float(displayed_profile.get(hid, -1)) - float(expected_price)) < 1e-6, \
            f"Displayed price for {hid} ({displayed_profile.get(hid)}) != stored ({expected_price})"


def test_crossing_condition_satisfied(data_service, first_tradeable_ts):
    """Every cleared transaction must satisfy bid >= ask - tolerance."""
    result = data_service.get_strategic_market_hourly(timestamp=first_tradeable_ts, strategy="strat_a")
    assert result is not None
    tol = 1e-6
    for tx in result["transactions"]:
        bid = float(tx["buyer_bid_aud_per_kwh"])
        ask = float(tx["seller_ask_aud_per_kwh"])
        assert bid >= ask - tol, f"Crossing condition violated: bid={bid} < ask={ask}"


def test_transaction_price_is_midpoint(data_service, first_tradeable_ts):
    """Transaction price must equal (ask + bid) / 2 for each transaction."""
    result = data_service.get_strategic_market_hourly(timestamp=first_tradeable_ts, strategy="strat_a")
    assert result is not None
    tol = 1e-6
    for tx in result["transactions"]:
        expected_price = (float(tx["seller_ask_aud_per_kwh"]) + float(tx["buyer_bid_aud_per_kwh"])) / 2.0
        actual_price = float(tx["transaction_price_aud_per_kwh"])
        assert abs(actual_price - expected_price) < tol, \
            f"Transaction price {actual_price} != midpoint {expected_price}"


def test_matched_quantities_balance(data_service, first_tradeable_ts):
    """Total seller matched quantity must equal total buyer matched quantity."""
    result = data_service.get_strategic_market_hourly(timestamp=first_tradeable_ts, strategy="strat_a")
    assert result is not None
    total_sold = sum(
        o["matched_quantity_kwh"] for o in result["household_orders"]
        if o["physical_role"] == "seller"
    )
    total_bought = sum(
        o["matched_quantity_kwh"] for o in result["household_orders"]
        if o["physical_role"] == "buyer"
    )
    assert abs(total_sold - total_bought) < 1e-6, \
        f"Energy conservation violation: sold={total_sold} != bought={total_bought}"


def test_buyer_payments_equal_seller_revenues(data_service, first_tradeable_ts):
    """Total buyer payments must equal total seller revenues."""
    result = data_service.get_strategic_market_hourly(timestamp=first_tradeable_ts, strategy="strat_a")
    assert result is not None
    total_payments = result["financial_summary"]["total_buyer_payments_aud"]
    total_revenues = result["financial_summary"]["total_seller_revenues_aud"]
    assert abs(total_payments - total_revenues) < 1e-6, \
        f"Financial balance violation: payments={total_payments} != revenues={total_revenues}"


# ============================================================================
# 3. No-Trade Hour Tests
# ============================================================================

def test_no_trade_hour_returns_empty_transactions(data_service, phase8c_hourly):
    """Hours with no trade must return empty transaction list and null VWAP."""
    no_trade = phase8c_hourly[phase8c_hourly["selected_traded_volume_kwh"] < 1e-6]
    if no_trade.empty:
        pytest.skip("All hours have trade in the dataset")
    ts = str(no_trade.iloc[0]["timestamp"])
    result = data_service.get_strategic_market_hourly(timestamp=ts, strategy="strat_a")
    assert result is not None
    assert result["financial_summary"]["total_p2p_traded_kwh"] < 1e-6
    assert result["transactions"] == [], f"Expected empty transactions but got {result['transactions']}"
    assert result["financial_summary"]["vwap_aud"] is None, "VWAP must be null when no trade"


# ============================================================================
# 4. Strategy Switching Tests
# ============================================================================

def test_changing_strategy_changes_displayed_profile(data_service, phase8d_hourly):
    """Changing the strategy must change the displayed profile when stored strategies differ."""
    # Find an hour where strategy A and B differ
    for _, row in phase8d_hourly.iterrows():
        a_profile_str = str(row["strat_a_price_profile"])
        b_profile_str = str(row["strat_b_price_profile"])
        if a_profile_str != b_profile_str:
            ts = str(row["timestamp"])
            result_a = data_service.get_strategic_market_hourly(timestamp=ts, strategy="strat_a")
            result_b = data_service.get_strategic_market_hourly(timestamp=ts, strategy="strat_b")
            assert result_a is not None
            assert result_b is not None
            assert result_a["selected_strategy"]["price_profile"] != result_b["selected_strategy"]["price_profile"], \
                "Switching strategy must change displayed profile"
            return
    pytest.skip("No hours found where strategy A and B differ")


def test_strategy_not_substituted_silently(data_service, first_tradeable_ts):
    """Selecting strategy B must not silently return strategy A results."""
    result_a = data_service.get_strategic_market_hourly(timestamp=first_tradeable_ts, strategy="strat_a")
    result_b = data_service.get_strategic_market_hourly(timestamp=first_tradeable_ts, strategy="strat_b")
    assert result_a is not None
    assert result_b is not None
    # Strategy key in response must match requested strategy
    assert result_a["selected_strategy"]["strategy_key"] == "strat_a"
    assert result_b["selected_strategy"]["strategy_key"] == "strat_b"


# ============================================================================
# 5. Household Benefit Tests
# ============================================================================

def test_household_incremental_benefits_match_clearing(data_service, first_tradeable_ts):
    """Household benefits must trace back to clearing function results."""
    from src.game.strategic_market import (
        MarketOrder, MarketRole, clear_strategic_double_auction,
        DEFAULT_GRID_IMPORT_TARIFF_AUD, DEFAULT_GRID_EXPORT_CREDIT_AUD
    )

    result = data_service.get_strategic_market_hourly(timestamp=first_tradeable_ts, strategy="strat_a")
    assert result is not None

    # Rebuild orders from the result's profile to verify benefit calculation
    orders = []
    for order in result["household_orders"]:
        if order["order_type"] in ("ASK", "BID"):
            role = MarketRole.SELLER if order["order_type"] == "ASK" else MarketRole.BUYER
            orders.append(MarketOrder(
                household_id=order["household_id"],
                role=role,
                price_aud_per_kwh=float(order["selected_action_price_aud"]),
                quantity_kwh=float(order["available_quantity_kwh"]),
            ))

    reference_result = clear_strategic_double_auction(
        orders=orders,
        grid_import_tariff_aud=DEFAULT_GRID_IMPORT_TARIFF_AUD,
        grid_export_credit_aud=DEFAULT_GRID_EXPORT_CREDIT_AUD,
        all_households=["H001", "H002", "H003"],
    )

    for hid in ["H001", "H002", "H003"]:
        expected_benefit = (
            reference_result.seller_incremental_benefits_aud.get(hid, 0.0)
            + reference_result.buyer_incremental_benefits_aud.get(hid, 0.0)
        )
        displayed = result["household_financial_outcomes"][hid]["incremental_benefit_aud"]
        assert abs(float(displayed) - expected_benefit) < 1e-6, \
            f"Benefit mismatch for {hid}: displayed={displayed}, expected={expected_benefit}"


def test_welfare_identity(data_service, first_tradeable_ts):
    """Community welfare must equal (p_imp - p_exp) * Q_traded = 0.22 * Q."""
    result = data_service.get_strategic_market_hourly(timestamp=first_tradeable_ts, strategy="strat_a")
    assert result is not None
    total_traded = result["financial_summary"]["total_p2p_traded_kwh"]
    welfare = result["financial_summary"]["community_welfare_aud"]
    expected_welfare = 0.22 * total_traded
    assert abs(welfare - expected_welfare) < 1e-4, \
        f"Welfare identity violated: welfare={welfare} != 0.22 * {total_traded} = {expected_welfare}"


# ============================================================================
# 6. API Endpoint Tests
# ============================================================================

def test_strategic_market_hourly_endpoint_success(flask_client, first_tradeable_ts):
    """GET /api/strategic-market/hourly must return 200 with correct structure."""
    import urllib.parse
    ts_encoded = urllib.parse.quote(first_tradeable_ts)
    response = flask_client.get(f"/api/strategic-market/hourly?timestamp={ts_encoded}&strategy=strat_a")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "success"
    data = body["data"]
    assert "timestamp" in data
    assert "household_orders" in data
    assert "transactions" in data
    assert "financial_summary" in data
    assert "selected_strategy" in data
    assert "strategic_price_grid" in data


def test_strategic_market_hourly_invalid_timestamp(flask_client):
    """Invalid timestamp must return 404."""
    response = flask_client.get("/api/strategic-market/hourly?timestamp=9999-01-01+00:00:00&strategy=strat_a")
    assert response.status_code == 404


def test_strategic_market_hourly_invalid_strategy(flask_client, first_tradeable_ts):
    """Invalid strategy name must return 400."""
    import urllib.parse
    ts_encoded = urllib.parse.quote(first_tradeable_ts)
    response = flask_client.get(f"/api/strategic-market/hourly?timestamp={ts_encoded}&strategy=strat_z_invalid")
    assert response.status_code == 400


def test_strategic_market_hourly_missing_timestamp(flask_client):
    """Missing timestamp parameter must return 400."""
    response = flask_client.get("/api/strategic-market/hourly?strategy=strat_a")
    assert response.status_code == 400


def test_strategic_market_strategies_endpoint(flask_client, first_tradeable_ts):
    """GET /api/strategic-market/strategies must return all 6 strategy choices."""
    import urllib.parse
    ts_encoded = urllib.parse.quote(first_tradeable_ts)
    response = flask_client.get(f"/api/strategic-market/strategies?timestamp={ts_encoded}")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "success"
    data = body["data"]
    assert "strategy_choices" in data
    assert len(data["strategy_choices"]) == 6


def test_strategic_market_strategies_missing_timestamp(flask_client):
    """Missing timestamp for strategies endpoint must return 400."""
    response = flask_client.get("/api/strategic-market/strategies")
    assert response.status_code == 400


def test_strategic_market_strategies_invalid_timestamp(flask_client):
    """Invalid timestamp for strategies endpoint must return 404."""
    response = flask_client.get("/api/strategic-market/strategies?timestamp=9999-01-01+00:00:00")
    assert response.status_code == 404


# ============================================================================
# 7. Phase 7 Preservation Tests
# ============================================================================

def test_phase7_p2p_benchmarks_unchanged(flask_client):
    """Phase 7 P2P benchmark endpoint must still return correct data."""
    response = flask_client.get("/api/p2p_benchmarks")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "success"
    assert len(body["data"]) == 32  # 32 rows in Phase 7 benchmark table


def test_phase7_nash_hour_unchanged(flask_client):
    """Phase 7 nash_hour endpoint must still return correct data."""
    response = flask_client.get("/api/nash_hour")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "success"


# ============================================================================
# 8. Phase 8E Absence Tests
# ============================================================================

def test_no_phase8e_implementation(data_service, first_tradeable_ts):
    """Strategic market result must declare Phase 8E as NOT_IMPLEMENTED."""
    result = data_service.get_strategic_market_hourly(timestamp=first_tradeable_ts, strategy="strat_a")
    assert result is not None
    assert "NOT_IMPLEMENTED" in str(result.get("phase_8e_status", "")), \
        "Phase 8E status must declare NOT_IMPLEMENTED"


def test_no_stochastic_claims_in_response(data_service, first_tradeable_ts):
    """Response must not contain stochastic Nash equilibrium claims."""
    result = data_service.get_strategic_market_hourly(timestamp=first_tradeable_ts, strategy="strat_a")
    result_str = json.dumps(result)
    forbidden_phrases = [
        "stochastic_nash", "ex_ante_nash", "monte_carlo_strategic",
        "phase_8e_results", "8e_implemented"
    ]
    for phrase in forbidden_phrases:
        assert phrase.lower() not in result_str.lower(), \
            f"Forbidden Phase 8E claim found in response: {phrase}"


# ============================================================================
# 9. Strategic Price Grid Tests
# ============================================================================

def test_strategic_price_grid_is_exact(data_service, first_tradeable_ts):
    """Strategic price grid must be exactly [0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30]."""
    result = data_service.get_strategic_market_hourly(timestamp=first_tradeable_ts, strategy="strat_a")
    assert result is not None
    expected = [0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30]
    actual = result["strategic_price_grid"]
    assert len(actual) == 7
    for exp, act in zip(expected, actual):
        assert abs(exp - act) < 1e-9, f"Price grid element mismatch: expected {exp}, got {act}"


def test_selected_prices_come_from_grid(data_service, first_tradeable_ts):
    """Selected ASK/BID prices must all belong to the strategic price grid."""
    result = data_service.get_strategic_market_hourly(timestamp=first_tradeable_ts, strategy="strat_a")
    assert result is not None
    grid = set(result["strategic_price_grid"])
    for order in result["household_orders"]:
        price = order["selected_action_price_aud"]
        if price is not None:
            assert any(abs(price - g) < 1e-9 for g in grid), \
                f"Price {price} for {order['household_id']} not in strategic price grid {sorted(grid)}"


# ============================================================================
# 10. Transaction Source Documentation Test
# ============================================================================

def test_transaction_source_documented(data_service, first_tradeable_ts):
    """Response must document that transactions are reconstructed via existing clearing function."""
    result = data_service.get_strategic_market_hourly(timestamp=first_tradeable_ts, strategy="strat_a")
    assert result is not None
    assert "transaction_source" in result
    assert "reconstructed" in str(result["transaction_source"]).lower() or \
           "existing_clearing" in str(result["transaction_source"]).lower()
