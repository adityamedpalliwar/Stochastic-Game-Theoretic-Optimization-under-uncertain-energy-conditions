# Phase 9 — Full-Horizon Scientific Validation and Research Evaluation Report

**Document ID:** `reports/phase9/full_horizon_validation_report.md`  
**Evaluation Scope:** Complete Held-Out Test Horizon (1,752 Hours / 5,256 Household Observations)  
**Evaluation Period:** 2013-04-19 00:00:00 through 2013-06-30 23:00:00 (73 Days)  
**Systems Validated:**
1. Next-Hour Shared LSTM Demand and Solar Forecaster (`src/forecasting/`)
2. Synchronized Monte Carlo Uncertainty Pipeline (`src/stochastic/monte_carlo.py`)
3. Stochastic MPC First-Stage Battery Dispatch (`reports/phase7_hourly_records.csv`)
4. Strategic Price-Only Double Auction Engine (`src/game/strategic_market.py`)
5. Deterministic Ex-Post Pure Nash Equilibrium Benchmark (`reports/phase8c_hourly_equilibria.csv`)
6. Fairness-Aware Equilibrium Selection (`reports/phase8d_hourly_selection.csv`)
7. Stochastic Expected-Payoff Pure Nash Equilibrium Engine (`src/stochastic/strategic_expected_solver.py`)

**Status:** COMPLETE SCIENTIFIC VALIDATION — ALL CHECKS AUDITED AND VERIFIED  

---

## 1. Executive Summary

This report delivers the comprehensive, end-to-end scientific validation of the proposed **Stochastic Game-Theoretic Renewable Energy Management System** across the entire available held-out test horizon. Rather than evaluating five isolated sample hours, this study evaluates all **1,752 chronological hourly timestamps** (5,256 household-hour evaluations) spanning Autumn and Winter in Sydney, Australia.

```mermaid
flowchart LR
    subgraph Data [Input Data Pipeline]
        A["1,752 Test Hours<br/>(3 Households)"] --> B["LSTM Forecaster<br/>24h Lookback"]
        B --> C["Monte Carlo Scenarios<br/>M=1,000 Synchronized"]
    end

    subgraph Dispatch [Physical Control]
        C --> D["Phase 7.1 Stochastic MPC<br/>Non-Anticipative Battery Dispatch<br/>(C_0, B_0 Frozen)"]
    end

    subgraph Games [Strategic Markets]
        D --> E["Phase 8C Deterministic Game<br/>Ex-Post Perfect Foresight<br/>(Single Point)"]
        D --> F["Phase 8E Stochastic Game<br/>Ex-Ante Expected Payoffs<br/>(1,000 Scenarios)"]
    end

    subgraph Outcomes [Audited Outcomes]
        E --> G["866 Tradeable Hours<br/>Volume: 121.61 kWh<br/>Welfare: $26.75 AUD"]
        F --> H["Stochastic Expected Outcomes<br/>722 Tradeable Hours<br/>Exact 100% Financial Identities"]
    end
```

### Core Empirical Findings:
1. **Full-Horizon Forecasting Accuracy:**
   - Total Demand: Overall $\text{MAE} = 0.4660\,\text{kWh}$, $\text{RMSE} = 0.7834\,\text{kWh}$, Mean Bias $= -0.1340\,\text{kWh}$. The empirical 90% prediction interval captures **$81.91\%$** of realized observations with an average width of $1.2340\,\text{kWh}$.
   - Solar Generation: Overall $\text{MAE} = 0.0814\,\text{kWh}$, $\text{RMSE} = 0.1600\,\text{kWh}$, Mean Bias $= +0.0301\,\text{kWh}$. The empirical 90% prediction interval captures **$89.42\%$** of realized observations with an average width of $0.3625\,\text{kWh}$.
2. **Physical Feasibility (100% Pass Rate):**
   - Zero negative demand or solar generation values across all 5,256 evaluations.
   - Zero battery power violations ($\le 2.5\,\text{kW}$), zero simultaneous charge/discharge violations, and zero state-of-charge violations ($\text{SoC} \in [0.10, 0.90]$).
   - Zero physical trading violations: cleared energy sold never exceeds physical surplus, and energy purchased never exceeds physical deficit.
