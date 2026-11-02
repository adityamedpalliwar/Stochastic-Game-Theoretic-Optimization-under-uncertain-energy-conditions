"""Unit tests for N-player energy trading game with battery storage and dynamic pricing."""

import pytest
import numpy as np
import pandas as pd

from src.energy.battery import BatteryStorage
from src.game.pricing import (
    LinearDemandPricing,
    ElasticDemandPricing,
    StackelbergDemandPricing,
    MidMarketPricing,
    get_pricing_model,
)
from src.game.payoff_matrix import (
    build_n_player_payoff_matrix,
    dispatch_battery_pre_game,
    BatteryDispatchResult,
)
from src.game.nash import find_nash_equilibria_n_players
from src.game.best_response import compute_best_responses_n_players, get_dominant_strategy
from src.game.game import run_n_player_game, create_default_batteries


def test_battery_pre_game_dispatch():
    """Verify battery charging from surplus and discharging to cover deficit."""
    batt = BatteryStorage(capacity_kwh=5.0, initial_soc=0.5, max_charge_rate_kw=2.5, max_discharge_rate_kw=2.5)

    # Surplus case: battery absorbs up to headroom
    disp_s = dispatch_battery_pre_game(
        player_id="H001",
        raw_surplus_kwh=2.0,
        raw_deficit_kwh=0.0,
        battery=batt,
    )
    assert disp_s.charged_kwh == pytest.approx(2.0)
    assert disp_s.net_surplus_kwh == pytest.approx(0.0)
    assert disp_s.final_soc > disp_s.initial_soc

    # Deficit case: battery discharges to meet demand
    disp_d = dispatch_battery_pre_game(
        player_id="H002",
        raw_surplus_kwh=0.0,
        raw_deficit_kwh=1.5,
        battery=batt,
    )
    assert disp_d.discharged_kwh == pytest.approx(1.5)
    assert disp_d.net_deficit_kwh == pytest.approx(0.0)


def test_n_player_game_with_batteries_and_dynamic_pricing():
    """Verify complete 5-player game execution with batteries and dynamic pricing."""
    pids = ["H001", "H002", "H003", "H004", "H005"]
    surpluses = [4.0, 0.0, 3.0, 0.0, 0.0]
    deficits  = [0.0, 3.0, 0.0, 2.5, 2.0]

    batteries = create_default_batteries(pids, capacity_kwh=5.0, initial_soc=0.50)
    pricing = LinearDemandPricing(max_pressure=2.0)

    result = run_n_player_game(
        player_ids=pids,
        surpluses_kwh=surpluses,
        deficits_kwh=deficits,
        batteries=batteries,
        pricing_model=pricing,
    )

    assert result.has_equilibrium
    assert len(result.selected_actions) == 5
    for pid in pids:
        assert result.selected_actions[pid] in ["TRADE", "GRID_ONLY"]

    # Check that batteries performed charge/discharge
    assert result.battery_charged_kwh["H001"] > 0.0
    assert result.battery_discharged_kwh["H002"] > 0.0

    # Summary dataframe test
    df_sum = result.to_summary_dataframe()
    assert df_sum.shape[0] == 6  # 5 houses + 1 community row
    assert "COMMUNITY_TOTAL" in df_sum["player_id"].values
    assert result.total_community_savings_aud >= 0.0
