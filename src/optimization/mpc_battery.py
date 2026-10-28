"""Single-household Rolling-Horizon Model Predictive Control (MPC) battery controller.

Implements:
- 24-hour deterministic rolling-horizon MILP dispatch
- Power limits, SOC limits, efficiency losses, and exact dynamics
- Strict mutual exclusion between charging and discharging via binary variables
- Configurable terminal horizon treatment (terminal value, terminal target, unconstrained)
- Strict information boundary separation (forecasts vs ground truth realizations)
- Direct comparison harness against the repository greedy battery baseline
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint

from src.energy.battery import BatteryStorage
from src.energy.energy_balance import compute_battery_aware_balance
from src.optimization.constraints import (
    BatteryOptimizationParams,
    MPCConfig,
    TariffParams,
)
from src.optimization.solver import MILPResult, solve_milp


@dataclass
class MPCOptimizationResult:
    """Detailed output of a single MPC horizon optimization."""

    success: bool
    status: int
    message: str
    horizon_hours: int
    c_kwh: np.ndarray  # Charging energy per step [T]
    d_kwh: np.ndarray  # Discharging energy per step [T]
    m_kwh: np.ndarray  # Grid import energy per step [T]
    x_kwh: np.ndarray  # Grid export energy per step [T]
    u_ch: np.ndarray   # Binary charging mode per step [T]
    e_kwh: np.ndarray  # Stored chemical energy at start of each step + terminal [T+1]
    soc: np.ndarray    # SOC trajectory [T+1]
    net_cost_aud: float
    import_expenditure_aud: float
    export_revenue_aud: float
    solve_time_sec: float
    terminal_slack_kwh: float = 0.0

    @property
    def first_action(self) -> Tuple[float, float]:
        """First-hour planned charging and discharging action (C_0, D_0)."""
        if len(self.c_kwh) == 0:
            return 0.0, 0.0
        return float(self.c_kwh[0]), float(self.d_kwh[0])


class SingleHouseholdMPCController:
    """Optimal rolling-horizon battery controller for a single household."""

    def __init__(
        self,
        battery_params: Optional[BatteryOptimizationParams] = None,
        tariff_params: Optional[TariffParams] = None,
        config: Optional[MPCConfig] = None,
    ) -> None:
        self.battery_params = battery_params or BatteryOptimizationParams()
        self.tariffs = tariff_params or TariffParams()
        self.config = config or MPCConfig()

    def optimize(
        self,
        initial_energy_kwh: float,
        demand_forecast: Union[np.ndarray, Sequence[float]],
        solar_forecast: Union[np.ndarray, Sequence[float]],
    ) -> MPCOptimizationResult:
        """Formulate and solve the finite-horizon MILP.

        Parameters
        ----------
        initial_energy_kwh : float
            Current stored chemical energy in battery (must be in [E_min, E_max]).
        demand_forecast : Sequence[float]
            Forecasted demand for each hour of the horizon (kWh).
        solar_forecast : Sequence[float]
            Forecasted solar generation for each hour of the horizon (kWh).

        Returns
        -------
        MPCOptimizationResult
            Optimal trajectories and solver status.
        """
        # Validate inputs
        d_fc = np.asarray(demand_forecast, dtype=float)
        s_fc = np.asarray(solar_forecast, dtype=float)

        if d_fc.ndim != 1 or s_fc.ndim != 1:
            raise ValueError("demand_forecast and solar_forecast must be 1D sequences.")
        if len(d_fc) != len(s_fc):
            raise ValueError(f"Forecast length mismatch: demand ({len(d_fc)}) != solar ({len(s_fc)})")
        if len(d_fc) < 1:
            raise ValueError("Forecast length must be at least 1.")

        if not np.all(np.isfinite(d_fc)):
            raise ValueError("Non-finite values detected in demand_forecast.")
        if not np.all(np.isfinite(s_fc)):
            raise ValueError("Non-finite values detected in solar_forecast.")
        if np.any(d_fc < -1e-6):
            raise ValueError("Negative values detected in demand_forecast.")
        if np.any(s_fc < -1e-6):
            raise ValueError("Negative values detected in solar_forecast.")

        d_fc = np.maximum(0.0, d_fc)
        s_fc = np.maximum(0.0, s_fc)

        if not np.isfinite(initial_energy_kwh):
            raise ValueError(f"initial_energy_kwh must be finite, got {initial_energy_kwh}")

        tol = 1e-4
        e_min = self.battery_params.min_energy_kwh
        e_max = self.battery_params.max_energy_kwh
        if initial_energy_kwh < e_min - tol or initial_energy_kwh > e_max + tol:
            raise ValueError(
                f"initial_energy_kwh ({initial_energy_kwh:.4f}) outside permitted range [{e_min:.4f}, {e_max:.4f}]"
            )
        initial_energy_kwh = float(np.clip(initial_energy_kwh, e_min, e_max))

        T = len(d_fc)
        p_import = self.tariffs.import_price_aud_per_kwh
        p_export = self.tariffs.solar_export_credit_aud_per_kwh
        eta_ch = self.battery_params.charge_efficiency
        eta_dis = self.battery_params.discharge_efficiency
        dt = self.config.time_step_hours
        c_max = self.battery_params.max_charge_rate_kw * dt
        d_max = self.battery_params.max_discharge_rate_kw * dt

        # Terminal valuation determination:
        # We use a 0.98 factor on (eta_dis * p_import) to ensure a strict economic preference
        # for serving known current demand over hoarding stored energy for the future,
        # while maintaining a strong incentive (0.279 vs 0.08) to store surplus solar rather than export.
        if self.config.terminal_strategy == "terminal_value":
            lambda_term = (
                self.config.terminal_value_aud_per_kwh
                if self.config.terminal_value_aud_per_kwh is not None
                else 0.98 * eta_dis * p_import
            )
        else:
            lambda_term = 0.0

        use_terminal_target = self.config.terminal_strategy == "terminal_soc_target"

        # Variable layout:
        # Index offsets for horizon T:
        # C_t: 0 .. T-1
        # D_t: T .. 2T-1
        # M_t: 2T .. 3T-1
        # X_t: 3T .. 4T-1
        # u_t: 4T .. 5T-1
        # E_{t+1}: 5T .. 6T-1 (for t = 0..T-1)
        # s_term: 6T (if use_terminal_target)
        n_vars = 6 * T + (1 if use_terminal_target else 0)

        # Objective vector c:
        c_obj = np.zeros(n_vars, dtype=float)
        # Grid import cost
        c_obj[2 * T : 3 * T] = p_import
        # Grid export revenue (negative cost)
        c_obj[3 * T : 4 * T] = -p_export
        # Terminal stored energy valuation (bonus = negative cost)
        if self.config.terminal_strategy == "terminal_value":
            c_obj[6 * T - 1] = -lambda_term
        # Terminal slack penalty
        if use_terminal_target:
            c_obj[6 * T] = self.config.slack_penalty

        # Integrality vector: 1 for binary u_t, 0 for continuous
        integrality = np.zeros(n_vars, dtype=int)
        integrality[4 * T : 5 * T] = 1

        # Bounds:
        lb = np.zeros(n_vars, dtype=float)
        ub = np.full(n_vars, np.inf, dtype=float)

        # C_t in [0, c_max]
        ub[0:T] = c_max
        # If solar-only charging configured
        if not self.config.allow_grid_charging:
            ub[0:T] = np.minimum(c_max, s_fc)

        # D_t in [0, d_max]
        ub[T : 2 * T] = d_max

        # M_t in [0, inf)
        # X_t in [0, inf)

        # u_t in [0, 1]
        ub[4 * T : 5 * T] = 1.0

        # E_{t+1} in [e_min, e_max]
        lb[5 * T : 6 * T] = e_min
        ub[5 * T : 6 * T] = e_max

        # s_term in [0, inf) if present

        bounds = Bounds(lb, ub)

        # Build Linear Constraints
        # Total constraint rows:
        # 1. C_t - c_max * u_t <= 0 (T rows)
        # 2. D_t + d_max * u_t <= d_max (T rows)
        # 3. SOC dynamics (T rows): E_{t+1} - E_t - eta_ch * C_t + (1/eta_dis) * D_t = 0
        # 4. Energy balance (T rows): M_t - X_t - C_t + D_t = d_t - s_t
        # 5. Terminal target (1 row, if active): E_T + s_term >= E_target
        n_rows = 4 * T + (1 if use_terminal_target else 0)
        A = np.zeros((n_rows, n_vars), dtype=float)
        lhs = np.full(n_rows, -np.inf, dtype=float)
        rhs = np.full(n_rows, np.inf, dtype=float)

        row = 0

        # 1. Charging power with mutual exclusion: C_t - c_max * u_t <= 0
        for t in range(T):
            A[row, t] = 1.0
            A[row, 4 * T + t] = -c_max
            lhs[row] = -np.inf
            rhs[row] = 0.0
            row += 1

        # 2. Discharging power with mutual exclusion: D_t + d_max * u_t <= d_max
        for t in range(T):
            A[row, T + t] = 1.0
            A[row, 4 * T + t] = d_max
            lhs[row] = -np.inf
            rhs[row] = d_max
            row += 1

        # 3. SOC dynamics:
        # For t = 0: -eta_ch * C_0 + (1 / eta_dis) * D_0 + E_1 = E_0
        # For t > 0: -eta_ch * C_t + (1 / eta_dis) * D_t - E_t + E_{t+1} = 0
        inv_eta_dis = 1.0 / eta_dis
        for t in range(T):
            A[row, t] = -eta_ch
            A[row, T + t] = inv_eta_dis
            A[row, 5 * T + t] = 1.0
            if t == 0:
                lhs[row] = initial_energy_kwh
                rhs[row] = initial_energy_kwh
            else:
                A[row, 5 * T + (t - 1)] = -1.0
                lhs[row] = 0.0
                rhs[row] = 0.0
            row += 1

        # 4. Energy balance: -C_t + D_t + M_t - X_t = d_t - s_t
        for t in range(T):
            A[row, t] = -1.0
            A[row, T + t] = 1.0
            A[row, 2 * T + t] = 1.0
            A[row, 3 * T + t] = -1.0
            net_d = float(d_fc[t] - s_fc[t])
            lhs[row] = net_d
            rhs[row] = net_d
            row += 1

        # 5. Terminal target constraint if active: E_T + s_term >= E_target
        if use_terminal_target:
            e_target = self.config.terminal_soc_target * self.battery_params.capacity_kwh
            A[row, 6 * T - 1] = 1.0
            A[row, 6 * T] = 1.0
            lhs[row] = e_target
            rhs[row] = np.inf
            row += 1

        constraints = LinearConstraint(A, lhs, rhs)
        milp_options = {"time_limit": self.config.time_limit_sec}

        # Solve
        sol: MILPResult = solve_milp(
            c=c_obj,
            integrality=integrality,
            bounds=bounds,
            constraints=constraints,
            options=milp_options,
        )

        if not sol.success or sol.x is None:
            # Fallback safe trajectory (zero dispatch)
            return MPCOptimizationResult(
                success=False,
                status=sol.status,
                message=sol.message,
                horizon_hours=T,
                c_kwh=np.zeros(T),
                d_kwh=np.zeros(T),
                m_kwh=np.maximum(0.0, d_fc - s_fc),
                x_kwh=np.maximum(0.0, s_fc - d_fc),
                u_ch=np.zeros(T),
                e_kwh=np.full(T + 1, initial_energy_kwh),
                soc=np.full(T + 1, initial_energy_kwh / self.battery_params.capacity_kwh),
                net_cost_aud=float(np.sum(p_import * np.maximum(0.0, d_fc - s_fc) - p_export * np.maximum(0.0, s_fc - d_fc))),
                import_expenditure_aud=float(np.sum(p_import * np.maximum(0.0, d_fc - s_fc))),
                export_revenue_aud=float(np.sum(p_export * np.maximum(0.0, s_fc - d_fc))),
                solve_time_sec=sol.solve_time_sec,
            )

        x_opt = sol.x
        c_kwh = np.maximum(0.0, x_opt[0:T])
        d_kwh = np.maximum(0.0, x_opt[T : 2 * T])
        m_kwh = np.maximum(0.0, x_opt[2 * T : 3 * T])
        x_kwh = np.maximum(0.0, x_opt[3 * T : 4 * T])
        u_ch = np.round(x_opt[4 * T : 5 * T])
        e_post = x_opt[5 * T : 6 * T]

        e_traj = np.zeros(T + 1, dtype=float)
        e_traj[0] = initial_energy_kwh
        e_traj[1:] = e_post

        soc_traj = e_traj / self.battery_params.capacity_kwh

        import_cost = float(np.sum(p_import * m_kwh))
        export_rev = float(np.sum(p_export * x_kwh))
        net_cost = import_cost - export_rev

        slack_val = float(x_opt[6 * T]) if use_terminal_target else 0.0

        return MPCOptimizationResult(
            success=True,
            status=sol.status,
            message=sol.message,
            horizon_hours=T,
            c_kwh=c_kwh,
            d_kwh=d_kwh,
            m_kwh=m_kwh,
            x_kwh=x_kwh,
            u_ch=u_ch,
            e_kwh=e_traj,
            soc=soc_traj,
            net_cost_aud=net_cost,
            import_expenditure_aud=import_cost,
            export_revenue_aud=export_rev,
            solve_time_sec=sol.solve_time_sec,
            terminal_slack_kwh=slack_val,
        )


@dataclass
class SimulationStepRecord:
    """Detailed record of one executed simulation step."""

    step_index: int
    timestamp: Optional[pd.Timestamp]
    actual_demand_kwh: float
    actual_solar_kwh: float
    forecast_demand_kwh: float
    forecast_solar_kwh: float
    battery_initial_soc: float
    battery_final_soc: float
    battery_initial_kwh: float
    battery_final_kwh: float
    charged_kwh: float
    discharged_kwh: float
    grid_imported_kwh: float
    grid_exported_kwh: float
    import_cost_aud: float
    export_credit_aud: float
    net_cost_aud: float
    energy_balance_residual_kwh: float
    solver_success: bool
    solver_time_sec: float


@dataclass
class SimulationResult:
    """Summary and timeseries of a multi-period simulation run."""

    controller_type: str
    total_hours: int
    total_import_cost_aud: float
    total_export_revenue_aud: float
    net_electricity_cost_aud: float
    total_imported_kwh: float
    total_exported_kwh: float
    total_charged_kwh: float
    total_discharged_kwh: float
    initial_soc: float
    final_soc: float
    initial_stored_kwh: float
    final_stored_kwh: float
    net_stored_energy_change_kwh: float
    adjusted_net_cost_aud: float  # Accounting for terminal energy valuation
    min_soc_observed: float
    max_soc_observed: float
    soc_boundary_violations: int
    simultaneous_charge_discharge_violations: int
    max_energy_balance_residual_kwh: float
    total_solver_failures: int
    average_solve_time_sec: float
    max_solve_time_sec: float
    step_records: List[SimulationStepRecord] = field(default_factory=list)

    def to_summary_dict(self) -> Dict[str, Any]:
        """Produce dictionary of summary KPIs."""
        return {
            "controller_type": self.controller_type,
            "total_hours": self.total_hours,
            "total_import_cost_aud": round(self.total_import_cost_aud, 4),
            "total_export_revenue_aud": round(self.total_export_revenue_aud, 4),
            "net_electricity_cost_aud": round(self.net_electricity_cost_aud, 4),
            "adjusted_net_cost_aud": round(self.adjusted_net_cost_aud, 4),
            "total_imported_kwh": round(self.total_imported_kwh, 4),
            "total_exported_kwh": round(self.total_exported_kwh, 4),
            "total_charged_kwh": round(self.total_charged_kwh, 4),
            "total_discharged_kwh": round(self.total_discharged_kwh, 4),
            "initial_soc": round(self.initial_soc, 4),
            "final_soc": round(self.final_soc, 4),
            "net_stored_energy_change_kwh": round(self.net_stored_energy_change_kwh, 4),
            "min_soc_observed": round(self.min_soc_observed, 4),
            "max_soc_observed": round(self.max_soc_observed, 4),
            "soc_boundary_violations": self.soc_boundary_violations,
            "simultaneous_charge_discharge_violations": self.simultaneous_charge_discharge_violations,
            "max_energy_balance_residual_kwh": f"{self.max_energy_balance_residual_kwh:.2e}",
            "total_solver_failures": self.total_solver_failures,
            "average_solve_time_ms": round(self.average_solve_time_sec * 1000.0, 3),
            "max_solve_time_ms": round(self.max_solve_time_sec * 1000.0, 3),
        }


class RollingHorizonSimulator:
    """Simulator running MPC and Greedy controllers with strict information boundaries."""

    def __init__(
        self,
        battery_params: Optional[BatteryOptimizationParams] = None,
        tariff_params: Optional[TariffParams] = None,
        mpc_config: Optional[MPCConfig] = None,
    ) -> None:
        self.battery_params = battery_params or BatteryOptimizationParams()
        self.tariffs = tariff_params or TariffParams()
        self.mpc_config = mpc_config or MPCConfig()

    def run_mpc(
        self,
        df: pd.DataFrame,
        actual_demand_col: str = "actual_demand_kwh",
        actual_solar_col: str = "actual_solar_generation_kwh",
        predicted_demand_col: str = "predicted_demand_kwh",
        predicted_solar_col: str = "predicted_solar_generation_kwh",
        timestamp_col: Optional[str] = "forecast_timestamp",
        initial_soc: float = 0.50,
        shrink_horizon_at_end: bool = True,
        max_steps: Optional[int] = None,
    ) -> SimulationResult:
        """Execute rolling-horizon MPC controller over dataset.

        Strict information boundary:
        - At step k, the controller only receives predictions for [k : k+H].
        - Ground truth actuals [k : k+H] are never exposed to the optimizer.
        - First step decision is applied to step k actuals.
        """
        N = len(df) if max_steps is None else min(len(df), max_steps)
        H = self.mpc_config.horizon_hours
        dt = self.mpc_config.time_step_hours
        p_import = self.tariffs.import_price_aud_per_kwh
        p_export = self.tariffs.solar_export_credit_aud_per_kwh
        eta_dis = self.battery_params.discharge_efficiency

        # Initialize physical battery model
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

        controller = SingleHouseholdMPCController(
            battery_params=self.battery_params,
            tariff_params=self.tariffs,
            config=self.mpc_config,
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
            # Window slice
            end_idx = min(k + H, len(df))
            d_window = pred_d_arr[k:end_idx]
            s_window = pred_s_arr[k:end_idx]

            if len(d_window) < H and not shrink_horizon_at_end:
                break

            current_kwh = battery.current_charge_kwh
            init_soc_step = battery.soc

            # 1. Plan using available forecasts only
            plan: MPCOptimizationResult = controller.optimize(
                initial_energy_kwh=current_kwh,
                demand_forecast=d_window,
                solar_forecast=s_window,
            )

            solve_times.append(plan.solve_time_sec)
            if not plan.success:
                solver_failures += 1

            c_plan, d_plan = plan.first_action

            # 2. Execute on actual realized observations
            d_act = float(actual_d_arr[k])
            s_act = float(actual_s_arr[k])
            d_fc = float(pred_d_arr[k])
            s_fc = float(pred_s_arr[k])

            # Apply battery physical dispatch
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

            # 3. Exact physical energy balance at household meter
            # Demand + Charge + Grid Export == Solar + Discharge + Grid Import
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
                    timestamp=timestamps[k],
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
                    solver_success=plan.success,
                    solver_time_sec=plan.solve_time_sec,
                )
            )

        return self._summarize_results("MPC_Rolling_Horizon", records, battery, init_kwh, initial_soc, solver_failures, solve_times)

    def run_greedy_baseline(
        self,
        df: pd.DataFrame,
        actual_demand_col: str = "actual_demand_kwh",
        actual_solar_col: str = "actual_solar_generation_kwh",
        timestamp_col: Optional[str] = "forecast_timestamp",
        initial_soc: float = 0.50,
        max_steps: Optional[int] = None,
    ) -> SimulationResult:
        """Execute repository greedy baseline battery dispatch over the exact same dataset."""
        N = len(df) if max_steps is None else min(len(df), max_steps)
        dt = self.mpc_config.time_step_hours
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

        records: List[SimulationStepRecord] = []
        actual_d_arr = df[actual_demand_col].to_numpy(dtype=float)
        actual_s_arr = df[actual_solar_col].to_numpy(dtype=float)
        timestamps = df[timestamp_col].tolist() if timestamp_col in df.columns else [None] * len(df)

        init_kwh = battery.current_charge_kwh

        for k in range(N):
            d_act = float(actual_d_arr[k])
            s_act = float(actual_s_arr[k])
            init_kwh_step = battery.current_charge_kwh
            init_soc_step = battery.soc

            # Greedy dispatch using compute_battery_aware_balance
            t_start = time.perf_counter()
            bal = compute_battery_aware_balance(
                demand_kwh=d_act,
                solar_generation_kwh=s_act,
                battery=battery,
                duration_hours=dt,
                inplace=True,
            )
            elapsed = time.perf_counter() - t_start

            actual_c = bal.solar_to_battery_kwh
            actual_d = bal.battery_to_demand_kwh

            # Under single-household without P2P:
            # post-battery deficit is imported from grid, post-battery surplus is exported
            grid_in = bal.deficit_kwh
            grid_out = bal.surplus_kwh

            residual = abs((d_act + actual_c + grid_out) - (s_act + actual_d + grid_in))

            imp_cost = grid_in * p_import
            exp_rev = grid_out * p_export
            net_step_cost = imp_cost - exp_rev

            records.append(
                SimulationStepRecord(
                    step_index=k,
                    timestamp=timestamps[k],
                    actual_demand_kwh=d_act,
                    actual_solar_kwh=s_act,
                    forecast_demand_kwh=d_act,  # greedy reacts to realized
                    forecast_solar_kwh=s_act,
                    battery_initial_soc=init_soc_step,
                    battery_final_soc=battery.soc,
                    battery_initial_kwh=init_kwh_step,
                    battery_final_kwh=battery.current_charge_kwh,
                    charged_kwh=actual_c,
                    discharged_kwh=actual_d,
                    grid_imported_kwh=grid_in,
                    grid_exported_kwh=grid_out,
                    import_cost_aud=imp_cost,
                    export_credit_aud=exp_rev,
                    net_cost_aud=net_step_cost,
                    energy_balance_residual_kwh=residual,
                    solver_success=True,
                    solver_time_sec=elapsed,
                )
            )

        return self._summarize_results("Greedy_Baseline", records, battery, init_kwh, initial_soc, 0, [r.solver_time_sec for r in records])

    def _summarize_results(
        self,
        controller_type: str,
        records: List[SimulationStepRecord],
        battery: BatteryStorage,
        init_kwh: float,
        init_soc: float,
        solver_failures: int,
        solve_times: List[float],
    ) -> SimulationResult:
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

        # Adjusted net cost: penalize if battery was depleted, credit if battery was enriched
        # Value per kWh of chemical stored energy = eta_dis * p_import
        chemical_energy_val = self.battery_params.discharge_efficiency * self.tariffs.import_price_aud_per_kwh
        adjusted_cost = net_cost - (net_stored_change * chemical_energy_val)

        all_socs = [r.battery_final_soc for r in records]
        min_soc = min(all_socs) if all_socs else init_soc
        max_soc = max(all_socs) if all_socs else init_soc

        # Violations
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
            controller_type=controller_type,
            total_hours=total_hours,
            total_import_cost_aud=total_imp_cost,
            total_export_revenue_aud=total_exp_rev,
            net_electricity_cost_aud=net_cost,
            total_imported_kwh=total_imported,
            total_exported_kwh=total_exported,
            total_charged_kwh=total_charged,
            total_discharged_kwh=total_discharged,
            initial_soc=init_soc,
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


def compare_controllers(
    mpc_result: SimulationResult,
    greedy_result: SimulationResult,
) -> Dict[str, Any]:
    """Compare performance metrics between MPC and Greedy baseline."""
    cost_diff = mpc_result.net_electricity_cost_aud - greedy_result.net_electricity_cost_aud
    adj_cost_diff = mpc_result.adjusted_net_cost_aud - greedy_result.adjusted_net_cost_aud

    pct_diff = (
        (cost_diff / abs(greedy_result.net_electricity_cost_aud) * 100.0)
        if abs(greedy_result.net_electricity_cost_aud) > 1e-6
        else 0.0
    )
    adj_pct_diff = (
        (adj_cost_diff / abs(greedy_result.adjusted_net_cost_aud) * 100.0)
        if abs(greedy_result.adjusted_net_cost_aud) > 1e-6
        else 0.0
    )

    return {
        "hours_evaluated": mpc_result.total_hours,
        "greedy_net_cost_aud": round(greedy_result.net_electricity_cost_aud, 4),
        "mpc_net_cost_aud": round(mpc_result.net_electricity_cost_aud, 4),
        "net_cost_difference_aud": round(cost_diff, 4),
        "net_cost_diff_pct": round(pct_diff, 2),
        "greedy_adjusted_cost_aud": round(greedy_result.adjusted_net_cost_aud, 4),
        "mpc_adjusted_cost_aud": round(mpc_result.adjusted_net_cost_aud, 4),
        "adjusted_cost_diff_aud": round(adj_cost_diff, 4),
        "adjusted_cost_diff_pct": round(adj_pct_diff, 2),
        "greedy_import_kwh": round(greedy_result.total_imported_kwh, 4),
        "mpc_import_kwh": round(mpc_result.total_imported_kwh, 4),
        "greedy_export_kwh": round(greedy_result.total_exported_kwh, 4),
        "mpc_export_kwh": round(mpc_result.total_exported_kwh, 4),
        "greedy_charged_kwh": round(greedy_result.total_charged_kwh, 4),
        "mpc_charged_kwh": round(mpc_result.total_charged_kwh, 4),
        "greedy_discharged_kwh": round(greedy_result.total_discharged_kwh, 4),
        "mpc_discharged_kwh": round(mpc_result.total_discharged_kwh, 4),
        "greedy_final_soc": round(greedy_result.final_soc, 4),
        "mpc_final_soc": round(mpc_result.final_soc, 4),
        "mpc_avg_solve_time_ms": round(mpc_result.average_solve_time_sec * 1000.0, 3),
        "mpc_max_solve_time_ms": round(mpc_result.max_solve_time_sec * 1000.0, 3),
        "mpc_solver_failures": mpc_result.total_solver_failures,
        "max_conservation_residual_kwh": max(
            mpc_result.max_energy_balance_residual_kwh,
            greedy_result.max_energy_balance_residual_kwh,
        ),
    }
