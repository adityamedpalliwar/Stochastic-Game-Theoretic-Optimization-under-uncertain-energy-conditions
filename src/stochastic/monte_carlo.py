"""Monte Carlo simulation for forecast uncertainty and expected payoff estimation.

1. Calculates forecast residuals e_t = y_t - y_hat_t on chronological validation data.
2. Extracts empirical residual distribution (mean, standard deviation sigma = sqrt(Var(e)),
   quantiles, min, max).
3. Generates 1,000 paired demand and solar scenarios via empirical resampling or Gaussian sampling.
4. Enforces physical bounds: nonnegative demand (>= 0) and nonnegative solar (>= 0).
5. Computes expected payoffs E[U(a)] across scenarios for game-theoretic decision making
   WITHOUT averaging independent equilibria.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import zlib

import numpy as np
import pandas as pd

from src.energy.battery import BatteryStorage
from src.forecasting.lstm import LSTMWeights, predict_lstm_numpy
from src.forecasting.predict import EnergyForecaster, ForecastResult
from src.game.payoff_matrix import GamePayoffMatrix, build_two_household_payoff_matrix
from src.game.utility import compute_household_payoff


def derive_observation_seed(
    house_id: str,
    timestamp: Union[str, pd.Timestamp],
    base_seed: int = 42,
) -> int:
    """Generate a deterministic, 32-bit unsigned integer seed from observation identifiers.

    Provides reproducible, order-independent random number generation (Protocol B).
    """
    identifier = f"{house_id}_{pd.to_datetime(timestamp)}_{base_seed}"
    return zlib.crc32(identifier.encode("utf-8"))


@dataclass
class ResidualStatistics:
    """Statistical summary of forecast residuals."""

    target_name: str
    sample_size: int
    mean: float
    std_dev: float  # sigma = sqrt(Var(e))
    median: float
    q05: float
    q25: float
    q75: float
    q95: float
    min_val: float
    max_val: float

    def to_dict(self) -> Dict[str, Union[str, int, float]]:
        return {
            "target_name": self.target_name,
            "sample_size": self.sample_size,
            "mean": round(self.mean, 4),
            "std_dev": round(self.std_dev, 4),
            "median": round(self.median, 4),
            "q05": round(self.q05, 4),
            "q25": round(self.q25, 4),
            "q75": round(self.q75, 4),
            "q95": round(self.q95, 4),
            "min_val": round(self.min_val, 4),
            "max_val": round(self.max_val, 4),
        }


@dataclass
class ScenarioDistribution:
    """Summary of 1,000 generated next-hour physical scenarios."""

    house_id: str
    num_scenarios: int
    forecast_demand_mean_kwh: float
    forecast_solar_mean_kwh: float
    scenarios_demand_kwh: np.ndarray  # Shape (num_scenarios,)
    scenarios_solar_kwh: np.ndarray   # Shape (num_scenarios,)
    actual_demand_kwh: Optional[float] = None
    actual_solar_kwh: Optional[float] = None

    def get_summary_dataframe(self) -> pd.DataFrame:
        """Tabulate scenario statistics compared with forecast and actuals."""
        d = self.scenarios_demand_kwh
        s = self.scenarios_solar_kwh
        return pd.DataFrame([
            {
                "Variable": "Demand (kWh)",
                "Forecast_Mean": round(self.forecast_demand_mean_kwh, 4),
                "Scenario_Mean": round(float(np.mean(d)), 4),
                "Scenario_Std": round(float(np.std(d, ddof=1)), 4),
                "Q05": round(float(np.percentile(d, 5)), 4),
                "Median": round(float(np.median(d)), 4),
                "Q95": round(float(np.percentile(d, 95)), 4),
                "Min": round(float(np.min(d)), 4),
                "Max": round(float(np.max(d)), 4),
                "Actual": round(self.actual_demand_kwh, 4) if self.actual_demand_kwh is not None else None,
                "In_90pct_PI": (
                    bool(np.percentile(d, 5) <= self.actual_demand_kwh <= np.percentile(d, 95))
                    if self.actual_demand_kwh is not None else None
                ),
            },
            {
                "Variable": "Solar (kWh)",
                "Forecast_Mean": round(self.forecast_solar_mean_kwh, 4),
                "Scenario_Mean": round(float(np.mean(s)), 4),
                "Scenario_Std": round(float(np.std(s, ddof=1)), 4),
                "Q05": round(float(np.percentile(s, 5)), 4),
                "Median": round(float(np.median(s)), 4),
                "Q95": round(float(np.percentile(s, 95)), 4),
                "Min": round(float(np.min(s)), 4),
                "Max": round(float(np.max(s)), 4),
                "Actual": round(self.actual_solar_kwh, 4) if self.actual_solar_kwh is not None else None,
                "In_90pct_PI": (
                    bool(np.percentile(s, 5) <= self.actual_solar_kwh <= np.percentile(s, 95))
                    if self.actual_solar_kwh is not None else None
                ),
            },
        ])


class ValidationResidualPool:
    """Computes and caches validation residuals from lstm_sequences.npz."""

    def __init__(
        self,
        forecaster: Optional[EnergyForecaster] = None,
        sequences_path: Union[str, Path] = "data/processed/lstm_sequences.npz",
    ) -> None:
        self.forecaster = forecaster or EnergyForecaster()
        self.sequences_path = Path(sequences_path)

        seq = np.load(self.sequences_path)
        self.X_val = seq["X_val"]
        self.y_val = seq["y_val"]
        self.val_house_ids = np.asarray(seq["val_house_id"])
        self.val_timestamps = seq["val_target_timestamp"]
        self.val_hours = pd.to_datetime(self.val_timestamps).hour.to_numpy()

        # Run model on validation sequences
        preds_scaled = predict_lstm_numpy(self.X_val, self.forecaster.weights)
        self.preds_val_raw = np.maximum(0.0, self.forecaster.inverse_scale(preds_scaled))
        self.actual_val_raw = self.forecaster.inverse_scale(self.y_val)

        # Residuals: e = y - y_hat
        self.residuals = self.actual_val_raw - self.preds_val_raw
        self.demand_residuals = self.residuals[:, 0]
        self.solar_residuals = self.residuals[:, 1]

    def get_statistics(self, house_id: Optional[str] = None) -> Tuple[ResidualStatistics, ResidualStatistics]:
        """Compute residual statistics for demand and solar."""
        if house_id is not None:
            mask = (self.val_house_ids == house_id)
            ed = self.demand_residuals[mask]
            es = self.solar_residuals[mask]
        else:
            ed = self.demand_residuals
            es = self.solar_residuals

        def _stats(arr: np.ndarray, name: str) -> ResidualStatistics:
            return ResidualStatistics(
                target_name=name,
                sample_size=len(arr),
                mean=float(np.mean(arr)),
                std_dev=float(np.std(arr, ddof=1)),
                median=float(np.median(arr)),
                q05=float(np.percentile(arr, 5)),
                q25=float(np.percentile(arr, 25)),
                q75=float(np.percentile(arr, 75)),
                q95=float(np.percentile(arr, 95)),
                min_val=float(np.min(arr)),
                max_val=float(np.max(arr)),
            )

        return _stats(ed, "demand_residual_kwh"), _stats(es, "solar_residual_kwh")

    def sample_residuals(
        self,
        num_scenarios: int = 1000,
        house_id: Optional[str] = None,
        hour_of_day: Optional[int] = None,
        random_seed: Union[int, np.random.Generator, None] = 42,
        paired: bool = True,
        method: str = "empirical",
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Sample residuals preserving correlation and variance."""
        if isinstance(random_seed, np.random.Generator):
            rng = random_seed
        else:
            rng = np.random.default_rng(random_seed)

        mask = np.ones(len(self.residuals), dtype=bool)
        if house_id is not None:
            mask = mask & (self.val_house_ids == house_id)
        if hour_of_day is not None:
            mask = mask & (self.val_hours == hour_of_day)

        res = self.residuals[mask]
        if len(res) == 0:
            # Fallback if specific hour has no matching entries
            res = self.residuals[self.val_house_ids == house_id] if house_id is not None else self.residuals

        if method == "empirical":
            if paired:
                # Resample paired residuals from validation observations (preserves joint distribution)
                indices = rng.choice(len(res), size=num_scenarios, replace=True)
                sampled = res[indices]
                return sampled[:, 0], sampled[:, 1]
            else:
                # Resample demand and solar independently (breaks joint dependence)
                idx_d = rng.choice(len(res), size=num_scenarios, replace=True)
                idx_s = rng.choice(len(res), size=num_scenarios, replace=True)
                return res[idx_d, 0], res[idx_s, 1]
        elif method == "gaussian":
            # Parametric Gaussian using standard deviation sigma = sqrt(Var(e))
            mean_d, std_d = np.mean(res[:, 0]), np.std(res[:, 0], ddof=1)
            mean_s, std_s = np.mean(res[:, 1]), np.std(res[:, 1], ddof=1)
            ed = rng.normal(mean_d, std_d, size=num_scenarios)
            es = rng.normal(mean_s, std_s, size=num_scenarios)
            return ed, es
        else:
            raise ValueError(f"Unknown sampling method: {method}")


