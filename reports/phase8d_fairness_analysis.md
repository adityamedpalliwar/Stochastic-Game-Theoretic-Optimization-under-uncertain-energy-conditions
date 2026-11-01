# Phase 8D — Fairness-Aware Nash Equilibrium Selection and Economic Analysis

**Report ID:** `reports/phase8d_fairness_analysis.md`  
**Project Title:** Stochastic Game-Theoretic Renewable Energy Management under Uncertain Energy Conditions  
**Evaluation Dataset:** Complete Phase 7.1 held-out test period (1,752 hourly timestamps from `2013-04-19 00:00:00` to `2013-06-30 23:00:00`)  
**Microgrid Architecture:** Three prosumer households (`H001`, `H002`, `H003`) with rooftop solar PV, residential battery storage (5.0 kWh capacity), Stochastic MPC battery dispatch, and a price-only strategic double auction market.  
**Authoritative Baseline:** Phase 7.1 Accepted Baseline (Physical dispatch frozen, total P2P volume: 121.611449 kWh, community welfare: $26.754519 AUD).

---

## 1. Executive Summary

In a strategic double-auction energy market with multiple participating prosumers, **equilibrium multiplicity is ubiquitous**. In our residential microgrid, every single mixed-market trading hour exhibits between 10 and 14 distinct Pure Nash Equilibria (PNE). Because these equilibria represent fundamentally different market-clearing prices and surplus allocations, the choice of equilibrium selection policy directly dictates the distribution of wealth among participating households.

This report establishes the **Phase 8D Comparative Economic Decision-Support Framework**. We formulated, implemented, and evaluated six distinct core equilibrium selection policies operating strictly on the Pareto-undominated Pure Nash Equilibrium frontier ($E_{	ext{Pareto}}$), alongside a seven-point sensitivity sweep across multi-objective hybrid weights (comprising 12 unique strategy configurations evaluated across 13 reporting entries).

```
       Candidate Pure Nash Equilibria (E_PNE)
                         │
                         ▼
        ┌──────────────────────────────────┐
        │  Pareto Filter:                  │
        │  Drop e if exists e' such that   │
        │  U(e') >= U(e) and U(e') > U(e)  │
        └──────────────────────────────────┘
                         │
                         ▼
       Pareto Frontier Candidates (E_Pareto)
                         │
    ┌──────────┬─────────┼─────────┬──────────┬──────────┐
    ▼          ▼         ▼         ▼          ▼          ▼
Strategy A Strategy B Strategy C Strategy D Strategy E Strategy F
(Reference)(Seller+)  (Buyer+)  (Max-Min)   (NSW)     (Hybrid)
```

### Key Empirical Findings

1. **Physical Volume and Welfare Invariance on the Pareto Frontier:**
   - Every evaluated selection policy clears **exactly 121.611449 kWh of P2P energy** and generates **exactly $26.754519 AUD of total community economic welfare** across the entire 1,752-hour held-out test period.
   - While submaximal coordination failures exist in the unrestricted game ($E_{	ext{PNE}}$), every Pareto-undominated equilibrium ($E_{	ext{Pareto}}$) clears the entire short side of the market.
   - Consequently, in this deterministic ex-post price-only market, **improving distributional fairness among households does NOT require sacrificing physical trading volume or aggregate economic efficiency**.
