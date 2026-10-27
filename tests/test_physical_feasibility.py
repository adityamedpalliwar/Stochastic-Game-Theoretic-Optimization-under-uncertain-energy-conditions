"""Automated regression test suite for physical energy feasibility, conservation, and transactions.

Audit coverage:
1. Household energy balances: surplus, deficit, self-consumption, complementarity.
2. Boundary cases: generation > demand, demand > generation, generation == demand, all zeros, near-zero epsilons.
3. Invalid inputs: NaN, infinity, negative values rejected across all entry points.
4. Feasible and infeasible P2P trade requests (seller surplus and buyer deficit bounds).
5. Post-trade energy balances: conservation of demand, solar generation, and community net grid balance.
6. Action-selection vs physically executed trade distinction (zero-surplus / zero-deficit degenerate games).
7. Protocol B Monte Carlo scenario physical feasibility and reproducibility.
8. Jensen's inequality and expected vs scenario-level trade feasibility.
9. Battery storage operational bounds, efficiencies, and isolation verification.
"""

from __future__ import annotations

import math
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

from src.energy.energy_balance import (
    EnergyBalance,
    PostTradeEnergyBalance,
    compute_energy_balance,
    compute_energy_balance_series,
    compute_post_trade_balance,
)
from src.energy.battery import BatteryStorage
from src.game.payoff_matrix import build_two_household_payoff_matrix
from src.game.utility import P2PTransaction, compute_household_payoff
from src.stochastic.monte_carlo import (
    MonteCarloSimulator,
    ValidationResidualPool,
    derive_observation_seed,
)


ROOT = Path(__file__).resolve().parent.parent


# ===========================================================================
# 1. Pre-Trade Energy Balance & Complementarity Tests
# ===========================================================================

def test_surplus_deficit_generation_exceeds_demand():
    """Solar exceeds demand -> surplus > 0, deficit == 0, S * B == 0."""
    d, g = 1.2, 3.5
    b = compute_energy_balance(demand_kwh=d, solar_generation_kwh=g, house_id="H001")
    assert b.demand_kwh == pytest.approx(1.2)
    assert b.solar_generation_kwh == pytest.approx(3.5)
    assert b.self_consumption_kwh == pytest.approx(1.2)
    assert b.surplus_kwh == pytest.approx(2.3)
    assert b.deficit_kwh == 0.0
    assert b.has_surplus is True
    assert b.has_deficit is False
    # Complementarity
    assert b.surplus_kwh * b.deficit_kwh == 0.0
    # Conservation identities
    assert b.demand_kwh == pytest.approx(b.self_consumption_kwh + b.deficit_kwh)
    assert b.solar_generation_kwh == pytest.approx(b.self_consumption_kwh + b.surplus_kwh)
    assert (b.demand_kwh - b.solar_generation_kwh) == pytest.approx(b.deficit_kwh - b.surplus_kwh)


def test_surplus_deficit_demand_exceeds_generation():
    """Demand exceeds solar -> deficit > 0, surplus == 0, S * B == 0."""
    d, g = 4.0, 1.5
    b = compute_energy_balance(demand_kwh=d, solar_generation_kwh=g, house_id="H002")
    assert b.demand_kwh == pytest.approx(4.0)
    assert b.solar_generation_kwh == pytest.approx(1.5)
    assert b.self_consumption_kwh == pytest.approx(1.5)
    assert b.deficit_kwh == pytest.approx(2.5)
    assert b.surplus_kwh == 0.0
    assert b.has_surplus is False
    assert b.has_deficit is True
    # Complementarity
    assert b.surplus_kwh * b.deficit_kwh == 0.0
    # Conservation identities
    assert b.demand_kwh == pytest.approx(b.self_consumption_kwh + b.deficit_kwh)
    assert b.solar_generation_kwh == pytest.approx(b.self_consumption_kwh + b.surplus_kwh)
    assert (b.demand_kwh - b.solar_generation_kwh) == pytest.approx(b.deficit_kwh - b.surplus_kwh)


def test_exact_balance_generation_equals_demand():
    """Solar equals demand -> surplus == 0, deficit == 0, exact self-consumption."""
    d, g = 2.75, 2.75
    b = compute_energy_balance(demand_kwh=d, solar_generation_kwh=g, house_id="H001")
    assert b.self_consumption_kwh == pytest.approx(2.75)
    assert b.surplus_kwh == 0.0
    assert b.deficit_kwh == 0.0
    assert b.has_surplus is False
    assert b.has_deficit is False
    assert b.demand_kwh == pytest.approx(b.self_consumption_kwh)
    assert b.solar_generation_kwh == pytest.approx(b.self_consumption_kwh)


