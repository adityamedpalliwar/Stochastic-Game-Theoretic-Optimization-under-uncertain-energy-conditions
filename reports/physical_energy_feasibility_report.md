# Comprehensive Physical Energy Feasibility, Energy Conservation, and Transaction Validation Report

## Executive Summary

This report delivers a rigorous, evidence-based physical energy feasibility audit for the **Stochastic Game-Theoretic Renewable Energy Management** project. Conducted prior to economic modifications or conformal calibration, this audit verifies that every energy flow, household balance, Monte Carlo realization, and transaction allocation is mathematically consistent, conserved, and physically realizable.

### Scope of the Audit
- **3 Households:** `H001` (solar exporter / candidate seller), `H002` (net consumer / candidate buyer), and `H003` (forecasting evaluation baseline).
- **1,752 Chronological Test Hours per Household:** Held-out test period (2013-04-19 00:00:00 to 2013-06-30 23:00:00), totaling **5,256 household-hour observations**.
- **1,752,000 Monte Carlo Scenario Realizations:** 1,000 paired scenarios per hour across all 1,752 hours evaluated under **Protocol B** deterministic seeding (`derive_observation_seed`).
- **10,512 Pre-Trade Point Energy Balances:** 5,256 ground-truth actual balances and 5,256 point-forecast balances.
- **81 Passing Automated Regression Tests:** Entire test suite passing (62 baseline tests + 19 newly authored Step 4 physical feasibility tests).

### Key Findings
1. **Perfect Energy Conservation in Evaluated Scenarios:** Across all 1,752,000 Monte Carlo scenario realizations and 10,512 point balances, the maximum observed absolute energy-balance residual is **$4.77 \times 10^{-7}$ kWh** (pure floating-point precision noise). Zero energy conservation violations ($> 10^{-5}$ kWh) were detected.
2. **Identification and Elimination of Silent Data Corruption:** A critical audit of existing code revealed that several functions (`compute_energy_balance`, `build_two_household_payoff_matrix`, `compute_household_payoff`) silently converted `NaN` and negative energy values into plausible physical numbers (`0.0`) via unguarded `max(0.0, float(val))` statements. Furthermore, `EnergyBalance` previously permitted simultaneous positive surplus and deficit without failing. All modules have been hardened with strict finiteness, non-negativity, and complementarity guards.
3. **Formalization of Post-Trade Flow Conservation:** Implemented `PostTradeEnergyBalance` and `compute_post_trade_balance` in `src/energy/energy_balance.py` to track and enforce the complete 6-flow post-trade accounting: local self-consumption ($E_{\text{self}}$), P2P import ($q_{\text{buy}}$), P2P export ($q_{\text{sell}}$), grid import ($E_{\text{grid\_in}}$), and grid export ($E_{\text{grid\_out}}$).
4. **Action Selection vs. Physical Trade Execution:** In the two-action game (`OFFER_P2P` vs. `EXPORT_GRID`, `ACCEPT_P2P` vs. `GRID_IMPORT`), choosing the cooperative action profile `(OFFER_P2P, ACCEPT_P2P)` executes physical energy transfer **only when mutual trade capacity exists** ($q = \min(S_1, B_2) > 0$). In **91.31% of all test hours and 85.1% of midday/diurnal scenarios**, either seller surplus or buyer deficit is zero. In such hours, the game degenerates into a zero-volume exchange where both actions yield identical payoffs, representing weak Nash equilibrium indifference.
5. **Empirical Proof of Jensen's Inequality Distortion:** In **93.21% of test hours**, calculating trade feasibility at the mean forecast ($\min(\mathbb{E}[S_1], \mathbb{E}[B_2])$) overestimates the true expected physical trade ($\mathbb{E}[\min(S_1, B_2)]$), with an average overestimation of **$0.0214$ kWh/h** and a maximum of **$0.1638$ kWh/h**. This demonstrates why scenario-level Monte Carlo evaluation is physically essential.
6. **Battery Storage Isolation:** A verified physical battery model exists in `src/energy/battery.py`, but it is intentionally uncoupled from the current hourly game clearing pipeline. Integrating storage without a multi-period dynamic optimization framework would compromise the current game formulation.

---

