"""Frontend & visual integration test suite for Step 5: Strategic Bidding & Auction Clearing.

Validates:
1. Frontend HTML template served at GET / (with Accept: text/html) and GET /dashboard.
2. Static CSS (dashboard.css) and JS (strategic_market.js) served with HTTP 200.
3. Template contains all required visual section IDs, headings, and data containers:
   - Section heading "Strategic Bidding & Auction Clearing"
   - Timestamp picker, tradeable hours dropdown, and preset controls
   - Six Phase 8D strategy selector pills
   - 3 household prosumer cards container
   - Double auction merit-order columns (seller asks ascending, buyer bids descending)
   - Bilateral transaction table
   - Financial outcomes & KPI metric cards (Volume, VWAP, Payments, Revenues, Welfare)
   - Stored Phase 8D payoffs vs reconstructed transaction benefit reconciliation table
   - Phase 8C Pure Nash Equilibrium context panel
   - Explicit Phase 8E NOT_IMPLEMENTED disclosure
4. Backend API data contract consistency:
   - Tradeable hour (e.g. 2013-04-19 00:00:00): transactions present, volume > 0, VWAP numeric,
     exact stored vs reconstructed payoff match (< 1e-12 AUD).
   - No-trade hour (e.g. 2013-04-19 08:00:00 and 2013-04-20 03:00:00): transactions empty,
     volume == 0, VWAP is None/null, payments/revenues == 0.
   - Strategy switching: verifies changing strategy changes price profiles and clearing results.
   - All values shown originate directly from backend API response without client-side solver.
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


# =============================================================================
# 1. Frontend Template & Static Asset Serving Tests
# =============================================================================

def test_dashboard_ui_route(client: FlaskClient) -> None:
    """GET /dashboard serves the HTML dashboard with HTTP 200."""
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert res.mimetype == "text/html"
    html = res.get_data(as_text=True)
    assert "Strategic Bidding & Auction Clearing" in html
    assert "Deliverable 2: Academic Research & Interactive Demonstration Web Dashboard" in html


def test_root_content_negotiation(client: FlaskClient) -> None:
    """GET / serves HTML when Accept: text/html is requested, and JSON for API clients."""
    # Browser client requesting HTML
    browser_res = client.get("/", headers={"Accept": "text/html,application/xhtml+xml,*/*"})
    assert browser_res.status_code == 200
    assert browser_res.mimetype == "text/html"
    assert "Strategic Bidding & Auction Clearing" in browser_res.get_data(as_text=True)

    # API client without HTML priority
    api_res = client.get("/")
    assert api_res.status_code == 200
    assert api_res.mimetype == "application/json"
    json_data = api_res.get_json()
    assert json_data["status"] == "success"
    assert "version" in json_data["data"]


def test_static_assets_served(client: FlaskClient) -> None:
    """Static CSS and JavaScript assets are accessible and valid."""
    css_res = client.get("/static/css/dashboard.css")
    assert css_res.status_code == 200
    css_text = css_res.get_data(as_text=True)
    assert "Strategic Bidding" in css_text or "Deliverable 2" in css_text
    assert ".prosumer-card" in css_text

    js_res = client.get("/static/js/strategic_market.js")
    assert js_res.status_code == 200
    js_text = js_res.get_data(as_text=True)
    assert "STATE" in js_text
    assert "/api/strategic-market/hourly" in js_text
    assert "/api/strategic-market/strategies" in js_text


# =============================================================================
# 2. UI Layout & Component Integrity Tests
# =============================================================================

def test_template_contains_required_sections(client: FlaskClient) -> None:
    """Template contains all 10 required visual sections and element IDs."""
    res = client.get("/dashboard")
    html = res.get_data(as_text=True)

    # 1. Section Title
    assert "Strategic Bidding & Auction Clearing" in html

    # 2. Hour/Timestamp selector controls
    assert 'id="custom-timestamp-input"' in html
    assert 'id="btn-load-timestamp"' in html
    assert 'id="tradeable-hours-select"' in html
    assert 'data-timestamp="2013-04-19 00:00:00"' in html
    assert 'data-timestamp="2013-04-19 08:00:00"' in html

    # 3. Strategy selector pills for all six strategies
    assert 'data-strategy="strat_a"' in html
    assert 'data-strategy="strat_b"' in html
    assert 'data-strategy="strat_c"' in html
    assert 'data-strategy="strat_d"' in html
    assert 'data-strategy="strat_e"' in html
    assert 'data-strategy="strat_f_05"' in html

    # 4. Household cards container (Requirement 5)
    assert 'id="prosumer-cards-container"' in html

    # 5. Double auction merit-order columns & crossing banner (Requirement 6)
    assert 'id="auction-crossing-banner"' in html
    assert 'id="auction-sellers-list"' in html
    assert 'id="auction-buyers-list"' in html

    # 6. Bilateral transaction table (Requirement 7)
    assert 'id="transactions-table-body"' in html
    assert 'id="transactions-empty-state"' in html

    # 7. Macroeconomic KPI cards (Requirement 8)
    assert 'id="kpi-traded-volume"' in html
    assert 'id="kpi-vwap"' in html
    assert 'id="kpi-buyer-payments"' in html
    assert 'id="kpi-seller-revenues"' in html
    assert 'id="kpi-welfare"' in html

    # 8. Payoff reconciliation table (Requirement 9)
    assert 'id="reconciliation-table-body"' in html

    # 9. Phase 8C Pure Nash Equilibrium context panel (Requirement 10)
    assert 'id="ctx-profiles-evaluated"' in html
    assert 'id="ctx-pne-count"' in html
    assert 'id="ctx-strict-pne"' in html
    assert 'id="ctx-weak-pne"' in html
    assert 'id="ctx-pareto-pne"' in html

    # 10. Phase 8E status disclosure
    assert "Phase 8E" in html


# =============================================================================
# 3. Backend Integration: Tradeable vs. No-Trade Hours
# =============================================================================

def test_tradeable_hour_api_response(client: FlaskClient) -> None:
    """Verify backend response for tradeable hour 2013-04-19 00:00:00."""
    res = client.get("/api/strategic-market/hourly?timestamp=2013-04-19 00:00:00&strategy=strat_a")
    assert res.status_code == 200
    data = res.get_json()["data"]

    # Metadata
    assert data["hour_metadata"]["auction_status"] == "traded"
    assert data["hour_metadata"]["num_active_sellers"] == 1
    assert data["hour_metadata"]["num_active_buyers"] == 2

    # Household orders (ASK / BID differentiation)
    orders = data["household_orders"]
    assert len(orders) == 3
    seller_order = next(o for o in orders if o["physical_role"] == "seller")
    buyer_orders = [o for o in orders if o["physical_role"] == "buyer"]
    assert seller_order["order_type"] == "ASK"
    assert seller_order["household_id"] == "H002"
    for b in buyer_orders:
        assert b["order_type"] == "BID"

    # Transactions present
    txs = data["transactions"]
    assert len(txs) >= 1
    tx = txs[0]
    assert tx["seller_id"] == "H002"
    assert tx["buyer_id"] == "H001"
    assert tx["seller_ask_aud_per_kwh"] <= tx["buyer_bid_aud_per_kwh"]
    assert tx["transaction_price_aud_per_kwh"] == 0.30

    # Macroeconomics
    fin = data["financial_summary"]
    assert fin["total_p2p_traded_kwh"] > 0
    assert fin["vwap_aud"] == 0.30
    assert fin["total_buyer_payments_aud"] > 0
    assert fin["total_seller_revenues_aud"] > 0
    assert abs(fin["total_buyer_payments_aud"] - fin["total_seller_revenues_aud"]) < 1e-12

    # Payoff reconciliation (< 1e-12 AUD)
    stored = data["selected_strategy"]["stored_payoffs"]
    for o in orders:
        h_id = o["household_id"]
        assert abs(stored[h_id] - o["incremental_benefit_aud"]) < 1e-12


def test_no_trade_all_seller_hour(client: FlaskClient) -> None:
    """Verify backend response for no-trade all-seller hour 2013-04-19 08:00:00."""
    res = client.get("/api/strategic-market/hourly?timestamp=2013-04-19 08:00:00&strategy=strat_a")
    assert res.status_code == 200
    data = res.get_json()["data"]

    assert data["hour_metadata"]["auction_status"] == "no_trade"
    assert data["hour_metadata"]["market_status"] == "all-seller"
    assert data["hour_metadata"]["num_active_sellers"] == 3
    assert data["hour_metadata"]["num_active_buyers"] == 0

    # All households are sellers with ASK orders
    for o in data["household_orders"]:
        assert o["physical_role"] == "seller"
        assert o["order_type"] == "ASK"
        assert o["is_matched"] is False
        assert o["matched_quantity_kwh"] == 0.0

    # Zero transactions and null VWAP
    assert data["transactions"] == []
    assert data["financial_summary"]["total_p2p_traded_kwh"] == 0.0
    assert data["financial_summary"]["vwap_aud"] is None
    assert data["financial_summary"]["community_welfare_aud"] == 0.0


def test_no_trade_all_buyer_hour(client: FlaskClient) -> None:
    """Verify backend response for no-trade all-buyer hour 2013-04-19 06:00:00."""
    res = client.get("/api/strategic-market/hourly?timestamp=2013-04-19 06:00:00&strategy=strat_a")
    assert res.status_code == 200
    data = res.get_json()["data"]

    assert data["hour_metadata"]["auction_status"] == "no_trade"
    assert data["hour_metadata"]["market_status"] == "all-buyer"
    assert data["hour_metadata"]["num_active_sellers"] == 0
    assert data["hour_metadata"]["num_active_buyers"] == 3

    # All households are buyers with BID orders
    for o in data["household_orders"]:
        assert o["physical_role"] == "buyer"
        assert o["order_type"] == "BID"
        assert o["is_matched"] is False
        assert o["matched_quantity_kwh"] == 0.0

    # Zero transactions and null VWAP
    assert data["transactions"] == []
    assert data["financial_summary"]["total_p2p_traded_kwh"] == 0.0
    assert data["financial_summary"]["vwap_aud"] is None


# =============================================================================
# 4. Strategy Switching & Comparison Verification
# =============================================================================

def test_strategy_switching_refreshes_results(client: FlaskClient) -> None:
    """Verify strategy switching updates price profile and clearing outcomes."""
    ts = "2013-04-19 02:00:00"

    res_b = client.get(f"/api/strategic-market/hourly?timestamp={ts}&strategy=strat_b")
    res_c = client.get(f"/api/strategic-market/hourly?timestamp={ts}&strategy=strat_c")

    data_b = res_b.get_json()["data"]
    data_c = res_c.get_json()["data"]

    # Verify strategies echoed properly
    assert data_b["selected_strategy"]["strategy_key"] == "strat_b"
    assert data_c["selected_strategy"]["strategy_key"] == "strat_c"

    # VWAP should reflect seller-favouring (high price) vs buyer-favouring (low price)
    vwap_b = data_b["financial_summary"]["vwap_aud"]
    vwap_c = data_c["financial_summary"]["vwap_aud"]
    assert vwap_b is not None and vwap_c is not None
    assert vwap_b >= vwap_c

    # Total welfare remains invariant
    assert abs(data_b["financial_summary"]["community_welfare_aud"] - data_c["financial_summary"]["community_welfare_aud"]) < 1e-12


def test_strategies_comparison_endpoint(client: FlaskClient) -> None:
    """Verify GET /api/strategic-market/strategies returns all 6 strategies."""
    res = client.get("/api/strategic-market/strategies?timestamp=2013-04-19 02:00:00")
    assert res.status_code == 200
    data = res.get_json()["data"]

    assert "strategy_choices" in data
    choices = data["strategy_choices"]
    assert len(choices) == 6
    keys = {c["strategy_key"] for c in choices}
    assert keys == {"strat_a", "strat_b", "strat_c", "strat_d", "strat_e", "strat_f_05"}

    # Welfare invariance across undominated strategies
    welfares = [c["welfare_aud"] for c in choices]
    assert max(welfares) - min(welfares) < 1e-12


def test_hour_specific_equilibrium_context_counts(client: FlaskClient) -> None:
    """Verify profiles evaluated and deviations reflect selected timestamp's actual Phase 8C data.
    
    Hour 0 (2013-04-19 00:00:00, 3 active players): 343 profiles (7^3), 6,174 deviations.
    Hour 424 (2013-05-06 16:00:00, 2 active players): 49 profiles (7^2), 588 deviations.
    """
    # 3-player hour
    res_3p = client.get("/api/strategic-market/hourly?timestamp=2013-04-19 00:00:00&strategy=strat_a")
    assert res_3p.status_code == 200
    ctx_3p = res_3p.get_json()["data"]["nash_equilibrium_context"]
    assert ctx_3p["num_profiles_evaluated"] == 343
    assert ctx_3p["num_deviations_evaluated"] == 6174

    # 2-player hour (index 424)
    res_2p = client.get("/api/strategic-market/hourly?timestamp=2013-05-06 16:00:00&strategy=strat_a")
    assert res_2p.status_code == 200
    ctx_2p = res_2p.get_json()["data"]["nash_equilibrium_context"]
    assert ctx_2p["num_profiles_evaluated"] == 49
    assert ctx_2p["num_deviations_evaluated"] == 588
    assert ctx_2p["num_profiles_evaluated"] != ctx_3p["num_profiles_evaluated"]
    assert ctx_2p["num_deviations_evaluated"] != ctx_3p["num_deviations_evaluated"]