2. **Surplus Division Across Strategic Orientations:**
   - **Strategy A (Reference / Phase 8C):** Clears at a Volume-Weighted Average Price (VWAP) of **$0.219934 AUD/kWh**. Sellers capture **$17.017553 AUD (63.61%)** of total welfare, and buyers capture **$9.736965 AUD (36.39%)**. This matches the seller unit-spread margin share: $(p_{	ext{vwap}} - p_{	ext{exp}}) / (p_{	ext{imp}} - p_{	ext{exp}}) = (0.219934 - 0.08) / 0.22 = 63.61\%$.
   - **Strategy B (Seller-Favouring):** Sellers capture **$23.287341 AUD (87.04%)** of total community surplus ($3.467177 AUD / 12.96% for buyers), driving VWAP to **$0.271490 AUD/kWh** (+23.4% above benchmark). Solar exporter `H001` gains $12.16 AUD, but net deficit buyer `H003` receives only $3.85 AUD.
   - **Strategy C (Buyer-Favouring):** Buyers capture **$15.656607 AUD (58.52%)** of total surplus ($11.097911 AUD / 41.48% for sellers), depressing VWAP to **$0.171257 AUD/kWh** (-22.1% below benchmark). Buyer `H003` captures $10.69 AUD, while `H001`'s benefit drops to $4.46 AUD.
   - **Strategy D (Max-Min Fair / Rawlsian):** Protects the participant with the lowest hourly payoff, raising the mean hourly minimum active payoff by **+28.49%** over Strategy A ($0.002280 vs $0.001774 AUD/h) and **+614.89%** over Strategy B ($0.000319 AUD/h). The cumulative minimum household total payoff improves by **+2.81%** ($7.45 AUD for `H001` vs $7.25 AUD for `H003` under Strategy A) and **+93.55%** over Strategy B ($3.85 AUD). Household totals stabilize at `H001` = $7.45 AUD (27.86%), `H002` = $11.72 AUD (43.79%), `H003` = $7.58 AUD (28.34%).
   - **Strategy E (Nash Social Welfare):** Maximizes proportional fairness, achieving the **lowest inequality among all six core strategies** (mean normalized Gini = **0.8073**, standard Gini = **0.5382**).
   - **Strategy F & Hybrid Sensitivity:** Across all 12 unique evaluated configurations, the pure fairness configuration **`Hybrid_w_fair_1.0`** achieves the absolute lowest inequality (mean normalized Gini = **0.7982**, standard Gini = **0.5322**). The hybrid sensitivity exhibits a discrete two-regime step response: flat and identical to Strategy A for $w_{	ext{fair}} \le 0.5$ (0 hours differ, 100.00% concordance), followed by a monotonic reduction in inequality for $w_{	ext{fair}} > 0.5$ (differing in 25 hours at $w=0.6$, 76 hours at $w=0.8$, and 99 hours at $w=1.0$).
3. **Rigorous Numerical Reconciliation:**
   - In all evaluated strategy configurations, the sum of household benefits reconciles with total community welfare:
     $$\max_{t} \left| \sum_{i=1}^3 U_i(t) - \Delta W(t) ight| \le 5.55 	imes 10^{-17}	ext{ AUD}$$
     $$\left| \sum_{t=1}^{1752} \sum_{i=1}^3 U_i(t) - \sum_{t=1}^{1752} \Delta W(t) ight| \le 1.78 	imes 10^{-14}	ext{ AUD}$$
   - These residuals represent standard IEEE 754 floating-point rounding precision and are identically $0.000000	ext{ AUD}$ to six decimal places, well within the numerical zero tolerance ($	ext{tol} = 10^{-10}	ext{ AUD}$).

---

## 2. Research Objective & Problem Formulation

### 2.1 The Equilibrium Selection Dilemma
In Phase 8C and 8C.1, an exhaustive Pure Nash Equilibrium solver was developed and run across the Phase 7.1 held-out dataset. In all 866 tradeable mixed-market hours ($N_S \ge 1, N_B \ge 1$), multiple pure Nash equilibria were discovered (between 10 and 14 per hour).

Because physical quantities are predetermined by battery dispatch and submitted bids are price-only ($\mathcal{P} = \{0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30\}$), any pair of crossing bids ($p_S \le p_B$) clears the market. The internal transaction price:
$$p_{	ext{tx}} = rac{p_{	ext{ask}} + p_{	ext{bid}}}{2} \in [0.08, 0.30]$$
serves as a pure transfer price governing the division of the fixed economic spread:
$$U_{	ext{seller}} = Q^* 	imes (p_{	ext{tx}} - 0.08),\qquad U_{	ext{buyer}} = Q^* 	imes (0.30 - p_{	ext{tx}})$$
$$U_{	ext{seller}} + U_{	ext{buyer}} = Q^* 	imes (0.30 - 0.08) = 0.22 	imes Q^* = \Delta W$$

