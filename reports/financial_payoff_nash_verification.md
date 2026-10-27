# Financial Payoff and Nash Equilibrium Verification Report (Step 4.2 & Step 4.3)

**Project:** Stochastic Game-Theoretic Renewable Energy Management under Uncertain Energy Conditions  
**Audit Phase:** Step 4.2 & Step 4.3 — Financial Utility, Equilibrium Multiplicity, and Dependence Verification  
**Evaluation Period:** 1,752 chronological hours (Ausgrid Solar Home Electricity Dataset, held-out test split)  
**Households Evaluated:** H001 (Prosumer Seller), H002 (Consumer Buyer), H003 (Evaluation Benchmark)  
**Status:** **MATHEMATICALLY & EMPIRICALLY VERIFIED — 100% PASS (94/94 Regression Tests Passing)**

---

## 1. Executive Summary

This report delivers the comprehensive mathematical and empirical verification of the financial utility formulations, payoff matrices, best-response determinations, and pure-strategy Nash equilibrium classifications across the entire project pipeline.

### Core Verified Findings:
1. **Financial Accounting Integrity:** All revenue and expenditure signs are consistent throughout the codebase. Grid import cost is non-negative, grid export credit is non-negative, and peer-to-peer (P2P) cash transfers satisfy zero-sum conservation:
   $$\text{Buyer P2P Expenditure} \equiv \text{Seller P2P Revenue} = q \cdot p_{\text{p2p}}$$