## 1. Existing Architecture and Implementation Files Inspected

The repository was inspected across all modules related to energy calculations, game clearing, stochastic simulation, and hardware modeling:

| File Path | Core Functions / Classes Inspected | Operational Role |
| :--- | :--- | :--- |
| `src/energy/energy_balance.py` | `EnergyBalance`, `PostTradeEnergyBalance`, `compute_energy_balance`, `compute_post_trade_balance`, `compute_energy_balance_series` | Computes local self-consumption, surplus, deficit, post-trade flows, and enforces conservation laws. |
| `src/energy/grid.py` | `TariffScenario`, `GridCostResult`, `GridCostCalculator` | Evaluates grid import expenditures and solar export credits under flat retail tariffs. |
| `src/energy/household.py` | `Household`, `load_households` | Loads household metadata, solar PV capacities (kWp), and postcodes. |
| `src/energy/battery.py` | `BatteryState`, `BatteryStorage` | Standalone residential BESS physical model with power limits, efficiency losses, and SOC bounds. |
| `src/game/utility.py` | `P2PTransaction`, `HouseholdPayoff`, `compute_household_payoff` | Validates bilateral P2P transfers and computes player utility (negative net expenditure). |
| `src/game/payoff_matrix.py` | `GamePayoffMatrix`, `build_two_household_payoff_matrix` | Constructs the $2 \times 2$ normal-form game matrix across all 4 strategy profiles. |
| `src/game/nash.py` | `NashEquilibrium`, `EquilibriumAnalysisResult`, `find_pure_nash_equilibria` | Identifies pure-strategy Nash equilibria (strict and weak) without fabricating missing equilibria. |
| `src/game/best_response.py` | `BestResponseDetail`, `compute_detailed_best_responses` | Evaluates unilateral best responses and dominance relationships for each player. |
| `src/game/game.py` | `GameComparisonResult`, `run_two_household_game` | Executes deterministic single-hour game comparisons between baseline and coordinated clearing. |
| `src/stochastic/monte_carlo.py` | `ValidationResidualPool`, `MonteCarloSimulator`, `ScenarioDistribution`, `build_stochastic_payoff_matrix`, `estimate_expected_payoff_matrix` | Generates 1,000 paired non-negative scenarios per observation and computes expected payoffs. |
| `src/evaluation/forecast_evaluator.py` | `PointMetrics`, `IntervalMetrics`, `ForecastEvaluator` | Comprehensive evaluation runner for LSTM predictions and Monte Carlo prediction intervals. |
| `main.py` / `demo_prototype.py` | `main`, `run_demo`, `format_clean_table` | Interactive terminal demonstration showing deterministic vs. stochastic game clearing. |
| `src/optimization/constraints.py` | *(Empty file, 0 bytes)* | Placeholder for future constrained optimization solvers. |
| `src/optimization/solver.py` | *(Empty file, 0 bytes)* | Placeholder for future mathematical programming solvers. |
| `src/game/player.py` / `strategy.py` | *(Empty files, 0 bytes)* | Placeholder stubs; player logic is handled directly in `payoff_matrix.py` and `utility.py`. |

---

## 2. Current Physical Energy-Flow Assumptions

The existing implementation operates under a defined set of physical assumptions:

1. **Consistent Energy and Time Units:** 
   - All electricity quantities ($D$, $G$, $E_{\text{self}}$, $S$, $B$, $q$, $E_{\text{grid}}$) are measured in physical **kilowatt-hours (kWh)** per discrete **1-hour interval** ($\Delta t = 1.0\text{ h}$).
   - Tariffs and prices are denominated in **AUD per kWh**.
2. **Local Self-Consumption Priority (Dispatch Rule 1):** 
   - Behind-the-meter solar generation strictly serves the household's own contemporaneous electricity demand first:
     $$E_{\text{self}, i} = \min(D_i, G_i)$$
   - Only excess solar above demand can be offered for P2P export or grid feed-in.
   - Only unmet demand above solar can be supplied by P2P import or utility grid import.
3. **Lossless Distribution Model:** 
   - Transmission and distribution losses across the low-voltage peer connection are neglected ($\eta_{\text{line}} = 1.0$).
   - Kirchhoff voltage drops, reactive power ($Q$), line impedance ($R + jX$), and phase imbalances are not modeled.