def test_zero_demand_and_zero_generation_edge_cases():
    """Exhaustive boundary testing of zero states."""
    # 1. Both zero
    b_zero = compute_energy_balance(demand_kwh=0.0, solar_generation_kwh=0.0, house_id="H001")
    assert b_zero.self_consumption_kwh == 0.0
    assert b_zero.deficit_kwh == 0.0
    assert b_zero.surplus_kwh == 0.0

    # 2. Zero demand, positive solar (pure generation)
    b_gen = compute_energy_balance(demand_kwh=0.0, solar_generation_kwh=3.0, house_id="H001")
    assert b_gen.self_consumption_kwh == 0.0
    assert b_gen.surplus_kwh == pytest.approx(3.0)
    assert b_gen.deficit_kwh == 0.0

    # 3. Positive demand, zero solar (night-time load)
    b_night = compute_energy_balance(demand_kwh=2.5, solar_generation_kwh=0.0, house_id="H002")
    assert b_night.self_consumption_kwh == 0.0
    assert b_night.deficit_kwh == pytest.approx(2.5)
    assert b_night.surplus_kwh == 0.0


def test_near_zero_epsilon_values():
    """Verify numerical stability near floating point epsilon."""
    eps_d = 1e-8
    eps_g = 1e-9
    b = compute_energy_balance(demand_kwh=eps_d, solar_generation_kwh=eps_g, house_id="H001")
    assert b.self_consumption_kwh == pytest.approx(1e-9)
    assert b.deficit_kwh == pytest.approx(9e-9)
    assert b.surplus_kwh == 0.0
    assert b.demand_kwh == pytest.approx(b.self_consumption_kwh + b.deficit_kwh, abs=1e-12)


# ===========================================================================
# 2. Input Validation: Non-Finite, Negative, & Contradictory States
# ===========================================================================

def test_non_finite_inputs_rejected_compute_energy_balance():
    """NaN, Inf, and -Inf must raise ValueError, not silently convert to 0.0."""
    with pytest.raises(ValueError, match="finite"):
        compute_energy_balance(demand_kwh=float("nan"), solar_generation_kwh=1.0)
    with pytest.raises(ValueError, match="finite"):
        compute_energy_balance(demand_kwh=1.0, solar_generation_kwh=float("nan"))
    with pytest.raises(ValueError, match="finite"):
        compute_energy_balance(demand_kwh=float("inf"), solar_generation_kwh=1.0)
    with pytest.raises(ValueError, match="finite"):
        compute_energy_balance(demand_kwh=1.0, solar_generation_kwh=float("-inf"))


def test_negative_physical_inputs_rejected():
    """Negative demand or generation must raise ValueError."""
    with pytest.raises(ValueError, match="must be >= 0"):
        compute_energy_balance(demand_kwh=-0.5, solar_generation_kwh=1.0)
    with pytest.raises(ValueError, match="must be >= 0"):
        compute_energy_balance(demand_kwh=1.0, solar_generation_kwh=-0.1)


def test_simultaneous_surplus_and_deficit_rejected_in_dataclass():
    """EnergyBalance dataclass must reject simultaneous surplus and deficit."""
    with pytest.raises(ValueError, match="Complementarity violation"):
        EnergyBalance(
            house_id="H001",
            demand_kwh=5.0,
            solar_generation_kwh=5.0,
            self_consumption_kwh=2.0,
            deficit_kwh=3.0,
            surplus_kwh=3.0,
        )


def test_inconsistent_self_consumption_rejected_in_dataclass():
    """EnergyBalance dataclass must reject non-conserving self-consumption."""
    with pytest.raises(ValueError, match="Demand conservation violation"):
        EnergyBalance(
            house_id="H001",
            demand_kwh=5.0,
            solar_generation_kwh=5.0,
            self_consumption_kwh=4.0,  # 4 + 0 != 5
            deficit_kwh=0.0,
            surplus_kwh=0.0,
        )