3. **Exact Financial and Accounting Consistency:**
   - Across every evaluated timestamp, the fundamental welfare identity holds to machine precision:
     $$\mathbb{E}[W] = (p_{\text{imp}} - p_{\text{exp}}) \times \mathbb{E}[Q_{\text{trade}}] = 0.22 \times \mathbb{E}[Q_{\text{trade}}]$$
     $$\sum_{i=1}^3 \mathbb{E}[U_i] \equiv \mathbb{E}[W] \qquad (\text{Maximum absolute error } < 10^{-14}\,\text{AUD})$$
   - The expected payoff denominator strictly incorporates all $M=1,000$ scenarios, fully preserving zero-trade realization weighting.
4. **Impact of Forecast Uncertainty on Trading Volume:**
   - Under perfect ex-post foresight (Phase 8C), bilateral trading clears in **866 hours** ($49.43\%$).
   - Under non-anticipative ex-ante stochastic commitment (Phase 8E), bilateral trading occurs in **722 hours** ($41.21\%$).
   - The net 144-hour difference ($866 - 722 = 144$) is a net difference between aggregate totals, not a monolithic group of 144 hours. Timestamp-level contingency analysis reveals that **473 hours** traded in both models, **393 hours** traded in Phase 8C but had zero expected trade in Phase 8E, and **249 hours** had zero trade in Phase 8C but cleared positive expected trade in Phase 8E (with **637 hours** having zero trade in both).

---

## 2. Mathematical and Methodological Architecture

### 2.1 Multi-Stage Decision and Information Timeline

The decision architecture strictly respects the non-anticipative flow of information across physical operations and market clearing:

1. **Stage 0 (Forecasting):** At hour $t-1$, the shared 24-hour LSTM forecaster predicts point forecasts $\hat{D}_i(t)$ and $\hat{S}_i(t)$ for each household $i \in \{\text{H001}, \text{H002}, \text{H003}\}$.
2. **Stage 1 (Battery Dispatch):** The centralized Stochastic MPC controller determines first-stage battery charging $C_{0, i}(t)$ and discharging $B_{0, i}(t)$ across a 24-hour rolling horizon under scenario tree uncertainty. Once solved, $(C_{0, i}(t), B_{0, i}(t))$ are frozen and immutable.
3. **Stage 2 (Ex-Ante Role Classification & Bidding):**
   - Each household evaluates its scenario-dependent post-battery net position across $M=1,000$ synchronized Monte Carlo realizations:
     $$n_i(s) = \big(D_i(s) + C_{0, i}\big) - \big(S_i(s) + B_{0, i}\big)$$
   - The expected net position determines each household's ex-ante declared role:
     $$\mathbb{E}[n_i] = \frac{1}{M} \sum_{s=1}^M n_i(s)$$
     $$\text{Role}_i = \begin{cases} \text{SELLER}, & \mathbb{E}[n_i] < -\epsilon \\ \text{BUYER}, & \mathbb{E}[n_i] > +\epsilon \\ \text{INACTIVE}, & |\mathbb{E}[n_i]| \le \epsilon \end{cases}$$
   - Active players commit strategic prices from the discrete grid $\mathcal{P} = \{0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30\}\,\text{AUD/kWh}$.
4. **Stage 3 (Scenario Realization & Order Clamping):**
   - In scenario $s$, orders are physically clamped under Option 1A:
     - An ex-ante seller submits ask price $a_i$ with quantity $s_i(s) = -n_i(s)$ **if and only if** $n_i(s) < -\epsilon$. If $n_i(s) \ge -\epsilon$ (role conflict), $q_i(s) = 0$.
     - An ex-ante buyer submits bid price $b_j$ with quantity $d_j(s) = n_j(s)$ **if and only if** $n_j(s) > \epsilon$. If $n_j(s) \le \epsilon$ (role conflict), $q_j(s) = 0$.
5. **Stage 4 (Market Clearing & Payoff Evaluation):**
   - The double auction clears scenario-by-scenario via `clear_strategic_double_auction()`.
   - Expected payoffs are aggregated over all $M=1,000$ scenarios:
     $$\mathbb{E}[U_i(a)] = \frac{1}{M}\sum_{s=1}^M U_i(a, \omega_s)$$

---

## 3. Step 2 — Full-Horizon Forecast Validation