4. **Infinite Central Grid Swing Bus:** 
   - The central utility grid acts as an unconstrained buffer: it absorbs 100% of residual exportable surplus ($S_i - q$) at the feed-in credit ($0.08$ AUD/kWh) and supplies 100% of residual unmet deficit ($B_j - q$) at the retail import rate ($0.30$ AUD/kWh).
   - No grid-level export curtailment or import brownout limits are imposed.
5. **Strictly Bilateral P2P Market Clearing:** 
   - P2P exchange is modeled as a 2-player normal-form game between Household `H001` (seller) and Household `H002` (buyer). Multi-household multilateral clearing or auction mechanics are not implemented.
6. **Storage Decoupling:** 
   - Battery storage is not active in the trading game pipeline. Households have no temporal state carryover between intervals.

---

## 3. Mathematical Energy-Balance Equations

### 3.1 Pre-Trade Single Household Balance
For household $i$ in time interval $t$, let $D_i \ge 0$ denote demand and $G_i \ge 0$ denote solar generation:

$$\text{Local Self-Consumption:} \quad E_{\text{self}, i} = \min(D_i, G_i)$$

$$\text{Available Surplus:} \quad S_i = \max(0, G_i - D_i)$$

$$\text{Unmet Deficit:} \quad B_i = \max(0, D_i - G_i)$$

**Physical Complementarity Invariant:**
A single household cannot simultaneously experience surplus and deficit in the same interval:
$$S_i \cdot B_i = 0 \quad \iff \quad \min(S_i, B_i) = 0$$

**Exact Pre-Trade Conservation Identities:**
$$D_i = E_{\text{self}, i} + B_i$$
$$G_i = E_{\text{self}, i} + S_i$$
$$D_i - G_i = B_i - S_i$$

### 3.2 Post-Trade Household Balance
Let $q_{ij} \ge 0$ denote the physical energy traded from seller $i$ to buyer $j$.

**Transaction Feasibility Constraints:**
$$0 \le q_{ij} \le S_i \quad \text{and} \quad 0 \le q_{ij} \le B_j \implies q_{ij} \le \min(S_i, B_j)$$

**Post-Trade Grid Flows:**
- Remaining Export to Grid (Seller $i$):
  $$E_{\text{grid\_out}, i} = S_i - q_{ij} = \max(0, S_i - q_{ij})$$
  $$E_{\text{grid\_in}, i} = 0.0$$
- Remaining Import from Grid (Buyer $j$):
  $$E_{\text{grid\_in}, j} = B_j - q_{ij} = \max(0, B_j - q_{ij})$$
  $$E_{\text{grid\_out}, j} = 0.0$$

**Exact Post-Trade Conservation Identities:**
For every participating household $k \in \{i, j\}$:
$$D_k = E_{\text{self}, k} + q_{\text{buy}, k} + E_{\text{grid\_in}, k}$$
$$G_k = E_{\text{self}, k} + q_{\text{sell}, k} + E_{\text{grid\_out}, k}$$
$$\text{Mutual Exclusion:} \quad q_{\text{buy}, k} \cdot q_{\text{sell}, k} = 0 \quad \text{and} \quad E_{\text{grid\_in}, k} \cdot E_{\text{grid\_out}, k} = 0$$

### 3.3 Community-Level Conservation Law
Summing across all households in the microgrid:
$$\sum_k D_k = \sum_k E_{\text{self}, k} + \sum_k q_{\text{buy}, k} + \sum_k E_{\text{grid\_in}, k}$$
$$\sum_k G_k = \sum_k E_{\text{self}, k} + \sum_k q_{\text{sell}, k} + \sum_k E_{\text{grid\_out}, k}$$

Because every P2P transfer is internally balanced between buyer and seller ($\sum_k q_{\text{buy}, k} = \sum_k q_{\text{sell}, k} = q_{ij}$), subtracting the two equations yields:
$$\left(\sum_k D_k - \sum_k G_k\right) \equiv \left(\sum_k E_{\text{grid\_in}, k} - \sum_k E_{\text{grid\_out}, k}\right)$$