class MonteCarloSimulator:
    """Generates physical scenario distributions around LSTM forecast means."""

    def __init__(self, residual_pool: Optional[ValidationResidualPool] = None) -> None:
        self.residual_pool = residual_pool or ValidationResidualPool()

    def generate_scenarios(
        self,
        forecast: ForecastResult,
        num_scenarios: int = 1000,
        random_seed: Union[int, np.random.Generator, None] = 42,
        sampling_method: str = "empirical",
    ) -> ScenarioDistribution:
        """Generate 1,000 next-hour physical scenarios for a household.

        Parameters
        ----------
        forecast : ForecastResult
            Deterministic LSTM prediction.
        num_scenarios : int
            Number of Monte Carlo realizations (default 1,000).
        random_seed : Union[int, np.random.Generator, None]
            Reproducible seed or active Generator.
        sampling_method : str
            'empirical' (recommended paired resampling) or 'gaussian'.

        Returns
        -------
        ScenarioDistribution
            Bound-checked physical realizations (demand >= 0, solar >= 0).
        """
        ed, es = self.residual_pool.sample_residuals(
            num_scenarios=num_scenarios,
            house_id=forecast.house_id,
            random_seed=random_seed,
            method=sampling_method,
        )

        # Perturb forecast mean with sampled residuals
        scenarios_demand = forecast.predicted_demand_kwh + ed
        scenarios_solar = forecast.predicted_solar_generation_kwh + es

        # Physical constraints: energy must be nonnegative
        scenarios_demand = np.maximum(0.0, scenarios_demand)
        scenarios_solar = np.maximum(0.0, scenarios_solar)

        return ScenarioDistribution(
            house_id=forecast.house_id,
            num_scenarios=num_scenarios,
            forecast_demand_mean_kwh=forecast.predicted_demand_kwh,
            forecast_solar_mean_kwh=forecast.predicted_solar_generation_kwh,
            scenarios_demand_kwh=scenarios_demand,
            scenarios_solar_kwh=scenarios_solar,
            actual_demand_kwh=forecast.actual_demand_kwh,
            actual_solar_kwh=forecast.actual_solar_generation_kwh,
        )