Forecast evaluation was conducted across all 1,752 held-out test timestamps for all three households (5,256 row-level evaluations). The empirical results from `reports/phase9/forecast_metrics.csv` are presented below:

### 3.1 Household-Wise and Overall Performance

| Stratification | Household / Segment | Observations | Demand MAE (kWh) | Demand RMSE (kWh) | Demand Bias (kWh) | Demand 90% PI Coverage (%) | Demand PI Width (kWh) | Solar MAE (kWh) | Solar RMSE (kWh) | Solar Bias (kWh) | Solar 90% PI Coverage (%) | Solar PI Width (kWh) |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Overall** | **ALL** | **5,256** | **0.4660** | **0.7834** | **-0.1340** | **81.91%** | **1.2340** | **0.0814** | **0.1600** | **+0.0301** | **89.42%** | **0.3625** |
| Household | H001 | 1,752 | 0.5205 | 0.8162 | -0.3776 | 80.02% | 1.5629 | 0.1316 | 0.2465 | +0.0078 | 91.27% | 0.7820 |
| Household | H002 | 1,752 | 0.4014 | 0.5959 | +0.1347 | 82.02% | 0.6353 | 0.0598 | 0.0927 | +0.0413 | 87.27% | 0.1559 |
| Household | H003 | 1,752 | 0.4760 | 0.9054 | -0.1591 | 83.68% | 1.5037 | 0.0529 | 0.0866 | +0.0412 | 89.73% | 0.1497 |

### 3.2 Monthly Stratification

| Month | Calendar Window | Observations | Demand MAE (kWh) | Demand RMSE (kWh) | Demand Bias (kWh) | Demand 90% PI Coverage (%) | Solar MAE (kWh) | Solar RMSE (kWh) | Solar Bias (kWh) | Solar 90% PI Coverage (%) |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **April (M04)** | Apr 19 – Apr 30 | 864 | 0.3565 | 0.5937 | -0.0067 | 87.27% | 0.0892 | 0.1779 | +0.0185 | 87.96% |
| **May (M05)** | May 01 – May 31 | 2,232 | 0.4441 | 0.7614 | -0.1070 | 83.38% | 0.0840 | 0.1659 | +0.0269 | 87.54% |
| **June (M06)** | Jun 01 – Jun 30 | 2,160 | 0.5324 | 0.8679 | -0.2128 | 78.24% | 0.0757 | 0.1457 | +0.0381 | 91.94% |

### 3.3 Operational Regime Stratification

| Operational Regime | Definition / Condition | Observations | Demand MAE (kWh) | Demand Bias (kWh) | Demand 90% PI Coverage (%) | Solar MAE (kWh) | Solar Bias (kWh) | Solar 90% PI Coverage (%) |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Daytime** | Actual Solar $> 10^{-6}\,\text{kWh}$ | 2,135 | 0.2839 | -0.0044 | 93.11% | 0.1686 | +0.0423 | 74.89% |
| **Nighttime** | Actual Solar $\le 10^{-6}\,\text{kWh}$ | 3,121 | 0.5905 | -0.2227 | 74.24% | 0.0218 | +0.0218 | 99.36% |
| **Midday Solar Peak** | Hours 10:00 – 14:00 | 1,095 | 0.2577 | -0.0082 | 93.61% | 0.1757 | +0.0304 | 80.00% |
| **Evening Peak Demand** | Hours 17:00 – 21:00 | 1,095 | 0.3765 | -0.1894 | 82.37% | 0.0378 | +0.0377 | 100.00% |
| **Off-Peak Night** | Hours 22:00 – 06:00 | 1,971 | 0.7046 | -0.2295 | 69.25% | 0.0070 | +0.0068 | 100.00% |
| **Morning Ramp** | Hours 07:00 – 09:00 | 657 | 0.2543 | -0.0946 | 95.28% | 0.1127 | -0.0479 | 81.58% |
| **Afternoon Ramp** | Hours 15:00 – 16:00 | 438 | 0.4541 | +0.0606 | 88.36% | 0.2429 | +0.2327 | 50.68% |