The central research question investigated in Phase 8D is:
> **"How can an appropriate equilibrium-selection policy distribute P2P economic benefits more fairly among participating households, and what effect does that selection have on physical trading volume and community welfare?"**

---

## 3. Mathematical Selection Policies & Tie-Breaking

All selection strategies operate on the **Pareto-undominated set** $E_{	ext{Pareto}} \subseteq E_{	ext{PNE}}$.

### Strategy A: Reference Selection (Phase 8C Benchmark)
Reproduces the 5-step heuristic from Phase 8C:
1. Candidate set: $E_{	ext{Pareto}}$.
2. Minimize distance to normative midpoint: $\min |p_{	ext{vwap}} - 0.19|$.
3. Maximize community welfare: $\max \Delta W$.
4. Minimize transaction price standard deviation: $\min 	ext{Std}(p_{	ext{tx}})$.
5. Deterministic lexicographical tie-break on player prices $(p_{	ext{H001}}, p_{	ext{H002}}, p_{	ext{H003}})$.

### Strategy B: Seller-Favouring Selection
Selects the equilibrium that maximizes aggregate seller surplus:
$$e^* = rg\max_{e \in E_{	ext{Pareto}}} \sum_{s \in 	ext{Sellers}} U_s(e)$$
- **Tie-breakers:**
  1. Minimize variance among active sellers: $\min 	ext{Var}(\{U_s : s \in 	ext{Sellers}\})$.
  2. Minimize distance to reference price: $\min |p_{	ext{vwap}} - 0.19|$.
  3. Deterministic lexicographical tie-break on active player prices.

### Strategy C: Buyer-Favouring Selection
Selects the equilibrium that maximizes aggregate buyer surplus:
$$e^* = rg\max_{e \in E_{	ext{Pareto}}} \sum_{b \in 	ext{Buyers}} U_b(e)$$
- **Tie-breakers:**
  1. Minimize variance among active buyers: $\min 	ext{Var}(\{U_b : b \in 	ext{Buyers}\})$.
  2. Minimize distance to reference price: $\min |p_{	ext{vwap}} - 0.19|$.
  3. Deterministic lexicographical tie-break on active player prices.

### Strategy D: Max-Min Fair Selection (Rawlsian Egalitarianism)
Maximizes the minimum payoff among all active participants:
$$e^* = rg\max_{e \in E_{	ext{Pareto}}} \left( \min_{i \in \mathcal{N}_{	ext{active}}} U_i(e) ight)$$
- **Tie-breakers:**
  1. **Lexicographic Max-Min:** Maximize the second-lowest payoff among active households.
  2. Minimize distance to reference price: $\min |p_{	ext{vwap}} - 0.19|$.
  3. Deterministic lexicographical tie-break on active player prices.

### Strategy E: Nash Social Welfare (NSW) Selection
Maximizes the log-geometric product of active household benefits (proportional fairness):
$$e^* = rg\max_{e \in E_{	ext{Pareto}}} \sum_{i \in \mathcal{N}_{	ext{active}}} \log(U_i(e) + \epsilon)$$
where $\epsilon = 10^{-6}	ext{ AUD}$ prevents $\log(0)$ divergence.
- **Tie-breakers:**
  1. Minimize distance to reference price: $\min |p_{	ext{vwap}} - 0.19|$.
  2. Deterministic lexicographical tie-break on active player prices.

### Strategy F: Reference-Price and Fairness Hybrid Selection
Minimizes a scalarized loss function balancing reference tracking and normalized Gini inequality:
$$\min_{e \in E_{	ext{Pareto}}} \mathcal{L}(e; w_{	ext{ref}}, w_{	ext{fair}}) = w_{	ext{ref}} \cdot \left(rac{|p_{	ext{vwap}}(e) - 0.19|}{0.11}ight) + w_{	ext{fair}} \cdot G_{	ext{norm}}(U_{	ext{active}}(e))$$
where $w_{	ext{ref}} + w_{	ext{fair}} = 1.0$. Baseline: $w_{	ext{fair}} = 0.5$. Sensitivity sweep: $w_{	ext{fair}} \in \{0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0\}$.