**Physical Conclusion:** P2P energy trading rearranges internal allocation and financial cash flows within the community, but **cannot create, destroy, or duplicate energy**. The net physical exchange with the central utility grid is identically preserved.

---

## 4. Seller and Buyer Transaction Constraints

### 4.1 Normal-Form Strategy Space and Physical Clearing
The game models two players with discrete action sets:
- **Seller $i$ ($H001$):** $A_1 = \{\text{OFFER\_P2P}, \text{EXPORT\_GRID}\}$
- **Buyer $j$ ($H002$):** $A_2 = \{\text{ACCEPT\_P2P}, \text{GRID\_IMPORT}\}$

The physical trade quantity $q_{ij}(a_1, a_2)$ executed under each strategy profile is:

| Seller Action ($a_1$) | Buyer Action ($a_2$) | Physical Traded Quantity ($q_{ij}$) | Seller Grid Export ($E_{\text{grid\_out}, 1}$) | Buyer Grid Import ($E_{\text{grid\_in}, 2}$) | Market Outcome |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `OFFER_P2P` | `ACCEPT_P2P` | $\min(S_1, B_2)$ | $S_1 - \min(S_1, B_2)$ | $B_2 - \min(S_1, B_2)$ | **Bilateral P2P Trade Cleared** |
| `OFFER_P2P` | `GRID_IMPORT` | $0.0$ | $S_1$ | $B_2$ | Buyer Defaults to Grid |
| `EXPORT_GRID` | `ACCEPT_P2P` | $0.0$ | $S_1$ | $B_2$ | Seller Defaults to Grid |
| `EXPORT_GRID` | `GRID_IMPORT` | $0.0$ | $S_1$ | $B_2$ | Status-Quo Central Grid |

### 4.2 Financial Conservation
For any cleared transaction with mid-market price $p_{\text{p2p}} = \frac{p_{\text{import}} + p_{\text{export}}}{2} = \frac{0.30 + 0.08}{2} = 0.19\text{ AUD/kWh}$:
$$\text{Buyer P2P Expenditure} = q_{ij} \cdot p_{\text{p2p}} \equiv \text{Seller P2P Revenue} = q_{ij} \cdot p_{\text{p2p}}$$
No intermediary fee, transaction surcharge, or unaccounted capital leakage exists in the model.

### 4.3 Action Selection vs. Physical Trade Distinction (The Zero-Trade Inactive State)
A vital distinction confirmed by this audit is that **selecting `OFFER_P2P` and `ACCEPT_P2P` does NOT imply energy is traded**.
When $S_1 = 0$ (e.g., night-time or overcast demand peak) or $B_2 = 0$ (e.g., buyer solar covers load):
$$q_{ij} = \min(0, B_2) = 0.0 \quad \text{or} \quad q_{ij} = \min(S_1, 0) = 0.0$$
In this state:
- Traded energy is identically $0.0\text{ kWh}$.
- Payoffs across all four matrix cells are identical for each player.
- Both actions are best responses, resulting in **weak Nash equilibrium indifference**.

---

## 5. Scenario-Level Physical Feasibility Results

### 5.1 Comprehensive Audit Across Test Period
An audit script (`feasibility_audit.py`) was executed across all 1,752 held-out test hours for households `H001` and `H002`, evaluating 1,000 Monte Carlo scenarios per hour under **Protocol B** deterministic seeding (`derive_observation_seed`).

| Audit Metric | Ground-Truth Actuals | Point Predictions | Monte Carlo Scenarios (Protocol B) |
| :--- | :---: | :---: | :---: |
| **Total Observations / Realizations Evaluated** | 5,256 obs | 5,256 obs | **1,752,000 realizations** |
| **Invalid / Non-Finite Inputs Detected ($NaN, \pm\infty$)** | 0 | 0 | **0** |
| **Negative Physical Values Detected ($< 0$)** | 0 | 0 | **0** |
| **Complementarity Violations ($S \cdot B > 10^{-6}$)** | 0 | 0 | **0** |
| **Energy Conservation Violations ($|\Delta E| > 10^{-5}$ kWh)** | 0 | 0 | **0** |
| **Maximum Absolute Energy-Balance Residual** | $0.00\text{ kWh}$ | $0.00\text{ kWh}$ | **$4.77 \times 10^{-7}\text{ kWh}$** |
| **Scenarios with Feasible P2P Trade ($q > 0$)** | 157 hours (8.96%) | 149 hours (8.50%) | **152,269 realizations (8.69%)** |
| **Mean Feasible Trade Quantity** | $0.0487\text{ kWh/h}$ | $0.0441\text{ kWh/h}$ | **$0.0242\text{ kWh/h}$** |
| **Maximum Feasible Trade in Single Interval** | $1.4630\text{ kWh}$ | $1.2940\text{ kWh}$ | **$1.6820\text{ kWh}$** |

