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

import numpy as np
import pandas as pd

from src.forecasting.lstm import LSTMWeights, predict_lstm_numpy
from src.forecasting.predict import EnergyForecaster, ForecastResult
from src.game.payoff_matrix import GamePayoffMatrix, build_two_household_payoff_matrix
from src.game.utility import compute_household_payoff


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
        random_seed: int = 42,
        paired: bool = True,
        method: str = "empirical",
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Sample residuals preserving correlation and variance."""
        rng = np.random.default_rng(random_seed)

        if house_id is not None:
            mask = (self.val_house_ids == house_id)
            res = self.residuals[mask]
        else:
            res = self.residuals

        if method == "empirical":
            # Resample paired residuals from validation observations
            indices = rng.choice(len(res), size=num_scenarios, replace=True)
            sampled = res[indices]
            return sampled[:, 0], sampled[:, 1]
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
        random_seed: int = 42,
        sampling_method: str = "empirical",
    ) -> ScenarioDistribution:
        """Generate 1,000 next-hour physical scenarios for a household.

        Parameters
        ----------
        forecast : ForecastResult
            Deterministic LSTM prediction.
        num_scenarios : int
            Number of Monte Carlo realizations (default 1,000).
        random_seed : int
            Reproducible seed.
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
) -> Tuple[GamePayoffMatrix, pd.DataFrame, Dict[str, Union[float, int]]]:
    """Construct a GamePayoffMatrix and detailed accounting metrics for expected payoffs.

    For every strategy profile a = (a1, a2), utilities and physical energy flows
    are evaluated scenario-by-scenario across all realizations s:
        S_1^{(s)} = max(0, G_1^{(s)} - D_1^{(s)})
        L_2^{(s)} = max(0, D_2^{(s)} - G_2^{(s)})
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

    exp_u1 = np.zeros((2, 2), dtype=float)
    exp_u2 = np.zeros((2, 2), dtype=float)
    exp_q = np.zeros((2, 2), dtype=float)

    # Physical surplus and deficit across scenarios
    surplus_seller = np.maximum(
        0.0, dist_seller.scenarios_solar_kwh - dist_seller.scenarios_demand_kwh
    )
    deficit_buyer = np.maximum(
        0.0, dist_buyer.scenarios_demand_kwh - dist_buyer.scenarios_solar_kwh
    )
    trade_q_scenarios = np.minimum(surplus_seller, deficit_buyer)

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

            total_seller_rev = gross_p2p_revenue + seller_export_rev
            total_buyer_cost = gross_p2p_payment + buyer_import_cost

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
                "Expected_Social_Welfare_AUD": round(float(np.mean(welfare_s)), 4),
                "Expected_Community_Net_Cost_AUD": round(float(np.mean(total_buyer_cost - total_seller_rev)), 4),
                "Std_Seller_Utility_AUD": round(float(np.std(u1_s, ddof=ddof_val)), 4),
                "Std_Buyer_Utility_AUD": round(float(np.std(u2_s, ddof=ddof_val)), 4),
                "Seller_Utility_Q05_AUD": round(float(np.percentile(u1_s, 5)), 4),
                "Seller_Utility_Q95_AUD": round(float(np.percentile(u1_s, 95)), 4),
                "Buyer_Utility_Q05_AUD": round(float(np.percentile(u2_s, 5)), 4),
                "Buyer_Utility_Q95_AUD": round(float(np.percentile(u2_s, 95)), 4),
                "Expected_Payoff_Pair": f"({mean_u1:.4f}, {mean_u2:.4f})",
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
    }

    return matrix, pd.DataFrame(rows), scenario_stats


def estimate_expected_payoff_matrix(
    dist_seller: ScenarioDistribution,
    dist_buyer: ScenarioDistribution,
    grid_import_price_aud: float = 0.30,
    grid_export_credit_aud: float = 0.08,
    p2p_price_aud: Optional[float] = None,
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
    )
    return df_summary, matrix.payoffs_p1, matrix.payoffs_p2