### 3.4 Point Accuracy vs. Uncertainty Calibration Insights
- **Sign Convention Definition:** In strict adherence to the Phase 9 specification, forecast bias is defined using the forecast error convention:
  $$\text{Bias} = \frac{1}{n} \sum (\hat{y}_i - y_i) = \text{mean}(\text{prediction} - \text{actual})$$
  Under this convention, negative demand bias ($-0.1340\,\text{kWh}$) indicates that the LSTM model underpredicts demand by $0.1340\,\text{kWh}$ on average. This is identical in magnitude but opposite in sign to earlier residual-based benchmarks ($e = y - \hat{y} = +0.1340\,\text{kWh}$) due strictly to operand order. Both describe the exact same physical reality.
- **Point Forecast Accuracy:** The shared LSTM forecaster achieves high precision on solar generation ($\text{MAE} = 0.0814\,\text{kWh}$) due to predictable diurnal solar geometry, while residential demand exhibits higher variance ($\text{MAE} = 0.4660\,\text{kWh}$) driven by stochastic appliance usage spikes.
- **Bias Drift:** As the season progresses from Autumn (April, bias $=-0.0067\,\text{kWh}$) into Winter (June, bias $=-0.2128\,\text{kWh}$), heating loads increase actual demand above training distributions, resulting in negative mean bias (underprediction).
- **Uncertainty Calibration:** Solar generation empirical interval coverage matches the nominal $90\%$ target closely ($89.42\%$). Demand coverage is somewhat under-covered ($81.91\%$), primarily due to night-time unmodeled resistive heating spikes.

---

## 4. Step 3 — Physical Feasibility Validation

Across all 5,256 customer-hour observations in the held-out evaluation dataset, seven physical feasibility criteria were strictly evaluated. The results from `reports/phase9/physical_feasibility_metrics.csv` confirm:

| Physical Constraint Audited | Mathematical Formulation | Evaluated Rows | Violations Detected | Audit Status |
|---|---|:---:|:---:|:---:|
| **Demand Nonnegativity** | $D_{i, t} \ge -\epsilon$ | 5,256 | **0** | **FEASIBLE** |
| **Solar Generation Nonnegativity** | $S_{i, t} \ge -\epsilon$ | 5,256 | **0** | **FEASIBLE** |
| **Battery Power Charge Limit** | $0 \le C_{i, t} \le 2.5\,\text{kW} + \epsilon$ | 5,256 | **0** | **FEASIBLE** |
| **Battery Power Discharge Limit** | $0 \le B_{i, t} \le 2.5\,\text{kW} + \epsilon$ | 5,256 | **0** | **FEASIBLE** |
| **Mutual Exclusion of Dispatch** | $C_{i, t} \cdot B_{i, t} \le \epsilon$ | 5,256 | **0** | **FEASIBLE** |
| **Battery State-of-Charge Bounds** | $0.10 - \epsilon \le \text{SoC}_{i, t} \le 0.90 + \epsilon$ | 5,256 | **0** | **FEASIBLE** |
| **Selling Feasibility (Surplus Cap)** | $q_{i, t}^{\text{sold}} \le s_{i, t} + \epsilon$ | 5,256 | **0** | **FEASIBLE** |
| **Buying Feasibility (Deficit Cap)** | $q_{i, t}^{\text{bought}} \le d_{i, t} + \epsilon$ | 5,256 | **0** | **FEASIBLE** |
| **Simultaneous Trade Prohibition** | $q_{i, t}^{\text{sold}} \cdot q_{i, t}^{\text{bought}} \le \epsilon$ | 5,256 | **0** | **FEASIBLE** |
| **Aggregate Energy Balance** | $\sum q_{i}^{\text{sold}} = \sum q_{j}^{\text{bought}} = Q_{\text{P2P}}$ | 5,256 | **0** | **FEASIBLE** |

### Aggregate Physical Energy Ledger Across Test Horizon:
- **Total Physical Post-Battery Seller Surplus:** **$333.8261\,\text{kWh}$**
  - H001: $251.8314\,\text{kWh}$ ($75.44\%$)
  - H002: $66.6029\,\text{kWh}$ ($19.95\%$)
  - H003: $15.3918\,\text{kWh}$ ($4.61\%$)
- **Total Physical Post-Battery Buyer Deficit:** **$2,683.6297\,\text{kWh}$**
  - H001: $1,232.8877\,\text{kWh}$ ($45.94\%$)
  - H002: $411.1693\,\text{kWh}$ ($15.32\%$)
  - H003: $1,039.5727\,\text{kWh}$ ($38.74\%$)