def build_stochastic_payoff_matrix(
    dist_seller: ScenarioDistribution,
    dist_buyer: ScenarioDistribution,
    grid_import_price_aud: float = 0.30,
    grid_export_credit_aud: float = 0.08,
    p2p_price_aud: Optional[float] = None,
    battery_seller: Optional[BatteryStorage] = None,
    battery_buyer: Optional[BatteryStorage] = None,
    duration_hours: float = 1.0,
    degradation_cost_per_kwh: float = 0.0,
) -> Tuple[GamePayoffMatrix, pd.DataFrame, Dict[str, Union[float, int]]]:
    """Construct a GamePayoffMatrix and detailed accounting metrics for expected payoffs.

    For every strategy profile a = (a1, a2), utilities and physical energy flows
    are evaluated scenario-by-scenario across all realizations s:
        S_1^{(s)} = max(0, G_1^{(s)} - D_1^{(s)} - C_1^{(s)})
        L_2^{(s)} = max(0, D_2^{(s)} - G_2^{(s)} - D_2^{(s)})
        Q_P2P^{(s)} = min(S_1^{(s)}, L_2^{(s)}) if (a1, a2) == ('OFFER_P2P', 'ACCEPT_P2P') else 0.0

    Then:
        E[U_i(a)] = (1/N) * sum_s U_i(a, omega_s)
    """
    if p2p_price_aud is None:
        p2p_price = (grid_import_price_aud + grid_export_credit_aud) / 2.0
    else:
        p2p_price = float(p2p_price_aud)

    actions_p1 = ["OFFER_P2P", "EXPORT_GRID"]
    actions_p2 = ["ACCEPT_P2P", "GRID_IMPORT"]

    n_scenarios = len(dist_seller.scenarios_demand_kwh)
    if n_scenarios != len(dist_buyer.scenarios_demand_kwh):
        raise ValueError(
            f"Scenario count mismatch: seller has {n_scenarios}, buyer has {len(dist_buyer.scenarios_demand_kwh)}"
        )

    # Raw physical surplus and deficit across scenarios
    raw_surplus_seller = np.maximum(
        0.0, dist_seller.scenarios_solar_kwh - dist_seller.scenarios_demand_kwh
    )
    raw_deficit_seller = np.maximum(
        0.0, dist_seller.scenarios_demand_kwh - dist_seller.scenarios_solar_kwh
    )

    raw_surplus_buyer = np.maximum(
        0.0, dist_buyer.scenarios_solar_kwh - dist_buyer.scenarios_demand_kwh
    )
    raw_deficit_buyer = np.maximum(
        0.0, dist_buyer.scenarios_demand_kwh - dist_buyer.scenarios_solar_kwh
    )

    # Battery dispatch for seller (if present)
    if battery_seller is not None:
        e0_s = float(battery_seller.current_charge_kwh)
        headroom_s = (battery_seller.max_charge_kwh - e0_s) / battery_seller.charge_efficiency
        max_p_ch_s = battery_seller.max_charge_rate_kw * duration_hours
        seller_charged = np.maximum(0.0, np.minimum(raw_surplus_seller, np.minimum(max_p_ch_s, headroom_s)))

        footroom_s = (e0_s - battery_seller.min_charge_kwh) * battery_seller.discharge_efficiency
        max_p_dis_s = battery_seller.max_discharge_rate_kw * duration_hours
        seller_discharged = np.maximum(0.0, np.minimum(raw_deficit_seller, np.minimum(max_p_dis_s, footroom_s)))

        surplus_seller = raw_surplus_seller - seller_charged
        deficit_seller = raw_deficit_seller - seller_discharged
        final_e_s = e0_s + battery_seller.charge_efficiency * seller_charged - (seller_discharged / battery_seller.discharge_efficiency)
        final_soc_s = final_e_s / battery_seller.capacity_kwh
        init_soc_s = e0_s / battery_seller.capacity_kwh
    else:
        seller_charged = np.zeros(n_scenarios, dtype=float)
        seller_discharged = np.zeros(n_scenarios, dtype=float)
        surplus_seller = raw_surplus_seller
        deficit_seller = raw_deficit_seller
        final_soc_s = np.zeros(n_scenarios, dtype=float)
        init_soc_s = 0.0

    # Battery dispatch for buyer (if present)
    if battery_buyer is not None:
        e0_b = float(battery_buyer.current_charge_kwh)
        headroom_b = (battery_buyer.max_charge_kwh - e0_b) / battery_buyer.charge_efficiency
        max_p_ch_b = battery_buyer.max_charge_rate_kw * duration_hours
        buyer_charged = np.maximum(0.0, np.minimum(raw_surplus_buyer, np.minimum(max_p_ch_b, headroom_b)))

        footroom_b = (e0_b - battery_buyer.min_charge_kwh) * battery_buyer.discharge_efficiency
        max_p_dis_b = battery_buyer.max_discharge_rate_kw * duration_hours
        buyer_discharged = np.maximum(0.0, np.minimum(raw_deficit_buyer, np.minimum(max_p_dis_b, footroom_b)))

        surplus_buyer = raw_surplus_buyer - buyer_charged
        deficit_buyer = raw_deficit_buyer - buyer_discharged
        final_e_b = e0_b + battery_buyer.charge_efficiency * buyer_charged - (buyer_discharged / battery_buyer.discharge_efficiency)
        final_soc_b = final_e_b / battery_buyer.capacity_kwh
        init_soc_b = e0_b / battery_buyer.capacity_kwh
    else:
        buyer_charged = np.zeros(n_scenarios, dtype=float)
        buyer_discharged = np.zeros(n_scenarios, dtype=float)
        surplus_buyer = raw_surplus_buyer
        deficit_buyer = raw_deficit_buyer
        final_soc_b = np.zeros(n_scenarios, dtype=float)
        init_soc_b = 0.0

    trade_q_scenarios = np.minimum(surplus_seller, deficit_buyer)

    exp_u1 = np.zeros((2, 2), dtype=float)
    exp_u2 = np.zeros((2, 2), dtype=float)
    exp_q = np.zeros((2, 2), dtype=float)

    rows = []

    for i, a1 in enumerate(actions_p1):
        for j, a2 in enumerate(actions_p2):
            if a1 == "OFFER_P2P" and a2 == "ACCEPT_P2P":
                q_s = trade_q_scenarios
            else:
                q_s = np.zeros(n_scenarios, dtype=float)

            rem_surplus = surplus_seller - q_s
            rem_deficit = deficit_buyer - q_s

            # Cash flows per scenario
            gross_p2p_revenue = q_s * p2p_price
            gross_p2p_payment = q_s * p2p_price
            seller_export_rev = rem_surplus * grid_export_credit_aud
            buyer_import_cost = rem_deficit * grid_import_price_aud

            seller_deg = (seller_charged + seller_discharged) * degradation_cost_per_kwh
            buyer_deg = (buyer_charged + buyer_discharged) * degradation_cost_per_kwh

            total_seller_rev = gross_p2p_revenue + seller_export_rev - seller_deg
            total_buyer_cost = gross_p2p_payment + buyer_import_cost + buyer_deg

            u1_s = total_seller_rev
            u2_s = -total_buyer_cost
            welfare_s = u1_s + u2_s

            mean_u1 = float(np.mean(u1_s))
            mean_u2 = float(np.mean(u2_s))
            mean_q = float(np.mean(q_s))

            exp_u1[i, j] = mean_u1
            exp_u2[i, j] = mean_u2
            exp_q[i, j] = mean_q

            ddof_val = 1 if n_scenarios > 1 else 0
            rows.append({
                f"Action_{dist_seller.house_id}": a1,
                f"Action_{dist_buyer.house_id}": a2,
                "Expected_P2P_Traded_kWh": round(mean_q, 4),
                "Expected_Residual_Surplus_kWh": round(float(np.mean(rem_surplus)), 4),
                "Expected_Residual_Deficit_kWh": round(float(np.mean(rem_deficit)), 4),
                "Expected_Gross_P2P_Payment_AUD": round(float(np.mean(gross_p2p_payment)), 4),
                "Expected_Seller_Export_Revenue_AUD": round(float(np.mean(seller_export_rev)), 4),
                "Expected_Buyer_Grid_Cost_AUD": round(float(np.mean(buyer_import_cost)), 4),
                "Expected_Seller_Revenue_AUD": round(float(np.mean(total_seller_rev)), 4),
                "Expected_Buyer_Cost_AUD": round(float(np.mean(total_buyer_cost)), 4),
                f"Expected_Utility_{dist_seller.house_id}": round(mean_u1, 4),
                f"Expected_Utility_{dist_buyer.house_id}": round(mean_u2, 4),
                "Expected_Combined_Household_Utility_AUD": round(float(np.mean(welfare_s)), 4),
                "Expected_Social_Welfare_AUD": round(float(np.mean(welfare_s)), 4),  # alias for backward compatibility
                "Expected_Community_Net_Cost_AUD": round(float(np.mean(total_buyer_cost - total_seller_rev)), 4),
                "Std_Seller_Utility_AUD": round(float(np.std(u1_s, ddof=ddof_val)), 4),
                "Std_Buyer_Utility_AUD": round(float(np.std(u2_s, ddof=ddof_val)), 4),
                "Seller_Utility_Q05_AUD": round(float(np.percentile(u1_s, 5)), 4),
                "Seller_Utility_Q95_AUD": round(float(np.percentile(u1_s, 95)), 4),
                "Buyer_Utility_Q05_AUD": round(float(np.percentile(u2_s, 5)), 4),
                "Buyer_Utility_Q95_AUD": round(float(np.percentile(u2_s, 95)), 4),
                "Expected_Payoff_Pair": f"({mean_u1:.4f}, {mean_u2:.4f})",
                "Expected_Seller_Battery_Charged_kWh": round(float(np.mean(seller_charged)), 4),
                "Expected_Seller_Battery_Discharged_kWh": round(float(np.mean(seller_discharged)), 4),
                "Expected_Buyer_Battery_Charged_kWh": round(float(np.mean(buyer_charged)), 4),
                "Expected_Buyer_Battery_Discharged_kWh": round(float(np.mean(buyer_discharged)), 4),
            })

    matrix = GamePayoffMatrix(
        player1_id=dist_seller.house_id,
        player2_id=dist_buyer.house_id,
        actions_p1=actions_p1,
        actions_p2=actions_p2,
        payoffs_p1=exp_u1,
        payoffs_p2=exp_u2,
        traded_quantities=exp_q,
        p2p_price_aud=p2p_price,
        grid_import_price_aud=grid_import_price_aud,
        grid_export_credit_aud=grid_export_credit_aud,
        details={},
    )

    tradeable_count = int(np.sum(trade_q_scenarios > 1e-6))
    ddof_stats = 1 if n_scenarios > 1 else 0
    scenario_stats: Dict[str, Union[float, int]] = {
        "num_scenarios": n_scenarios,
        "seller_surplus_mean_kwh": float(np.mean(surplus_seller)),
        "seller_surplus_std_kwh": float(np.std(surplus_seller, ddof=ddof_stats)),
        "buyer_deficit_mean_kwh": float(np.mean(deficit_buyer)),
        "buyer_deficit_std_kwh": float(np.std(deficit_buyer, ddof=ddof_stats)),
        "tradeable_scenarios_count": tradeable_count,
        "tradeable_scenarios_pct": round((tradeable_count / n_scenarios) * 100.0, 2),
        "mean_feasible_trade_kwh": float(np.mean(trade_q_scenarios)),
        "max_feasible_trade_kwh": float(np.max(trade_q_scenarios)),
        "seller_expected_gain_aud": float(exp_u1[0, 0] - exp_u1[1, 1]),
        "buyer_expected_saving_aud": float(exp_u2[0, 0] - exp_u2[1, 1]),
        "community_expected_saving_aud": float(
            (exp_u1[0, 0] + exp_u2[0, 0]) - (exp_u1[1, 1] + exp_u2[1, 1])
        ),
        "seller_battery_charged_mean_kwh": float(np.mean(seller_charged)),
        "seller_battery_discharged_mean_kwh": float(np.mean(seller_discharged)),
        "seller_battery_initial_soc": float(init_soc_s),
        "seller_battery_final_soc_mean": float(np.mean(final_soc_s)),
        "buyer_battery_charged_mean_kwh": float(np.mean(buyer_charged)),
        "buyer_battery_discharged_mean_kwh": float(np.mean(buyer_discharged)),
        "buyer_battery_initial_soc": float(init_soc_b),
        "buyer_battery_final_soc_mean": float(np.mean(final_soc_b)),
    }

    return matrix, pd.DataFrame(rows), scenario_stats