### 5.2 The Jensen's Inequality Trade Feasibility Distortion
In literature and naive prototypes, dispatchers frequently compute trade feasibility from expected/mean forecasts:
$$q_{\text{mean\_eval}} = \min(\mathbb{E}[S_1], \mathbb{E}[B_2])$$
However, because the minimum function $\min(x, y)$ is concave, **Jensen's Inequality** dictates:
$$\mathbb{E}[\min(S_1, B_2)] \le \min(\mathbb{E}[S_1], \mathbb{E}[B_2])$$

We audited this inequality across all 1,752 test hours:
- **Percentage of Hours where Point/Mean Evaluation Overestimates Feasible Trade:** **$93.21\%$** of hours.
- **Mean Overestimation Magnitude:** **$0.0214\text{ kWh/h}$**.
- **Maximum Overestimation in Single Hour:** **$0.1638\text{ kWh/h}$**.

**Implication:** If a trading system schedules commitments based on mean forecasts or expected energy balances, it will over-commit physical energy in over 93% of trading periods, forcing households to purchase expensive balancing power from the utility grid. Evaluating expected utility scenario-by-scenario ($\frac{1}{N} \sum_s U(a, \omega_s)$), as implemented in `build_stochastic_payoff_matrix`, is strictly necessary to preserve physical feasibility.

---

## 6. Battery Storage Audit and Isolation Verification

### 6.1 BatteryStorage Operational Verification
The residential battery storage class (`src/energy/battery.py`) was audited against its physical governing equations:

1. **Capacity and State-of-Charge Bounds:**
   $$E_{\min} \le E_t \le E_{\max} \quad \iff \quad \text{SOC}_{\min} \cdot C \le E_t \le \text{SOC}_{\max} \cdot C$$
   For default parameters ($C = 5.0\text{ kWh}, \text{SOC} \in [0.10, 0.90]$), usable stored energy is strictly bounded within $[0.50, 4.50]\text{ kWh}$.
2. **Charge and Discharge Power Limits:**
   Charging energy is bounded by $P_{\text{ch},\max} \cdot \Delta t$ ($2.5\text{ kW} \times 1\text{ h} = 2.5\text{ kWh}$). Discharging energy is bounded by $P_{\text{dis},\max} \cdot \Delta t$.
3. **Asymmetric Efficiency Losses:**
   - Charging: Energy added to internal chemical storage is $\Delta E_{\text{stored}} = E_{\text{terminal}} \cdot \eta_{\text{ch}}$ ($\eta_{\text{ch}} = 0.95$). Thermal dissipation is $E_{\text{terminal}} \cdot (1 - \eta_{\text{ch}})$.
   - Discharging: Internal chemical storage depleted is $\Delta E_{\text{stored}} = E_{\text{delivered}} / \eta_{\text{dis}}$ ($\eta_{\text{dis}} = 0.95$).
   - Round-trip efficiency is $\eta_{\text{RT}} = \eta_{\text{ch}} \cdot \eta_{\text{dis}} = 0.95 \times 0.95 = 90.25\%$.
4. **Mutual Exclusion:**
   Simultaneous charging and discharging requests raise `ValueError("Cannot charge and discharge simultaneously in the same step.")`.
5. **Input Validation:**
   Non-finite values ($NaN, \infty$), negative energy quantities, and non-positive durations are strictly rejected with `ValueError`.

