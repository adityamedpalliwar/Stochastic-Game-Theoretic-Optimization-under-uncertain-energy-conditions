"""Two-household game theory model execution and comparison."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Union

import pandas as pd

from src.energy.energy_balance import EnergyBalance, compute_energy_balance
from src.game.nash import EquilibriumAnalysisResult, find_pure_nash_equilibria
from src.game.payoff_matrix import GamePayoffMatrix, build_two_household_payoff_matrix


@dataclass
class GameComparisonResult:
    """Comparison between uncoordinated baseline and game equilibrium."""

    timestamp: Optional[pd.Timestamp]
    player1_id: str
    player2_id: str
    player1_surplus_kwh: float
    player2_deficit_kwh: float
    energy_traded_kwh: float
    p2p_price_aud: float
    baseline_cost_p1_aud: float
    baseline_cost_p2_aud: float
    baseline_total_cost_aud: float
    game_cost_p1_aud: float
    game_cost_p2_aud: float
    game_total_cost_aud: float
    saving_p1_aud: float
    saving_p2_aud: float
    total_community_savings_aud: float
    selected_strategy_p1: str
    selected_strategy_p2: str
    is_nash_equilibrium: bool
    is_strict_equilibrium: bool

    def to_dataframe(self) -> pd.DataFrame:
        """Present comparison as a clear summary table."""
        return pd.DataFrame([
            {
                "Household": self.player1_id,
                "Role": "Seller (Surplus)",
                "Energy_Available_kWh": round(self.player1_surplus_kwh, 4),
                "Baseline_Cost_AUD": round(self.baseline_cost_p1_aud, 4),
                "Game_Cost_AUD": round(self.game_cost_p1_aud, 4),
                "Cost_Savings_AUD": round(self.saving_p1_aud, 4),
                "Action": self.selected_strategy_p1,
            },
            {
                "Household": self.player2_id,
                "Role": "Buyer (Deficit)",
                "Energy_Available_kWh": round(self.player2_deficit_kwh, 4),
                "Baseline_Cost_AUD": round(self.baseline_cost_p2_aud, 4),
                "Game_Cost_AUD": round(self.game_cost_p2_aud, 4),
                "Cost_Savings_AUD": round(self.saving_p2_aud, 4),
                "Action": self.selected_strategy_p2,
            },
            {
                "Household": "TOTAL_COMMUNITY",
                "Role": "Microgrid Aggregation",
                "Energy_Available_kWh": round(self.energy_traded_kwh, 4),
                "Baseline_Cost_AUD": round(self.baseline_total_cost_aud, 4),
                "Game_Cost_AUD": round(self.game_total_cost_aud, 4),
                "Cost_Savings_AUD": round(self.total_community_savings_aud, 4),
                "Action": "COORDINATED_EQUILIBRIUM" if self.is_nash_equilibrium else "NO_EQUILIBRIUM",
            },
        ])


def run_two_household_game(
    balance_p1: EnergyBalance,
    balance_p2: EnergyBalance,
    grid_import_price_aud: float = 0.30,
    grid_export_credit_aud: float = 0.08,
    p2p_price_aud: Optional[float] = None,
) -> Tuple[GamePayoffMatrix, EquilibriumAnalysisResult, GameComparisonResult]:
    """Execute a 2-household energy trading game from energy balances.

    Parameters
    ----------
    balance_p1 : EnergyBalance
        Energy balance for Player 1.
    balance_p2 : EnergyBalance
        Energy balance for Player 2.
    grid_import_price_aud : float
        Grid retail purchase price.
    grid_export_credit_aud : float
        Grid solar feed-in credit.
    p2p_price_aud : Optional[float]
        Negotiated P2P price. If None, mid-market rate is used.

    Returns
    -------
    payoff_matrix : GamePayoffMatrix
    equilibrium_result : EquilibriumAnalysisResult
    comparison : GameComparisonResult
    """
    # Identify which player has surplus and which has deficit
    # If p1 has surplus and p2 deficit:
    seller = balance_p1 if balance_p1.surplus_kwh >= balance_p2.surplus_kwh else balance_p2
    buyer = balance_p2 if seller == balance_p1 else balance_p1

    matrix = build_two_household_payoff_matrix(
        seller_id=seller.house_id,
        seller_surplus_kwh=seller.surplus_kwh,
        buyer_id=buyer.house_id,
        buyer_deficit_kwh=buyer.deficit_kwh,
        grid_import_price_aud=grid_import_price_aud,
        grid_export_credit_aud=grid_export_credit_aud,
        p2p_price_aud=p2p_price_aud,
    )

    eq_result = find_pure_nash_equilibria(matrix)

    # Baseline cost (U = -C_net => C_net = -U)
    base_u_seller, base_u_buyer = eq_result.baseline_utilities
    base_cost_seller = -base_u_seller
    base_cost_buyer = -base_u_buyer

    if eq_result.selected_equilibrium is not None:
        eq = eq_result.selected_equilibrium
        game_cost_seller = -eq.utility_player1
        game_cost_buyer = -eq.utility_player2
        trade_q = eq.traded_energy_kwh
        act_seller = eq.action_player1
        act_buyer = eq.action_player2
        is_nash = True
        is_strict = eq.is_strict
    else:
        game_cost_seller = base_cost_seller
        game_cost_buyer = base_cost_buyer
        trade_q = 0.0
        act_seller = "NO_EQUILIBRIUM"
        act_buyer = "NO_EQUILIBRIUM"
        is_nash = False
        is_strict = False

    comp = GameComparisonResult(
        timestamp=balance_p1.timestamp,
        player1_id=seller.house_id,
        player2_id=buyer.house_id,
        player1_surplus_kwh=seller.surplus_kwh,
        player2_deficit_kwh=buyer.deficit_kwh,
        energy_traded_kwh=trade_q,
        p2p_price_aud=matrix.p2p_price_aud,
        baseline_cost_p1_aud=base_cost_seller,
        baseline_cost_p2_aud=base_cost_buyer,
        baseline_total_cost_aud=base_cost_seller + base_cost_buyer,
        game_cost_p1_aud=game_cost_seller,
        game_cost_p2_aud=game_cost_buyer,
        game_total_cost_aud=game_cost_seller + game_cost_buyer,
        saving_p1_aud=base_cost_seller - game_cost_seller,
        saving_p2_aud=base_cost_buyer - game_cost_buyer,
        total_community_savings_aud=(base_cost_seller + base_cost_buyer) - (game_cost_seller + game_cost_buyer),
        selected_strategy_p1=act_seller,
        selected_strategy_p2=act_buyer,
        is_nash_equilibrium=is_nash,
        is_strict_equilibrium=is_strict,
    )

    return matrix, eq_result, comp