def estimate_expected_payoff_matrix(
    dist_seller: ScenarioDistribution,
    dist_buyer: ScenarioDistribution,
    grid_import_price_aud: float = 0.30,
    grid_export_credit_aud: float = 0.08,
    p2p_price_aud: Optional[float] = None,
    battery_seller: Optional[BatteryStorage] = None,
    battery_buyer: Optional[BatteryStorage] = None,
    duration_hours: float = 1.0,
    degradation_cost_per_kwh: float = 0.0,
) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Estimate expected payoffs across 1,000 Monte Carlo scenarios.

    DOES NOT average 1,000 independent Nash equilibria.
    Estimates E[U_i(a_1, a_2)] directly by evaluating payoff across realizations.
    """
    matrix, df_summary, _ = build_stochastic_payoff_matrix(
        dist_seller=dist_seller,
        dist_buyer=dist_buyer,
        grid_import_price_aud=grid_import_price_aud,
        grid_export_credit_aud=grid_export_credit_aud,
        p2p_price_aud=p2p_price_aud,
        battery_seller=battery_seller,
        battery_buyer=battery_buyer,
        duration_hours=duration_hours,
        degradation_cost_per_kwh=degradation_cost_per_kwh,
    )
    return df_summary, matrix.payoffs_p1, matrix.payoffs_p2


@dataclass
class StochasticMarketClearingSummary:
    """Statistical summary of multi-household market clearing evaluated across Monte Carlo scenarios."""

    num_scenarios: int
    policy: str
    expected_traded_kwh: float
    std_traded_kwh: float
    max_traded_kwh: float
    active_trading_frequency_pct: float
    expected_household_utilities: Dict[str, float]
    utility_std: Dict[str, float]
    utility_q05: Dict[str, float]
    utility_q95: Dict[str, float]
    expected_combined_utility_aud: float
    expected_p2p_sold_kwh: Dict[str, float]
    expected_p2p_bought_kwh: Dict[str, float]
    expected_grid_export_kwh: Dict[str, float]
    expected_grid_import_kwh: Dict[str, float]
    expected_battery_charged_kwh: Dict[str, float]
    expected_battery_discharged_kwh: Dict[str, float]
    expected_final_soc: Dict[str, float]
    deterministic_mean_traded_kwh: float
    jensen_overestimation_kwh: float
    scenario_dataframe: pd.DataFrame


def run_stochastic_multi_household_clearing(
    scenario_distributions: Dict[str, ScenarioDistribution],
    batteries: Optional[Dict[str, BatteryStorage]] = None,
    p2p_price_aud: float = 0.19,
    grid_import_price_aud: float = 0.30,
    grid_export_credit_aud: float = 0.08,
    policy: str = "priority_order",
    priority_order: Optional[Sequence[str]] = None,
    degradation_cost_per_kwh: float = 0.0,
    timestamp: Optional[pd.Timestamp] = None,
) -> Tuple[StochasticMarketClearingSummary, pd.DataFrame]:
    """Execute scenario-by-scenario multi-household P2P market clearing across Monte Carlo realizations.

    CRITICAL INVARIANT: Evaluates market clearing scenario-by-scenario. Does not replace
    uncertain solar/demand with mean values prior to market clearing.

    Parameters:
        scenario_distributions: Map of house_id -> ScenarioDistribution (all with same num_scenarios).
        batteries: Optional map of house_id -> BatteryStorage (dispatched battery-first before clearing).
        p2p_price_aud: Mid-market P2P transaction price.
        grid_import_price_aud: Retail grid import tariff.
        grid_export_credit_aud: Solar feed-in credit.
        policy: MarketClearingPolicy name ('priority_order', 'largest_surplus_first', 'pro_rata').
        priority_order: Optional priority sequence for matching.
        degradation_cost_per_kwh: Battery cycle degradation cost.
        timestamp: Optional observation timestamp.

    Returns:
        (StochasticMarketClearingSummary, scenario_dataframe)
    """
    from src.energy.market_clearing import MarketClearingPolicy, clear_multi_household_market
    from src.energy.energy_balance import compute_energy_balance, compute_battery_aware_balance

    house_ids = sorted(scenario_distributions.keys())
    if not house_ids:
        raise ValueError("Must provide at least one household scenario distribution.")

    n_scenarios = scenario_distributions[house_ids[0]].num_scenarios
    for hid in house_ids:
        if scenario_distributions[hid].num_scenarios != n_scenarios:
            raise ValueError(
                f"Scenario count mismatch: {hid} has {scenario_distributions[hid].num_scenarios} "
                f"while {house_ids[0]} has {n_scenarios}"
            )

    traded_kwh_arr = np.zeros(n_scenarios, dtype=float)
    utilities_arr = {hid: np.zeros(n_scenarios, dtype=float) for hid in house_ids}
    p2p_sold_arr = {hid: np.zeros(n_scenarios, dtype=float) for hid in house_ids}
    p2p_bought_arr = {hid: np.zeros(n_scenarios, dtype=float) for hid in house_ids}
    grid_exp_arr = {hid: np.zeros(n_scenarios, dtype=float) for hid in house_ids}
    grid_imp_arr = {hid: np.zeros(n_scenarios, dtype=float) for hid in house_ids}
    bat_ch_arr = {hid: np.zeros(n_scenarios, dtype=float) for hid in house_ids}
    bat_dis_arr = {hid: np.zeros(n_scenarios, dtype=float) for hid in house_ids}
    final_soc_arr = {hid: np.zeros(n_scenarios, dtype=float) for hid in house_ids}

    scenario_rows = []

    # Scenario-by-scenario evaluation
    for s in range(n_scenarios):
        scenario_balances = []
        for hid in house_ids:
            d_s = float(scenario_distributions[hid].scenarios_demand_kwh[s])
            g_s = float(scenario_distributions[hid].scenarios_solar_kwh[s])

            if batteries is not None and hid in batteries and batteries[hid] is not None:
                b_s = compute_battery_aware_balance(
                    demand_kwh=d_s,
                    solar_generation_kwh=g_s,
                    battery=batteries[hid].copy(),
                    house_id=hid,
                    timestamp=timestamp,
                )
            else:
                b_s = compute_energy_balance(
                    demand_kwh=d_s,
                    solar_generation_kwh=g_s,
                    house_id=hid,
                    timestamp=timestamp,
                )
            scenario_balances.append(b_s)

        res = clear_multi_household_market(
            bids_or_balances=scenario_balances,
            p2p_price_aud=p2p_price_aud,
            grid_import_price_aud=grid_import_price_aud,
            grid_export_credit_aud=grid_export_credit_aud,
            policy=policy,
            priority_order=priority_order,
            degradation_cost_per_kwh=degradation_cost_per_kwh,
            timestamp=timestamp,
        )

        traded_kwh_arr[s] = res.total_traded_kwh
        row = {"Scenario": s, "Total_P2P_Traded_kWh": res.total_traded_kwh, "Transactions_Count": len(res.transactions)}

        for hid in house_ids:
            pt = res.post_trade_balances[hid]
            pay = res.payoffs[hid]

            utilities_arr[hid][s] = pay.utility
            p2p_sold_arr[hid][s] = pt.p2p_sold_kwh
            p2p_bought_arr[hid][s] = pt.p2p_bought_kwh
            grid_exp_arr[hid][s] = pt.grid_exported_kwh
            grid_imp_arr[hid][s] = pt.grid_imported_kwh
            bat_ch_arr[hid][s] = getattr(pt, "solar_to_battery_kwh", 0.0)
            bat_dis_arr[hid][s] = getattr(pt, "battery_to_demand_kwh", 0.0)
            final_soc_arr[hid][s] = getattr(pt, "battery_final_soc", 0.0)

            row[f"Utility_{hid}_AUD"] = pay.utility
            row[f"P2P_Sold_{hid}_kWh"] = pt.p2p_sold_kwh
            row[f"P2P_Bought_{hid}_kWh"] = pt.p2p_bought_kwh

        row["Combined_Utility_AUD"] = res.community_summary.combined_household_utility_aud
        scenario_rows.append(row)

    df_scenarios = pd.DataFrame(scenario_rows)

    # Naive mean deterministic evaluation for Jensen's inequality comparison
    mean_balances = []
    for hid in house_ids:
        mean_d = float(np.mean(scenario_distributions[hid].scenarios_demand_kwh))
        mean_g = float(np.mean(scenario_distributions[hid].scenarios_solar_kwh))
        if batteries is not None and hid in batteries and batteries[hid] is not None:
            b_m = compute_battery_aware_balance(
                demand_kwh=mean_d,
                solar_generation_kwh=mean_g,
                battery=batteries[hid].copy(),
                house_id=hid,
                timestamp=timestamp,
            )
        else:
            b_m = compute_energy_balance(
                demand_kwh=mean_d,
                solar_generation_kwh=mean_g,
                house_id=hid,
                timestamp=timestamp,
            )
        mean_balances.append(b_m)

    res_mean = clear_multi_household_market(
        bids_or_balances=mean_balances,
        p2p_price_aud=p2p_price_aud,
        grid_import_price_aud=grid_import_price_aud,
        grid_export_credit_aud=grid_export_credit_aud,
        policy=policy,
        priority_order=priority_order,
        degradation_cost_per_kwh=degradation_cost_per_kwh,
        timestamp=timestamp,
    )
    det_mean_traded = res_mean.total_traded_kwh
    exp_traded = float(np.mean(traded_kwh_arr))
    jensen_diff = det_mean_traded - exp_traded

    ddof_val = 1 if n_scenarios > 1 else 0
    tradeable_count = int(np.sum(traded_kwh_arr > 1e-6))
    active_freq = (tradeable_count / n_scenarios) * 100.0

    summary = StochasticMarketClearingSummary(
        num_scenarios=n_scenarios,
        policy=str(policy),
        expected_traded_kwh=round(exp_traded, 4),
        std_traded_kwh=round(float(np.std(traded_kwh_arr, ddof=ddof_val)), 4),
        max_traded_kwh=round(float(np.max(traded_kwh_arr)), 4),
        active_trading_frequency_pct=round(active_freq, 2),
        expected_household_utilities={hid: round(float(np.mean(utilities_arr[hid])), 4) for hid in house_ids},
        utility_std={hid: round(float(np.std(utilities_arr[hid], ddof=ddof_val)), 4) for hid in house_ids},
        utility_q05={hid: round(float(np.percentile(utilities_arr[hid], 5)), 4) for hid in house_ids},
        utility_q95={hid: round(float(np.percentile(utilities_arr[hid], 95)), 4) for hid in house_ids},
        expected_combined_utility_aud=round(float(np.mean([sum(utilities_arr[h][s] for h in house_ids) for s in range(n_scenarios)])), 4),
        expected_p2p_sold_kwh={hid: round(float(np.mean(p2p_sold_arr[hid])), 4) for hid in house_ids},
        expected_p2p_bought_kwh={hid: round(float(np.mean(p2p_bought_arr[hid])), 4) for hid in house_ids},
        expected_grid_export_kwh={hid: round(float(np.mean(grid_exp_arr[hid])), 4) for hid in house_ids},
        expected_grid_import_kwh={hid: round(float(np.mean(grid_imp_arr[hid])), 4) for hid in house_ids},
        expected_battery_charged_kwh={hid: round(float(np.mean(bat_ch_arr[hid])), 4) for hid in house_ids},
        expected_battery_discharged_kwh={hid: round(float(np.mean(bat_dis_arr[hid])), 4) for hid in house_ids},
        expected_final_soc={hid: round(float(np.mean(final_soc_arr[hid])), 4) for hid in house_ids},
        deterministic_mean_traded_kwh=round(det_mean_traded, 4),
        jensen_overestimation_kwh=round(jensen_diff, 4),
        scenario_dataframe=df_scenarios,
    )

    return summary, df_scenarios
