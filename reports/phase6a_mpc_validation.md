# Phase 6A — Single-Household Rolling-Horizon MPC Baseline Validation Audit Report

**Project Title:** Stochastic Game-Theoretic Optimization under Uncertain Energy Conditions  
**Phase Under Audit:** Phase 6A — Single-Household 24-Hour Rolling-Horizon Model Predictive Control (MPC) Battery Baseline  
**Auditor:** Independent Technical Verification & Optimization Agent  
**Date of Audit:** October 28, 2026  
**Artifact Path:** [`reports/phase6a_mpc_validation.md`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/reports/phase6a_mpc_validation.md)  
**Readiness Verdict:** **`READY FOR PHASE 6B (STOCHASTIC SCENARIO MPC)`**

---

## 1. Executive Summary & Objective

Phase 6A establishes the **single-household, 24-hour rolling-horizon Model Predictive Control (MPC) battery controller baseline**. Prior to extending to multi-household optimization or dynamic stochastic games, Phase 6A constructs an optimal, testable single-agent benchmark and evaluates it against the existing heuristic/greedy battery dispatch policy in [`src/energy/energy_balance.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/energy/energy_balance.py).

### Core Findings:
1. **Mathematical Optimization Integrity**: Formulated as a Mixed-Integer Linear Program (MILP) solved using the native C++ **HiGHS** branch-and-cut solver in `scipy.optimize.milp` (`scipy 1.15.1`). **Zero external dependencies or pip packages were added**.
2. **Mutual Exclusion & Physical Conservation**: Binary indicator variables ($u_t^{\text{ch}} \in \{0, 1\}$) enforce strict physical mutual exclusion: simultaneous charging and discharging is strictly impossible ($C_t \cdot D_t = 0$). Household physical energy conservation holds with a maximum residual of **$< 4.45 \times 10^{-16}\text{ kWh}$** (machine epsilon precision).
3. **Terminal Horizon Preservation**: Solved the classic finite-horizon battery depletion phenomenon by implementing discounted terminal energy valuation ($\lambda_{\text{term}} = 0.98 \cdot \eta_{\text{dis}} \cdot p^{\text{import}} = 0.2793\text{ AUD/kWh}$). This prevents the controller from dumping stored chemical energy at the end of the horizon, while maintaining strict preference for serving immediate domestic demand.
4. **Empirical Benchmark on 1,752 Held-Out Hours**: Evaluated across all 1,752 chronological test hours ($10,512$ total MILP optimizations across households H001, H002, and H003):
   - **Perfect-Foresight MPC vs Greedy**: Achieved **$0.00 discrepancy** ($100\%$ identical net electricity cost down to the exact cent across all households: H001 $=\$335.95$, H002 $=\$105.03$, H003 $=\$306.38$). Under a flat tariff with single-household self-consumption, the greedy policy is the global optimum if future information is identical.
   - **Realistic MPC with Forecast Uncertainty vs Greedy**: When operating strictly behind information boundaries using LSTM point forecasts, realistic MPC incurred slightly higher net electricity costs (+5.01% for H001, +19.27% for H002, +2.15% for H003) due to forecast prediction errors committing sub-optimal battery setpoints. This empirically quantifies the **Cost of Forecast Uncertainty** and justifies stochastic scenario optimization in Phase 6B.
5. **Test Suite Verification**: **131/131 tests passing** (10/10 focused MPC tests, 121/121 legacy repository tests, 0 regressions).

---

## 2. Mathematical Optimization Formulation

### 2.1 Horizon and Discretization
- **Horizon length**: $T = 24$ hourly time steps ($t = 0, \dots, T-1$).
- **Time step**: $\Delta t = 1.0\text{ hour}$.

### 2.2 Battery Physical Parameters
- Rated Capacity: $E_{\text{cap}} = 5.0\text{ kWh}$.
- Usable SOC range: $[10\%, 90\%] \implies E_{\min} = 0.50\text{ kWh}, \quad E_{\max} = 4.50\text{ kWh}$.
- Power limits: $P_{\text{ch}}^{\max} = 2.5\text{ kW}, \quad P_{\text{dis}}^{\max} = 2.5\text{ kW} \implies C^{\max} = 2.50\text{ kWh}, \quad D^{\max} = 2.50\text{ kWh}$.
- Efficiencies: $\eta_{\text{ch}} = 0.95, \quad \eta_{\text{dis}} = 0.95 \implies \eta_{\text{rt}} = 90.25\%$.
- Illustrative Base Tariffs: Import $p^{\text{import}} = 0.30\text{ AUD/kWh}$, Export credit $p^{\text{export}} = 0.08\text{ AUD/kWh}$.

### 2.3 Optimization Variables
For each time step $t \in \{0, \dots, T-1\}$:
1. $C_t \in [0, C^{\max}]$: Battery charging electrical energy entering terminals ($\text{kWh}$).
2. $D_t \in [0, D^{\max}]$: Battery discharging electrical energy delivered to demand ($\text{kWh}$).
3. $M_t \in [0, \infty)$: Grid import electrical energy ($\text{kWh}$).
4. $X_t \in [0, \infty)$: Grid export electrical energy ($\text{kWh}$).
5. $u_t^{\text{ch}} \in \{0, 1\}$: Binary charging mode indicator ($1 = \text{charging}, 0 = \text{discharging/idle}$).
6. $E_{t+1} \in [E_{\min}, E_{\max}]$: Battery stored chemical energy at the end of step $t$ ($\text{kWh}$).

### 2.4 Governing Equations and Constraints
1. **Power Limits & Mutual Exclusion**:
   $$C_t - C^{\max} u_t^{\text{ch}} \le 0, \quad \forall t$$
   $$D_t + D^{\max} u_t^{\text{ch}} \le D^{\max}, \quad \forall t$$
   *Mathematical Guarantee*:
   - If $u_t^{\text{ch}} = 1 \implies C_t \in [0, C^{\max}]$ and $D_t \le 0 \implies D_t = 0$.
   - If $u_t^{\text{ch}} = 0 \implies C_t \le 0 \implies C_t = 0$ and $D_t \in [0, D^{\max}]$.
   - Therefore, $C_t \cdot D_t = 0$ is strictly guaranteed.

2. **State of Charge (Stored Energy) Dynamics**:
   $$E_{t+1} = E_t + \eta_{\text{ch}} C_t - \frac{1}{\eta_{\text{dis}}} D_t, \quad \forall t \in \{0, \dots, T-1\}$$
   with boundary condition $E_0 = E_{\text{init}}$.

3. **Household Physical Energy Conservation**:
   $$M_t - X_t - C_t + D_t = \hat{d}_t - \hat{s}_t, \quad \forall t$$
   $$\iff \hat{d}_t + C_t + X_t = \hat{s}_t + D_t + M_t$$
   *(Total inflows equal total outflows).*

4. **Terminal Energy Valuation**:
   To prevent artificial horizon-tail dumping (where an unconstrained optimizer discharges stored energy to $E_{\min}$ at hour 23 because remaining energy has zero post-horizon objective value), we include a terminal energy valuation in the objective:
   $$\lambda_{\text{term}} = 0.98 \cdot \eta_{\text{dis}} \cdot p^{\text{import}} = 0.98 \cdot (0.95) \cdot (0.30) = 0.2793\text{ AUD/kWh}$$
   - *Why $0.2793\text{ AUD/kWh}$?* It satisfies $\frac{p^{\text{export}}}{\eta_{\text{ch}}} (0.084) < \lambda_{\text{term}} (0.2793) < \eta_{\text{dis}} p^{\text{import}} (0.2850)$.
   - It guarantees that storing surplus solar is strictly preferred to exporting (+0.185 AUD/kWh gain).
   - It guarantees that dumping stored energy to the grid is strictly prohibited (-0.203 AUD/kWh loss).
   - It breaks mathematical ties in favor of serving immediate known demand rather than hoarding energy for the future.

### 2.5 Objective Function
$$\min_{C, D, M, X, u^{\text{ch}}, E} \sum_{t=0}^{T-1} \left( p^{\text{import}} M_t - p^{\text{export}} X_t \right) - \lambda_{\text{term}} (E_T - E_{\min})$$

---

## 3. Solver & Implementation Details

- **Optimization Engine**: HiGHS C++ Branch-and-Cut MILP Solver via `scipy.optimize.milp` (`scipy 1.15.1`).
- **Dependencies Added**: None (0 new packages).
- **Files Modified / Added**:
  - [`src/optimization/solver.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/optimization/solver.py): Generic MILP wrapper with standardized `MILPResult` dataclass, profiling, and error guards.
  - [`src/optimization/constraints.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/optimization/constraints.py): Parameter dataclasses (`BatteryOptimizationParams`, `TariffParams`, `MPCConfig`).
  - [`src/optimization/mpc_battery.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/optimization/mpc_battery.py): `SingleHouseholdMPCController` and `RollingHorizonSimulator` with strict forecast-vs-actual boundary separation.
  - [`tests/test_mpc_battery.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/tests/test_mpc_battery.py): 10 focused unit tests covering all mathematical properties.
  - [`evaluate_mpc_vs_greedy.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/evaluate_mpc_vs_greedy.py): Full empirical evaluation harness across 1,752 hours.
  - [`reports/phase6a_simulation_metrics.csv`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/reports/phase6a_simulation_metrics.csv): Exact numerical audit outputs.