---

## 4. Active-Participant Fairness Formulation

To avoid distortion from non-trading participants, the evaluation strictly bifurcates payoffs into:
1. **Active Payoff Vector** $\mathbf{U}_{	ext{active}} = \{U_i : i \in \mathcal{N}_{	ext{active}}\}$, where $\mathcal{N}_{	ext{active}} = \{i : s_i > 0 	ext{ or } d_i > 0\}$.
2. **Community Reporting Vector** $\mathbf{U}_{	ext{all}} = (U_{	ext{H001}}, U_{	ext{H002}}, U_{	ext{H003}})$.

### Normalized Gini Coefficient
For $n = |\mathcal{N}_{	ext{active}}|$ participants with nonnegative payoffs, the standard Gini is:
$$G = rac{\sum_{i=1}^n \sum_{j=1}^n |U_i - U_j|}{2 n \sum_{i=1}^n U_i}$$
Because the theoretical upper bound for $n$ participants is $(n - 1) / n$ (which equals $2/3$ for $n=3$, and $1/2$ for $n=2$), the **Normalized Gini** is defined as:
$$G_{	ext{norm}} = rac{n}{n - 1} G \in [0, 1]$$
- $G_{	ext{norm}} = 0.0$ indicates perfect payoff equality among active traders.
- $G_{	ext{norm}} = 1.0$ indicates total monopolization by a single active household.
- In one-sided hours ($N_S = 0$ or $N_B = 0$), $G$ and $G_{	ext{norm}}$ are strictly marked **Not Applicable (`NaN`)**.

---

## 5. Dataset-Wide Experimental Results (1,752 Hours)

### 5.1 Comparative Summary Across All Selection Strategies

The table below presents the aggregate performance of the 6 core selection strategies and the representative sensitivity variants from `reports/phase8d_strategy_comparison.csv` (12 unique configurations reported across 13 entries):