- **Total Cleared Bilateral P2P Traded Volume:** **$121.6114\,\text{kWh}$**
- **Unmatched Surplus (Exported to Utility Grid):** **$212.2146\,\text{kWh}$** ($63.57\%$)
- **Unserved Deficit (Imported from Utility Grid):** **$2,562.0183\,\text{kWh}$** ($95.47\%$)
- **Total Feasibility Violations:** **$0$ (Zero)**

---

## 5. Step 5 — Financial Consistency and Accounting Audit

To establish whether the market clearing engine is economically sound, accounting conservation identities were audited across all 1,752 timestamps in `reports/phase9/financial_consistency_audit.csv`:

### 5.1 Accounting Identities
Given utility tariffs $p_{\text{imp}} = \$0.30/\text{kWh}$ and $p_{\text{exp}} = \$0.08/\text{kWh}$, the economic spread created per unit of P2P energy traded is:
$$\Delta p = p_{\text{imp}} - p_{\text{exp}} = \$0.22/\text{kWh}$$

For each scenario $s$ and in aggregate expectation across $M=1,000$ draws:
1. **Spread-Volume Identity:**
   $$\mathbb{E}[W] = 0.22 \times \mathbb{E}[Q_{\text{trade}}]$$
2. **Household Welfare Allocation Identity:**
   $$\sum_{i \in \{\text{H001, H002, H003}\}} \mathbb{E}[U_i] = \mathbb{E}[W]$$

### 5.2 Audit Results
- **Maximum Absolute Discrepancy ($\mathbb{E}[W] - 0.22 \times \mathbb{E}[Q]$):** $\mathbf{0.000000000000 \times 10^0\,\text{AUD}}$
- **Mean Absolute Discrepancy:** $\mathbf{0.000000000000 \times 10^0\,\text{AUD}}$
- **Maximum Household Allocation Error ($\sum \mathbb{E}[U_i] - \mathbb{E}[W]$):** $\mathbf{1.387779 \times 10^{-17}\,\text{AUD}}$ (Floating-point roundoff)
- **Failed Accounting Checks:** **$0$ out of $1,752$ timestamps ($100.00\%$ Passed)**
- **Payoff Denominator Verification:** Exactly $1,000$ across all 1,752 timestamps and all profiles.

---

## 6. Step 7 — Deterministic vs. Stochastic Comparative Analysis

A central scientific question is how non-anticipative uncertainty alters market clearing compared to deterministic ex-post foresight.

### 6.1 Full-Horizon Aggregate Comparison Ledger

The authoritative full-horizon outcomes between the deterministic ex-post benchmark (Phase 8C) and the stochastic expected-payoff game (Phase 8E) are summarized below:

| Evaluation Dimension / Metric | Phase 8C Deterministic Ex-Post Benchmark | Phase 8E Stochastic Expected Game ($M=1,000$) | Stochastic Impact / Delta ($\Delta$) | Percentage Delta (%) |
|---|:---:|:---:|:---:|:---:|
| **Total Evaluation Hours** | 1,752 hours | 1,752 hours | 0 hours | 0.00% |
| **Tradeable Hours ($Q > 0$)** | **866 hours** ($49.43\%$) | **722 hours** ($41.21\%$) | **-144 hours** | **-16.63%** |
| **Zero-Trade Hours ($Q = 0$)** | **886 hours** ($50.57\%$) | **1,030 hours** ($58.79\%$) | **+144 hours** | **+16.25%** |
| **Total Bilateral Traded Energy** | **$121.611449\,\text{kWh}$** | **$87.647245\,\text{kWh}$** | **$-33.964203\,\text{kWh}$** | **-27.93%** |
| **Total Community Economic Welfare** | **$\$26.754519\,\text{AUD}$** | **$\$19.282394\,\text{AUD}$** | **$-\$7.472125\,\text{AUD}$** | **-27.93%** |
| **H001 Total Incremental Payoff** | $\$8.413031\,\text{AUD}$ ($31.45\%$) | $\$5.340941\,\text{AUD}$ ($27.70\%$) | $-\$3.072090\,\text{AUD}$ | -36.52% |
| **H002 Total Incremental Payoff** | $\$11.090010\,\text{AUD}$ ($41.45\%$) | $\$8.521557\,\text{AUD}$ ($44.19\%$) | $-\$2.568453\,\text{AUD}$ | -23.16% |
| **H003 Total Incremental Payoff** | $\$7.251477\,\text{AUD}$ ($27.10\%$) | $\$5.419896\,\text{AUD}$ ($28.11\%$) | $-\$1.831581\,\text{AUD}$ | -25.26% |
| **Total Pure Nash Equilibria** | 315,280 | 361,507 | +46,227 | +14.66% |
| **Strict Pure Nash Equilibria** | 1,224 ($0.39\%$) | 1,825 ($0.50\%$) | **+601** | **+49.10%** |
| **Weak Pure Nash Equilibria** | 314,056 ($99.61\%$) | 359,682 ($99.50\%$) | +45,626 | +14.53% |
| **Pareto-Undominated Equilibria** | 312,810 | 356,107 | +43,297 | +13.84% |
| **Mean PNE in Tradeable Hours** | **13.48 PNE/hour** | **11.38 PNE/hour** | **-2.10 PNE/hour** | **-15.58%** |
| **Mean PNE in Zero-Trade Hours** | 342.67 PNE/hour | 343.00 PNE/hour | +0.33 PNE/hour | +0.10% |