def test_series_validation_rejects_nan_and_negative():
    """compute_energy_balance_series must fail fast on corrupted columns."""
    df_nan = pd.DataFrame({
        "total_demand_kwh": [1.0, float("nan"), 2.0],
        "solar_generation_kwh": [0.5, 1.0, 1.5],
        "house_id": ["H001"] * 3,
    })
    with pytest.raises(ValueError, match="Non-finite values found"):
        compute_energy_balance_series(df_nan)

    df_neg = pd.DataFrame({
        "total_demand_kwh": [1.0, -0.5, 2.0],
        "solar_generation_kwh": [0.5, 1.0, 1.5],
        "house_id": ["H001"] * 3,
    })
    with pytest.raises(ValueError, match="Negative values found"):
        compute_energy_balance_series(df_neg)


# ===========================================================================
# 3. P2P Transaction Feasibility & Conservation Tests
# ===========================================================================

def test_p2p_transaction_feasibility_validation():
    """P2PTransaction validates trade feasibility against seller surplus and buyer deficit."""
    tx = P2PTransaction(seller_id="H001", buyer_id="H002", traded_energy_kwh=1.5, price_aud_per_kwh=0.19)
    # Feasible case
    assert tx.validate_feasibility(seller_surplus_kwh=2.0, buyer_deficit_kwh=1.8) is True

    # Infeasible: exceeds seller surplus
    with pytest.raises(ValueError, match="exceeds seller available surplus"):
        tx.validate_feasibility(seller_surplus_kwh=1.2, buyer_deficit_kwh=2.0)

    # Infeasible: exceeds buyer deficit
    with pytest.raises(ValueError, match="exceeds buyer unmet deficit"):
        tx.validate_feasibility(seller_surplus_kwh=2.0, buyer_deficit_kwh=1.4)


def test_p2p_transaction_rejects_self_trading_and_invalid_values():
    """A household cannot trade with itself, and values must be finite and nonnegative."""
    with pytest.raises(ValueError, match="Seller and buyer cannot be the same"):
        P2PTransaction(seller_id="H001", buyer_id="H001", traded_energy_kwh=1.0, price_aud_per_kwh=0.19)

    with pytest.raises(ValueError, match="finite"):
        P2PTransaction(seller_id="H001", buyer_id="H002", traded_energy_kwh=float("nan"), price_aud_per_kwh=0.19)

    with pytest.raises(ValueError, match="nonnegative"):
        P2PTransaction(seller_id="H001", buyer_id="H002", traded_energy_kwh=-1.0, price_aud_per_kwh=0.19)


def test_compute_post_trade_balance_exact_conservation():
    """Compute post-trade balance and verify exact 6-flow conservation."""
    # Seller H001: Demand 0.5 kWh, Solar 2.5 kWh -> Surplus 2.0 kWh, Deficit 0.0 kWh
    b_seller = compute_energy_balance(demand_kwh=0.5, solar_generation_kwh=2.5, house_id="H001")
    # Buyer H002: Demand 3.0 kWh, Solar 1.0 kWh -> Surplus 0.0 kWh, Deficit 2.0 kWh
    b_buyer = compute_energy_balance(demand_kwh=3.0, solar_generation_kwh=1.0, house_id="H002")

    # Trade 1.25 kWh
    trade_q = 1.25
    post_seller = compute_post_trade_balance(b_seller, p2p_sold_kwh=trade_q, p2p_bought_kwh=0.0)
    post_buyer = compute_post_trade_balance(b_buyer, p2p_sold_kwh=0.0, p2p_bought_kwh=trade_q)

    # Seller verification:
    assert post_seller.self_consumption_kwh == pytest.approx(0.5)
    assert post_seller.p2p_sold_kwh == pytest.approx(1.25)
    assert post_seller.grid_exported_kwh == pytest.approx(0.75)  # 2.0 - 1.25
    assert post_seller.grid_imported_kwh == 0.0
    # Solar conservation: Solar == Self + P2P_sold + Grid_exported
    assert post_seller.solar_generation_kwh == pytest.approx(0.5 + 1.25 + 0.75)
    # Demand conservation: Demand == Self + P2P_bought + Grid_imported
    assert post_seller.demand_kwh == pytest.approx(0.5 + 0.0 + 0.0)

    # Buyer verification:
    assert post_buyer.self_consumption_kwh == pytest.approx(1.0)
    assert post_buyer.p2p_bought_kwh == pytest.approx(1.25)
    assert post_buyer.grid_imported_kwh == pytest.approx(0.75)  # 2.0 - 1.25
    assert post_buyer.grid_exported_kwh == 0.0
    # Demand conservation: Demand == Self + P2P_bought + Grid_imported
    assert post_buyer.demand_kwh == pytest.approx(1.0 + 1.25 + 0.75)
    # Solar conservation: Solar == Self + P2P_sold + Grid_exported
    assert post_buyer.solar_generation_kwh == pytest.approx(1.0 + 0.0 + 0.0)

    # Community net conservation: Net Demand - Net Solar == Net Grid Import - Net Grid Export
    comm_demand = post_seller.demand_kwh + post_buyer.demand_kwh
    comm_solar = post_seller.solar_generation_kwh + post_buyer.solar_generation_kwh
    comm_grid_in = post_seller.grid_imported_kwh + post_buyer.grid_imported_kwh
    comm_grid_out = post_seller.grid_exported_kwh + post_buyer.grid_exported_kwh
    assert (comm_demand - comm_solar) == pytest.approx(comm_grid_in - comm_grid_out)