2. **Cancellation of P2P Cash Flows & Metric Clarification:** When summing household utilities, the P2P transaction payment cancels identically to zero ($+q \cdot p_{\text{p2p}} - q \cdot p_{\text{p2p}} = 0$). The resulting sum equals the **prosumers' net grid cash flow** ($S_1^{\text{net}} \cdot p_{\text{export}} - B_2^{\text{net}} \cdot p_{\text{import}}$). To avoid misleading terminology, this metric is formally designated as `combined_household_utility` rather than total social welfare, as retail grid operator generation costs and utility margins are not modeled.
3. **Equilibrium Multiplicity & Absence of Uniqueness:** Pure-strategy Nash equilibrium is **never unique (0 hours)** in this 2×2 game formulation. Because a prosumer refusing trade blocks P2P clearing and forces identical status-quo grid flows regardless of the other prosumer's action, the uncoordinated baseline $(\text{EXPORT\_GRID}, \text{GRID\_IMPORT})$ is a **weak Nash equilibrium in 100% of hours (1,752 hours)**.
4. **Cooperative Equilibrium Pareto Dominance:** In **1,748 hours (99.77%)**, $(\text{OFFER\_P2P}, \text{ACCEPT\_P2P})$ is a **strict pure-strategy Nash equilibrium** that **strictly Pareto-dominates** the grid baseline. In the remaining **4 hours (0.23%)**, all 1,000 scenarios have zero feasible trade ($q=0$), making all 4 strategy profiles weak Nash equilibria. In **0 hours** is the cooperative profile defected from or non-equilibrium.
5. **Exact Scenario-Level Expectation:** Across all 1,752 hours ($1,752,000$ joint scenarios), expected payoffs are calculated as the arithmetic mean of scenario-level payoffs ($\frac{1}{N}\sum_s U_i(a, \omega_s)$) on identical scenario index alignments, strictly respecting Jensen's inequality.
6. **Uncertainty Dependence Characterization:** Residual sampling in `ValidationResidualPool` preserves intra-household demand–solar pairing ($e_d$ and $e_s$ drawn jointly from identical historical hours), but samples H001 and H002 independently across households under Protocol B. This is formally documented as an explicit modeling assumption.
7. **Regression Test Suite:** 12 dedicated regression tests were implemented in [`tests/test_financial_payoffs.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/tests/test_financial_payoffs.py), expanding the test suite to 94 tests (100% passing).

---

## 2. Files Inspected and Audited

The audit verified the following repository modules line-by-line:

| File Path | Audited Components | Verification Result |
|---|---|---|
| [`src/game/utility.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/utility.py) | `compute_household_payoff`, `P2PTransaction`, `HouseholdPayoff` | Revenue/cost signs consistent; physical bound guards prevent $q > S_1$ or $q > B_2$. |
| [`src/game/payoff_matrix.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/payoff_matrix.py) | `build_two_household_payoff_matrix`, `GamePayoffMatrix` | Normal-form matrix maps all 4 strategy profiles accurately. |
| [`src/game/best_response.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/best_response.py) | `compute_detailed_best_responses`, `BestResponseDetail` | Strictly dominant vs weakly dominant mappings evaluated correctly. |
| [`src/game/nash.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/nash.py) | `find_pure_nash_equilibria`, `EquilibriumAnalysisResult` | Identifies all pure Nash equilibria; distinguishes strict from weak equilibria. |
| [`src/game/game.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/game.py) | `run_two_household_game` | Individual and community savings relative to centralized baseline verified. |
| [`src/stochastic/monte_carlo.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/stochastic/monte_carlo.py) | `build_stochastic_payoff_matrix`, `ValidationResidualPool`, `MonteCarloSimulator` | Scenario-by-scenario evaluation verified; `Expected_Combined_Household_Utility_AUD` implemented. |
| [`demo_prototype.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/demo_prototype.py) | Pipeline demonstrator | Metrics updated to `Combined Utility` / `Comb U`. Verified end-to-end execution. |
| [`tests/test_financial_payoffs.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/tests/test_financial_payoffs.py) | Step 4.2 & 4.3 regression tests | 12 dedicated regression tests covering all audit requirements. |

---

## 3. Mathematical Foundations and Sign Conventions

### 3.1 Market Parameters and Pre-Trade Balances
- Grid import tariff: $p_{\text{import}} = 0.30\text{ AUD/kWh}$
- Grid export credit (feed-in tariff): $p_{\text{export}} = 0.08\text{ AUD/kWh}$
- Mid-market P2P tariff: $p_{\text{p2p}} = \frac{p_{\text{import}} + p_{\text{export}}}{2} = 0.19\text{ AUD/kWh}$
- Pre-trade surplus: $S_i = \max(0, G_i - D_i) \ge 0$
- Pre-trade deficit: $B_i = \max(0, D_i - G_i) \ge 0$
- Traded energy flow:
  $$q(a_1, a_2) = \begin{cases} \min(S_1, B_2), & \text{if } (a_1, a_2) = (\text{OFFER\_P2P}, \text{ACCEPT\_P2P}) \\ 0.0, & \text{otherwise} \end{cases}$$

### 3.2 Individual Household Payoffs and Net Utilities
- **Seller (H001):**
  $$R_{\text{grid\_out}} = (S_1 - q) \cdot p_{\text{export}} \ge 0, \quad R_{\text{p2p}} = q \cdot p_{\text{p2p}} \ge 0$$
  $$C_{\text{net}, 1} = -(R_{\text{grid\_out}} + R_{\text{p2p}}) \le 0\text{ AUD} \implies U_1 = -C_{\text{net}, 1} = R_{\text{grid\_out}} + R_{\text{p2p}} \ge 0\text{ AUD}$$
- **Buyer (H002):**
  $$C_{\text{grid\_in}} = (B_2 - q) \cdot p_{\text{import}} \ge 0, \quad C_{\text{p2p}} = q \cdot p_{\text{p2p}} \ge 0$$
  $$C_{\text{net}, 2} = C_{\text{grid\_in}} + C_{\text{p2p}} \ge 0\text{ AUD} \implies U_2 = -C_{\text{net}, 2} = -(C_{\text{grid\_in}} + C_{\text{p2p}}) \le 0\text{ AUD}$$

### 3.3 Financial Metrics Clarification: Combined Household Utility
Summing the utilities of the two microgrid prosumers yields:
$$\begin{aligned}
U_1 + U_2 &= \left[(S_1 - q) \cdot p_{\text{export}} + q \cdot p_{\text{p2p}}\right] - \left[(B_2 - q) \cdot p_{\text{import}} + q \cdot p_{\text{p2p}}\right] \\
&= (S_1 - q) \cdot p_{\text{export}} - (B_2 - q) \cdot p_{\text{import}} + \underbrace{(q \cdot p_{\text{p2p}} - q \cdot p_{\text{p2p}})}_{= 0.0\text{ AUD}} \\
&= S_1^{\text{net}} \cdot p_{\text{export}} - B_2^{\text{net}} \cdot p_{\text{import}}
\end{aligned}$$

**Key Accounting Insights:**
1. The internal P2P transaction cancels out identically; P2P trade is a purely internal zero-sum cash transfer.
2. The metric $U_1 + U_2$ represents the **net cash flow between the two households and the central distribution grid** (export credits received minus import bills paid).
3. **Distinction from Total Social Welfare:** This sum cannot be labeled "Social Welfare" because it excludes the financial surplus of the central grid operator. When prosumers trade locally, the grid operator loses retail spread margin ($p_{\text{import}} - p_{\text{export}} = 0.22\text{ AUD/kWh}$). The reported metric is therefore strictly termed `combined_household_utility`.

---

## 4. Deterministic 4-Profile Hand-Checked Benchmark

Evaluated for $S_1 = 2.0\text{ kWh}$, $B_2 = 1.5\text{ kWh}$, $p_{\text{import}} = 0.30$, $p_{\text{export}} = 0.08$, $p_{\text{p2p}} = 0.19\text{ AUD/kWh}$:

```
                      Buyer (H002)
                    ACCEPT_P2P          GRID_IMPORT
Seller  OFFER_P2P   (+0.3250, -0.2850)    (+0.1600, -0.4500)
(H001)  EXPORT_GRID (+0.1600, -0.4500)    (+0.1600, -0.4500)
```

### Complete Strategy Profiles Comparison:

| Profile | Traded $q$ | Seller Net Flow | Buyer Net Flow | Seller $U_1$ | Buyer $U_2$ | Combined Utility | Discrepancy vs Code |
|---|---|---|---|---|---|---|---|
| **OFFER_P2P / ACCEPT_P2P** | $1.50\text{ kWh}$ | Export $0.50\text{ kWh}$ | Import $0.00\text{ kWh}$ | $+0.3250\text{ AUD}$ | $-0.2850\text{ AUD}$ | $+0.0400\text{ AUD}$ | $0.0000$ |
| **OFFER_P2P / GRID_IMPORT** | $0.00\text{ kWh}$ | Export $2.00\text{ kWh}$ | Import $1.50\text{ kWh}$ | $+0.1600\text{ AUD}$ | $-0.4500\text{ AUD}$ | $-0.2900\text{ AUD}$ | $0.0000$ |
| **EXPORT_GRID / ACCEPT_P2P**| $0.00\text{ kWh}$ | Export $2.00\text{ kWh}$ | Import $1.50\text{ kWh}$ | $+0.1600\text{ AUD}$ | $-0.4500\text{ AUD}$ | $-0.2900\text{ AUD}$ | $0.0000$ |
| **EXPORT_GRID / GRID_IMPORT**| $0.00\text{ kWh}$ | Export $2.00\text{ kWh}$ | Import $1.50\text{ kWh}$ | $+0.1600\text{ AUD}$ | $-0.4500\text{ AUD}$ | $-0.2900\text{ AUD}$ | $0.0000$ |

### Unilateral Deviations & Best Responses:
- $\text{BR}_1(\text{ACCEPT\_P2P}) = \{\text{OFFER\_P2P}\}$ (strict, $\Delta = +0.1650\text{ AUD}$)
- $\text{BR}_1(\text{GRID\_IMPORT}) = \{\text{OFFER\_P2P}, \text{EXPORT\_GRID}\}$ (weak indifference, $\Delta = 0.0000\text{ AUD}$)
- $\text{BR}_2(\text{OFFER\_P2P}) = \{\text{ACCEPT\_P2P}\}$ (strict, $\Delta = +0.1650\text{ AUD}$)
- $\text{BR}_2(\text{EXPORT\_GRID}) = \{\text{ACCEPT\_P2P}, \text{GRID\_IMPORT}\}$ (weak indifference, $\Delta = 0.0000\text{ AUD}$)

---

## 5. Comprehensive 1,752-Hour Equilibrium Audit & Reconciliation

A complete simulation across all 1,752 chronological test hours was executed to audit equilibrium multiplicity, uniqueness, and profile classifications.

```
================================================================================
HOURLY EQUILIBRIUM AUDIT REPORT ACROSS 1,752 TEST HOURS
================================================================================
Total Test Hours Evaluated                      : 1,752 hours (100.00%)

--- 1. MUTUALLY EXCLUSIVE EQUILIBRIUM MULTIPLICITY CATEGORIES ---
Hours with exactly 1 Pure Nash Equilibrium (Unique):     0 hours (  0.00%)
Hours with exactly 2 Pure Nash Equilibria          : 1,748 hours ( 99.77%)
Hours with exactly 3 Pure Nash Equilibria          :     0 hours (  0.00%)
Hours with exactly 4 Pure Nash Equilibria          :     4 hours (  0.23%)
Hours with other equilibrium count                 :     0 hours (  0.00%)
Reconciliation Check: 0 + 1748 + 0 + 4 + 0 = 1,752 (Exact 100.00% Reconciliation)

--- 2. INDIVIDUAL STRATEGY PROFILE EQUILIBRIUM CLASSIFICATIONS (OVERLAPPING) ---
Cooperative Profile (OFFER_P2P, ACCEPT_P2P):
  ├─ Is an Equilibrium                             : 1,752 hours (100.00%)
  ├─ Is a STRICT Equilibrium                       : 1,748 hours ( 99.77%)
  ├─ Is a WEAK Equilibrium                         :     4 hours (  0.23%)
  └─ Is NOT an Equilibrium                         :     0 hours (  0.00%)

Grid Baseline Profile (EXPORT_GRID, GRID_IMPORT):
  ├─ Is an Equilibrium                             : 1,752 hours (100.00%)
  ├─ Is a STRICT Equilibrium                       :     0 hours (  0.00%)
  └─ Is a WEAK Equilibrium                         : 1,752 hours (100.00%)

Off-Diagonal Profiles (OFFER/GRID & EXPORT/ACCEPT):
  ├─ Hours where either off-diagonal is an Eq      :     4 hours (  0.23%)
  ├─ Hours where both off-diagonals are Eq         :     4 hours (  0.23%)
  ├─ Hours where (OFFER_P2P, GRID_IMPORT) is Eq    :     4 hours (  0.23%)
  └─ Hours where (EXPORT_GRID, ACCEPT_P2P) is Eq   :     4 hours (  0.23%)
================================================================================
```

### Key Mathematical Takeaways on Equilibrium Structure:
1. **Uniqueness:** Pure-strategy Nash equilibrium is **never unique (0.00%)** in this game.
2. **Persistence of Coordination Failure:** The uncoordinated grid default $(\text{EXPORT\_GRID}, \text{GRID\_IMPORT})$ is a **weak pure Nash equilibrium in 100% of hours (1,752 hours)**. This occurs because if the buyer chooses `GRID_IMPORT`, the seller's P2P offer cannot clear, leaving the seller with export tariff $p_{\text{export}}$ regardless of whether they play `OFFER` or `EXPORT`. Conversely, if the seller plays `EXPORT_GRID`, the buyer receives import tariff $p_{\text{import}}$ regardless of whether they play `ACCEPT` or `GRID`.
3. **Pareto Dominance:** Although multiple equilibria exist, in all 1,748 positive-trade hours, $(\text{OFFER\_P2P}, \text{ACCEPT\_P2P})$ strictly Pareto-dominates the coordination-failure equilibrium ($\mathbb{E}[U_i(\text{coop})] > \mathbb{E}[U_i(\text{base})]$ for both prosumers).

---

## 6. Independent Verification of Stochastic Expected Payoffs

At the representative demo hour (`2013-06-08 10:00:00`), an independent benchmark script was executed to verify that `build_stochastic_payoff_matrix` calculates expectations scenario-by-scenario on identical scenario indices:

### Hand-Check vs Code Output Comparison:

| Strategy Profile | Metric | Independent Scenario Mean | Code Output | Discrepancy |
|---|---|---|---|---|
| **OFFER_P2P / ACCEPT_P2P** | Traded Energy ($q$) | $0.023682\text{ kWh}$ | $0.023682\text{ kWh}$ | $0.00\times 10^0$ |
| | Seller Expected Utility $\mathbb{E}[U_1]$ | $+0.049827\text{ AUD}$ | $+0.049827\text{ AUD}$ | $1.86\times 10^{-9}$ |
| | Buyer Expected Utility $\mathbb{E}[U_2]$ | $-0.007965\text{ AUD}$ | $-0.007965\text{ AUD}$ | $8.23\times 10^{-10}$ |
| **OFFER_P2P / GRID_IMPORT** | Traded Energy ($q$) | $0.000000\text{ kWh}$ | $0.000000\text{ kWh}$ | $0.00\times 10^0$ |
| | Seller Expected Utility $\mathbb{E}[U_1]$ | $+0.047222\text{ AUD}$ | $+0.047222\text{ AUD}$ | $1.86\times 10^{-9}$ |
| | Buyer Expected Utility $\mathbb{E}[U_2]$ | $-0.010570\text{ AUD}$ | $-0.010570\text{ AUD}$ | $8.23\times 10^{-10}$ |
| **EXPORT_GRID / ACCEPT_P2P**| Traded Energy ($q$) | $0.000000\text{ kWh}$ | $0.000000\text{ kWh}$ | $0.00\times 10^0$ |
| | Seller Expected Utility $\mathbb{E}[U_1]$ | $+0.047222\text{ AUD}$ | $+0.047222\text{ AUD}$ | $1.86\times 10^{-9}$ |
| | Buyer Expected Utility $\mathbb{E}[U_2]$ | $-0.010570\text{ AUD}$ | $-0.010570\text{ AUD}$ | $8.23\times 10^{-10}$ |
| **EXPORT_GRID / GRID_IMPORT**| Traded Energy ($q$) | $0.000000\text{ kWh}$ | $0.000000\text{ kWh}$ | $0.00\times 10^0$ |
| | Seller Expected Utility $\mathbb{E}[U_1]$ | $+0.047222\text{ AUD}$ | $+0.047222\text{ AUD}$ | $1.86\times 10^{-9}$ |
| | Buyer Expected Utility $\mathbb{E}[U_2]$ | $-0.010570\text{ AUD}$ | $-0.010570\text{ AUD}$ | $8.23\times 10^{-10}$ |

### Contrast with Mean-Based Approximations:
- **Scenario Feasible Trade:** $\mathbb{E}[\min(S_1, B_2)] = 0.023682\text{ kWh}$
- **Naive Surplus/Deficit Means:** $\min(\mathbb{E}[S_1], \mathbb{E}[B_2]) = 0.035233\text{ kWh}$ (overestimates trade by $+48.8\%$)
- **Point Forecast Raw Means:** $S_{\text{mean}} = 0.6963\text{ kWh}, B_{\text{mean}} = 0.0000\text{ kWh} \implies q(\text{means}) = 0.0000\text{ kWh}$ (completely misses all 149 tradeable scenarios)

---

## 7. Uncertainty Dependence Characterization

An audit of [`src/stochastic/monte_carlo.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/stochastic/monte_carlo.py) (`ValidationResidualPool.sample_residuals` and `generate_scenarios`) revealed the exact uncertainty dependency structure:

1. **Intra-Household Pairing (Demand vs Solar):**
   - **PRESERVED.** When `sample_residuals` is invoked with `paired=True` (default), resampled row indices select simultaneously occurring demand and solar residuals:
     $$\left(e_{d, i}^{(s)}, e_{s, i}^{(s)}\right) = \mathbf{e}_i\left(t_{\text{val}}^{(s)}\right)$$
   - This accurately preserves the physical negative or positive correlation between cloud cover (solar drop) and temperature/lighting (demand change) within that household.
2. **Inter-Household Dependence (H001 vs H002):**
   - **NOT PRESERVED.** Under Protocol B, observation seeds are derived independently per household:
     $$\text{seed}_{H001} = \text{CRC32}(H001, t, 42) \neq \text{seed}_{H002} = \text{CRC32}(H002, t, 42)$$
   - Each household's 1,000 Monte Carlo scenarios draw random historical hours from its own validation residual pool independently. Contemporaneous weather shocks affecting both prosumers simultaneously (such as a localized thunderstorm hitting both houses at the exact same hour) are not explicitly coupled via a joint copula.
   - **Status:** Documented as an explicit modeling limitation. The existing sampling code was preserved without introducing unauthorized modifications.

---

## 8. Test Execution and Command Results

### 8.1 Unit & Regression Test Suite (`pytest`)
- Command: `python -m pytest`
- Exit Code: `0`
- Result: **94 passed in 10.76s**
```
============================= test session starts =============================
platform win32 -- Python 3.13.6, pytest-8.3.4, pluggy-1.5.0
rootdir: D:\5thSem\GT project\Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions
collected 94 items

tests\test_battery.py .....                                              [  5%]
tests\test_energy.py .....                                               [ 10%]
tests\test_financial_payoffs.py ............                             [ 23%]
tests\test_forecast_evaluation.py .............                          [ 37%]
tests\test_game.py .........                                             [ 46%]
tests\test_monte_carlo.py .......................                        [ 71%]
tests\test_physical_feasibility.py ....................                  [ 92%]
tests\test_preprocessing.py ...                                          [ 95%]
tests\test_utility.py ....                                               [100%]

============================= 94 passed in 10.76s =============================
```