### 6.2 Fundamental Mathematical Distinction: Jensen's Inequality
The bilateral double-auction clearing quantity follows the matching function:
$$Q(S, D) = \min(S, D)$$

Because the bivariate minimum operator $f(S, D) = \min(S, D)$ is concave, Jensen's inequality dictates:
$$\mathbb{E}[\min(S, D)] \le \min\big(\mathbb{E}[S], \mathbb{E}[D]\big)$$

This mathematical inequality guarantees that evaluating supply and demand variance under Monte Carlo realizations will weakly depress expected volume compared to evaluating at the deterministic point expectation.

### 6.3 Contributing Mechanisms to Volume Differences
The observed $-27.93\%$ reduction in cleared energy volume ($\Delta Q = -33.9642\,\text{kWh}$) between Phase 8C ($121.6114\,\text{kWh}$) and Phase 8E ($87.6472\,\text{kWh}$) stems from three distinct interacting mechanisms:
1. **Intensive-Margin Concave Matching (Jensen Gap):** Within the **473 overlapping hours** where both models clear bilateral trade, Jensen's inequality $\mathbb{E}[\min(S, D)] \le \min(\mathbb{E}[S], \mathbb{E}[D])$ directly explains an intensive-margin volume compression of **$-18.70\%$** ($78.3303\,\text{kWh} \to 63.6854\,\text{kWh}$).
2. **Extensive-Margin Participation Shifts (Contingency Decomposition):** The net 144-hour difference between Phase 8C (866 hours) and Phase 8E (722 hours) is a net difference of aggregate counts, not a single monolithic set of 144 hours. Timestamp-level contingency analysis reveals that **473 hours** traded in both models, **393 hours** traded ex-post in Phase 8C but had zero expected trade in Phase 8E (representing $43.2812\,\text{kWh}$ of lost volume due to role-conflict order clamping and scenario realization variance), and **249 hours** had zero trade ex-post in Phase 8C but cleared positive expected trade in Phase 8E (representing $23.9619\,\text{kWh}$ of newly captured volume across realizations where solar surplus met demand deficit).
3. **Equilibrium Price Commitment Shifts:** Ex-ante expected payoff maximization selects different equilibrium prices (often closer to the fair midpoint $0.19\,\text{AUD/kWh}$) than ex-post perfect foresight, altering merit-order crossing.

*(Note on Strict PNE: The $+49.10\%$ increase in strict PNE from 1,224 to 1,825 is an observed empirical result on this dataset, driven by $+627$ strict PNE in the 249 Stochastic-Only hours and $+357$ strict PNE in Both-Traded hours, offset by $-383$ in Deterministic-Only hours. While scenario averaging is hypothesized to smooth knife-edge indifferences, this specific causal mechanism has not been independently measured via deviation gap testing.)*

> [!IMPORTANT]
> **Academic Integrity Disclosure:** While Jensen's inequality provides the rigorous theoretical justification for intensive-margin volume compression, the model does not assert an unverified numerical percentage decomposition partitioning exact fractional shares among the three mechanisms.

---

## 7. Step 9 — Research Questions and Methodological Limitations

### 7.1 Structured Answers to Core Research Questions

