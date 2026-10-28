"""Phase 6B: Single-Household Stochastic Scenario-Based Model Predictive Control (MPC).

Implements:
- Multi-scenario rolling-horizon Mixed-Integer Linear Program (MILP)
- Strict non-anticipativity on first-stage decisions (C_0, D_0, u_0_ch shared across all scenarios)
- Recourse decisions (C_{t,w}, D_{t,w}, u_{t,w}_ch, E_{t+1,w}, M_{t,w}, X_{t,w}) for t >= 1
- Empirical scenario generation using historical validation residuals (ValidationResidualPool)
- Deterministic order-independent observation seeding (derive_observation_seed)
- Strict physical energy conservation and mutual exclusion per scenario
- Clean physical simulator enforcing identical information boundaries and physical operating rules
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint
from scipy.sparse import csc_matrix

from src.energy.battery import BatteryStorage
from src.optimization.constraints import (
    BatteryOptimizationParams,
    MPCConfig,
    TariffParams,
)
from src.optimization.solver import MILPResult, solve_milp
from src.stochastic.monte_carlo import ValidationResidualPool, derive_observation_seed


@dataclass(frozen=True)
class StochasticMPCConfig:
    """Configuration for Stochastic Scenario-Based MPC."""

    horizon_hours: int = 24
    time_step_hours: float = 1.0
    num_scenarios: int = 5
    sampling_method: str = "empirical"  # 'empirical' or 'gaussian'
    include_nominal: bool = True       # Scenario 0 is the nominal deterministic forecast
    terminal_strategy: str = "terminal_value"  # 'terminal_value', 'terminal_soc_target', 'unconstrained'
    terminal_soc_target: float = 0.50
    terminal_value_aud_per_kwh: Optional[float] = None
    allow_grid_charging: bool = True   # Consistent with Phase 6A benchmark
    slack_penalty: float = 1000.0
    time_limit_sec: float = 30.0
    base_seed: int = 42

    def __post_init__(self) -> None:
        if self.horizon_hours < 1:
            raise ValueError("horizon_hours must be at least 1.")
        if self.num_scenarios < 1:
            raise ValueError("num_scenarios must be at least 1.")
        if self.time_step_hours <= 0:
            raise ValueError("time_step_hours must be strictly positive.")


@dataclass
class ScenarioSet:
    """Bundle of scenarios over the planning horizon."""

    num_scenarios: int
    horizon_hours: int
    scenarios_demand_kwh: np.ndarray  # Shape (num_scenarios, horizon_hours)
    scenarios_solar_kwh: np.ndarray   # Shape (num_scenarios, horizon_hours)
    probabilities: np.ndarray         # Shape (num_scenarios,), sums to 1.0

    def __post_init__(self) -> None:
        if self.scenarios_demand_kwh.shape != (self.num_scenarios, self.horizon_hours):
            raise ValueError(
                f"Demand scenario shape {self.scenarios_demand_kwh.shape} mismatch with ({self.num_scenarios}, {self.horizon_hours})"
            )
        if self.scenarios_solar_kwh.shape != (self.num_scenarios, self.horizon_hours):
            raise ValueError(
                f"Solar scenario shape {self.scenarios_solar_kwh.shape} mismatch with ({self.num_scenarios}, {self.horizon_hours})"
            )
        if len(self.probabilities) != self.num_scenarios:
            raise ValueError("Probabilities length must match num_scenarios.")
        if not np.allclose(np.sum(self.probabilities), 1.0, atol=1e-5):
            raise ValueError("Scenario probabilities must sum to 1.0.")


class StochasticScenarioGenerator:
    """Generates physically constrained scenario bundles over a lookahead horizon."""

    def __init__(self, residual_pool: Optional[ValidationResidualPool] = None) -> None:
        self.residual_pool = residual_pool or ValidationResidualPool()

    def generate_horizon_scenarios(
        self,
        demand_forecast: Union[np.ndarray, Sequence[float]],
        solar_forecast: Union[np.ndarray, Sequence[float]],
        house_id: str = "H001",
        timestamp: Optional[Union[str, pd.Timestamp]] = None,
        num_scenarios: int = 5,
        include_nominal: bool = True,
        sampling_method: str = "empirical",
        base_seed: int = 42,
    ) -> ScenarioSet:
        """Generate S scenarios of demand and solar generation over horizon T.

        Parameters
        ----------
        demand_forecast : Sequence[float]
            Point prediction vector of length T.
        solar_forecast : Sequence[float]
            Point prediction vector of length T.
        house_id : str
            Identifier of the household.
        timestamp : Optional[Timestamp]
            Timestamp of decision step k for deterministic seeding (Protocol B).
        num_scenarios : int
            Total scenarios S.
        include_nominal : bool
            If True, scenario 0 is the unperturbed nominal forecast.
        sampling_method : str
            'empirical' (paired validation residual resampling) or 'gaussian'.
        base_seed : int
            Base random seed.
        """
        d_fc = np.asarray(demand_forecast, dtype=float)
        s_fc = np.asarray(solar_forecast, dtype=float)
        T = len(d_fc)

        if T < 1 or len(s_fc) != T:
            raise ValueError("Forecast vectors must be non-empty and of equal length.")

        # Seed generation
        if timestamp is not None:
            seed = derive_observation_seed(house_id, timestamp, base_seed=base_seed)
        else:
            seed = base_seed

        rng = np.random.default_rng(seed)

        n_sample = num_scenarios - 1 if (include_nominal and num_scenarios > 1) else num_scenarios

        scen_d = np.zeros((num_scenarios, T), dtype=float)
        scen_s = np.zeros((num_scenarios, T), dtype=float)

        # Determine verified night-time / physical dark hours
        base_ts = pd.to_datetime(timestamp) if timestamp is not None else None
        # Verified night hours in Sydney (autumn/winter): hours 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6
        night_hours_set = {19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6}

        is_night = np.zeros(T, dtype=bool)
        step_hours: List[Optional[int]] = []
        for t in range(T):
            if base_ts is not None:
                step_h = (base_ts + pd.Timedelta(hours=t)).hour
                step_hours.append(step_h)
                if step_h in night_hours_set:
                    is_night[t] = True
            else:
                step_hours.append(None)
                if s_fc[t] <= 0.01:
                    is_night[t] = True

        start_idx = 0
        if include_nominal and num_scenarios > 1:
            scen_d[0, :] = np.maximum(0.0, d_fc)
            scen_s[0, :] = np.where(is_night, 0.0, np.maximum(0.0, s_fc))
            start_idx = 1

        if n_sample > 0:
            for t in range(T):
                h_val = step_hours[t]
                ed_t, es_t = self.residual_pool.sample_residuals(
                    num_scenarios=n_sample,
                    house_id=house_id,
                    hour_of_day=h_val,
                    random_seed=rng,
                    method=sampling_method,
                    paired=True,
                )
                scen_d[start_idx : start_idx + n_sample, t] = np.maximum(0.0, d_fc[t] + ed_t)
                if is_night[t]:
                    scen_s[start_idx : start_idx + n_sample, t] = 0.0
                else:
                    scen_s[start_idx : start_idx + n_sample, t] = np.maximum(0.0, s_fc[t] + es_t)

        # Equiprobable scenarios
        probs = np.full(num_scenarios, 1.0 / num_scenarios, dtype=float)

        return ScenarioSet(
            num_scenarios=num_scenarios,
            horizon_hours=T,
            scenarios_demand_kwh=scen_d,
            scenarios_solar_kwh=scen_s,
            probabilities=probs,
        )


@dataclass
class StochasticOptimizationResult:
    """Output of a stochastic scenario MPC optimization."""

    success: bool
    status: int
    message: str
    num_scenarios: int
    horizon_hours: int
    first_action: Tuple[float, float]  # (C_0, D_0) shared first-stage action
    first_u_ch: float                  # u_0_ch
    expected_cost_aud: float
    expected_import_cost_aud: float
    expected_export_revenue_aud: float
    scenario_costs_aud: np.ndarray     # Shape (S,)
    c_kwh: np.ndarray                  # Shape (S, T)
    d_kwh: np.ndarray                  # Shape (S, T)
    m_kwh: np.ndarray                  # Shape (S, T)
    x_kwh: np.ndarray                  # Shape (S, T)
    e_kwh: np.ndarray                  # Shape (S, T+1)
    soc: np.ndarray                    # Shape (S, T+1)
    solve_time_sec: float


class SingleHouseholdStochasticMPCController:
    """Stochastic Scenario-Based MPC Controller for a single residential battery."""

    def __init__(
        self,
        battery_params: Optional[BatteryOptimizationParams] = None,
        tariff_params: Optional[TariffParams] = None,
        config: Optional[StochasticMPCConfig] = None,
        scenario_generator: Optional[StochasticScenarioGenerator] = None,
    ) -> None:
        self.battery_params = battery_params or BatteryOptimizationParams()
        self.tariffs = tariff_params or TariffParams()
        self.config = config or StochasticMPCConfig()
        self.scenario_generator = scenario_generator or StochasticScenarioGenerator()

    def optimize_scenarios(
        self,
        initial_energy_kwh: float,
        scenario_set: ScenarioSet,
    ) -> StochasticOptimizationResult:
        """Formulate and solve the multi-scenario MILP with non-anticipativity.

        Decision Variable Layout:
        - 3 First-stage variables:
            x[0]: C_0
            x[1]: D_0
            x[2]: u_0_ch (binary)
        - For each scenario w in 0..S-1:
            Block offset = 3 + w * (6*T - 3)
            Indices within block:
              0 .. T-2:           C_{t, w} for t=1..T-1 (T-1 continuous)
              T-1 .. 2*T-3:       D_{t, w} for t=1..T-1 (T-1 continuous)
              2*T-2 .. 3*T-4:     u_{t, w}_ch for t=1..T-1 (T-1 binary)
              3*T-3 .. 4*T-4:     M_{t, w} for t=0..T-1 (T continuous)
              4*T-3 .. 5*T-4:     X_{t, w} for t=0..T-1 (T continuous)
              5*T-3 .. 6*T-4:     E_{t+1, w} for t=0..T-1 (T continuous)
        """
        S = scenario_set.num_scenarios
        T = scenario_set.horizon_hours
        probs = scenario_set.probabilities

        p_import = self.tariffs.import_price_aud_per_kwh
        p_export = self.tariffs.solar_export_credit_aud_per_kwh
        eta_ch = self.battery_params.charge_efficiency
        eta_dis = self.battery_params.discharge_efficiency
        dt = self.config.time_step_hours
        c_max = self.battery_params.max_charge_rate_kw * dt
        d_max = self.battery_params.max_discharge_rate_kw * dt
        e_min = self.battery_params.min_energy_kwh
        e_max = self.battery_params.max_energy_kwh

        initial_energy_kwh = float(np.clip(initial_energy_kwh, e_min, e_max))

        # Terminal valuation
        if self.config.terminal_strategy == "terminal_value":
            lambda_term = (
                self.config.terminal_value_aud_per_kwh
                if self.config.terminal_value_aud_per_kwh is not None
                else 0.98 * eta_dis * p_import
            )
        else:
            lambda_term = 0.0

        vars_per_scenario = 6 * T - 3
        n_vars = 3 + S * vars_per_scenario

        c_obj = np.zeros(n_vars, dtype=float)
        integrality = np.zeros(n_vars, dtype=int)
        integrality[2] = 1  # u_0_ch is binary

        lb = np.zeros(n_vars, dtype=float)
        ub = np.full(n_vars, np.inf, dtype=float)

        ub[0] = c_max
        ub[1] = d_max
        ub[2] = 1.0

        offset = 3
        for w in range(S):
            pi_w = probs[w]
            c_w = offset
            d_w = offset + (T - 1)
            u_w = offset + 2 * (T - 1)
            m_w = offset + 3 * (T - 1)
            x_w = m_w + T
            e_w = x_w + T

            # Bounds
            ub[c_w : c_w + T - 1] = c_max
            ub[d_w : d_w + T - 1] = d_max
            ub[u_w : u_w + T - 1] = 1.0
            integrality[u_w : u_w + T - 1] = 1

            lb[e_w : e_w + T] = e_min
            ub[e_w : e_w + T] = e_max

            # Objective weights
            c_obj[m_w : m_w + T] = pi_w * p_import
            c_obj[x_w : x_w + T] = -pi_w * p_export
            if lambda_term > 0.0:
                c_obj[e_w + T - 1] = -pi_w * lambda_term

            offset += vars_per_scenario

        bounds = Bounds(lb, ub)

        # Build Constraints
        # Rows:
        # First-stage mutual exclusion: 2 rows
        # For each scenario w:
        #   Recourse mutual exclusion: 2*(T-1) rows
        #   SOC dynamics: T rows
        #   Energy balance: T rows
        rows_per_scenario = 2 * (T - 1) + 2 * T
        n_rows = 2 + S * rows_per_scenario

        A = np.zeros((n_rows, n_vars), dtype=float)
        lhs = np.full(n_rows, -np.inf, dtype=float)
        rhs = np.full(n_rows, np.inf, dtype=float)

        row = 0
        # 1. First-stage mutual exclusion
        # C_0 - c_max * u_0 <= 0
        A[row, 0] = 1.0; A[row, 2] = -c_max; rhs[row] = 0.0; row += 1
        # D_0 + d_max * u_0 <= d_max
        A[row, 1] = 1.0; A[row, 2] = d_max; rhs[row] = d_max; row += 1

        inv_eta_dis = 1.0 / eta_dis
        offset = 3

        d_scen = scenario_set.scenarios_demand_kwh
        s_scen = scenario_set.scenarios_solar_kwh

        for w in range(S):
            c_w = offset
            d_w = offset + (T - 1)
            u_w = offset + 2 * (T - 1)
            m_w = offset + 3 * (T - 1)
            x_w = m_w + T
            e_w = x_w + T

            # 2a. Recourse mutual exclusion (t = 1..T-1)
            for t in range(T - 1):
                # C_{t,w} - c_max * u_{t,w} <= 0
                A[row, c_w + t] = 1.0; A[row, u_w + t] = -c_max; rhs[row] = 0.0; row += 1
                # D_{t,w} + d_max * u_{t,w} <= d_max
                A[row, d_w + t] = 1.0; A[row, u_w + t] = d_max; rhs[row] = d_max; row += 1

            # 2b. SOC Dynamics
            # t = 0: -eta_ch * C_0 + (1/eta_dis) * D_0 + E_{1, w} = E_0
            A[row, 0] = -eta_ch
            A[row, 1] = inv_eta_dis
            A[row, e_w] = 1.0
            lhs[row] = initial_energy_kwh; rhs[row] = initial_energy_kwh; row += 1

            for t in range(1, T):
                # -eta_ch * C_{t,w} + (1/eta_dis) * D_{t,w} - E_{t,w} + E_{t+1,w} = 0
                A[row, c_w + (t - 1)] = -eta_ch
                A[row, d_w + (t - 1)] = inv_eta_dis
                A[row, e_w + (t - 1)] = -1.0
                A[row, e_w + t] = 1.0
                lhs[row] = 0.0; rhs[row] = 0.0; row += 1

            # 2c. Energy Balance
            # t = 0: -C_0 + D_0 + M_{0,w} - X_{0,w} = d_{0,w} - s_{0,w}
            A[row, 0] = -1.0
            A[row, 1] = 1.0
            A[row, m_w] = 1.0
            A[row, x_w] = -1.0
            net_0 = float(d_scen[w, 0] - s_scen[w, 0])
            lhs[row] = net_0; rhs[row] = net_0; row += 1

            for t in range(1, T):
                # -C_{t,w} + D_{t,w} + M_{t,w} - X_{t,w} = d_{t,w} - s_{t,w}
                A[row, c_w + (t - 1)] = -1.0
                A[row, d_w + (t - 1)] = 1.0
                A[row, m_w + t] = 1.0
                A[row, x_w + t] = -1.0
                net_t = float(d_scen[w, t] - s_scen[w, t])
                lhs[row] = net_t; rhs[row] = net_t; row += 1

            offset += vars_per_scenario

        constraints = LinearConstraint(csc_matrix(A), lhs, rhs)
        milp_options = {"time_limit": self.config.time_limit_sec}

        t_start = time.perf_counter()
        sol: MILPResult = solve_milp(
            c=c_obj,
            integrality=integrality,
            bounds=bounds,
            constraints=constraints,
            options=milp_options,
        )
        elapsed = time.perf_counter() - t_start

        if not sol.success or sol.x is None:
            # Fallback zero dispatch
            return StochasticOptimizationResult(
                success=False,
                status=sol.status,
                message=sol.message,
                num_scenarios=S,
                horizon_hours=T,
                first_action=(0.0, 0.0),
                first_u_ch=0.0,
                expected_cost_aud=0.0,
                expected_import_cost_aud=0.0,
                expected_export_revenue_aud=0.0,
                scenario_costs_aud=np.zeros(S),
                c_kwh=np.zeros((S, T)),
                d_kwh=np.zeros((S, T)),
                m_kwh=np.maximum(0.0, d_scen - s_scen),
                x_kwh=np.maximum(0.0, s_scen - d_scen),
                e_kwh=np.full((S, T + 1), initial_energy_kwh),
                soc=np.full((S, T + 1), initial_energy_kwh / self.battery_params.capacity_kwh),
                solve_time_sec=elapsed,
            )

        x_opt = sol.x
        c0 = float(max(0.0, x_opt[0]))
        d0 = float(max(0.0, x_opt[1]))
        u0 = float(round(x_opt[2]))

        c_mat = np.zeros((S, T), dtype=float)
        d_mat = np.zeros((S, T), dtype=float)
        m_mat = np.zeros((S, T), dtype=float)
        x_mat = np.zeros((S, T), dtype=float)
        e_mat = np.zeros((S, T + 1), dtype=float)
        scen_costs = np.zeros(S, dtype=float)

        e_mat[:, 0] = initial_energy_kwh
        c_mat[:, 0] = c0
        d_mat[:, 0] = d0

        offset = 3
        for w in range(S):
            c_w = offset
            d_w = offset + (T - 1)
            u_w = offset + 2 * (T - 1)
            m_w = offset + 3 * (T - 1)
            x_w = m_w + T
            e_w = x_w + T

            c_mat[w, 1:] = np.maximum(0.0, x_opt[c_w : c_w + T - 1])
            d_mat[w, 1:] = np.maximum(0.0, x_opt[d_w : d_w + T - 1])
            m_mat[w, :] = np.maximum(0.0, x_opt[m_w : m_w + T])
            x_mat[w, :] = np.maximum(0.0, x_opt[x_w : x_w + T])
            e_mat[w, 1:] = x_opt[e_w : e_w + T]

            imp_c = float(np.sum(p_import * m_mat[w, :]))
            exp_r = float(np.sum(p_export * x_mat[w, :]))
            scen_costs[w] = imp_c - exp_r

            offset += vars_per_scenario

        soc_mat = e_mat / self.battery_params.capacity_kwh
        exp_import_cost = float(np.sum(probs * np.sum(p_import * m_mat, axis=1)))
        exp_export_rev = float(np.sum(probs * np.sum(p_export * x_mat, axis=1)))
        exp_cost = exp_import_cost - exp_export_rev

        return StochasticOptimizationResult(
            success=True,
            status=sol.status,
            message=sol.message,
            num_scenarios=S,
            horizon_hours=T,
            first_action=(c0, d0),
            first_u_ch=u0,
            expected_cost_aud=exp_cost,
            expected_import_cost_aud=exp_import_cost,
            expected_export_revenue_aud=exp_export_rev,
            scenario_costs_aud=scen_costs,
            c_kwh=c_mat,
            d_kwh=d_mat,
            m_kwh=m_mat,
            x_kwh=x_mat,
            e_kwh=e_mat,
            soc=soc_mat,
            solve_time_sec=elapsed,
        )

    def optimize(
        self,
        initial_energy_kwh: float,
        demand_forecast: Union[np.ndarray, Sequence[float]],
        solar_forecast: Union[np.ndarray, Sequence[float]],
        house_id: str = "H001",
        timestamp: Optional[Union[str, pd.Timestamp]] = None,
    ) -> StochasticOptimizationResult:
        """Generate scenarios and solve stochastic MPC."""
        scen_set = self.scenario_generator.generate_horizon_scenarios(
            demand_forecast=demand_forecast,
            solar_forecast=solar_forecast,
            house_id=house_id,
            timestamp=timestamp,
            num_scenarios=self.config.num_scenarios,
            include_nominal=self.config.include_nominal,
            sampling_method=self.config.sampling_method,
            base_seed=self.config.base_seed,
        )
        return self.optimize_scenarios(initial_energy_kwh, scen_set)


class StochasticRollingHorizonSimulator:
    """Rolling-horizon evaluation simulator with strict information boundaries."""

    def __init__(
        self,
        battery_params: Optional[BatteryOptimizationParams] = None,
        tariff_params: Optional[TariffParams] = None,
        stochastic_config: Optional[StochasticMPCConfig] = None,
        scenario_generator: Optional[StochasticScenarioGenerator] = None,
    ) -> None:
        self.battery_params = battery_params or BatteryOptimizationParams()
        self.tariffs = tariff_params or TariffParams()
        self.stochastic_config = stochastic_config or StochasticMPCConfig()
        self.scenario_generator = scenario_generator or StochasticScenarioGenerator()

    def run_stochastic_mpc(
        self,
        df: pd.DataFrame,
        house_id: str = "H001",
        actual_demand_col: str = "actual_demand_kwh",
        actual_solar_col: str = "actual_solar_generation_kwh",
        predicted_demand_col: str = "predicted_demand_kwh",
        predicted_solar_col: str = "predicted_solar_generation_kwh",
        timestamp_col: Optional[str] = "forecast_timestamp",
        initial_soc: float = 0.50,
        shrink_horizon_at_end: bool = True,
        max_steps: Optional[int] = None,
    ) -> Any:
        """Execute rolling-horizon Stochastic MPC.

        Strict information boundaries:
        - Scenarios for horizon [k : k+H] are generated solely from predictions and historical validation residuals.
        - Future realizations [k+1 : k+H] are never accessed during scenario generation or optimization.
        - First-stage decision (C_0, D_0) is executed against step k ground-truth realization.
        """
        from src.optimization.mpc_battery import SimulationResult, SimulationStepRecord

        N = len(df) if max_steps is None else min(len(df), max_steps)
        H = self.stochastic_config.horizon_hours
        dt = self.stochastic_config.time_step_hours
        p_import = self.tariffs.import_price_aud_per_kwh
        p_export = self.tariffs.solar_export_credit_aud_per_kwh

        battery = BatteryStorage(
            capacity_kwh=self.battery_params.capacity_kwh,
            max_charge_rate_kw=self.battery_params.max_charge_rate_kw,
            max_discharge_rate_kw=self.battery_params.max_discharge_rate_kw,
            charge_efficiency=self.battery_params.charge_efficiency,
            discharge_efficiency=self.battery_params.discharge_efficiency,
            min_soc=self.battery_params.min_soc,
            max_soc=self.battery_params.max_soc,
            initial_soc=initial_soc,
        )

        controller = SingleHouseholdStochasticMPCController(
            battery_params=self.battery_params,
            tariff_params=self.tariffs,
            config=self.stochastic_config,
            scenario_generator=self.scenario_generator,
        )

        records: List[SimulationStepRecord] = []
        solver_failures = 0
        solve_times: List[float] = []

        actual_d_arr = df[actual_demand_col].to_numpy(dtype=float)
        actual_s_arr = df[actual_solar_col].to_numpy(dtype=float)
        pred_d_arr = df[predicted_demand_col].to_numpy(dtype=float)
        pred_s_arr = df[predicted_solar_col].to_numpy(dtype=float)
        timestamps = df[timestamp_col].tolist() if timestamp_col in df.columns else [None] * len(df)

        init_kwh = battery.current_charge_kwh

        for k in range(N):
            end_idx = min(k + H, len(df))
            d_window = pred_d_arr[k:end_idx]
            s_window = pred_s_arr[k:end_idx]

            if len(d_window) < H and not shrink_horizon_at_end:
                break

            current_kwh = battery.current_charge_kwh
            init_soc_step = battery.soc
            ts_k = timestamps[k]

            # 1. Plan using stochastic scenarios around forecasts
            res: StochasticOptimizationResult = controller.optimize(
                initial_energy_kwh=current_kwh,
                demand_forecast=d_window,
                solar_forecast=s_window,
                house_id=house_id,
                timestamp=ts_k,
            )

            solve_times.append(res.solve_time_sec)
            if not res.success:
                solver_failures += 1

            c_plan, d_plan = res.first_action

            # 2. Execute on ground truth realization
            d_act = float(actual_d_arr[k])
            s_act = float(actual_s_arr[k])
            d_fc = float(pred_d_arr[k])
            s_fc = float(pred_s_arr[k])

            if c_plan > 1e-6:
                bat_state = battery.step(
                    energy_available_to_charge_kwh=c_plan,
                    energy_requested_to_discharge_kwh=0.0,
                    duration_hours=dt,
                )
            elif d_plan > 1e-6:
                bat_state = battery.step(
                    energy_available_to_charge_kwh=0.0,
                    energy_requested_to_discharge_kwh=d_plan,
                    duration_hours=dt,
                )
            else:
                bat_state = battery.step(0.0, 0.0, duration_hours=dt)

            actual_c = bat_state.charged_kwh
            actual_d = bat_state.discharged_kwh

            # 3. Physical energy balance at household meter
            net_flow = d_act - s_act + actual_c - actual_d
            if net_flow >= 0.0:
                grid_in = net_flow
                grid_out = 0.0
            else:
                grid_in = 0.0
                grid_out = -net_flow

            residual = abs((d_act + actual_c + grid_out) - (s_act + actual_d + grid_in))

            imp_cost = grid_in * p_import
            exp_rev = grid_out * p_export
            net_step_cost = imp_cost - exp_rev

            records.append(
                SimulationStepRecord(
                    step_index=k,
                    timestamp=ts_k,
                    actual_demand_kwh=d_act,
                    actual_solar_kwh=s_act,
                    forecast_demand_kwh=d_fc,
                    forecast_solar_kwh=s_fc,
                    battery_initial_soc=init_soc_step,
                    battery_final_soc=battery.soc,
                    battery_initial_kwh=current_kwh,
                    battery_final_kwh=battery.current_charge_kwh,
                    charged_kwh=actual_c,
                    discharged_kwh=actual_d,
                    grid_imported_kwh=grid_in,
                    grid_exported_kwh=grid_out,
                    import_cost_aud=imp_cost,
                    export_credit_aud=exp_rev,
                    net_cost_aud=net_step_cost,
                    energy_balance_residual_kwh=residual,
                    solver_success=res.success,
                    solver_time_sec=res.solve_time_sec,
                )
            )

        # Summarize using SimulationResult
        total_hours = len(records)
        total_imp_cost = sum(r.import_cost_aud for r in records)
        total_exp_rev = sum(r.export_credit_aud for r in records)
        net_cost = total_imp_cost - total_exp_rev
        total_imported = sum(r.grid_imported_kwh for r in records)
        total_exported = sum(r.grid_exported_kwh for r in records)
        total_charged = sum(r.charged_kwh for r in records)
        total_discharged = sum(r.discharged_kwh for r in records)
        final_kwh = battery.current_charge_kwh
        final_soc = battery.soc
        net_stored_change = final_kwh - init_kwh

        chemical_val = self.battery_params.discharge_efficiency * self.tariffs.import_price_aud_per_kwh
        adjusted_cost = net_cost - (net_stored_change * chemical_val)

        all_socs = [r.battery_final_soc for r in records]
        min_soc = min(all_socs) if all_socs else initial_soc
        max_soc = max(all_socs) if all_socs else initial_soc

        soc_violations = sum(
            1 for r in records
            if r.battery_final_soc < self.battery_params.min_soc - 1e-5
            or r.battery_final_soc > self.battery_params.max_soc + 1e-5
        )
        simul_violations = sum(
            1 for r in records if r.charged_kwh > 1e-5 and r.discharged_kwh > 1e-5
        )
        max_res = max((r.energy_balance_residual_kwh for r in records), default=0.0)

        avg_time = float(np.mean(solve_times)) if solve_times else 0.0
        max_time = float(np.max(solve_times)) if solve_times else 0.0

        return SimulationResult(
            controller_type="Stochastic_MPC",
            total_hours=total_hours,
            total_import_cost_aud=total_imp_cost,
            total_export_revenue_aud=total_exp_rev,
            net_electricity_cost_aud=net_cost,
            total_imported_kwh=total_imported,
            total_exported_kwh=total_exported,
            total_charged_kwh=total_charged,
            total_discharged_kwh=total_discharged,
            initial_soc=initial_soc,
            final_soc=final_soc,
            initial_stored_kwh=init_kwh,
            final_stored_kwh=final_kwh,
            net_stored_energy_change_kwh=net_stored_change,
            adjusted_net_cost_aud=adjusted_cost,
            min_soc_observed=min_soc,
            max_soc_observed=max_soc,
            soc_boundary_violations=soc_violations,
            simultaneous_charge_discharge_violations=simul_violations,
            max_energy_balance_residual_kwh=max_res,
            total_solver_failures=solver_failures,
            average_solve_time_sec=avg_time,
            max_solve_time_sec=max_time,
            step_records=records,
        )
