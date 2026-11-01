"""Unit tests for Phase 8B.1: Price-Only Strategic Double-Auction Market Engine.

Tests:
1. One seller, one buyer (Hand-calculated benchmark).
2. One seller, two buyers (Iterative matching by highest bid).
3. Two sellers, one buyer (Iterative matching by lowest ask).
4. Tied seller prices (Pro-rata allocation across sellers).
5. Tied buyer prices (Pro-rata allocation across buyers).
6. Simultaneous tied seller and buyer groups (2x2 bilateral decomposition).
7. Uncrossed order book (Bid < Ask -> Zero trade).
8. Inactive households and zero-flow handling.
9. All-seller hour and all-buyer hour boundary cases.
10. Input validation: invalid price outside grid, negative quantity, non-finite values.
11. Energy conservation, financial balance, and welfare identity invariants.
12. Physical net-position helper functions and order factory.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.game.strategic_market import (
    DEFAULT_GRID_EXPORT_CREDIT_AUD,
    DEFAULT_GRID_IMPORT_TARIFF_AUD,
    STRATEGIC_PRICE_GRID,
    MarketOrder,
    MarketRole,
    StrategicMarketResult,
    StrategicTransaction,
    clear_strategic_double_auction,
    compute_physical_net_position,
    create_order_from_physical_position,
    is_valid_strategic_price,
    validate_market_configuration,
    validate_price_grid,
)


# =============================================================================
# 1. HAND-CALCULATED BENCHMARK TESTS
# =============================================================================

def test_scenario_1_one_seller_one_buyer():
    """Test 1: One seller, one buyer.

    Seller H001: Surplus = 2.0 kWh, Ask = $0.16/kWh
    Buyer H002:  Deficit = 1.5 kWh, Bid = $0.22/kWh
    Expected:
      - Traded volume = 1.5 kWh
      - Midpoint transaction price = (0.16 + 0.22) / 2 = $0.19/kWh
      - Seller revenue = 1.5 * 0.19 = $0.285 AUD
      - Buyer payment  = 1.5 * 0.19 = $0.285 AUD
      - Seller incremental benefit = 1.5 * (0.19 - 0.08) = $0.165 AUD
      - Buyer incremental benefit  = 1.5 * (0.30 - 0.19) = $0.165 AUD
      - Community welfare = $0.165 + $0.165 = $0.330 AUD (= 0.22 * 1.5)
      - Unmatched seller surplus = 0.5 kWh, unmet buyer deficit = 0.0 kWh
    """
    s1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=2.0)
    b2 = MarketOrder("H002", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=1.5)

    res = clear_strategic_double_auction([s1, b2])

    assert len(res.transactions) == 1
    assert pytest.approx(res.total_traded_kwh, abs=1e-6) == 1.5
    assert pytest.approx(res.weighted_average_transaction_price_aud, abs=1e-6) == 0.19

    tx = res.transactions[0]
    assert tx.seller_id == "H001"
    assert tx.buyer_id == "H002"
    assert pytest.approx(tx.traded_energy_kwh, abs=1e-6) == 1.5
    assert pytest.approx(tx.price_aud_per_kwh, abs=1e-6) == 0.19
    assert pytest.approx(tx.seller_revenue_aud, abs=1e-6) == 0.285
    assert pytest.approx(tx.buyer_payment_aud, abs=1e-6) == 0.285

    assert pytest.approx(res.seller_revenues_aud["H001"], abs=1e-6) == 0.285
    assert pytest.approx(res.buyer_payments_aud["H002"], abs=1e-6) == 0.285
    assert pytest.approx(res.seller_incremental_benefits_aud["H001"], abs=1e-6) == 0.165
    assert pytest.approx(res.buyer_incremental_benefits_aud["H002"], abs=1e-6) == 0.165
    assert pytest.approx(res.community_incremental_welfare_aud, abs=1e-6) == 0.330

    assert pytest.approx(res.unmatched_seller_surplus_kwh["H001"], abs=1e-6) == 0.5
    assert pytest.approx(res.unmatched_buyer_deficit_kwh["H002"], abs=1e-6) == 0.0


def test_scenario_2_one_seller_two_buyers():
    """Test 2: One seller, two buyers on standard strategic price grid P.

    Seller H001: Surplus = 3.0 kWh, Ask = $0.12/kWh
    Buyer 1 H002: Deficit = 1.0 kWh, Bid = $0.22/kWh
    Buyer 2 H003: Deficit = 2.0 kWh, Bid = $0.19/kWh
    Expected:
      - Both buyers served completely (total trade = 3.0 kWh)
      - Buyer 1 (H002) has higher bid ($0.22 > $0.19), so matches first:
        TX1: H001 -> H002, 1.0 kWh @ (0.12 + 0.22)/2 = $0.17/kWh, Payment = $0.170 AUD
      - Buyer 2 (H003) matches second:
        TX2: H001 -> H003, 2.0 kWh @ (0.12 + 0.19)/2 = $0.155/kWh, Payment = $0.310 AUD
      - Total revenue for H001 = $0.170 + $0.310 = $0.480 AUD
      - Total payments = $0.170 (H002) + $0.310 (H003) = $0.480 AUD
      - Welfare = 0.22 * 3.0 = $0.660 AUD
      - Weighted average price = 0.48 / 3.0 = $0.160 AUD/kWh
    """
    s1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.12, quantity_kwh=3.0)
    b2 = MarketOrder("H002", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=1.0)
    b3 = MarketOrder("H003", MarketRole.BUYER, price_aud_per_kwh=0.19, quantity_kwh=2.0)

    res = clear_strategic_double_auction([s1, b2, b3])

    assert len(res.transactions) == 2
    assert pytest.approx(res.total_traded_kwh, abs=1e-6) == 3.0
    assert res.rounds_executed == 2

    tx1, tx2 = res.transactions[0], res.transactions[1]
    # First match must be H002
    assert tx1.buyer_id == "H002"
    assert pytest.approx(tx1.traded_energy_kwh, abs=1e-6) == 1.0
    assert pytest.approx(tx1.price_aud_per_kwh, abs=1e-6) == 0.17
    assert pytest.approx(tx1.buyer_payment_aud, abs=1e-6) == 0.170

    # Second match must be H003
    assert tx2.buyer_id == "H003"
    assert pytest.approx(tx2.traded_energy_kwh, abs=1e-6) == 2.0
    assert pytest.approx(tx2.price_aud_per_kwh, abs=1e-6) == 0.155
    assert pytest.approx(tx2.buyer_payment_aud, abs=1e-6) == 0.310

    # Revenues and payments
    assert pytest.approx(res.seller_revenues_aud["H001"], abs=1e-6) == 0.480
    assert pytest.approx(res.buyer_payments_aud["H002"], abs=1e-6) == 0.170
    assert pytest.approx(res.buyer_payments_aud["H003"], abs=1e-6) == 0.310

    # Benefits
    # H001: 1.0 * (0.17 - 0.08) + 2.0 * (0.155 - 0.08) = 0.09 + 0.15 = $0.240 AUD
    assert pytest.approx(res.seller_incremental_benefits_aud["H001"], abs=1e-6) == 0.240
    # H002: 1.0 * (0.30 - 0.17) = $0.130 AUD
    assert pytest.approx(res.buyer_incremental_benefits_aud["H002"], abs=1e-6) == 0.130
    # H003: 2.0 * (0.30 - 0.155) = $0.290 AUD
    assert pytest.approx(res.buyer_incremental_benefits_aud["H003"], abs=1e-6) == 0.290
    # Community: 0.240 + 0.130 + 0.290 = $0.660 AUD
    assert pytest.approx(res.community_incremental_welfare_aud, abs=1e-6) == 0.660
    assert pytest.approx(res.weighted_average_transaction_price_aud, abs=1e-6) == 0.160


def test_scenario_3_two_sellers_one_buyer():
    """Test 3: Two sellers, one buyer.

    Seller 1 H001: Surplus = 1.0 kWh, Ask = $0.12/kWh
    Seller 2 H002: Surplus = 2.0 kWh, Ask = $0.16/kWh
    Buyer H003:    Deficit = 2.0 kWh, Bid = $0.22/kWh
    Expected:
      - Seller 1 (H001) has lowest ask ($0.12 < $0.16), so clears first:
        TX1: H001 -> H003, 1.0 kWh @ (0.12 + 0.22)/2 = $0.17/kWh, Payment = $0.170 AUD
      - Seller 2 (H002) supplies remaining 1.0 kWh:
        TX2: H002 -> H003, 1.0 kWh @ (0.16 + 0.22)/2 = $0.19/kWh, Payment = $0.190 AUD
      - Total trade = 2.0 kWh
      - Seller 2 has 1.0 kWh unmatched surplus
    """
    s1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.12, quantity_kwh=1.0)
    s2 = MarketOrder("H002", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=2.0)
    b3 = MarketOrder("H003", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=2.0)

    res = clear_strategic_double_auction([s1, s2, b3])

    assert len(res.transactions) == 2
    assert pytest.approx(res.total_traded_kwh, abs=1e-6) == 2.0

    tx1, tx2 = res.transactions[0], res.transactions[1]
    assert tx1.seller_id == "H001"
    assert pytest.approx(tx1.traded_energy_kwh, abs=1e-6) == 1.0
    assert pytest.approx(tx1.price_aud_per_kwh, abs=1e-6) == 0.17

    assert tx2.seller_id == "H002"
    assert pytest.approx(tx2.traded_energy_kwh, abs=1e-6) == 1.0
    assert pytest.approx(tx2.price_aud_per_kwh, abs=1e-6) == 0.19

    assert pytest.approx(res.seller_allocations_kwh["H001"], abs=1e-6) == 1.0
    assert pytest.approx(res.seller_allocations_kwh["H002"], abs=1e-6) == 1.0
    assert pytest.approx(res.unmatched_seller_surplus_kwh["H002"], abs=1e-6) == 1.0
    assert pytest.approx(res.community_incremental_welfare_aud, abs=1e-6) == 0.440


def test_scenario_4_tied_seller_prices():
    """Test 4: Tied seller prices.

    Two sellers: Each has 2.0 kWh, Both ask $0.16/kWh
    One buyer:   Deficit = 2.0 kWh, Bid = $0.22/kWh
    Expected:
      - Tied ask group at $0.16: H001 (2.0) and H002 (2.0). Total supply = 4.0 kWh.
      - Buyer needs 2.0 kWh.
      - Pro-rata allocation: Each seller sells 2.0 * (2.0 / 4.0) = 1.0 kWh.
      - Total trade = 2.0 kWh.
      - Price = (0.16 + 0.22) / 2 = $0.19/kWh.
      - Strict symmetry: Both sellers receive identical allocation and revenue ($0.190 AUD).
    """
    s1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=2.0)
    s2 = MarketOrder("H002", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=2.0)
    b3 = MarketOrder("H003", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=2.0)

    res = clear_strategic_double_auction([s1, s2, b3])

    assert len(res.transactions) == 2
    assert pytest.approx(res.total_traded_kwh, abs=1e-6) == 2.0

    assert pytest.approx(res.seller_allocations_kwh["H001"], abs=1e-6) == 1.0
    assert pytest.approx(res.seller_allocations_kwh["H002"], abs=1e-6) == 1.0
    assert pytest.approx(res.buyer_allocations_kwh["H003"], abs=1e-6) == 2.0

    assert pytest.approx(res.seller_revenues_aud["H001"], abs=1e-6) == 0.190
    assert pytest.approx(res.seller_revenues_aud["H002"], abs=1e-6) == 0.190
    assert pytest.approx(res.buyer_payments_aud["H003"], abs=1e-6) == 0.380

    for tx in res.transactions:
        assert pytest.approx(tx.price_aud_per_kwh, abs=1e-6) == 0.19
        assert pytest.approx(tx.traded_energy_kwh, abs=1e-6) == 1.0


def test_scenario_5_tied_buyer_prices():
    """Test 5: Tied buyer prices.

    One seller: Surplus = 2.0 kWh, Ask = $0.16/kWh
    Two buyers: Each has 2.0 kWh deficit, Both bid $0.22/kWh
    Expected:
      - Tied bid group at $0.22: H002 (2.0) and H003 (2.0). Total demand = 4.0 kWh.
      - Seller supplies 2.0 kWh.
      - Pro-rata allocation: Each buyer buys 2.0 * (2.0 / 4.0) = 1.0 kWh.
      - Total trade = 2.0 kWh.
      - Both buyers receive identical 1.0 kWh allocation and pay $0.190 AUD each.
    """
    s1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=2.0)
    b2 = MarketOrder("H002", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=2.0)
    b3 = MarketOrder("H003", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=2.0)

    res = clear_strategic_double_auction([s1, b2, b3])

    assert len(res.transactions) == 2
    assert pytest.approx(res.total_traded_kwh, abs=1e-6) == 2.0

    assert pytest.approx(res.seller_allocations_kwh["H001"], abs=1e-6) == 2.0
    assert pytest.approx(res.buyer_allocations_kwh["H002"], abs=1e-6) == 1.0
    assert pytest.approx(res.buyer_allocations_kwh["H003"], abs=1e-6) == 1.0

    assert pytest.approx(res.seller_revenues_aud["H001"], abs=1e-6) == 0.380
    assert pytest.approx(res.buyer_payments_aud["H002"], abs=1e-6) == 0.190
    assert pytest.approx(res.buyer_payments_aud["H003"], abs=1e-6) == 0.190


def test_scenario_6_simultaneous_tied_seller_and_buyer_groups():
    """Test 6: Simultaneous tied seller and buyer groups.

    Two sellers: Surplus = 2.0 kWh each, Ask = $0.16 each
    Two buyers:  Deficit = 2.0 kWh each, Bid = $0.22 each
    Expected:
      - Total supply = 4.0 kWh, Total demand = 4.0 kWh.
      - Q_trade = 4.0 kWh.
      - Bilateral transaction decomposition matrix (2x2):
        Each q_ij = (2.0 * 2.0) / 4.0 = 1.0 kWh.
      - Exactly 4 transactions, each trading 1.0 kWh @ $0.19/kWh.
      - Each seller receives 2.0 kWh total allocation.
      - Each buyer receives 2.0 kWh total allocation.
    """
    s1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=2.0)
    s2 = MarketOrder("H002", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=2.0)
    b3 = MarketOrder("H003", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=2.0)
    b4 = MarketOrder("H004", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=2.0)

    res = clear_strategic_double_auction([s1, s2, b3, b4])

    assert len(res.transactions) == 4
    assert pytest.approx(res.total_traded_kwh, abs=1e-6) == 4.0

    assert pytest.approx(res.seller_allocations_kwh["H001"], abs=1e-6) == 2.0
    assert pytest.approx(res.seller_allocations_kwh["H002"], abs=1e-6) == 2.0
    assert pytest.approx(res.buyer_allocations_kwh["H003"], abs=1e-6) == 2.0
    assert pytest.approx(res.buyer_allocations_kwh["H004"], abs=1e-6) == 2.0

    for tx in res.transactions:
        assert pytest.approx(tx.traded_energy_kwh, abs=1e-6) == 1.0
        assert pytest.approx(tx.price_aud_per_kwh, abs=1e-6) == 0.19
        assert pytest.approx(tx.seller_revenue_aud, abs=1e-6) == 0.190
        assert pytest.approx(tx.buyer_payment_aud, abs=1e-6) == 0.190


def test_scenario_7_uncrossed_order_book():
    """Test 7: Uncrossed order book.

    Seller H001: Surplus = 2.0 kWh, Ask = $0.26/kWh
    Buyer H002:  Deficit = 2.0 kWh, Bid = $0.22/kWh
    Expected:
      - Bid ($0.22) < Ask ($0.26) -> Order book does not cross.
      - Total trade = 0.0 kWh.
      - Transactions list is empty.
      - Unmatched surplus = 2.0 kWh, Unmatched deficit = 2.0 kWh.
      - Community welfare = $0.00 AUD.
      - Weighted average price is None.
    """
    s1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.26, quantity_kwh=2.0)
    b2 = MarketOrder("H002", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=2.0)

    res = clear_strategic_double_auction([s1, b2])

    assert len(res.transactions) == 0
    assert res.total_traded_kwh == 0.0
    assert res.weighted_average_transaction_price_aud is None
    assert pytest.approx(res.unmatched_seller_surplus_kwh["H001"], abs=1e-6) == 2.0
    assert pytest.approx(res.unmatched_buyer_deficit_kwh["H002"], abs=1e-6) == 2.0
    assert pytest.approx(res.community_incremental_welfare_aud, abs=1e-6) == 0.0


def test_multi_price_level_double_auction_custom_grid():
    """Test multi-level order-book matching across multiple distinct price levels on both sides.

    Required code review example:
    Sellers:
      - S1 (H001): 1.0 kWh at $0.12/kWh
      - S2 (H002): 2.0 kWh at $0.16/kWh
    Buyers:
      - B1 (H003): 1.0 kWh at $0.22/kWh
      - B2 (H004): 2.0 kWh at $0.20/kWh

    Explicit custom grid containing $0.20:
      (0.08, 0.12, 0.16, 0.19, 0.20, 0.22, 0.26, 0.30)

    Expected:
      - Round 1: S1 (best ask $0.12) matches B1 (best bid $0.22):
        TX1: S1 -> B1: 1.0 kWh @ (0.12 + 0.22) / 2 = $0.17/kWh
      - Round 2: S2 (next ask $0.16) matches B2 (next bid $0.20):
        TX2: S2 -> B2: 2.0 kWh @ (0.16 + 0.20) / 2 = $0.18/kWh
      - Total trade: 1.0 + 2.0 = 3.0 kWh
      - Weighted average price: (1.0 * 0.17 + 2.0 * 0.18) / 3.0 = 0.53 / 3 = 0.1766667 AUD/kWh
      - Total community welfare: (0.30 - 0.08) * 3.0 = $0.660 AUD
      - Exactly 2 matching rounds executed.
    """
    custom_grid = (0.08, 0.12, 0.16, 0.19, 0.20, 0.22, 0.26, 0.30)
    s1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.12, quantity_kwh=1.0, allowed_price_grid=custom_grid)
    s2 = MarketOrder("H002", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=2.0, allowed_price_grid=custom_grid)
    b1 = MarketOrder("H003", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=1.0, allowed_price_grid=custom_grid)
    b2 = MarketOrder("H004", MarketRole.BUYER, price_aud_per_kwh=0.20, quantity_kwh=2.0, allowed_price_grid=custom_grid)

    res = clear_strategic_double_auction([s1, s2, b1, b2], price_grid=custom_grid)

    assert len(res.transactions) == 2
    assert pytest.approx(res.total_traded_kwh, abs=1e-6) == 3.0
    assert res.rounds_executed == 2

    tx1, tx2 = res.transactions[0], res.transactions[1]
    assert tx1.seller_id == "H001" and tx1.buyer_id == "H003"
    assert pytest.approx(tx1.traded_energy_kwh, abs=1e-6) == 1.0
    assert pytest.approx(tx1.price_aud_per_kwh, abs=1e-6) == 0.17
    assert pytest.approx(tx1.seller_revenue_aud, abs=1e-6) == 0.170
    assert pytest.approx(tx1.buyer_payment_aud, abs=1e-6) == 0.170

    assert tx2.seller_id == "H002" and tx2.buyer_id == "H004"
    assert pytest.approx(tx2.traded_energy_kwh, abs=1e-6) == 2.0
    assert pytest.approx(tx2.price_aud_per_kwh, abs=1e-6) == 0.18
    assert pytest.approx(tx2.seller_revenue_aud, abs=1e-6) == 0.360
    assert pytest.approx(tx2.buyer_payment_aud, abs=1e-6) == 0.360

    expected_avg_price = (1.0 * 0.17 + 2.0 * 0.18) / 3.0
    assert pytest.approx(res.weighted_average_transaction_price_aud, abs=1e-6) == expected_avg_price
    assert pytest.approx(res.community_incremental_welfare_aud, abs=1e-6) == 0.660
    assert pytest.approx(res.unmatched_seller_surplus_kwh["H001"], abs=1e-6) == 0.0
    assert pytest.approx(res.unmatched_seller_surplus_kwh["H002"], abs=1e-6) == 0.0
    assert pytest.approx(res.unmatched_buyer_deficit_kwh["H003"], abs=1e-6) == 0.0
    assert pytest.approx(res.unmatched_buyer_deficit_kwh["H004"], abs=1e-6) == 0.0


def test_multi_price_level_double_auction_standard_grid():
    """Test multi-level order matching on default strategic price grid P.

    Sellers:
      - S1 (H001): 1.0 kWh at $0.12/kWh
      - S2 (H002): 2.0 kWh at $0.16/kWh
    Buyers:
      - B1 (H003): 1.0 kWh at $0.26/kWh
      - B2 (H004): 2.0 kWh at $0.22/kWh

    Expected:
      - Round 1: S1 (best ask $0.12) matches B1 (best bid $0.26):
        TX1: S1 -> B1: 1.0 kWh @ (0.12 + 0.26)/2 = $0.19/kWh
      - Round 2: S2 (next ask $0.16) matches B2 (next bid $0.22):
        TX2: S2 -> B2: 2.0 kWh @ (0.16 + 0.22)/2 = $0.19/kWh
      - Total trade: 3.0 kWh
      - Weighted average price: $0.19/kWh
      - Community welfare: 3.0 * 0.22 = $0.660 AUD
      - Exactly 2 matching rounds executed.
    """
    s1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.12, quantity_kwh=1.0)
    s2 = MarketOrder("H002", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=2.0)
    b1 = MarketOrder("H003", MarketRole.BUYER, price_aud_per_kwh=0.26, quantity_kwh=1.0)
    b2 = MarketOrder("H004", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=2.0)

    res = clear_strategic_double_auction([s1, s2, b1, b2])

    assert len(res.transactions) == 2
    assert pytest.approx(res.total_traded_kwh, abs=1e-6) == 3.0
    assert res.rounds_executed == 2

    tx1, tx2 = res.transactions[0], res.transactions[1]
    assert tx1.seller_id == "H001" and tx1.buyer_id == "H003"
    assert pytest.approx(tx1.traded_energy_kwh, abs=1e-6) == 1.0
    assert pytest.approx(tx1.price_aud_per_kwh, abs=1e-6) == 0.19

    assert tx2.seller_id == "H002" and tx2.buyer_id == "H004"
    assert pytest.approx(tx2.traded_energy_kwh, abs=1e-6) == 2.0
    assert pytest.approx(tx2.price_aud_per_kwh, abs=1e-6) == 0.19

    assert pytest.approx(res.weighted_average_transaction_price_aud, abs=1e-6) == 0.19
    assert pytest.approx(res.community_incremental_welfare_aud, abs=1e-6) == 0.660


def test_partial_seller_exhaustion():
    """Verify partial seller exhaustion across multiple buyer price tiers.

    Seller 1 (H001): 2.0 kWh @ $0.12/kWh (large capacity)
    Seller 2 (H002): 1.0 kWh @ $0.16/kWh
    Buyer 1  (H003): 1.0 kWh @ $0.22/kWh (high bid)
    Buyer 2  (H004): 1.0 kWh @ $0.19/kWh (lower bid)

    Matching steps:
      - Round 1: S1 (best ask $0.12) matches B1 (best bid $0.22):
        TX1: S1 -> B1: 1.0 kWh @ (0.12 + 0.22)/2 = $0.17/kWh
        S1 has 1.0 kWh remaining @ $0.12. B1 is fully exhausted.
      - Round 2: S1 remaining (1.0 kWh @ $0.12) matches B2 (best remaining bid $0.19):
        TX2: S1 -> B2: 1.0 kWh @ (0.12 + 0.19)/2 = $0.155/kWh
        S1 is now fully exhausted. B2 is fully exhausted.
      - S2 is completely unserved (1.0 kWh unmatched surplus @ $0.16).
      - Total trade: 2.0 kWh, both from S1 across 2 distinct buyer price levels.
    """
    s1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.12, quantity_kwh=2.0)
    s2 = MarketOrder("H002", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=1.0)
    b1 = MarketOrder("H003", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=1.0)
    b2 = MarketOrder("H004", MarketRole.BUYER, price_aud_per_kwh=0.19, quantity_kwh=1.0)

    res = clear_strategic_double_auction([s1, s2, b1, b2])

    assert len(res.transactions) == 2
    assert pytest.approx(res.total_traded_kwh, abs=1e-6) == 2.0
    assert res.rounds_executed == 2

    assert pytest.approx(res.seller_allocations_kwh["H001"], abs=1e-6) == 2.0
    assert pytest.approx(res.seller_allocations_kwh["H002"], abs=1e-6) == 0.0
    assert pytest.approx(res.unmatched_seller_surplus_kwh["H001"], abs=1e-6) == 0.0
    assert pytest.approx(res.unmatched_seller_surplus_kwh["H002"], abs=1e-6) == 1.0

    assert pytest.approx(res.buyer_allocations_kwh["H003"], abs=1e-6) == 1.0
    assert pytest.approx(res.buyer_allocations_kwh["H004"], abs=1e-6) == 1.0

    tx1, tx2 = res.transactions[0], res.transactions[1]
    assert tx1.seller_id == "H001" and tx1.buyer_id == "H003"
    assert pytest.approx(tx1.price_aud_per_kwh, abs=1e-6) == 0.17
    assert tx2.seller_id == "H001" and tx2.buyer_id == "H004"
    assert pytest.approx(tx2.price_aud_per_kwh, abs=1e-6) == 0.155


def test_partial_buyer_exhaustion():
    """Verify partial buyer exhaustion across multiple seller price tiers.

    Seller 1 (H001): 1.0 kWh @ $0.12/kWh (low ask)
    Seller 2 (H002): 1.0 kWh @ $0.16/kWh (higher ask)
    Buyer 1  (H003): 2.0 kWh @ $0.22/kWh (large demand, high bid)
    Buyer 2  (H004): 1.0 kWh @ $0.19/kWh (lower bid)

    Matching steps:
      - Round 1: S1 (1.0 kWh @ $0.12) matches B1 (best bid $0.22):
        TX1: S1 -> B1: 1.0 kWh @ (0.12 + 0.22)/2 = $0.17/kWh
        S1 is fully exhausted. B1 has 1.0 kWh remaining @ $0.22.
      - Round 2: S2 (1.0 kWh @ $0.16) matches B1 remaining (1.0 kWh @ $0.22):
        TX2: S2 -> B1: 1.0 kWh @ (0.16 + 0.22)/2 = $0.19/kWh
        S2 is fully exhausted. B1 is fully exhausted.
      - B2 is completely unserved (1.0 kWh unmatched deficit @ $0.19).
      - Total trade: 2.0 kWh, both delivered to B1 across 2 distinct seller price levels.
    """
    s1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.12, quantity_kwh=1.0)
    s2 = MarketOrder("H002", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=1.0)
    b1 = MarketOrder("H003", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=2.0)
    b2 = MarketOrder("H004", MarketRole.BUYER, price_aud_per_kwh=0.19, quantity_kwh=1.0)

    res = clear_strategic_double_auction([s1, s2, b1, b2])

    assert len(res.transactions) == 2
    assert pytest.approx(res.total_traded_kwh, abs=1e-6) == 2.0
    assert res.rounds_executed == 2

    assert pytest.approx(res.seller_allocations_kwh["H001"], abs=1e-6) == 1.0
    assert pytest.approx(res.seller_allocations_kwh["H002"], abs=1e-6) == 1.0
    assert pytest.approx(res.buyer_allocations_kwh["H003"], abs=1e-6) == 2.0
    assert pytest.approx(res.buyer_allocations_kwh["H004"], abs=1e-6) == 0.0

    assert pytest.approx(res.unmatched_buyer_deficit_kwh["H003"], abs=1e-6) == 0.0
    assert pytest.approx(res.unmatched_buyer_deficit_kwh["H004"], abs=1e-6) == 1.0

    tx1, tx2 = res.transactions[0], res.transactions[1]
    assert tx1.seller_id == "H001" and tx1.buyer_id == "H003"
    assert pytest.approx(tx1.price_aud_per_kwh, abs=1e-6) == 0.17
    assert tx2.seller_id == "H002" and tx2.buyer_id == "H003"
    assert pytest.approx(tx2.price_aud_per_kwh, abs=1e-6) == 0.19


def test_unequal_quantities_simultaneous_tied_groups():
    """Verify 2x2 bilateral decomposition with asymmetric quantities in tied groups.

    Sellers at $0.16/kWh:
      - S1 (H001): 1.0 kWh
      - S2 (H002): 3.0 kWh
      Total supply = 4.0 kWh
    Buyers at $0.22/kWh:
      - B1 (H003): 1.0 kWh
      - B2 (H004): 1.0 kWh
      Total demand = 2.0 kWh

    Q_trade = min(4.0, 2.0) = 2.0 kWh
    Pro-rata supply allocation:
      - S1: 2.0 * (1.0 / 4.0) = 0.5 kWh
      - S2: 2.0 * (3.0 / 4.0) = 1.5 kWh
    Pro-rata demand allocation:
      - B1: 2.0 * (1.0 / 2.0) = 1.0 kWh
      - B2: 2.0 * (1.0 / 2.0) = 1.0 kWh
    Bilateral matrix decomposition:
      - q_11 = (0.5 * 1.0) / 2.0 = 0.25 kWh
      - q_12 = (0.5 * 1.0) / 2.0 = 0.25 kWh
      - q_21 = (1.5 * 1.0) / 2.0 = 0.75 kWh
      - q_22 = (1.5 * 1.0) / 2.0 = 0.75 kWh
    All transactions at midpoint price (0.16 + 0.22)/2 = $0.19/kWh.
    """
    s1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=1.0)
    s2 = MarketOrder("H002", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=3.0)
    b1 = MarketOrder("H003", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=1.0)
    b2 = MarketOrder("H004", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=1.0)

    res = clear_strategic_double_auction([s1, s2, b1, b2])

    assert len(res.transactions) == 4
    assert pytest.approx(res.total_traded_kwh, abs=1e-6) == 2.0
    assert res.rounds_executed == 1

    assert pytest.approx(res.seller_allocations_kwh["H001"], abs=1e-6) == 0.5
    assert pytest.approx(res.seller_allocations_kwh["H002"], abs=1e-6) == 1.5
    assert pytest.approx(res.buyer_allocations_kwh["H003"], abs=1e-6) == 1.0
    assert pytest.approx(res.buyer_allocations_kwh["H004"], abs=1e-6) == 1.0

    assert pytest.approx(res.unmatched_seller_surplus_kwh["H001"], abs=1e-6) == 0.5
    assert pytest.approx(res.unmatched_seller_surplus_kwh["H002"], abs=1e-6) == 1.5
    assert pytest.approx(res.unmatched_buyer_deficit_kwh["H003"], abs=1e-6) == 0.0
    assert pytest.approx(res.unmatched_buyer_deficit_kwh["H004"], abs=1e-6) == 0.0

    tx_map = {(tx.seller_id, tx.buyer_id): tx for tx in res.transactions}
    assert pytest.approx(tx_map[("H001", "H003")].traded_energy_kwh, abs=1e-6) == 0.25
    assert pytest.approx(tx_map[("H001", "H004")].traded_energy_kwh, abs=1e-6) == 0.25
    assert pytest.approx(tx_map[("H002", "H003")].traded_energy_kwh, abs=1e-6) == 0.75
    assert pytest.approx(tx_map[("H002", "H004")].traded_energy_kwh, abs=1e-6) == 0.75


# =============================================================================
# 2. EDGE CASES AND BOUNDARY CONDITIONS
# =============================================================================

def test_inactive_households_handling():
    """Verify that inactive households (zero quantity) do not trade and are cleanly reported."""
    s1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=1.5)
    b2 = MarketOrder("H002", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=1.5)
    # H003 is inactive (not submitting an order or listed explicitly)
    res = clear_strategic_double_auction([s1, b2], all_households=["H001", "H002", "H003"])

    assert "H003" in res.inactive_households
    assert res.seller_allocations_kwh["H003"] == 0.0
    assert res.buyer_allocations_kwh["H003"] == 0.0
    assert res.seller_revenues_aud["H003"] == 0.0
    assert res.buyer_payments_aud["H003"] == 0.0
    assert res.unmatched_seller_surplus_kwh["H003"] == 0.0
    assert res.unmatched_buyer_deficit_kwh["H003"] == 0.0


def test_all_seller_hour():
    """Verify hour where all 3 households have surplus and no buyers exist."""
    s1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.12, quantity_kwh=1.0)
    s2 = MarketOrder("H002", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=2.0)
    s3 = MarketOrder("H003", MarketRole.SELLER, price_aud_per_kwh=0.19, quantity_kwh=1.5)

    res = clear_strategic_double_auction([s1, s2, s3])

    assert len(res.transactions) == 0
    assert res.total_traded_kwh == 0.0
    assert pytest.approx(res.unmatched_seller_surplus_kwh["H001"], abs=1e-6) == 1.0
    assert pytest.approx(res.unmatched_seller_surplus_kwh["H002"], abs=1e-6) == 2.0
    assert pytest.approx(res.unmatched_seller_surplus_kwh["H003"], abs=1e-6) == 1.5


def test_all_buyer_hour():
    """Verify hour where all 3 households have deficit and no sellers exist."""
    b1 = MarketOrder("H001", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=1.0)
    b2 = MarketOrder("H002", MarketRole.BUYER, price_aud_per_kwh=0.26, quantity_kwh=2.0)
    b3 = MarketOrder("H003", MarketRole.BUYER, price_aud_per_kwh=0.30, quantity_kwh=1.5)

    res = clear_strategic_double_auction([b1, b2, b3])

    assert len(res.transactions) == 0
    assert res.total_traded_kwh == 0.0
    assert pytest.approx(res.unmatched_buyer_deficit_kwh["H001"], abs=1e-6) == 1.0
    assert pytest.approx(res.unmatched_buyer_deficit_kwh["H002"], abs=1e-6) == 2.0
    assert pytest.approx(res.unmatched_buyer_deficit_kwh["H003"], abs=1e-6) == 1.5


def test_zero_quantity_orders():
    """Verify that zero quantity orders are treated as inactive and produce no zero-quantity transactions."""
    s1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=0.0)
    b2 = MarketOrder("H002", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=1.0)

    res = clear_strategic_double_auction([s1, b2])
    assert len(res.transactions) == 0
    assert res.total_traded_kwh == 0.0
    assert "H001" in res.inactive_households


# =============================================================================
# 3. INPUT VALIDATION TESTS
# =============================================================================

def test_invalid_price_raises_error():
    """Verify that prices outside the discrete strategic price grid raise ValueError."""
    # 0.15 is not in {0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30}
    with pytest.raises(ValueError, match="does not belong to allowed strategic price grid"):
        MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.15, quantity_kwh=1.0)

    with pytest.raises(ValueError, match="does not belong to allowed strategic price grid"):
        MarketOrder("H002", MarketRole.BUYER, price_aud_per_kwh=0.35, quantity_kwh=1.0)


def test_negative_quantity_raises_error():
    """Verify that negative quantities raise ValueError."""
    with pytest.raises(ValueError, match="quantity_kwh must be nonnegative"):
        MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=-0.5)


def test_duplicate_order_per_household_raises_error():
    """Verify that duplicate orders for the same household raise ValueError."""
    o1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=1.0)
    o2 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.19, quantity_kwh=0.5)

    with pytest.raises(ValueError, match="Duplicate order submitted for household H001"):
        clear_strategic_double_auction([o1, o2])


def test_exact_price_grid_rejection_of_offgrid_prices():
    """Verify strict price grid rejection of arbitrary continuous values without bypass."""
    for offgrid_p in [0.07, 0.10, 0.15, 0.20, 0.25, 0.28, 0.31]:
        with pytest.raises(ValueError, match="does not belong to allowed strategic price grid"):
            MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=offgrid_p, quantity_kwh=1.0)
        with pytest.raises(ValueError, match="does not belong to allowed strategic price grid"):
            MarketOrder("H002", MarketRole.BUYER, price_aud_per_kwh=offgrid_p, quantity_kwh=1.0)

    # Rejection at market clearing if an order was created with custom grid but submitted to default market
    custom_g = (0.08, 0.20, 0.30)
    ord_custom = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.20, quantity_kwh=1.0, allowed_price_grid=custom_g)
    with pytest.raises(ValueError, match="does not belong to active market price grid"):
        clear_strategic_double_auction([ord_custom])  # default price_grid=STRATEGIC_PRICE_GRID


def test_market_configuration_validation():
    """Verify validation of tariffs, tolerance, price grid, and household IDs."""
    # Negative import tariff
    with pytest.raises(ValueError, match="grid_import_tariff_aud must be nonnegative"):
        validate_market_configuration(-0.01, 0.08, 1e-6, STRATEGIC_PRICE_GRID)

    # Negative export credit
    with pytest.raises(ValueError, match="grid_export_credit_aud must be nonnegative"):
        validate_market_configuration(0.30, -0.01, 1e-6, STRATEGIC_PRICE_GRID)

    # Import tariff < export credit
    with pytest.raises(ValueError, match="cannot be less than"):
        validate_market_configuration(0.05, 0.08, 1e-6, STRATEGIC_PRICE_GRID)

    # Non-finite tariffs
    with pytest.raises(ValueError, match="grid_import_tariff_aud must be finite"):
        validate_market_configuration(np.nan, 0.08, 1e-6, STRATEGIC_PRICE_GRID)
    with pytest.raises(ValueError, match="grid_export_credit_aud must be finite"):
        validate_market_configuration(0.30, np.inf, 1e-6, STRATEGIC_PRICE_GRID)

    # Tolerance <= 0 or non-finite
    with pytest.raises(ValueError, match="tolerance must be strictly positive"):
        validate_market_configuration(0.30, 0.08, 0.0, STRATEGIC_PRICE_GRID)
    with pytest.raises(ValueError, match="tolerance must be strictly positive"):
        validate_market_configuration(0.30, 0.08, -1e-6, STRATEGIC_PRICE_GRID)
    with pytest.raises(ValueError, match="tolerance must be strictly positive"):
        validate_market_configuration(0.30, 0.08, np.nan, STRATEGIC_PRICE_GRID)

    # Empty price grid
    with pytest.raises(ValueError, match="price_grid must be a non-empty sequence"):
        validate_price_grid([])

    # Non-strictly increasing price grid (duplicates or descending)
    with pytest.raises(ValueError, match="price_grid must be strictly increasing"):
        validate_price_grid([0.08, 0.12, 0.12, 0.30])
    with pytest.raises(ValueError, match="price_grid must be strictly increasing"):
        validate_price_grid([0.30, 0.20, 0.10])

    # Price grid out of bounds
    with pytest.raises(ValueError, match="outside commercial tariff bounds"):
        validate_price_grid([0.05, 0.12, 0.30], grid_export_credit_aud=0.08, grid_import_tariff_aud=0.30)
    with pytest.raises(ValueError, match="outside commercial tariff bounds"):
        validate_price_grid([0.08, 0.12, 0.35], grid_export_credit_aud=0.08, grid_import_tariff_aud=0.30)

    # Non-finite price in grid
    with pytest.raises(ValueError, match="Non-finite price in price_grid"):
        validate_price_grid([0.08, np.nan, 0.30])

    # Empty / whitespace household ID
    with pytest.raises(ValueError, match="Invalid household_id"):
        MarketOrder("", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=1.0)
    with pytest.raises(ValueError, match="Invalid household_id"):
        MarketOrder("   ", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=1.0)

    s1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.16, quantity_kwh=1.0)
    with pytest.raises(ValueError, match="Invalid household_id in all_households"):
        clear_strategic_double_auction([s1], all_households=["H001", "  "])


def test_matching_rounds_theoretical_bound():
    """Verify that matching rounds never exceed len(active_sellers) + len(active_buyers)."""
    s1 = MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=0.12, quantity_kwh=3.0)
    b1 = MarketOrder("H002", MarketRole.BUYER, price_aud_per_kwh=0.22, quantity_kwh=1.0)
    b2 = MarketOrder("H003", MarketRole.BUYER, price_aud_per_kwh=0.19, quantity_kwh=2.0)

    res = clear_strategic_double_auction([s1, b1, b2])
    max_bound = len(res.active_sellers) + len(res.active_buyers)
    assert res.rounds_executed <= max_bound
    assert res.rounds_executed == 2


# =============================================================================
# 4. PHYSICAL HELPERS AND FACTORY TESTS
# =============================================================================

def test_compute_physical_net_position():
    """Verify physical net flow calculation: n = (D + C) - (S + B)."""
    # Household A: Buyer deficit
    # D = 2.0, C = 0.0, S = 0.5, B = 0.7 -> net = 2.0 - 1.2 = +0.8
    net_A, s_A, d_A = compute_physical_net_position(2.0, 0.0, 0.5, 0.7)
    assert pytest.approx(net_A, abs=1e-9) == 0.8
    assert s_A == 0.0
    assert pytest.approx(d_A, abs=1e-9) == 0.8

    # Household B: Seller surplus
    # D = 0.4, C = 1.0, S = 2.5, B = 0.0 -> net = 1.4 - 2.5 = -1.1
    net_B, s_B, d_B = compute_physical_net_position(0.4, 1.0, 2.5, 0.0)
    assert pytest.approx(net_B, abs=1e-9) == -1.1
    assert pytest.approx(s_B, abs=1e-9) == 1.1
    assert d_B == 0.0

    # Household C: Balanced
    # D = 1.2, C = 0.0, S = 0.8, B = 0.4 -> net = 1.2 - 1.2 = 0.0
    net_C, s_C, d_C = compute_physical_net_position(1.2, 0.0, 0.8, 0.4)
    assert pytest.approx(net_C, abs=1e-9) == 0.0
    assert s_C == 0.0
    assert d_C == 0.0


def test_create_order_from_physical_position():
    """Verify order creation helper correctly identifies role and skips inactive prosumers."""
    # Buyer order
    ord_buy = create_order_from_physical_position("H001", 2.0, 0.0, 0.5, 0.7, price_aud_per_kwh=0.22)
    assert ord_buy is not None
    assert ord_buy.household_id == "H001"
    assert ord_buy.role == MarketRole.BUYER
    assert pytest.approx(ord_buy.quantity_kwh, abs=1e-9) == 0.8
    assert ord_buy.price_aud_per_kwh == 0.22

    # Seller order
    ord_sell = create_order_from_physical_position("H002", 0.4, 1.0, 2.5, 0.0, price_aud_per_kwh=0.16)
    assert ord_sell is not None
    assert ord_sell.household_id == "H002"
    assert ord_sell.role == MarketRole.SELLER
    assert pytest.approx(ord_sell.quantity_kwh, abs=1e-9) == 1.1
    assert ord_sell.price_aud_per_kwh == 0.16

    # Inactive prosumer
    ord_inact = create_order_from_physical_position("H003", 1.2, 0.0, 0.8, 0.4, price_aud_per_kwh=0.19)
    assert ord_inact is None


# =============================================================================
# 5. CONSERVATION LAWS AND FINANCIAL RECONCILIATION
# =============================================================================

def test_multi_hour_random_matching_conservation_invariants():
    """Stress test with 20 diverse random orders to verify all 5 conservation laws hold."""
    np.random.seed(42)
    price_levels = list(STRATEGIC_PRICE_GRID)

    for trial in range(20):
        # Random surpluses and deficits
        s1 = float(np.random.uniform(0.0, 3.0))
        d2 = float(np.random.uniform(0.0, 3.0))
        d3 = float(np.random.uniform(0.0, 3.0))

        p1 = float(np.random.choice(price_levels))
        p2 = float(np.random.choice(price_levels))
        p3 = float(np.random.choice(price_levels))

        orders = [
            MarketOrder("H001", MarketRole.SELLER, price_aud_per_kwh=p1, quantity_kwh=s1),
            MarketOrder("H002", MarketRole.BUYER, price_aud_per_kwh=p2, quantity_kwh=d2),
            MarketOrder("H003", MarketRole.BUYER, price_aud_per_kwh=p3, quantity_kwh=d3),
        ]

        res = clear_strategic_double_auction(orders)

        # 1. Energy conservation: Sold == Bought == Traded
        tot_sold = sum(res.seller_allocations_kwh.values())
        tot_bought = sum(res.buyer_allocations_kwh.values())
        assert pytest.approx(tot_sold, abs=1e-9) == res.total_traded_kwh
        assert pytest.approx(tot_bought, abs=1e-9) == res.total_traded_kwh

        # 2. Payment conservation: Payments == Revenues
        tot_rev = sum(res.seller_revenues_aud.values())
        tot_pmt = sum(res.buyer_payments_aud.values())
        assert pytest.approx(tot_rev, abs=1e-9) == tot_pmt

        # 3. Community economic welfare identity: Sum(Delta U) == 0.22 * Q_P2P
        tot_ben = sum(res.seller_incremental_benefits_aud.values()) + sum(
            res.buyer_incremental_benefits_aud.values()
        )
        expected_welfare = 0.22 * res.total_traded_kwh
        assert pytest.approx(tot_ben, abs=1e-9) == expected_welfare
        assert pytest.approx(res.community_incremental_welfare_aud, abs=1e-9) == expected_welfare

        # 4. Feasibility: Allocations <= available
        assert res.seller_allocations_kwh["H001"] <= s1 + 1e-9
        assert res.buyer_allocations_kwh["H002"] <= d2 + 1e-9
        assert res.buyer_allocations_kwh["H003"] <= d3 + 1e-9

        # 5. Ledger consistency
        df_ledger = res.get_ledger_dataframe()
        if len(res.transactions) > 0:
            assert pytest.approx(df_ledger["traded_energy_kwh"].sum(), abs=1e-9) == res.total_traded_kwh
            assert pytest.approx(df_ledger["seller_revenue_aud"].sum(), abs=1e-9) == tot_rev
            assert pytest.approx(df_ledger["buyer_payment_aud"].sum(), abs=1e-9) == tot_pmt