def test_post_trade_balance_rejects_infeasible_sales_and_purchases():
    """Post-trade computation raises ValueError when trade limits are exceeded."""
    b_seller = compute_energy_balance(demand_kwh=0.5, solar_generation_kwh=1.5, house_id="H001")  # Surplus = 1.0
    with pytest.raises(ValueError, match="Cannot sell 1.5000 kWh: only 1.0000 kWh surplus"):
        compute_post_trade_balance(b_seller, p2p_sold_kwh=1.5)

    b_buyer = compute_energy_balance(demand_kwh=2.0, solar_generation_kwh=1.2, house_id="H002")  # Deficit = 0.8
    with pytest.raises(ValueError, match="Cannot buy 1.0000 kWh: only 0.8000 kWh deficit"):
        compute_post_trade_balance(b_buyer, p2p_bought_kwh=1.0)


def test_post_trade_balance_rejects_simultaneous_buying_and_selling():
    """A household cannot sell and buy P2P electricity in the same interval."""
    b = compute_energy_balance(demand_kwh=1.0, solar_generation_kwh=1.0, house_id="H001")
    with pytest.raises(ValueError, match="cannot simultaneously sell and buy"):
        compute_post_trade_balance(b, p2p_sold_kwh=0.5, p2p_bought_kwh=0.5)


def test_zero_volume_game_when_surplus_or_deficit_zero():
    """When surplus or deficit is zero, trade quantity is zero and action choice has zero physical impact."""
    # Night time: surplus = 0.0, deficit = 2.0
    m = build_two_household_payoff_matrix(
        seller_id="H001", seller_surplus_kwh=0.0,
        buyer_id="H002", buyer_deficit_kwh=2.0,
        grid_import_price_aud=0.30, grid_export_credit_aud=0.08,
    )
    # Traded quantities across all 4 strategy profiles must be 0.0
    assert np.all(m.traded_quantities == 0.0)
    # Seller payoff identical across all profiles (0.0 AUD)
    assert np.all(m.payoffs_p1 == 0.0)
    # Buyer payoff identical across all profiles (-0.60 AUD)
    assert np.all(m.payoffs_p2 == pytest.approx(-0.60))