### 8.2 Prototype Demonstrator (`demo_prototype.py`)
- Command: `python demo_prototype.py`
- Exit Code: `0`
- Result: Cleanly executed with updated `Combined Utility` / `Comb U` column labels and callout notes explaining P2P payment cancellation.

### 8.3 Physical Feasibility Audit Script (`audit_physical_feasibility.py`)
- Command: `python audit_physical_feasibility.py`
- Exit Code: `0`
- Result: 1,752,000 joint scenarios verified; 0 conservation residual violations; all transaction guards verified.

---

## 9. Assumptions, Limitations, and Recommendations

### Modeling Assumptions & Current Limitations:
1. **Independent Inter-Household Resampling:** As documented in Section 7, cross-household residual dependence is uncoupled under Protocol B.
2. **Fixed Split Clearing:** Mid-market pricing ($0.19\text{ AUD/kWh}$) allocates trade surplus $50/50$ regardless of volume asymmetry.
3. **Flat Retail Tariffs:** TOU pricing, demand charges, and wholesale spot exposure are not currently parameterized.
4. **Standalone Battery:** The validated physical battery model operates independently and is not yet dispatched strategically within the game-theoretic payoff matrix.

### Conclusion:
All financial equations, cash flows, game payoff matrices, best responses, and equilibrium classifications across all 1,752 test hours are mathematically sound, internally consistent, and fully verified.

### Next Step Recommendation:
Proceed to **Step 5: Strategic Battery Storage Co-Optimization and Multi-Household Clearing**, incorporating battery state-of-charge constraints and dispatch actions into the game-theoretic payoff formulation.