---

## 4. Empirical Benchmark: MPC vs Greedy Baseline

Evaluation was performed on the held-out test predictions dataset (`data/processed/test_predictions.csv`) covering **1,752 chronological hours** (April 19, 2013 to June 30, 2013) across all three households.

Both controllers were initialized with the exact same state ($SOC_0 = 50\%$, $E_0 = 2.50\text{ kWh}$), identical battery specifications, and identical tariffs ($0.30\text{ import} / 0.08\text{ export}$).

### 4.1 Comparative Financial & Operational Results

| Household | Controller Strategy | Net Grid Cost (AUD) | Adjusted Cost (AUD) | Grid Import (kWh) | Grid Export (kWh) | Battery Charged (kWh) | Battery Discharged (kWh) | Final SOC | Cost Diff vs Greedy |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **H001** | **Greedy Baseline** | **$335.95** | **$336.52** | $1,172.06$ | $195.81$ | $245.30$ | $223.28$ | $10.0\%$ | — |
| **H001** | **Realistic MPC (Forecasts)** | **$352.77** | **$353.34** | $1,247.94$ | $270.09$ | $261.80$ | $238.17$ | $10.0\%$ | **+$16.82 (+5.01%)** |
| **H001** | **Perfect-Foresight MPC** | **$335.95** | **$336.52** | $1,172.06$ | $195.81$ | $245.30$ | $223.28$ | $10.0\%$ | **$0.00 (0.00%)** |
| | | | | | | | | | |
| **H002** | **Greedy Baseline** | **$105.03** | **$105.60** | $352.63$ | $9.52$ | $143.66$ | $131.56$ | $10.0\%$ | — |
| **H002** | **Realistic MPC (Forecasts)** | **$125.27** | **$125.84** | $445.90$ | $106.28$ | $107.84$ | $99.23$ | $10.0\%$ | **+$20.24 (+19.27%)** |
| **H002** | **Perfect-Foresight MPC** | **$105.03** | **$105.60** | $352.63$ | $9.52$ | $143.66$ | $131.56$ | $10.0\%$ | **$0.00 (0.00%)** |
| | | | | | | | | | |
| **H003** | **Greedy Baseline** | **$306.38** | **$306.95** | $1,021.26$ | $0.00$ | $64.53$ | $60.13$ | $10.0\%$ | — |
| **H003** | **Realistic MPC (Forecasts)** | **$312.97** | **$313.54** | $1,051.40$ | $30.65$ | $59.35$ | $55.47$ | $10.0\%$ | **+$6.59 (+2.15%)** |
| **H003** | **Perfect-Foresight MPC** | **$306.38** | **$306.95** | $1,021.26$ | $0.00$ | $64.53$ | $60.13$ | $10.0\%$ | **$0.00 (0.00%)** |

