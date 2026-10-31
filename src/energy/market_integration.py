"""Multi-Household Stochastic Energy Market Integration Module (Phase 7).

Integrates:
- Single-household residential battery controllers:
  * Corrected Stochastic Scenario-Based MPC (Phase 6B.2)
  * Deterministic Rolling-Horizon MPC (Phase 6A)
  * Equal-Information Forecast Greedy Baseline
  * Realized Ground-Truth Oracle Greedy Baseline
- Phase 5B Multi-Household Peer-to-Peer (P2P) Market Clearing
- Strict physical energy conservation and financial transaction conservation
- Flexible standalone (No-P2P) and integrated (P2P-clearing) operating modes
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from src.energy.battery import BatteryState, BatteryStorage
from src.energy.market_clearing import (
    HouseholdMarketBid,
    MarketClearingPolicy,
    MarketClearingResult,
    MarketTransaction,
    clear_multi_household_market,
)
from src.optimization.constraints import (
    BatteryOptimizationParams,
    MPCConfig,
    TariffParams,
)
from src.optimization.mpc_battery import SingleHouseholdMPCController
from src.optimization.mpc_stochastic import (
    SingleHouseholdStochasticMPCController,
    StochasticMPCConfig,
    StochasticScenarioGenerator,
)
from src.stochastic.monte_carlo import ValidationResidualPool


@dataclass
class HouseholdStepRecord:
    """Detailed per-household accounting at a single simulation interval."""

    house_id: str
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
    post_battery_surplus_kwh: float
    post_battery_deficit_kwh: float
    p2p_sold_kwh: float
    p2p_bought_kwh: float
    grid_imported_kwh: float
    grid_exported_kwh: float
    grid_import_cost_aud: float
    grid_export_credit_aud: float
    p2p_payment_aud: float
    p2p_revenue_aud: float
    net_cost_aud: float
    energy_balance_residual_kwh: float
    solver_success: bool
    solver_time_sec: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "house_id": self.house_id,
            "step_index": self.step_index,
            "timestamp": str(self.timestamp) if self.timestamp is not None else None,
            "actual_demand_kwh": self.actual_demand_kwh,
            "actual_solar_kwh": self.actual_solar_kwh,
            "forecast_demand_kwh": self.forecast_demand_kwh,
            "forecast_solar_kwh": self.forecast_solar_kwh,
            "battery_initial_soc": self.battery_initial_soc,
            "battery_final_soc": self.battery_final_soc,
            "battery_initial_kwh": self.battery_initial_kwh,
            "battery_final_kwh": self.battery_final_kwh,
            "charged_kwh": self.charged_kwh,
            "discharged_kwh": self.discharged_kwh,
            "post_battery_surplus_kwh": self.post_battery_surplus_kwh,
            "post_battery_deficit_kwh": self.post_battery_deficit_kwh,
            "p2p_sold_kwh": self.p2p_sold_kwh,
            "p2p_bought_kwh": self.p2p_bought_kwh,
            "grid_imported_kwh": self.grid_imported_kwh,
            "grid_exported_kwh": self.grid_exported_kwh,
            "grid_import_cost_aud": self.grid_import_cost_aud,
            "grid_export_credit_aud": self.grid_export_credit_aud,
            "p2p_payment_aud": self.p2p_payment_aud,
            "p2p_revenue_aud": self.p2p_revenue_aud,
            "net_cost_aud": self.net_cost_aud,
            "energy_balance_residual_kwh": self.energy_balance_residual_kwh,
            "solver_success": self.solver_success,
            "solver_time_sec": self.solver_time_sec,
        }


@dataclass
class CommunityStepRecord:
    """Community-wide aggregate outcome and transactions at a single simulation interval."""

    step_index: int
    timestamp: Optional[pd.Timestamp]
    household_records: Dict[str, HouseholdStepRecord]
    transactions: List[MarketTransaction]
    total_demand_kwh: float
    total_solar_kwh: float
    total_charged_kwh: float
    total_discharged_kwh: float
    total_p2p_traded_kwh: float
    total_p2p_payments_aud: float
    total_p2p_revenues_aud: float
    total_grid_imported_kwh: float
    total_grid_exported_kwh: float
    total_grid_import_cost_aud: float
    total_grid_export_credit_aud: float
    community_net_cost_aud: float
    p2p_payment_residual_aud: float
    is_trade_active: bool


@dataclass
class MultiHouseholdSimulationResult:
    """Comprehensive multi-household rolling-horizon simulation outcome."""

    controller_type: str
    enable_p2p: bool
    market_policy: str
    households: List[str]
    total_hours: int
    tradeable_hours: int
    no_trade_hours: int
    per_household_metrics: Dict[str, Dict[str, float]]
    portfolio_metrics: Dict[str, float]
    step_records: List[CommunityStepRecord]
    total_solver_failures: int
    average_solve_time_sec: float

    def get_hourly_records_df(self) -> pd.DataFrame:
        """Flatten per-household records across all hours into an audit DataFrame."""
        rows: List[Dict[str, Any]] = []
        for step in self.step_records:
            for hid in self.households:
                h_rec = step.household_records[hid]
                d = h_rec.to_dict()
                d["controller"] = self.controller_type
                d["enable_p2p"] = self.enable_p2p
                rows.append(d)
        return pd.DataFrame(rows)

    def get_transactions_df(self) -> pd.DataFrame:
        """Extract all bilateral transactions cleared throughout the benchmark."""
        rows: List[Dict[str, Any]] = []
        for step in self.step_records:
            for tx in step.transactions:
                rows.append({
                    "step_index": step.step_index,
                    "timestamp": str(step.timestamp) if step.timestamp is not None else None,
                    "transaction_id": tx.transaction_id,
                    "seller_id": tx.seller_id,
                    "buyer_id": tx.buyer_id,
                    "traded_energy_kwh": tx.traded_energy_kwh,
                    "price_aud_per_kwh": tx.price_aud_per_kwh,
                    "total_value_aud": tx.total_value_aud,
                })
        return pd.DataFrame(rows)


class MultiHouseholdCommunitySimulator:
    """Orchestrates multi-household rolling-horizon optimization and market clearing."""

    def __init__(
        self,
        households: Sequence[str] = ("H001", "H002", "H003"),
        battery_params: Optional[BatteryOptimizationParams] = None,
        tariff_params: Optional[TariffParams] = None,
        p2p_price_aud: float = 0.19,
        market_policy: Union[MarketClearingPolicy, str] = MarketClearingPolicy.PRIORITY_ORDER,
        priority_order: Optional[Sequence[str]] = None,
        mpc_config: Optional[MPCConfig] = None,
        stochastic_config: Optional[StochasticMPCConfig] = None,
        scenario_generator: Optional[StochasticScenarioGenerator] = None,
    ) -> None:
        self.households = sorted(list(households))
        self.battery_params = battery_params or BatteryOptimizationParams(
            capacity_kwh=5.0,
            min_soc=0.10,
            max_soc=0.90,
            max_charge_rate_kw=2.5,
            max_discharge_rate_kw=2.5,
            charge_efficiency=0.95,
            discharge_efficiency=0.95,
        )
        self.tariffs = tariff_params or TariffParams(
            import_price_aud_per_kwh=0.30,
            solar_export_credit_aud_per_kwh=0.08,
        )
        self.p2p_price_aud = float(p2p_price_aud)
        self.market_policy = (
            market_policy
            if isinstance(market_policy, MarketClearingPolicy)
            else MarketClearingPolicy(market_policy)
        )
        self.priority_order = priority_order
        self.mpc_config = mpc_config or MPCConfig(
            horizon_hours=24,
            time_step_hours=1.0,
            terminal_strategy="terminal_value",
            allow_grid_charging=True,
        )
        self.stochastic_config = stochastic_config or StochasticMPCConfig(
            horizon_hours=24,
            time_step_hours=1.0,
            num_scenarios=3,
            terminal_strategy="terminal_value",
            allow_grid_charging=True,
        )
        self.scenario_generator = scenario_generator or StochasticScenarioGenerator()

    def run_simulation(
        self,
        df_all: pd.DataFrame,
        controller_type: str = "Stochastic_MPC",
        enable_p2p: bool = True,
        initial_soc: float = 0.50,
        max_steps: Optional[int] = None,
        shrink_horizon_at_end: bool = True,
        precomputed_records: Optional[pd.DataFrame] = None,
    ) -> MultiHouseholdSimulationResult:
        """Execute chronological multi-household rolling-horizon simulation.

        Parameters
        ----------
        df_all : pd.DataFrame
            Combined DataFrame containing columns:
            `house_id`, `forecast_timestamp`, `actual_demand_kwh`,
            `actual_solar_generation_kwh`, `predicted_demand_kwh`,
            `predicted_solar_generation_kwh`.
        controller_type : str
            One of: 'Stochastic_MPC', 'Deterministic_MPC', 'Forecast_Greedy', 'Oracle_Greedy'.
        enable_p2p : bool
            If True, clears multi-household market. If False, settles directly with central grid.
        initial_soc : float
            Starting battery state of charge (default 0.50).
        max_steps : Optional[int]
            Limit on total simulation hours (for rapid testing).
        shrink_horizon_at_end : bool
            Whether to shrink horizon at end of dataset (default True).
        precomputed_records : Optional[pd.DataFrame]
            Optional pre-computed verified controller dispatches to reuse exact battery
            actions without re-solving MILP optimizations.
        """
        valid_controllers = {
            "Stochastic_MPC",
            "Deterministic_MPC",
            "Forecast_Greedy",
            "Oracle_Greedy",
        }
        if controller_type not in valid_controllers:
            raise ValueError(f"Unknown controller_type '{controller_type}'. Must be one of {valid_controllers}")

        # Partition dataframe per household
        df_houses: Dict[str, pd.DataFrame] = {}
        for hid in self.households:
            sub_df = df_all[df_all["house_id"] == hid].copy().reset_index(drop=True)
            if len(sub_df) == 0:
                raise ValueError(f"Household '{hid}' not found in dataframe.")
            df_houses[hid] = sub_df

        # Verify timestamp alignment
        ref_ts = df_houses[self.households[0]]["forecast_timestamp"].tolist()
        for hid in self.households[1:]:
            curr_ts = df_houses[hid]["forecast_timestamp"].tolist()
            if curr_ts != ref_ts:
                raise ValueError(f"Timestamp mismatch between {self.households[0]} and {hid}")

        N = len(ref_ts) if max_steps is None else min(len(ref_ts), max_steps)
        H = self.stochastic_config.horizon_hours if controller_type == "Stochastic_MPC" else self.mpc_config.horizon_hours
        dt = 1.0
        p_import = self.tariffs.import_price_aud_per_kwh
        p_export = self.tariffs.solar_export_credit_aud_per_kwh
        p_p2p = self.p2p_price_aud

        # Initialize physical batteries
        batteries: Dict[str, BatteryStorage] = {
            hid: BatteryStorage(
                capacity_kwh=self.battery_params.capacity_kwh,
                max_charge_rate_kw=self.battery_params.max_charge_rate_kw,
                max_discharge_rate_kw=self.battery_params.max_discharge_rate_kw,
                charge_efficiency=self.battery_params.charge_efficiency,
                discharge_efficiency=self.battery_params.discharge_efficiency,
                min_soc=self.battery_params.min_soc,
                max_soc=self.battery_params.max_soc,
                initial_soc=initial_soc,
            )
            for hid in self.households
        }
        init_stored_kwh: Dict[str, float] = {hid: batteries[hid].current_charge_kwh for hid in self.households}

        # Initialize controllers
        det_controllers: Dict[str, SingleHouseholdMPCController] = {}
        stoch_controllers: Dict[str, SingleHouseholdStochasticMPCController] = {}

        if controller_type == "Deterministic_MPC":
            for hid in self.households:
                det_controllers[hid] = SingleHouseholdMPCController(
                    battery_params=self.battery_params,
                    tariff_params=self.tariffs,
                    config=self.mpc_config,
                )
        elif controller_type == "Stochastic_MPC":
            for hid in self.households:
                stoch_controllers[hid] = SingleHouseholdStochasticMPCController(
                    battery_params=self.battery_params,
                    tariff_params=self.tariffs,
                    config=self.stochastic_config,
                    scenario_generator=self.scenario_generator,
                )

        step_records: List[CommunityStepRecord] = []
        solve_times: List[float] = []
        solver_failures = 0
        tradeable_hours = 0
        no_trade_hours = 0

        precomputed_lookup: Dict[Tuple[str, int], Any] = {}
        if precomputed_records is not None:
            for _, r in precomputed_records.iterrows():
                precomputed_lookup[(str(r["house_id"]), int(r["step_index"]))] = r

        # Simulation loop
        for k in range(N):
            ts_k = ref_ts[k]
            h_records_k: Dict[str, HouseholdStepRecord] = {}
            market_bids: Dict[str, HouseholdMarketBid] = {}

            # Step 1: Each household decides battery action independently
            for hid in self.households:
                df_h = df_houses[hid]
                bat = batteries[hid]
                d_act = float(df_h.loc[k, "actual_demand_kwh"])
                s_act = float(df_h.loc[k, "actual_solar_generation_kwh"])
                d_fc = float(df_h.loc[k, "predicted_demand_kwh"])
                s_fc = float(df_h.loc[k, "predicted_solar_generation_kwh"])

                if precomputed_lookup and (hid, k) in precomputed_lookup:
                    r_pre = precomputed_lookup[(hid, k)]
                    actual_c = float(r_pre["charged_kwh"])
                    actual_d = float(r_pre["discharged_kwh"])
                    init_soc_step = float(r_pre["battery_initial_soc"])
                    init_kwh_step = float(r_pre["battery_initial_kwh"])
                    final_soc_step = float(r_pre["battery_final_soc"])
                    final_kwh_step = float(r_pre["battery_final_kwh"])
                    s_success = bool(r_pre.get("solver_success", True))
                    s_time = float(r_pre.get("solver_time_sec", 0.0))
                    solve_times.append(s_time)
                    if not s_success:
                        solver_failures += 1
                    bat.reset(final_soc_step)
                else:
                    init_soc_step = bat.soc
                    init_kwh_step = bat.current_charge_kwh

                    end_idx = min(k + H, len(df_h))
                    d_window = df_h.loc[k:end_idx - 1, "predicted_demand_kwh"].to_numpy(dtype=float)
                    s_window = df_h.loc[k:end_idx - 1, "predicted_solar_generation_kwh"].to_numpy(dtype=float)

                    s_time = 0.0
                    s_success = True

                    if controller_type == "Stochastic_MPC":
                        res = stoch_controllers[hid].optimize(
                            initial_energy_kwh=init_kwh_step,
                            demand_forecast=d_window,
                            solar_forecast=s_window,
                            house_id=hid,
                            timestamp=ts_k,
                        )
                        c_plan, d_plan = res.first_action
                        s_time = res.solve_time_sec
                        s_success = res.success
                        solve_times.append(s_time)
                        if not s_success:
                            solver_failures += 1

                    elif controller_type == "Deterministic_MPC":
                        plan = det_controllers[hid].optimize(
                            initial_energy_kwh=init_kwh_step,
                            demand_forecast=d_window,
                            solar_forecast=s_window,
                        )
                        c_plan, d_plan = plan.first_action
                        s_time = plan.solve_time_sec
                        s_success = plan.success
                        solve_times.append(s_time)
                        if not s_success:
                            solver_failures += 1

                    elif controller_type == "Forecast_Greedy":
                        t0 = time.perf_counter()
                        net_fc = s_fc - d_fc
                        c_max = self.battery_params.max_charge_rate_kw * dt
                        d_max = self.battery_params.max_discharge_rate_kw * dt
                        if net_fc > 1e-6:
                            room = max(0.0, (self.battery_params.max_energy_kwh - init_kwh_step) / self.battery_params.charge_efficiency)
                            c_plan = min(net_fc, c_max, room)
                            d_plan = 0.0
                        else:
                            need = d_fc - s_fc
                            avail = max(0.0, (init_kwh_step - self.battery_params.min_energy_kwh) * self.battery_params.discharge_efficiency)
                            d_plan = min(need, d_max, avail)
                            c_plan = 0.0
                        s_time = time.perf_counter() - t0
                        solve_times.append(s_time)

                    elif controller_type == "Oracle_Greedy":
                        t0 = time.perf_counter()
                        net_act = s_act - d_act
                        c_max = self.battery_params.max_charge_rate_kw * dt
                        d_max = self.battery_params.max_discharge_rate_kw * dt
                        if net_act > 1e-6:
                            room = max(0.0, (self.battery_params.max_energy_kwh - init_kwh_step) / self.battery_params.charge_efficiency)
                            c_plan = min(net_act, c_max, room)
                            d_plan = 0.0
                        else:
                            need = d_act - s_act
                            avail = max(0.0, (init_kwh_step - self.battery_params.min_energy_kwh) * self.battery_params.discharge_efficiency)
                            d_plan = min(need, d_max, avail)
                            c_plan = 0.0
                        s_time = time.perf_counter() - t0
                        solve_times.append(s_time)

                    # Step 2: Physical battery execution
                    if c_plan > 1e-6:
                        bat_state = bat.step(
                            energy_available_to_charge_kwh=c_plan,
                            energy_requested_to_discharge_kwh=0.0,
                            duration_hours=dt,
                        )
                    elif d_plan > 1e-6:
                        bat_state = bat.step(
                            energy_available_to_charge_kwh=0.0,
                            energy_requested_to_discharge_kwh=d_plan,
                            duration_hours=dt,
                        )
                    else:
                        bat_state = bat.step(0.0, 0.0, duration_hours=dt)

                    actual_c = bat_state.charged_kwh
                    actual_d = bat_state.discharged_kwh

                # Step 3: Physical net flow post-battery
                net_flow = (d_act + actual_c) - (s_act + actual_d)
                if net_flow >= 0.0:
                    surplus_q = 0.0
                    deficit_q = net_flow
                else:
                    surplus_q = -net_flow
                    deficit_q = 0.0

                market_bids[hid] = HouseholdMarketBid(
                    house_id=hid,
                    surplus_kwh=surplus_q,
                    deficit_kwh=deficit_q,
                    p2p_price_aud=p_p2p,
                )

                # Interim record holder
                h_records_k[hid] = HouseholdStepRecord(
                    house_id=hid,
                    step_index=k,
                    timestamp=pd.to_datetime(ts_k),
                    actual_demand_kwh=d_act,
                    actual_solar_kwh=s_act,
                    forecast_demand_kwh=d_fc,
                    forecast_solar_kwh=s_fc,
                    battery_initial_soc=init_soc_step,
                    battery_final_soc=bat.soc,
                    battery_initial_kwh=init_kwh_step,
                    battery_final_kwh=bat.current_charge_kwh,
                    charged_kwh=actual_c,
                    discharged_kwh=actual_d,
                    post_battery_surplus_kwh=surplus_q,
                    post_battery_deficit_kwh=deficit_q,
                    p2p_sold_kwh=0.0,
                    p2p_bought_kwh=0.0,
                    grid_imported_kwh=0.0,
                    grid_exported_kwh=0.0,
                    grid_import_cost_aud=0.0,
                    grid_export_credit_aud=0.0,
                    p2p_payment_aud=0.0,
                    p2p_revenue_aud=0.0,
                    net_cost_aud=0.0,
                    energy_balance_residual_kwh=0.0,
                    solver_success=s_success,
                    solver_time_sec=s_time,
                )

            # Step 4: Multi-Household Market Clearing or Standalone Settlement
            transactions: List[MarketTransaction] = []
            if enable_p2p:
                clearing_res: MarketClearingResult = clear_multi_household_market(
                    bids_or_balances=market_bids,
                    p2p_price_aud=p_p2p,
                    grid_import_price_aud=p_import,
                    grid_export_credit_aud=p_export,
                    policy=self.market_policy,
                    priority_order=self.priority_order,
                    timestamp=pd.to_datetime(ts_k),
                )
                transactions = clearing_res.transactions
                for hid in self.households:
                    rec = h_records_k[hid]
                    rec.p2p_sold_kwh = clearing_res.seller_allocations_kwh[hid]
                    rec.p2p_bought_kwh = clearing_res.buyer_allocations_kwh[hid]
                    rec.grid_imported_kwh = clearing_res.unmet_demand_kwh[hid]
                    rec.grid_exported_kwh = clearing_res.unmatched_surplus_kwh[hid]
            else:
                for hid in self.households:
                    rec = h_records_k[hid]
                    rec.p2p_sold_kwh = 0.0
                    rec.p2p_bought_kwh = 0.0
                    rec.grid_imported_kwh = rec.post_battery_deficit_kwh
                    rec.grid_exported_kwh = rec.post_battery_surplus_kwh

            # Step 5: Complete Financial Settlement & Per-Household Energy Balance Audit
            for hid in self.households:
                rec = h_records_k[hid]
                rec.grid_import_cost_aud = rec.grid_imported_kwh * p_import
                rec.grid_export_credit_aud = rec.grid_exported_kwh * p_export
                rec.p2p_payment_aud = rec.p2p_bought_kwh * p_p2p
                rec.p2p_revenue_aud = rec.p2p_sold_kwh * p_p2p
                rec.net_cost_aud = (
                    (rec.grid_import_cost_aud + rec.p2p_payment_aud)
                    - (rec.grid_export_credit_aud + rec.p2p_revenue_aud)
                )

                # Physical balance check: Demand + Charged + Exported + Sold == Solar + Discharged + Imported + Bought
                lhs = rec.actual_demand_kwh + rec.charged_kwh + rec.grid_exported_kwh + rec.p2p_sold_kwh
                rhs = rec.actual_solar_kwh + rec.discharged_kwh + rec.grid_imported_kwh + rec.p2p_bought_kwh
                rec.energy_balance_residual_kwh = abs(lhs - rhs)
                if rec.energy_balance_residual_kwh > 1e-4:
                    raise ValueError(
                        f"Per-household physical balance violation at step {k} ({ts_k}) for {hid}: "
                        f"LHS={lhs:.6f} != RHS={rhs:.6f} (residual={rec.energy_balance_residual_kwh:.6e})"
                    )

            # Step 6: Community Financial Conservation & Trade Verification
            tot_p2p_traded = sum(rec.p2p_sold_kwh for rec in h_records_k.values())
            tot_p2p_bought = sum(rec.p2p_bought_kwh for rec in h_records_k.values())
            if abs(tot_p2p_traded - tot_p2p_bought) > 1e-5:
                raise ValueError(
                    f"Community trade conservation violation at step {k}: Sold={tot_p2p_traded} != Bought={tot_p2p_bought}"
                )

            tot_p2p_pmt = sum(rec.p2p_payment_aud for rec in h_records_k.values())
            tot_p2p_rev = sum(rec.p2p_revenue_aud for rec in h_records_k.values())
            pmt_res = abs(tot_p2p_pmt - tot_p2p_rev)
            if pmt_res > 1e-5:
                raise ValueError(
                    f"Community P2P payment conservation violation at step {k}: Payments={tot_p2p_pmt} != Revenues={tot_p2p_rev}"
                )

            is_trade = tot_p2p_traded > 1e-5
            if is_trade:
                tradeable_hours += 1
            else:
                no_trade_hours += 1

            comm_record = CommunityStepRecord(
                step_index=k,
                timestamp=pd.to_datetime(ts_k),
                household_records=h_records_k,
                transactions=transactions,
                total_demand_kwh=sum(r.actual_demand_kwh for r in h_records_k.values()),
                total_solar_kwh=sum(r.actual_solar_kwh for r in h_records_k.values()),
                total_charged_kwh=sum(r.charged_kwh for r in h_records_k.values()),
                total_discharged_kwh=sum(r.discharged_kwh for r in h_records_k.values()),
                total_p2p_traded_kwh=tot_p2p_traded,
                total_p2p_payments_aud=tot_p2p_pmt,
                total_p2p_revenues_aud=tot_p2p_rev,
                total_grid_imported_kwh=sum(r.grid_imported_kwh for r in h_records_k.values()),
                total_grid_exported_kwh=sum(r.grid_exported_kwh for r in h_records_k.values()),
                total_grid_import_cost_aud=sum(r.grid_import_cost_aud for r in h_records_k.values()),
                total_grid_export_credit_aud=sum(r.grid_export_credit_aud for r in h_records_k.values()),
                community_net_cost_aud=sum(r.net_cost_aud for r in h_records_k.values()),
                p2p_payment_residual_aud=pmt_res,
                is_trade_active=is_trade,
            )
            step_records.append(comm_record)

        # Summarize portfolio and per-household metrics
        per_house_metrics: Dict[str, Dict[str, float]] = {}
        chem_value = self.battery_params.discharge_efficiency * p_import  # 0.95 * 0.30 = 0.285 AUD/kWh

        for hid in self.households:
            recs = [s.household_records[hid] for s in step_records]
            imp_kwh = sum(r.grid_imported_kwh for r in recs)
            exp_kwh = sum(r.grid_exported_kwh for r in recs)
            ch_kwh = sum(r.charged_kwh for r in recs)
            dis_kwh = sum(r.discharged_kwh for r in recs)
            p2p_b_kwh = sum(r.p2p_bought_kwh for r in recs)
            p2p_s_kwh = sum(r.p2p_sold_kwh for r in recs)

            imp_cost = sum(r.grid_import_cost_aud for r in recs)
            exp_cred = sum(r.grid_export_credit_aud for r in recs)
            p2p_pmt = sum(r.p2p_payment_aud for r in recs)
            p2p_rev = sum(r.p2p_revenue_aud for r in recs)
            net_cost = sum(r.net_cost_aud for r in recs)

            final_bat_kwh = batteries[hid].current_charge_kwh
            final_soc = batteries[hid].soc
            init_kwh = init_stored_kwh[hid]
            delta_e = final_bat_kwh - init_kwh
            terminal_adj = -(delta_e * chem_value)
            adj_cost = net_cost + terminal_adj

            socs = [r.battery_final_soc for r in recs]
            soc_viol = sum(
                1 for s in socs
                if s < self.battery_params.min_soc - 1e-5 or s > self.battery_params.max_soc + 1e-5
            )
            simul_viol = sum(1 for r in recs if r.charged_kwh > 1e-5 and r.discharged_kwh > 1e-5)
            max_res = max((r.energy_balance_residual_kwh for r in recs), default=0.0)

            per_house_metrics[hid] = {
                "total_demand_kwh": sum(r.actual_demand_kwh for r in recs),
                "total_solar_kwh": sum(r.actual_solar_kwh for r in recs),
                "total_imported_kwh": imp_kwh,
                "total_exported_kwh": exp_kwh,
                "total_charged_kwh": ch_kwh,
                "total_discharged_kwh": dis_kwh,
                "total_p2p_bought_kwh": p2p_b_kwh,
                "total_p2p_sold_kwh": p2p_s_kwh,
                "grid_import_cost_aud": imp_cost,
                "grid_export_credit_aud": exp_cred,
                "p2p_payment_aud": p2p_pmt,
                "p2p_revenue_aud": p2p_rev,
                "realized_net_cost_aud": net_cost,
                "terminal_adjustment_aud": terminal_adj,
                "adjusted_net_cost_aud": adj_cost,
                "initial_soc": initial_soc,
                "final_soc": final_soc,
                "initial_kwh": init_kwh,
                "final_kwh": final_bat_kwh,
                "delta_stored_kwh": delta_e,
                "soc_boundary_violations": soc_viol,
                "simultaneous_charge_discharge_violations": simul_viol,
                "max_energy_balance_residual_kwh": max_res,
            }

        # Portfolio metrics
        port_import_kwh = sum(m["total_imported_kwh"] for m in per_house_metrics.values())
        port_export_kwh = sum(m["total_exported_kwh"] for m in per_house_metrics.values())
        port_ch_kwh = sum(m["total_charged_kwh"] for m in per_house_metrics.values())
        port_dis_kwh = sum(m["total_discharged_kwh"] for m in per_house_metrics.values())
        port_p2p_traded_kwh = sum(m["total_p2p_sold_kwh"] for m in per_house_metrics.values())

        port_import_cost = sum(m["grid_import_cost_aud"] for m in per_house_metrics.values())
        port_export_cred = sum(m["grid_export_credit_aud"] for m in per_house_metrics.values())
        port_p2p_pmt = sum(m["p2p_payment_aud"] for m in per_house_metrics.values())
        port_p2p_rev = sum(m["p2p_revenue_aud"] for m in per_house_metrics.values())
        port_net_cost = sum(m["realized_net_cost_aud"] for m in per_house_metrics.values())
        port_terminal_adj = sum(m["terminal_adjustment_aud"] for m in per_house_metrics.values())
        port_adj_cost = sum(m["adjusted_net_cost_aud"] for m in per_house_metrics.values())

        portfolio_metrics = {
            "total_hours": N,
            "tradeable_hours": tradeable_hours,
            "no_trade_hours": no_trade_hours,
            "total_imported_kwh": port_import_kwh,
            "total_exported_kwh": port_export_kwh,
            "total_charged_kwh": port_ch_kwh,
            "total_discharged_kwh": port_dis_kwh,
            "total_p2p_traded_kwh": port_p2p_traded_kwh,
            "grid_import_cost_aud": port_import_cost,
            "grid_export_credit_aud": port_export_cred,
            "p2p_payment_aud": port_p2p_pmt,
            "p2p_revenue_aud": port_p2p_rev,
            "realized_net_cost_aud": port_net_cost,
            "terminal_adjustment_aud": port_terminal_adj,
            "adjusted_net_cost_aud": port_adj_cost,
            "total_solver_failures": solver_failures,
            "average_solve_time_ms": (float(np.mean(solve_times)) * 1000.0) if solve_times else 0.0,
            "max_solve_time_ms": (float(np.max(solve_times)) * 1000.0) if solve_times else 0.0,
        }

        return MultiHouseholdSimulationResult(
            controller_type=controller_type,
            enable_p2p=enable_p2p,
            market_policy=self.market_policy.value,
            households=self.households,
            total_hours=N,
            tradeable_hours=tradeable_hours,
            no_trade_hours=no_trade_hours,
            per_household_metrics=per_house_metrics,
            portfolio_metrics=portfolio_metrics,
            step_records=step_records,
            total_solver_failures=solver_failures,
            average_solve_time_sec=float(np.mean(solve_times)) if solve_times else 0.0,
        )