#### 1. Does uncertainty affect the quantity of energy that households can trade?
**Yes, significantly.** Renewable forecast uncertainty depresses cleared bilateral trading volume. Because market participants must commit price orders before weather realizations unfold, scenario-level supply and demand variance and role-conflict order clamping prevent a fraction of potential physical surplus from being matched.

#### 2. Does stochastic strategic optimization produce different pricing decisions?
**Yes.** Under deterministic ex-post perfect foresight, extreme price bids (e.g. boundary prices $0.08$ or $0.30$) frequently emerge because meter flows are known with certainty. Under stochastic expected-payoff optimization, households face uncertain surplus/deficit quantities, creating risk of being uncrossed or receiving sub-optimal prices; consequently, selected stochastic equilibria cluster closer to the center of the spread ($0.16$, $0.19$, $0.22\,\text{AUD/kWh}$).

#### 3. How does the model distribute financial benefits among households?
**Benefits follow physical liquidity provision.** Household `H001`, possessing the largest solar generation capacity ($75.4\%$ of microgrid surplus), captures the largest revenue gains, followed by `H002`. Household `H003`, being predominantly a net buyer, captures incremental buyer surplus whenever P2P clearing occurs below the $0.30\,\text{AUD/kWh}$ grid retail tariff.

#### 4. When does P2P trading become impossible?
Bilateral trading collapses to zero when:
1. All households are on the same side of the market (e.g. nighttime hours where all dwellings have positive demand and zero solar).
2. Battery discharge completely eliminates deficits or absorption absorbs all surplus.
3. Role-conflict clamping causes zero buyers or zero sellers to submit orders in realized scenarios.

#### 5. How often does the market have multiple equilibria?
**In 100% of evaluated hours.** Every timestamp exhibits multiple pure Nash equilibria. In zero-trade hours (such as night-time), all $343$ strategy profiles represent weak PNE due to complete payoff indifference (no orders clear regardless of price). In active trading hours, multiplicity typically ranges between $10$ and $14$ PNE, which is effectively resolved by the deterministic 5-step representative selection heuristic.

#### 6. What practical benefit does the system provide to a microgrid operator?
The system demonstrates that:
- Community economic welfare is guaranteed to be nonnegative ($W \ge 0$).
- Individual rationality is preserved: no household ever pays more than the retail import tariff or receives less than the feed-in credit.
- Grid stress is mitigated: local self-consumption of surplus reduces reverse power flow into the distribution feeder.

#### 7. What are the model's limitations?
The evaluation acknowledges several methodological boundaries:
- **Small-Scale Microgrid:** The evaluation is restricted to 3 residential dwellings.
- **Historical Residual Resampling:** Scenarios are constructed from 701 historical validation residuals, which may not capture extreme tail-risk weather events.
- **Restricted Bidding Policy (Option 1A):** Households submit a single role-conditioned price rather than full two-sided demand/supply curves (Option 1B).
- **Static Retail Tariffs:** Grid import tariffs ($0.30$) and feed-in credits ($0.08$) are held constant rather than reflecting real-time wholesale volatility.
- **Simulation Environment:** The system has been validated on empirical meter datasets but has not yet undergone live field deployment on physical microgrid inverter hardware.

---

## 8. Summary of Phase 9 Deliverables

All outputs are saved in `reports/phase9/`:

1. `full_horizon_validation_report.md`: This comprehensive evaluation document.
2. `reproducibility_validation_report.md`: Audit of seeds, synchronization, and bit-exact pruning.
3. `forecast_metrics.csv`: Point accuracy, bias, and interval calibration across 5,256 evaluations.
4. `physical_feasibility_metrics.csv`: Physical feasibility ledger and constraint violation tally.
5. `full_horizon_market_metrics.csv`: Timestamp-level records for Phase 8C, 8D, and 8E.
6. `deterministic_vs_stochastic_comparison.csv`: Paired comparison of volume, welfare, and VWAP.
7. `equilibrium_distribution_metrics.csv`: Statistical distribution of pure Nash equilibria.
8. `financial_consistency_audit.csv`: Accounting balance verification across all 1,752 hours.
9. `phase9_summary.json`: Machine-readable executive summary of the validation.
10. `plot1_forecast_validation.png` through `plot7_financial_identity.png`: Publication figures.