### 4.2 Key Analytical Insights
1. **The Optimality of the Greedy Heuristic under Flat Tariffs**:
   Under flat tariffs ($p_t^{\text{import}} = 0.30$, $p_t^{\text{export}} = 0.08$) and without P2P trading, storing surplus solar to displace future grid import is always optimal, and timing within the day does not change the marginal tariff. Consequently, **Perfect-Foresight MPC achieves the exact same cost as Greedy ($0.000000$ difference)**.
2. **Empirical Measurement of the Cost of Forecast Uncertainty**:
   Realistic MPC plans against LSTM point predictions ($\hat{d}_t, \hat{s}_t$) but executes against realized observations ($d_t, s_t$). When solar forecasts over-predict or under-predict midday generation, the planned battery dispatch deviates from the instantaneous actual surplus/deficit, resulting in extra grid interaction (+5.01% for H001, +19.27% for H002).
   *Significance*: This demonstrates why point-forecast deterministic MPC is vulnerable to forecast error, motivating Phase 6B's Monte Carlo stochastic scenario MPC.

---

## 5. Physical Feasibility, Residuals, and Solver Performance

| Metric | Household H001 | Household H002 | Household H003 | Acceptance Threshold | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Total Horizon Optimizations** | $1,752$ | $1,752$ | $1,752$ | $1,752$ | **PASS** |
| **Optimization Solver Failures** | $0$ | $0$ | $0$ | $0$ | **PASS** |
| **SOC Boundary Violations** ($< 10\%$ or $> 90\%$) | $0$ | $0$ | $0$ | $0$ | **PASS** |
| **Simultaneous Charge/Discharge Steps** | $0$ | $0$ | $0$ | $0$ | **PASS** |
| **Max Energy Balance Residual** | $4.44 \times 10^{-16}\text{ kWh}$ | $4.44 \times 10^{-16}\text{ kWh}$ | $2.22 \times 10^{-16}\text{ kWh}$ | $< 10^{-5}\text{ kWh}$ | **PASS** |
| **Average Solver Runtime per Step** | $15.83\text{ ms}$ | $28.91\text{ ms}$ | $29.36\text{ ms}$ | $< 100\text{ ms}$ | **PASS** |
| **Maximum Solver Runtime** | $42.54\text{ ms}$ | $373.52\text{ ms}$ | $496.09\text{ ms}$ | $< 5000\text{ ms}$ | **PASS** |