### 6.2 Pipeline Integration Status
- **Current Pipeline Coupling:** The battery model is **NOT connected** to `run_two_household_game`, `build_two_household_payoff_matrix`, `build_stochastic_payoff_matrix`, or `demo_prototype.py`.
- **Architectural Rationale:** The current game formulation is a static, single-interval normal-form game. Coupling a battery introduces inter-temporal state dynamics ($E_{t+1} = f(E_t, a_t)$), which requires dynamic programming, Model Predictive Control (MPC), or extensive-form stochastic games. Integrating a battery into a single-period static matrix without dynamic multi-period clearing would introduce arbitrary state heuristics and distort equilibrium pricing.
- **Recommendation:** Keep battery storage decoupled as an isolated component until a multi-period rolling-horizon framework is introduced in future steps.

---

## 7. Violations Discovered and Hardening Fixes Made

During this audit, several latent validation gaps were discovered in the codebase. Although these gaps did not manifest on the clean historical dataset, they created vulnerabilities where corrupted or non-physical data could be silently converted into valid calculations.

All gaps were resolved with surgical, minimally scoped hardening:

| File | Component / Line | Pre-Fix Behavior (Vulnerability) | Post-Fix Behavior (Hardened) | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `src/energy/energy_balance.py` | `compute_energy_balance` | Evaluated `float(d) < -1e-6`. For `NaN`, this was `False`. Then `max(0.0, float('nan'))` returned `0.0`. | Added explicit `np.isfinite(d)` and `np.isfinite(s)` checks raising `ValueError`. | Prevents silent conversion of missing sensor data into zero demand/solar. |
| `src/energy/energy_balance.py` | `EnergyBalance.__post_init__` | Allowed simultaneous surplus and deficit if $(D - G) = (B - S)$ matched (e.g. $D=10, G=10, S=5, B=5$). | Added strict complementarity check: `if self.surplus_kwh > 1e-6 and self.deficit_kwh > 1e-6: raise ValueError`. | Enforces physical impossibility of simultaneous export surplus and unmet deficit. |
| `src/energy/energy_balance.py` | `EnergyBalance.__post_init__` | Did not verify that $D = E_{\text{self}} + B$ and $G = E_{\text{self}} + S$. | Added component conservation checks with $10^{-5}$ absolute tolerance. | Guarantees that local self-consumption exactly matches the physical dispatch rule. |
| `src/energy/energy_balance.py` | `compute_energy_balance_series` | Used `np.maximum(0.0, arr)` directly, silently clipping negative values and propagating `NaN`. | Added explicit checks for `np.all(np.isfinite(...))` and `np.any(arr < -1e-6)` raising `ValueError`. | Protects dataframe pipeline from corrupted time-series batches. |
| `src/energy/energy_balance.py` | *(New addition)* | No data structure existed to validate post-trade physical flows ($E_{\text{self}}, q_{\text{buy}}, q_{\text{sell}}, E_{\text{grid\_in}}, E_{\text{grid\_out}}$). | Added `PostTradeEnergyBalance` dataclass and `compute_post_trade_balance` function. | Formally verifies complete 6-flow conservation and mutual exclusivity after P2P trade. |
| `src/game/utility.py` | `P2PTransaction` | Only checked `traded_energy < 0.0`. Accepted `NaN`, $\infty$, and allowed seller to equal buyer. | Added finiteness checks, and enforced `seller_id != buyer_id` and added `validate_feasibility(...)`. | Prevents phantom transactions and prosumers trading with themselves. |
| `src/game/utility.py` | `compute_household_payoff` | Used `max(0.0, float(deficit_kwh))`, silently converting negative numbers to `0.0`. Allowed simultaneous buying and selling. | Added finiteness/non-negativity checks for all 7 inputs, and enforced mutual exclusion of P2P roles. | A prosumer cannot simultaneously buy and sell energy in the same interval. |
| `src/game/payoff_matrix.py` | `build_two_household_payoff_matrix` | Silently converted negative surplus/deficit or `NaN` into `0.0`. | Added strict finiteness and non-negativity validation for surplus, deficit, tariffs, and P2P price. | Guarantees payoff matrix is only computed for physically valid states. |
| `src/energy/battery.py` | `BatteryStorage.step` | Silently ignored negative available energy or non-finite inputs. | Added checks for finite, non-negative inputs and positive timestep duration. | Enforces strict physical validity on BESS operational simulation. |

---

## 8. Automated Regression Tests Added