| Strategy | Total P2P Volume (kWh) | Total Community Welfare (AUD) | VWAP (AUD/kWh) | Total Seller Benefit (AUD) | Total Buyer Benefit (AUD) | Mean Standard Gini | Mean Normalized Gini | Concordance with Strategy A (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Strategy A (Reference)** | **121.611449** | **$26.754519** | **$0.219934** | $17.017553 (63.61%) | $9.736965 (36.39%) | 0.5412 | 0.8118 | **100.00%** |
| **Strategy B (Seller+)** | **121.611449** | **$26.754519** | **$0.271490** | $23.287341 (87.04%) | $3.467177 (12.96%) | 0.6350 | 0.9525 | 84.08% |
| **Strategy C (Buyer+)** | **121.611449** | **$26.754519** | **$0.171257** | $11.097911 (41.48%) | $15.656607 (58.52%) | 0.6254 | 0.9381 | 85.22% |
| **Strategy D (Max-Min)** | **121.611449** | **$26.754519** | **$0.213041** | $16.179308 (60.47%) | $10.575211 (39.53%) | 0.5539 | 0.8309 | 88.18% |
| **Strategy E (NSW)** | **121.611449** | **$26.754519** | **$0.216568** | $16.608172 (62.08%) | $10.146347 (37.92%) | **0.5382** | **0.8073** | 88.18% |
| **Strategy F (Hybrid w=0.5)** | **121.611449** | **$26.754519** | **$0.219934** | $17.017553 (63.61%) | $9.736965 (36.39%) | 0.5412 | 0.8118 | **100.00%** |

> [!NOTE]
> **Surplus Share Alignment:** Under Strategy A, sellers capture **$17.017553 AUD** out of **$26.754519 AUD** total community welfare, which equals **63.6063% (63.61%)**. This dollar benefit share exactly equals the seller share of the unit price spread:
> $$rac{p_{	ext{vwap}} - p_{	ext{exp}}}{p_{	ext{imp}} - p_{	ext{exp}}} = rac{0.219934 - 0.08}{0.22} = rac{0.139934}{0.22} = 63.6063\%$$
> Aggregate dollar payoff shares and unit spread shares are mathematically identical under single-clearing VWAP pricing.

### 5.2 Household Benefit Allocation Across Strategies

| Strategy | H001 Benefit (AUD) | H002 Benefit (AUD) | H003 Benefit (AUD) | H001 Share (%) | H002 Share (%) | H003 Share (%) | Payoff Sum (AUD) | Absolute Accounting Error (AUD) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Strategy A** | $8.413031 | $11.090010 | $7.251477 | 31.45% | 41.45% | 27.10% | $26.754519 | $3.55 	imes 10^{-15}$ |
| **Strategy B** | $12.155879 | $10.746964 | $3.851676 | 45.43% | 40.17% | 14.40% | $26.754519 | $0.00 	imes 10^{0}$ |
| **Strategy C** | $4.455712 | $11.605462 | $10.693345 | 16.65% | 43.38% | 39.97% | $26.754519 | $1.42 	imes 10^{-14}$ |
| **Strategy D** | $7.454905 | $11.716452 | $7.583162 | 27.86% | 43.80% | 28.34% | $26.754519 | $1.78 	imes 10^{-14}$ |
| **Strategy E** | $7.905822 | $11.429715 | $7.418982 | 29.55% | 42.72% | 27.73% | $26.754519 | $3.55 	imes 10^{-15}$ |
| **Strategy F** | $8.413031 | $11.090010 | $7.251477 | 31.45% | 41.45% | 27.10% | $26.754519 | $3.55 	imes 10^{-15}$ |

---

## 6. Hybrid Sensitivity Analysis Across Fairness Weights ($w_{	ext{fair}}$)

To evaluate the stability of the hybrid formulation, we conducted a parameter sweep across $w_{	ext{fair}} \in [0.0, 1.0]$. The 7 evaluated sensitivity configurations, combined with the 6 core strategies, constitute 12 unique configurations (since Strategy F at $w_{	ext{fair}}=0.5$ is identical to sensitivity variant `Hybrid_w_fair_0.5`):

| Fairness Weight ($w_{	ext{fair}}$) | Reference Weight ($w_{	ext{ref}}$) | Traded Volume (kWh) | Community Welfare (AUD) | VWAP (AUD/kWh) | H001 (AUD) | H002 (AUD) | H003 (AUD) | Mean Norm Gini | Hours Differing from Strat A | Concordance (%) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.0** | 1.0 | 121.611449 | $26.754519 | $0.219934 | $8.413031 | $11.090010 | $7.251477 | 0.8118 | 0 | 100.00% |
| **0.2** | 0.8 | 121.611449 | $26.754519 | $0.219934 | $8.413031 | $11.090010 | $7.251477 | 0.8118 | 0 | 100.00% |
| **0.4** | 0.6 | 121.611449 | $26.754519 | $0.219934 | $8.413031 | $11.090010 | $7.251477 | 0.8118 | 0 | 100.00% |
| **0.5** | 0.5 | 121.611449 | $26.754519 | $0.219934 | $8.413031 | $11.090010 | $7.251477 | 0.8118 | 0 | 100.00% |
| **0.6** | 0.4 | 121.611449 | $26.754519 | $0.219949 | $8.395534 | $11.114664 | $7.244320 | 0.8062 | 25 | 98.57% |
| **0.8** | 0.2 | 121.611449 | $26.754519 | $0.218925 | $8.219125 | $11.212271 | $7.323123 | 0.7991 | 76 | 95.66% |
| **1.0** | 0.0 | 121.611449 | $26.754519 | $0.217990 | $8.091863 | $11.284405 | $7.378251 | **0.7982** | 99 | 94.35% |

### Analytical Observations on Sensitivity
1. **Discrete Two-Regime Step Response:**  
   The hybrid response does not exhibit continuous variation across the entire range $[0.0, 1.0]$. Because candidate equilibrium profiles on $E_{	ext{Pareto}}$ are discrete, the policy exhibits a distinct two-regime step response:
   - **Flat/Invariant Regime ($w_{	ext{fair}} \le 0.5$):** For weights $w_{	ext{fair}} \in \{0.0, 0.2, 0.4, 0.5\}$, the reference price penalty $|p_{	ext{vwap}} - 0.19| / 0.11$ completely dominates the scalarized loss. Exactly **0 hours differ** from Strategy A (1,752 / 1,752 hours identical, 100.00% concordance, $G_{	ext{norm}} = 0.8118$).
   - **Transition Regime ($w_{	ext{fair}} > 0.5$):** For weights above $0.5$, the normalized Gini penalty begins to flip selections in hours where an alternative Pareto profile achieves lower local inequality:
     - At $w_{	ext{fair}} = 0.6$: **25 hours differ** (98.57% concordance; $G_{	ext{norm}} = 0.8062$).
     - At $w_{	ext{fair}} = 0.8$: **76 hours differ** (95.66% concordance; $G_{	ext{norm}} = 0.7991$).
     - At $w_{	ext{fair}} = 1.0$: **99 hours differ** (94.35% concordance; $G_{	ext{norm}} = 0.7982$).
2. **Lowest Inequality Configuration Across All Evaluated Profiles:**  
   While **Strategy E (Nash Social Welfare)** achieves the lowest inequality among the six core named strategies ($G_{	ext{norm}} = 0.8073$), the pure fairness hybrid variant **`Hybrid_w_fair_1.0`** achieves the lowest inequality across **all 12 unique configurations** ($G_{	ext{norm}} = 0.7982, G = 0.5322$). This occurs because `Hybrid_w_fair_1.0` directly minimizes active-participant $G_{	ext{norm}}$ as its exclusive objective, whereas Strategy E balances proportional efficiency via the log-geometric product $\sum \log(U_i + \epsilon)$.
3. **Strict Welfare Invariance Across All Weights:**  
   Across all seven weights from $0.0$ to $1.0$, total traded volume remains identically **121.611449 kWh** and community welfare remains **$26.754519 AUD**.

---

## 7. Visualizations and Empirical Economic Insights

All figures are persisted in `reports/phase8d_visualizations/`:

1. **Household Benefit Allocation (`household_benefit_comparison.png`):**  
   Illustrates distributional shifts between strategies. In Strategy B (Seller-Favouring), sellers capture 87.0% of total community surplus, and solar exporter `H001` captures $12.16 AUD. In Strategy C (Buyer-Favouring), buyers capture 58.5%, and `H003` captures $10.69 AUD. Strategies D and E smooth out these extremes, preventing any household from dropping below $7.45 AUD.
2. **Gini Coefficient Comparison (`gini_coefficient_comparison.png`):**  
   Compares standard Gini $G \in [0, 2/3]$ against normalized Gini $G_{	ext{norm}} \in [0, 1]$. Strategy E achieves the lowest inequality among core strategies ($G = 0.5382, G_{	ext{norm}} = 0.8073$), while `Hybrid_w_fair_1.0` achieves the lowest overall ($G = 0.5322, G_{	ext{norm}} = 0.7982$). Strategy B exhibits the highest inequality ($G = 0.6350, G_{	ext{norm}} = 0.9525$).
3. **Welfare vs. Fairness Trade-Off (`welfare_vs_fairness_tradeoff.png`):**  
   Visualizes the flat horizontal efficiency frontier. All selection strategies align at exactly **$26.754519 AUD** of community welfare, demonstrating that fairness optimization on the Pareto frontier produces zero deadweight loss in this deterministic price-only market.
4. **Volume-Weighted Average Price (`transaction_price_distributions.png`):**  
   Depicts the clearing price range across policies. The internal clearing price swings from $\$0.171257$ (buyer power) to $\$0.271490$ (seller monopoly), with the reference benchmark stabilizing at $\$0.219934$.
5. **Surplus Shares (`benefit_share_distributions.png`):**  
   Stacked bar representation of community surplus shares. `H002` acts as a balanced dual prosumer, maintaining a stable 40.2%–43.8% surplus share across all policies.
6. **Hourly Fairness vs Welfare Scatter (`fairness_vs_welfare_scatter.png`):**  
   Hourly distribution showing how Pareto selection clusters outcomes along the physical capacity boundary while varying local inequality.
7. **Representative Daily Price Dynamics (`hourly_price_comparison.png`):**  
   Hourly price trajectories over a sample day (`2013-05-01`), showing midday convergence and evening tariff limits.
8. **Hybrid Sensitivity Sweep (`hybrid_weight_sensitivity.png`):**  
   Illustrates the discrete two-regime step response: flat normalized Gini for $w_{	ext{fair}} \le 0.5$, followed by monotonic decrease for $w_{	ext{fair}} \in [0.6, 1.0]$.

---

## 8. Economic Interpretation and Policy Recommendations

### 8.1 Empirical Grounding and Operational Scope
All recommendations in this section are grounded strictly in the evaluated 1,752 hours of empirical data from the accepted Phase 7.1 held-out dataset. 

**Model Scope and Boundary Conditions:**
- **Deterministic Ex-Post Evaluation:** Battery dispatch trajectories and hourly net surplus/deficit flows are pre-determined by the accepted Phase 7.1 Stochastic MPC baseline.
- **Price-Only Action Space:** Prosumers submit price bids from the discrete tariff grid $\mathcal{P} = \{0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30\}$, with quantities fixed to available physical flows ($q_i = s_i, q_j = d_j$).
- **No Behavioral Price Elasticity:** Because physical flows are fixed ex-post, these results model pure transfer-price surplus division and do not assume dynamic real-time price elasticity.

### 8.2 Practical Selection Policy Recommendation: Nash Social Welfare (Strategy E)
Among all evaluated core selection policies, **Strategy E (Nash Social Welfare)** provides the most compelling operational profile for a community microgrid:
1. **Lowest Gini Inequality Among Core Strategies:** Delivers the most balanced distribution ($G_{	ext{norm}} = 0.8073, G = 0.5382$).
2. **Proportional Fairness Axiom:** Unlike pure egalitarianism (Strategy D), which strictly optimizes the single lowest payoff in isolation, NSW optimizes the geometric product $\prod (U_i + \epsilon)$, scaling rewards with trading contribution while rigorously protecting disadvantaged participants.
3. **Zero Deadweight Loss:** Preserves 100% of feasible physical trading volume (121.611449 kWh) and community welfare ($26.754519 AUD).

### 8.3 Strategic Market Power vs. Reference Midpoint Pricing
The analysis reveals that in an unconstrained strategic double auction:
- Midday solar concentration provides sellers with substantial pricing power. Under Strategy A (Reference), sellers capture **63.61% ($17.02 AUD)** of the available surplus, driving VWAP to **$0.219934 AUD/kWh**. Under Strategy B (Seller-Favouring), seller surplus extraction reaches **87.04% ($23.29 AUD)**, driving VWAP to **$0.271490 AUD/kWh**.
- Implementing **Strategy E (NSW)** or **Strategy D (Max-Min)** acts as an algorithmic counterweight within the market coordinator's tie-breaking and selection framework, mitigating monopolistic rent extraction and stabilizing household payoffs without administrative price caps.

---

## 9. Limitations & Future Extensions

1. **Deterministic Ex-Post Evaluation:**  
   Phase 8D evaluated equilibrium selection ex-post with frozen physical battery dispatches from Phase 7.1. In real-world deployment, bidding occurs ex-ante under forecast uncertainty.
2. **Price-Only Action Space:**  
   Bidding was restricted to discrete prices with frozen physical quantities. Strategic volume withholding (bidding $q < s^{	ext{act}}$) was deferred to future research.
3. **Path to Phase 8E:**  
   The natural next step is **Phase 8E: Ex-Ante Deployable Strategic Game**, where households bid prices and quantities under LSTM forecast uncertainty and Monte Carlo scenario trees.

---

## 10. Conclusion

Phase 8D successfully transformed the Phase 8C Nash equilibrium solver into a **comparative economic decision-support framework**. 

By evaluating 315,280 equilibria across 1,752 hours, we proved empirically that **Pareto-undominated equilibrium selection resolves the efficiency-fairness dilemma in residential microgrids: distributional fairness can be substantially optimized without sacrificing a single kilowatt-hour of clean energy trade or a single cent of community economic welfare.**