---

## 6. Test Suite Execution Trace

The test suite was executed via `python -m pytest tests/test_mpc_battery.py -v` and `python -m pytest`:

```text
============================= test session starts =============================
platform win32 -- Python 3.13.6, pytest-8.3.4, pluggy-1.5.0
plugins: anyio-4.8.0, asyncio-0.25.2
collected 131 items

tests\test_battery.py .....                                              [  3%]
tests\test_battery_integration.py ..........                             [ 11%]
tests\test_energy.py .....                                               [ 15%]
tests\test_financial_payoffs.py ............                             [ 24%]
tests\test_forecast_evaluation.py .............                          [ 34%]
tests\test_game.py .........                                             [ 41%]
tests\test_market_clearing.py .................                          [ 54%]
tests\test_monte_carlo.py .......................                        [ 71%]
tests\test_mpc_battery.py ..........                                     [ 79%]
tests\test_physical_feasibility.py ....................                  [ 94%]
tests\test_preprocessing.py ...                                          [ 96%]
tests\test_utility.py ....                                               [100%]

============================ 131 passed in 18.07s =============================
```

---

## 7. Limitations & Recommendations for Phase 6B

1. **Deterministic Point Forecast Vulnerability**:
   As demonstrated by the empirical evaluation, single-point deterministic MPC suffers when predictions deviate from ground truth.
   *Recommendation for Phase 6B*: Integrate the existing 1,000 Monte Carlo empirical scenario distributions (`src/stochastic/monte_carlo.py`) to formulate a Stochastic Scenario-Based MPC that optimizes expected cost over the probabilistic distribution.
2. **Flat vs Time-Of-Use (TOU) Tariffs**:
   Under flat tariffs, arbitrage across time is economically unviable ($\eta_{\text{rt}} \times 0.30 = 0.27075 < 0.30$).
   *Recommendation*: In future phases, evaluate Time-of-Use tariffs (peak / off-peak) where MPC can perform scheduled pre-charging during low-tariff windows.
3. **P2P Market Clearing Integration**:
   Phase 5B multi-household clearing (`src/energy/market_clearing.py`) remains completely untouched in Phase 6A as mandated. Once stochastic MPC is validated, the MPC battery bids will be integrated into the multi-household P2P market clearing auction.