To permanently guard against physical violations, 19 focused regression tests were created in `tests/test_physical_feasibility.py`:

```
tests/test_physical_feasibility.py
├── 1. Pre-Trade Energy Balances & Complementarity
│   ├── test_surplus_deficit_generation_exceeds_demand
│   ├── test_surplus_deficit_demand_exceeds_generation
│   ├── test_exact_balance_generation_equals_demand
│   ├── test_zero_demand_and_zero_generation_edge_cases
│   └── test_near_zero_epsilon_values
├── 2. Input Validation & Contradictory States
│   ├── test_non_finite_inputs_rejected_compute_energy_balance
│   ├── test_negative_physical_inputs_rejected
│   ├── test_simultaneous_surplus_and_deficit_rejected_in_dataclass
│   ├── test_inconsistent_self_consumption_rejected_in_dataclass
│   └── test_series_validation_rejects_nan_and_negative
├── 3. P2P Transaction Feasibility & Conservation
│   ├── test_p2p_transaction_feasibility_validation
│   ├── test_p2p_transaction_rejects_self_trading_and_invalid_values
│   ├── test_compute_post_trade_balance_exact_conservation
│   ├── test_post_trade_balance_rejects_infeasible_sales_and_purchases
│   ├── test_post_trade_balance_rejects_simultaneous_buying_and_selling
│   └── test_zero_volume_game_when_surplus_or_deficit_zero
├── 4. Monte Carlo Physical Feasibility under Protocol B
│   ├── test_monte_carlo_scenarios_physical_feasibility_protocol_b
│   └── test_jensen_inequality_expected_trade_overestimation
└── 5. Battery Physical Bounds & Efficiencies
    └── test_battery_physical_bounds_and_efficiencies
```

### Test Suite Execution Summary
- **Target Test File:** `python -m pytest tests/test_physical_feasibility.py`
  - **Result:** **19 passed** in 2.60 seconds.
- **Full Test Suite:** `python -m pytest`
  - **Result:** **81 passed** in 9.97 seconds (0 failures, 0 errors, 0 skipped).

---

## 9. Remaining Limitations and Unresolved Assumptions

While the physical energy balance at the prosumer and bilateral transaction level is now validated, the following structural limitations remain in the project:

1. **Absence of Low-Voltage Grid Network Constraints:**
   - The model assumes a "copper-plate" microgrid bus. In real distribution networks, simultaneous solar export causes **voltage rise** at end-of-line prosumers, potentially exceeding distribution limits (e.g., 253V in Australia).
   - Line impedance, reactive power flow, and distribution transformer thermal limits are unmodeled.
2. **Absence of Network Use-of-System (NUOS) Charges:**
   - Physical P2P transfers traverse the local distributor's wires. In real regulatory regimes, distributors levy a network wheeling charge (e.g., 0.03–0.05 AUD/kWh). The current prototype models zero transaction fee.
3. **Decoupled Battery Storage:**
   - Although the battery physics are validated in `BatteryStorage`, prosumers currently have no ability to store midday solar for evening peak consumption within the game.
4. **Bilateral 2-Player Market Restriction:**
   - The game considers only two households (`H001` and `H002`). In a realistic community microgrid, multiple sellers and buyers would clear simultaneously via double auction or merit-order clearing.
5. **Fixed Price Mid-Market Rule:**
   - The P2P price is fixed at the exogenous mid-market rate ($0.19$ AUD/kWh). It does not dynamically adjust to supply-demand imbalances or marginal willingness to pay.

---

## 10. Verification Commands and Reproducibility

All evaluations and tests documented in this report can be reproduced using the following commands:

### Run the Full Pytest Suite (81 Tests)
```powershell
python -m pytest
```

### Run the Step 4 Physical Feasibility Test Suite (19 Tests)
```powershell
python -m pytest tests/test_physical_feasibility.py -v
```

### Run the Full 1,752-Hour Scenario Physical Feasibility Audit
```powershell
python "C:\Users\Aditya\.gemini\antigravity-ide\brain\2f03c91c-269d-4ec6-a57f-9a025a2cd99a\scratch\feasibility_audit.py"
```

### Run the Terminal Demonstration
```powershell
python demo_prototype.py
```