def test_four_strategy_profiles_physical_and_financial_consistency():
    """Verify executed trade, remaining grid flows, and financial payoffs across all 4 strategy profiles."""
    surplus = 2.0  # kWh
    deficit = 1.5  # kWh
    p_buy = 0.30   # AUD/kWh
    p_exp = 0.08   # AUD/kWh
    p_p2p = 0.19   # AUD/kWh

    m = build_two_household_payoff_matrix(
        seller_id="H001", seller_surplus_kwh=surplus,
        buyer_id="H002", buyer_deficit_kwh=deficit,
        grid_import_price_aud=p_buy, grid_export_credit_aud=p_exp,
        p2p_price_aud=p_p2p,
    )

    # Hand-calculated benchmark ground truth: (q_trade, U_seller, U_buyer)
    expected_outcomes = {
        ("OFFER_P2P", "ACCEPT_P2P"): (1.5, 0.5 * p_exp + 1.5 * p_p2p, -(1.5 * p_p2p + 0.0 * p_buy)),
        ("OFFER_P2P", "GRID_IMPORT"): (0.0, 2.0 * p_exp, -(1.5 * p_buy)),
        ("EXPORT_GRID", "ACCEPT_P2P"): (0.0, 2.0 * p_exp, -(1.5 * p_buy)),
        ("EXPORT_GRID", "GRID_IMPORT"): (0.0, 2.0 * p_exp, -(1.5 * p_buy)),
    }

    for (a1, a2), (exp_q, exp_u1, exp_u2) in expected_outcomes.items():
        i = m.actions_p1.index(a1)
        j = m.actions_p2.index(a2)
        assert m.traded_quantities[i, j] == pytest.approx(exp_q)
        assert m.payoffs_p1[i, j] == pytest.approx(exp_u1)
        assert m.payoffs_p2[i, j] == pytest.approx(exp_u2)

        # Detailed breakdown check
        payoff_s, payoff_b = m.details[(a1, a2)]
        assert payoff_s.p2p_exported_kwh == pytest.approx(exp_q)
        assert payoff_b.p2p_imported_kwh == pytest.approx(exp_q)
        assert payoff_s.grid_exported_kwh == pytest.approx(surplus - exp_q)
        assert payoff_b.grid_imported_kwh == pytest.approx(deficit - exp_q)


# ===========================================================================
# 4. Monte Carlo Scenario Feasibility & Protocol B Verification
# ===========================================================================

def test_monte_carlo_scenarios_physical_feasibility_protocol_b():
    """Validate physical feasibility and exact conservation across Monte Carlo scenarios under Protocol B."""
    seq_path = ROOT / "data" / "processed" / "lstm_sequences.npz"
    res_pool = ValidationResidualPool(sequences_path=seq_path)

    # Test timestamps covering different diurnal conditions
    test_cases = [
        ("2013-05-01 03:00:00", 1.5, 0.0, 0.8, 0.0),    # Night (zero solar)
        ("2013-05-01 11:00:00", 0.4, 1.8, 1.2, 0.3),    # Sunny midday
        ("2013-05-01 18:00:00", 2.2, 0.05, 1.9, 0.0),   # Evening peak
    ]

    for ts, d1_mean, s1_mean, d2_mean, s2_mean in test_cases:
        seed1 = derive_observation_seed("H001", ts, base_seed=42)
        seed2 = derive_observation_seed("H002", ts, base_seed=42)

        ed1, es1 = res_pool.sample_residuals(num_scenarios=200, house_id="H001", random_seed=seed1, method="empirical")
        ed2, es2 = res_pool.sample_residuals(num_scenarios=200, house_id="H002", random_seed=seed2, method="empirical")

        d1_s = np.maximum(0.0, d1_mean + ed1)
        s1_s = np.maximum(0.0, s1_mean + es1)
        d2_s = np.maximum(0.0, d2_mean + ed2)
        s2_s = np.maximum(0.0, s2_mean + es2)

        # 1. Finiteness & Non-negativity
        assert np.all(np.isfinite(d1_s)) and np.all(d1_s >= 0.0)
        assert np.all(np.isfinite(s1_s)) and np.all(s1_s >= 0.0)
        assert np.all(np.isfinite(d2_s)) and np.all(d2_s >= 0.0)
        assert np.all(np.isfinite(s2_s)) and np.all(s2_s >= 0.0)

        # 2. Local surplus and deficit
        surplus1 = np.maximum(0.0, s1_s - d1_s)
        deficit1 = np.maximum(0.0, d1_s - s1_s)
        surplus2 = np.maximum(0.0, s2_s - d2_s)
        deficit2 = np.maximum(0.0, d2_s - s2_s)

        # Complementarity
        assert np.all(surplus1 * deficit1 == 0.0)
        assert np.all(surplus2 * deficit2 == 0.0)

        # 3. Feasible trade quantity
        q_trade = np.minimum(surplus1, deficit2)
        assert np.all(q_trade >= 0.0)
        assert np.all(q_trade <= surplus1 + 1e-6)
        assert np.all(q_trade <= deficit2 + 1e-6)

        # 4. Post-trade balances and conservation
        self_c1 = np.minimum(d1_s, s1_s)
        self_c2 = np.minimum(d2_s, s2_s)
        rem_surp1 = surplus1 - q_trade
        rem_def2 = deficit2 - q_trade

        # Seller demand and solar conservation
        assert np.allclose(d1_s, self_c1 + deficit1, atol=1e-6)
        assert np.allclose(s1_s, self_c1 + q_trade + rem_surp1, atol=1e-6)

        # Buyer demand and solar conservation
        assert np.allclose(d2_s, self_c2 + q_trade + rem_def2, atol=1e-6)
        assert np.allclose(s2_s, self_c2 + surplus2, atol=1e-6)

        # Community net conservation
        comm_d = d1_s + d2_s
        comm_s = s1_s + s2_s
        comm_grid_in = deficit1 + rem_def2
        comm_grid_out = rem_surp1 + surplus2
        assert np.allclose(comm_d - comm_s, comm_grid_in - comm_grid_out, atol=1e-6)


