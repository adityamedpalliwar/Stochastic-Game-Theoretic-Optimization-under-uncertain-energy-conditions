"""Unit tests for transaction conservation and player utility."""

import pytest
from src.game.utility import P2PTransaction, compute_household_payoff


def test_p2p_transaction_conservation():
    """Buyer payment must equal seller revenue."""
    tx = P2PTransaction(seller_id="H001", buyer_id="H002", traded_energy_kwh=1.25, price_aud_per_kwh=0.19)
    assert tx.total_transaction_value_aud == pytest.approx(1.25 * 0.19)


def test_payoff_conservation_and_invariants():
    """Verify that seller and buyer cash flows balance and energy is conserved."""
    surplus_seller = 1.5  # kWh
    deficit_buyer = 2.0   # kWh
    trade_q = 1.5         # kWh
    p2p_price = 0.19      # AUD/kWh
    p_buy = 0.30          # AUD/kWh
    p_exp = 0.08          # AUD/kWh

    payoff_seller = compute_household_payoff(
        house_id="H001",
        deficit_kwh=0.0,
        surplus_kwh=surplus_seller,
        grid_import_price_aud=p_buy,
        grid_export_credit_aud=p_exp,
        p2p_energy_sold_kwh=trade_q,
        p2p_price_aud=p2p_price,
    )

    payoff_buyer = compute_household_payoff(
        house_id="H002",
        deficit_kwh=deficit_buyer,
        surplus_kwh=0.0,
        grid_import_price_aud=p_buy,
        grid_export_credit_aud=p_exp,
        p2p_energy_bought_kwh=trade_q,
        p2p_price_aud=p2p_price,
    )

    # 1. P2P Payment == P2P Revenue
    assert payoff_buyer.p2p_payment_aud == pytest.approx(payoff_seller.p2p_revenue_aud)
    assert payoff_seller.p2p_payment_aud == 0.0
    assert payoff_buyer.p2p_revenue_aud == 0.0

    # 2. Energy balance
    assert payoff_seller.grid_exported_kwh == pytest.approx(surplus_seller - trade_q)
    assert payoff_buyer.grid_imported_kwh == pytest.approx(deficit_buyer - trade_q)

    # 3. Utility = -Net Expenditure
    assert payoff_seller.utility == pytest.approx(-payoff_seller.net_expenditure_aud)
    assert payoff_buyer.utility == pytest.approx(-payoff_buyer.net_expenditure_aud)


def test_cannot_sell_more_than_available_surplus():
    """Attempting to sell more energy than physically available must raise ValueError."""
    with pytest.raises(ValueError):
        compute_household_payoff(
            house_id="H001",
            deficit_kwh=0.0,
            surplus_kwh=1.0,
            grid_import_price_aud=0.30,
            grid_export_credit_aud=0.08,
            p2p_energy_sold_kwh=1.5,  # Exceeds surplus
            p2p_price_aud=0.19,
        )


def test_cannot_buy_more_than_deficit():
    """Attempting to buy more energy than needed deficit must raise ValueError."""
    with pytest.raises(ValueError):
        compute_household_payoff(
            house_id="H002",
            deficit_kwh=0.8,
            surplus_kwh=0.0,
            grid_import_price_aud=0.30,
            grid_export_credit_aud=0.08,
            p2p_energy_bought_kwh=1.2,  # Exceeds deficit
            p2p_price_aud=0.19,
        )