def test_jensen_inequality_expected_trade_overestimation():
    """Mathematically verify that min(E[S], E[B]) >= E[min(S, B)] due to concavity."""
    # Concave min function: E[min(X, Y)] <= min(E[X], E[Y])
    rng = np.random.default_rng(42)
    s1 = rng.uniform(0.0, 2.0, size=1000)
    b2 = rng.uniform(0.0, 2.0, size=1000)

    trade_at_means = min(float(np.mean(s1)), float(np.mean(b2)))
    mean_of_trades = float(np.mean(np.minimum(s1, b2)))

    # Point/mean evaluation must be >= scenario-evaluated mean
    assert trade_at_means >= mean_of_trades - 1e-6
    # For independent uniform distributions, the difference is strictly positive
    assert trade_at_means > mean_of_trades


# ===========================================================================
# 5. Battery Physical Constraint Tests
# ===========================================================================

def test_battery_physical_bounds_and_efficiencies():
    """Verify SOC limits, rate limits, round-trip efficiencies, and invalid input rejection."""
    bat = BatteryStorage(
        capacity_kwh=5.0,
        initial_soc=0.50,
        min_soc=0.10,
        max_soc=0.90,
        max_charge_rate_kw=2.0,
        max_discharge_rate_kw=2.0,
        charge_efficiency=0.90,
        discharge_efficiency=0.90,
    )

    # 1. Reject invalid / non-finite inputs
    with pytest.raises(ValueError, match="finite"):
        bat.step(energy_available_to_charge_kwh=float("nan"))
    with pytest.raises(ValueError, match="nonnegative"):
        bat.step(energy_available_to_charge_kwh=-1.0)
    with pytest.raises(ValueError, match="positive"):
        bat.step(duration_hours=0.0)

    # 2. Charging respects power rate limit and efficiency
    # Initial energy = 2.5 kWh. Request 5.0 kWh charge over 1.0 hour.
    # Max power limit = 2.0 kW * 1.0 h = 2.0 kWh.
    # Stored energy increases by 2.0 * 0.90 = 1.8 kWh -> 4.3 kWh.
    st = bat.step(energy_available_to_charge_kwh=5.0, duration_hours=1.0)
    assert st.charged_kwh == pytest.approx(2.0)
    assert bat.current_charge_kwh == pytest.approx(4.3)
    assert st.discharged_kwh == 0.0

    # 3. Charging respects SOC max limit (headroom)
    # Max charge kWh = 0.90 * 5.0 = 4.5 kWh. Headroom = 4.5 - 4.3 = 0.2 kWh stored.
    # At terminal: 0.2 / 0.90 = 0.2222 kWh.
    st2 = bat.step(energy_available_to_charge_kwh=2.0, duration_hours=1.0)
    assert st2.charged_kwh == pytest.approx(0.2 / 0.90)
    assert bat.current_charge_kwh == pytest.approx(4.5)
    assert bat.soc == pytest.approx(0.90)

    # 4. Discharging respects SOC min limit (footroom)
    # Min charge kWh = 0.10 * 5.0 = 0.5 kWh. Stored = 4.5 kWh.
    # Available stored = 4.0 kWh. Delivered = 4.0 * 0.90 = 3.6 kWh.
    # But max discharge rate = 2.0 kW * 1.0 h = 2.0 kWh.
    st3 = bat.step(energy_requested_to_discharge_kwh=3.0, duration_hours=1.0)
    assert st3.discharged_kwh == pytest.approx(2.0)
    # Stored depleted by 2.0 / 0.90 = 2.2222 kWh -> 4.5 - 2.2222 = 2.2778 kWh
    assert bat.current_charge_kwh == pytest.approx(4.5 - (2.0 / 0.90))
    assert st3.charged_kwh == 0.0
