# Deliverable 2 — Step 3B: Mathematical and Data-Contract Reconciliation Audit
## Independent Verification of Research Artifacts, Strategy Spaces, Profile Counts, and Data Contracts

**Document Identifier:** `reports/dashboard_step3b_reconciliation_audit.md`  
**Date:** November 1, 2026  
**Audit Type:** Strict Read-Only Mathematical and Data-Contract Reconciliation  
**Auditor:** Independent Academic Verification Agent (Antigravity)  
**Target Repository:** `Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions`  
**Audited Modules:** `src/game/strategic_market.py`, `src/game/strategic_solver.py`, `src/game/equilibrium_selection.py`, `src/game/fairness_metrics.py`, `reports/phase8c_*`, `reports/phase8d_*`, `dashboard/data_service.py`, `dashboard/app.py`  
**Final Verdict:** **RECONCILED WITH CAVEATS — FRONTEND CAN PROCEED WITH SPECIFIED RESTRICTIONS**  

---

## 1. Executive Summary

This independent audit performs a strict read-only mathematical and data-contract reconciliation across the Deliverable 2 dashboard backend (`dashboard/data_service.py`, `dashboard/app.py`), its underlying Phase 8 game-theoretic engine (`src/game/`), and frozen research artifacts (`reports/phase8c_*`, `reports/phase8d_*`).

The previous audit (`reports/dashboard_data_service_audit.md`) verified the basic retrieval mechanics, absence of runtime recomputation, and overall physical conservation of the dashboard data service, classifying it as Category B. However, several critical documentation discrepancies were identified between earlier audit narratives and the actual source code—specifically concerning the exact discrete strategic action grid, total evaluated combinatorial profile counts, one-sided market hour breakdowns, and terminology surrounding Pareto-dominated equilibria.

### Major Reconciliation Findings:
1. **Strategic Action Grid Discrepancy Resolved:** The actual strategic price grid defined in source code and frozen across all 315,280 archived equilibria is **strictly asymmetric and centered on \$0.19/kWh**:
   $$\mathcal{P} = (0.08,\ 0.12,\ 0.16,\ 0.19,\ 0.22,\ 0.26,\ 0.30)\text{ AUD/kWh}$$
   The equispaced grid `[0.08, 0.1167, ..., 0.30]` mentioned in Section 19 of the previous audit report was a documentation approximation that does not exist in code or data.
2. **Profile Count Discrepancy Resolved:** The true total number of combinatorial price profiles evaluated across the 1,752 simulation hours is **600,642** (derived from $1,751\text{ hours} \times 343\text{ profiles} + 1\text{ hour} \times 49\text{ profiles}$), matching the exact sum of `num_profiles_evaluated` in `reports/phase8c_hourly_equilibria.csv`. The figure of **599,088** reported in the previous audit was an erroneous calculation.
3. **One-Sided Market Hours Reconciled:** The true composition of the 886 non-tradeable hours consists of **827 all-buyer hours** (at night/early morning) and **59 all-seller hours** (58 with 3 sellers, 1 with 2 sellers during high midday solar). The previous audit's narrative citing "16 all-seller hours and 237 all-buyer hours" was contradicted by the frozen data and has been fully corrected.
4. **Pure Nash Equilibrium (PNE) Multiplicity Confirmed:** The 315,280 evaluated PNE partition strictly and mutually exclusively into **1,224 strict PNE** and **314,056 weak PNE** ($N_{\text{PNE}} = N_{\text{strict}} + N_{\text{weak}}$ with zero error across all 1,752 hours).
5. **Pareto Dominance and "Submaximal Traps":** Of the 315,280 PNE, exactly **312,810 are Pareto-undominated** and **2,470 are Pareto-dominated**. These 2,470 dominated equilibria represent classical coordination failures (uncrossed bids or partial fills clearing less than maximum volume). The dashboard must label them neutrally as *"Pareto-dominated Pure Nash Equilibria (Coordination Failures)"*.
6. **Phase 8E Mandatory Scope Disclosure:** Phase 8E (an ex-ante stochastic strategic game with expected payoffs across Monte Carlo uncertainty scenarios) **is NOT implemented** anywhere in the codebase. The dashboard frontend must explicitly label Phase 8E as unimplemented future work and avoid displaying any stochastic strategic bidding claims.
7. **Final Verdict:** **RECONCILED WITH CAVEATS — FRONTEND CAN PROCEED WITH SPECIFIED RESTRICTIONS**.

---

## 2. Files and Functions Inspected

The audit conducted direct inspections of source code, data contracts, and serialized archives:

| Source File | Function / Class Inspected | Lines Inspected | Exact Value / Implementation Audited | Status |
|---|---|---|---|---|
| [`src/game/strategic_market.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_market.py) | `STRATEGIC_PRICE_GRID` | [L35-L40](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_market.py#L35-L40) | `(0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30)` | **VERIFIED** |
| [`src/game/strategic_market.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_market.py) | `MarketRole`, `build_market_order` | [L43-L49](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_market.py#L43-L49), [L400-L438](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_market.py#L400-L438) | Role classification based on $|net\_flow| > 10^{-6}\text{ kWh}$ | **VERIFIED** |
| [`src/game/strategic_market.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_market.py) | `clear_strategic_double_auction` | [L440-L620](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_market.py#L440-L620) | Midpoint pricing rule $p_{ij} = (a_i + b_j)/2$, pro-rata ties | **VERIFIED** |
| [`src/game/strategic_solver.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_solver.py) | `check_pareto_dominance` | [L240-L256](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_solver.py#L240-L256) | Multi-objective weak Pareto dominance ($\forall i: u_i^a \ge u_i^b \land \exists j: u_j^a > u_j^b$) | **VERIFIED** |
| [`src/game/strategic_solver.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_solver.py) | `identify_pareto_undominated` | [L258-L286](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_solver.py#L258-L286) | Pairwise Pareto dominance filtering strictly on verified PNE | **VERIFIED** |
| [`src/game/strategic_solver.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_solver.py) | Combinatorial Enumeration | [L512-L523](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_solver.py#L512-L523) | `profile_tuples = list(itertools.product(grid_prices, repeat=num_active))` | **VERIFIED** |
| [`src/game/strategic_solver.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_solver.py) | Unilateral Deviations & PNE Classification | [L564-L608](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_solver.py#L564-L608) | Epsilon tolerance $10^{-6}$, mutually exclusive Strict vs Weak | **VERIFIED** |
| [`src/game/equilibrium_selection.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/equilibrium_selection.py) | `select_strategy_a_reference` to `f_hybrid` | [L80-L400](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/equilibrium_selection.py#L80-L400) | Hierarchical selection from Pareto-undominated PNE candidate set | **VERIFIED** |
| [`reports/phase8c_hourly_equilibria.csv`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/reports/phase8c_hourly_equilibria.csv) | Entire CSV ($1,752 \times 33$) | Rows 0–1751 | Sum of `num_profiles_evaluated` $= 600,642$; PNE $= 315,280$ | **VERIFIED** |
| [`reports/phase8c_all_equilibria.json.gz`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/reports/phase8c_all_equilibria.json.gz) | 1,752 blocks (315,280 equilibria) | All entries | Profile price values drawn strictly from $\{0.08, 0.12, \dots, 0.30\}$ | **VERIFIED** |
| [`dashboard/data_service.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/dashboard/data_service.py) | `get_nash_hour` | [L553-L570](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/dashboard/data_service.py#L553-L570) | Volume-based Pareto filter matching archived Pareto flags 100% | **VERIFIED** |
| [`dashboard/app.py`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/dashboard/app.py) | Flask REST Endpoints | [L77-L308](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/dashboard/app.py#L77-L308) | 14 GET routes, uniform JSON envelope, error handlers | **VERIFIED** |

---

## 3. Reconciliation A — Actual Strategy Action Grid

### Audit Investigation
There was a discrepancy between:
- Earlier source-audit summaries describing: `[0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30]`
- The previous dashboard audit report (Section 19) describing: `[0.08, 0.1167, ..., 0.30]`

### Codebase and Data Evidence:
1. **Single Source of Truth in Code:**  
   In [`src/game/strategic_market.py:36`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_market.py#L36):
   ```python
   STRATEGIC_PRICE_GRID: Tuple[float, ...] = (0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30)
   ```
   This constant is directly imported by:
   - [`src/game/strategic_solver.py:49`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_solver.py#L49)
   - [`src/game/dataset_evaluation.py:23`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/dataset_evaluation.py#L23)
   There are no conflicting alternative action grids in the source tree.

2. **Discrete Step Properties:**  
   The grid has exactly seven discrete action levels ($K=7$) bounded by the grid export credit (\$0.08) and grid import tariff (\$0.30):
   $$\Delta_1 = 0.12 - 0.08 = 0.04$$
   $$\Delta_2 = 0.16 - 0.12 = 0.04$$
   $$\Delta_3 = 0.19 - 0.16 = 0.03\quad (\text{exact midpoint: } (0.08 + 0.30)/2 = 0.19)$$
   $$\Delta_4 = 0.22 - 0.19 = 0.03$$
   $$\Delta_5 = 0.26 - 0.22 = 0.04$$
   $$\Delta_6 = 0.30 - 0.26 = 0.04$$
   The grid is asymmetric with non-uniform step sizes deliberately engineered to place \$0.19 as the exact center. It is **not** an equispaced `np.linspace(0.08, 0.30, 7)`.

3. **Archive Verification:**  
   Scanning all 315,280 equilibria in `reports/phase8c_all_equilibria.json.gz` confirmed that every single submitted price across all households is strictly an element of $\{0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30\}$. Similarly, all selected prices in `reports/phase8c_hourly_equilibria.csv` belong strictly to this set.

4. **Transaction Prices vs Action Grid:**  
   Executed transaction prices $p_{ij} = (a_i + b_j)/2$ can take intermediate fractional values (e.g. $(0.08 + 0.19)/2 = 0.135\text{ AUD/kWh}$). The volume-weighted average price (VWAP) is a continuous real number.

### Conclusion:
- **Verified Action Grid:** `[0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30]` AUD/kWh ($K=7$).
- **Status:** **CONTRADICTED** (previous dashboard audit Section 19 equispaced description is refuted; actual source grid is confirmed).
- **Frontend Directive:** The frontend must display `[0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30]`. It must never display `0.1167` or imply an equispaced linear grid.

---

## 4. Reconciliation B — Profile Counts and Role Composition

### Audit Investigation
The previous dashboard audit claimed 599,088 evaluated profiles, 16 all-seller hours, and 237 all-buyer hours. An earlier audit noted 1,751 three-player hours and 1 two-player hour.

### Empirical Analysis of `reports/phase8c_hourly_equilibria.csv`

Every single hour of the 1,752 simulation hours was analyzed for physical roles, active players, and profile counts:

```
Total Hours: 1,752
Total Profiles Evaluated (Sum of CSV column 'num_profiles_evaluated'): 600,642
```

### Complete Role-Composition Breakdown

| Active Strategic Players ($A_t$) | Active Sellers | Active Buyers | Inactive Households | Hour Count | Profiles / Hour ($7^{A_t}$) | Total Combinatorial Profiles | Unilateral Deviations / Hour | Total Deviations Tested |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **2** | 2 | 0 | 1 (H001) | 1 | $7^2 = 49$ | 49 | $2 \times 6 \times 49 = 588$ | 588 |
| **3** | 0 | 3 | 0 | 827 | $7^3 = 343$ | 283,661 | $3 \times 6 \times 343 = 6,174$ | 5,105,898 |
| **3** | 1 | 2 | 0 | 649 | $7^3 = 343$ | 222,607 | $3 \times 6 \times 343 = 6,174$ | 4,006,926 |
| **3** | 2 | 1 | 0 | 217 | $7^3 = 343$ | 74,431 | $3 \times 6 \times 343 = 6,174$ | 1,339,758 |
| **3** | 3 | 0 | 0 | 58 | $7^3 = 343$ | 19,894 | $3 \times 6 \times 343 = 6,174$ | 358,092 |
| **TOTAL** | — | — | — | **1,752** | — | **600,642** | — | **10,811,262** |

### Critical Reconciliations:
1. **Total Profiles Evaluated:**
   $$\sum_{t=1}^{1752} N_t = (1,751 \times 343) + (1 \times 49) = 600,593 + 49 = \mathbf{600,642}$$
   The previous dashboard audit's claim of **599,088** was an arithmetic error ($600,642 - 599,088 = 1,554$ profiles missing).
2. **One-Sided Market Hours Breakdown:**
   - **All-Buyers Hours:** Exactly **827 hours** (all households have physical deficits at night/early morning).
   - **All-Sellers Hours:** Exactly **59 hours** (58 hours with 3 sellers, plus 1 hour with 2 sellers during high solar irradiance).
   - Total one-sided / non-tradeable hours: $827 + 59 = \mathbf{886\text{ hours}}$.
   - The previous audit's mention of "16 all-seller hours and 237 all-buyer hours" was a severe transcription error that contradicted the underlying dataset.
3. **Tradeable Hours:** Exactly **866 hours** ($649 + 217 = 866$ mixed-market hours where at least one seller and one buyer were present).
4. **Inactive Players in Strategic Space:** Inactive households (having $|net\_flow| \le 10^{-6}\text{ kWh}$) are assigned an **empty action space** ($A_i = \emptyset$). They submit no price bid, undergo zero deviations, and do not multiply the combinatorial profile space. This occurred in exactly 1 hour (row 424, `2013-05-06 16:00:00`, where H001 was inactive, leaving H002 and H003 active, yielding $7^2 = 49$ profiles).

---

## 5. Reconciliation C — Strict and Weak Pure Nash Equilibria

### Audit Investigation
Verify the reported 315,280 total PNE, 1,224 strict PNE, 314,056 weak PNE, and 0 hours without a PNE.

### Codebase Definition & Classification Mechanism:
In [`src/game/strategic_solver.py:564-608`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_solver.py#L564-L608):
1. **Unilateral Deviation Evaluation:**  
   For each candidate profile tuple $s^* = (p_1^*, \dots, p_A^*)$, every active player $i$ evaluates all alternative grid prices $p_i' \in \mathcal{P} \setminus \{p_i^*\}$:
   - If $\Delta U_i(p_i', s_{-i}^*) > \Delta U_i(s_i^*, s_{-i}^*) + 10^{-6}$: A profitable deviation exists. Profile is rejected (`is_pne = False`).
   - If $|\Delta U_i(p_i', s_{-i}^*) - \Delta U_i(s_i^*, s_{-i}^*)| \le 10^{-6}$: An indifferent deviation exists. Profile cannot be strict (`is_strict = False`).
2. **Mutual Exclusivity:**  
   Profiles passing all deviation checks are classified as:
   - `EquilibriumClassification.STRICT` if `is_strict == True` (every deviation strictly decreases payoff).
   - `EquilibriumClassification.WEAK` if `is_strict == False` (at least one deviation yields an identical payoff within $10^{-6}$).
   Therefore, strict and weak equilibria are **mutually exclusive partitions** of the PNE set:
   $$E_{\text{PNE}} = E_{\text{strict}} \cup E_{\text{weak}},\quad E_{\text{strict}} \cap E_{\text{weak}} = \emptyset$$
   $$N_{\text{PNE}} = N_{\text{strict}} + N_{\text{weak}}$$

### Empirical Verification from `reports/phase8c_hourly_equilibria.csv`:
- **Sum of `num_pne`:** 315,280
- **Sum of `num_strict_pne`:** 1,224
- **Sum of `num_weak_pne`:** 314,056
- **Residual ($N_{\text{PNE}} - (N_{\text{strict}} + N_{\text{weak}})$):** Exactly **0** for all 1,752 hours.
- **Zero-PNE Hours:** **0** hours (every hour has at least 10 PNE).

### Why Weak Equilibria Dominate (314,056 vs 1,224):
In double auctions, if an agent's order does not clear (e.g., an uncrossed buyer whose bid $0.08$ is below all asks), deviating to another uncrossed bid (e.g., $0.12$ or $0.16$) still yields zero trade and zero payoff ($\Delta U_i = 0$). Because alternative uncrossed bids yield identical payoffs, the equilibrium condition holds with equality ($0 \le 0$), rendering the PNE weak. In the 886 non-tradeable hours, all 343 (or 49) profiles are weak PNE for this reason.

---

## 6. Reconciliation D — Pareto Frontier and Submaximal Equilibria

### Audit Investigation
Clarify the mathematical meaning of "312,810 Pareto-undominated PNE" and "2,470 submaximal traps".

### Codebase Implementation:
In [`src/game/strategic_solver.py:240-286`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_solver.py#L240-L286):
1. **Pareto Dominance Definition:** Profile $e_a$ Pareto-dominates $e_b$ if and only if:
   $$\forall i \in \{H001, H002, H003\}: U_i(e_a) \ge U_i(e_b) - 10^{-6} \quad \land \quad \exists j: U_j(e_a) > U_j(e_b) + 10^{-6}$$
2. **Candidate Filter Scope:** Pareto filtering is performed **exclusively over the verified PNE set** (`candidate_equilibria`), never over non-equilibrium profiles.
3. **Equivalence with Maximum Volume Clearing:**  
   Under the midpoint double-auction rule, every PNE that clears the maximum physical volume $Q^*(t)$ achieves maximum community welfare $\Delta W^*(t) = 0.22 Q^*(t)$ and is Pareto-undominated.
   Testing all 315,280 archived equilibria verified that:
   $$\text{is\_pareto\_undominated} \iff (Q(e) = Q^*(t))$$
   with **zero mismatches** across the entire dataset.

### Deconstructing the "2,470 Submaximal Traps":
- **Total PNE:** 315,280
- **Pareto-Undominated PNE:** 312,810
- **Pareto-Dominated PNE:** $315,280 - 312,810 = \mathbf{2,470}$
- **What are they?** In active tradeable hours, these are Pure Nash Equilibria where households submit uncrossed or partially uncrossed prices that clear less than the maximum possible trade volume ($Q < Q^*(t)$), resulting in sub-optimal welfare. Because no single player can unilaterally improve their payoff without cooperation, the market is stuck in a coordination failure.
- **Recommended Dashboard Terminology:** Replace the informal term *"submaximal traps"* with the academically precise label:  
  **"Pareto-dominated Pure Nash Equilibria (Coordination Failures)"**.

---

## 7. Reconciliation E — Phase 8D Selection Strategies

### Audit Investigation
Verify the selection rules, candidate sets, tie-breaking heuristics, and welfare invariance across the six Phase 8D strategies and seven hybrid sensitivity variants.

### Selection Rules Summary Table

| Strategy Identifier | Strategy Name | Objective Function / Selection Criterion | Candidate Set | Tie-Break Hierarchy |
|---|---|---|---|---|
| `Strategy_A_Reference` | Strategy A (Reference) | Minimize distance of VWAP to benchmark \$0.19/kWh ($|p_{\text{vwap}} - 0.19|$) | Pareto-undominated PNE | Maximize $\Delta W \to$ Min price std $\to$ Lexicographical |
| `Strategy_B_Seller` | Strategy B (Seller-Favouring) | Maximize aggregate active seller surplus ($\sum_{s \in \text{sellers}} U_s$) | Pareto-undominated PNE | Min seller payoff variance $\to$ Min distance to \$0.19 $\to$ Lexicographical |
| `Strategy_C_Buyer` | Strategy C (Buyer-Favouring) | Maximize aggregate active buyer surplus ($\sum_{b \in \text{buyers}} U_b$) | Pareto-undominated PNE | Min buyer payoff variance $\to$ Min distance to \$0.19 $\to$ Lexicographical |
| `Strategy_D_MaxMin` | Strategy D (Max-Min Fair) | Maximize the minimum payoff among active players ($\max \min_{i \in \text{active}} U_i$) | Pareto-undominated PNE | Lexicographic 2nd lowest payoff $\to$ Min distance to \$0.19 $\to$ Lexicographical |
| `Strategy_E_NSW` | Strategy E (Nash Social Welfare) | Maximize Nash Social Welfare ($\sum_{i \in \text{active}} \ln(U_i + 10^{-6})$) | Pareto-undominated PNE | Min distance to \$0.19 $\to$ Lexicographical |
| `Strategy_F_Hybrid_w0.5`| Strategy F (Hybrid w=0.5) | Minimize loss $0.5 \cdot \frac{\|p - 0.19\|}{0.11} + 0.5 \cdot G_{\text{norm}}$ | Pareto-undominated PNE | Min distance to \$0.19 $\to$ Lexicographical |
| `Hybrid_w_fair_0.0`–`1.0` | Hybrid Variants ($w \in \{0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0\}$) | Minimize loss $(1-w) \cdot \frac{\|p - 0.19\|}{0.11} + w \cdot G_{\text{norm}}$ | Pareto-undominated PNE | Min distance to \$0.19 $\to$ Lexicographical |

### Proof of Welfare and Volume Invariance:
- **Total Cleared Volume:** Exactly **$121.611449\text{ kWh}$** across all 13 strategy configurations.
- **Total Community Welfare:** Exactly **$\$26.754519\text{ AUD}$** ($0.22 \times 121.611449$) across all 13 configurations.
- **Scope of Invariance:** These values refer to the **aggregate cumulative total over the entire 1,752-hour evaluation period** (April 19 – June 30, 2013).
- **Physical vs Financial Separation:** Because all 13 strategies select strictly from the Pareto-undominated PNE set, they all clear the exact same physical energy volume ($Q^*(t)$). The strategy choice changes only the transaction prices ($p_{ij}$), shifting financial surplus between sellers and buyers without altering total community welfare.

---

## 8. Reconciliation F — Economic and Accounting Definitions

### Formula Audits & Numerical Verification

1. **Market Crossing Rule:**  
   A bilateral match is feasible if and only if:
   $$b_j \ge a_i - 10^{-6}$$
2. **Clearing Price Rule:**  
   Executed transaction price is strictly the midpoint of submitted ask and bid:
   $$p_{ij} = \frac{a_i + b_j}{2}$$
3. **Bilateral Flow Balance:**  
   For every hour $t$:
   $$Q_{\text{sold}}(t) = \sum_{i \in \text{sellers}} q_{i,\text{sold}}(t) = \sum_{j \in \text{buyers}} q_{j,\text{bought}}(t) = Q_{\text{bought}}(t) = Q_{\text{P2P}}(t)$$
   Verified residual: $\le 1.67 \times 10^{-16}\text{ kWh}$.
4. **Zero Financial Leakage Identity:**  
   Every trade $q_{ij}$ clears at transaction price $p_{ij}$, so:
   $$\text{Buyer Payment}_{ij} = q_{ij} \cdot p_{ij} = \text{Seller Revenue}_{ij}$$
   Summing across all bilateral transactions:
   $$\sum_{j} \text{Buyer Payments}_j = \sum_{i} \text{Seller Revenues}_i$$
   Verified residual: **$0.0\text{ AUD}$** (exact zero leakage).
5. **Incremental Utility vs Absolute Utility:**  
   The data service exposes incremental economic benefits relative to standalone grid-only operation:
   $$\Delta U_i^{\text{seller}} = \sum_j q_{ij} (p_{ij} - p_{\text{exp}})$$
   $$\Delta U_j^{\text{buyer}} = \sum_i q_{ij} (p_{\text{imp}} - p_{ij})$$
   $$\Delta W = \sum_i \Delta U_i = (p_{\text{imp}} - p_{\text{exp}}) Q_{\text{P2P}} = 0.22 \cdot Q_{\text{P2P}}$$
   Verified residual: $\le 2.22 \times 10^{-16}\text{ AUD}$.
   The frontend must label these as **"Incremental Economic Benefit ($\Delta U_i$ in AUD)"**, not total household utility.

---

## 9. Dashboard Data Contract Findings

### Detailed Contract Audits

1. **Action Grid Contract:**  
   The data service exposes discrete submitted price profiles whose values are strictly in $\{0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30\}$. The frontend must use this exact discrete list for bid/ask visualization controls.
2. **No-Trade Hours Contract:**  
   In the 886 zero-trade hours, VWAP is returned as `None` (JSON `null`). The frontend must distinguish `null` (undefined price due to zero volume) from `$0.00/kWh`.
3. **Forecast Data Join Hygiene:**  
   In `dashboard/data_service.py:266`, `get_forecast_data()` uses `zip(df_pred.iterrows(), df_int.iterrows())`. While both files currently match 1:1 on timestamps and households in the frozen data, an explicit inner join on `["forecast_timestamp", "house_id"]` is recommended to prevent row-alignment risks.
4. **Historical Metadata Isolation:**  
   `tests_passing: 250` and `invariance_holds: True` are static Deliverable 1 metadata. They must be displayed in a dedicated "Audited Baseline Ledger" section rather than presented as live runtime health checks.

---

## 10. Phase 8E Implementation Status and Mandatory Scope Disclosure

### Mandatory Scope Statement:
> **"Phase 8E — ex-ante stochastic strategic game — is not implemented in the current project version. The existing Monte Carlo pipeline generates forecast/scenario information but does not, by itself, establish an expected-payoff strategic game or stochastic Nash equilibrium."**

### Verification Evidence:
- Exhaustive code search for `phase8e`, `8e`, `stochastic_nash`, `expected_payoffs`, or `ex_ante_game` across `src/` and `tests/` yielded **0 occurrences**.
- All Phase 8 code is strictly **deterministic ex-post**: it evaluates double-auction clearing and Pure Nash Equilibria on realized post-battery meter flows.
- The Monte Carlo uncertainty pipeline in `src/stochastic/monte_carlo.py` is utilized for battery MPC optimization (Phase 6B), **not** for strategic energy bidding.

### Recommended Dashboard Disclosure:
The dashboard frontend must prominently display the following implementation boundary:
- **Phase 7 Fixed-Price Double Auction:** Implemented & Verified.
- **Phase 8 Strategic Market & Double Auction:** Implemented & Verified.
- **Phase 8C Deterministic Pure Nash Equilibrium Enumeration:** Implemented & Verified.
- **Phase 8D Fairness-Based Equilibrium Selection (Strategies A–F):** Implemented & Verified.
- **Phase 8E Ex-Ante Stochastic Strategic Game:** **NOT IMPLEMENTED (Future Work)**.

---

## 11. Final Reconciliation Table

| Claim / Metric | Previous Audit Value | Independently Verified Value | Source / Evidence | Status |
|---|---|---|---|---|
| **Strategy Action Grid** | `[0.08, 0.1167, ..., 0.30]` | `[0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30]` | [`src/game/strategic_market.py:36`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_market.py#L36) | **CONTRADICTED** |
| **Actions per Active Player** | 7 actions | 7 actions | [`src/game/strategic_market.py:36`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_market.py#L36) | **VERIFIED** |
| **Total Evaluated Profiles** | 599,088 profiles | **600,642 profiles** | Sum of `num_profiles_evaluated` in `reports/phase8c_hourly_equilibria.csv` | **CONTRADICTED** |
| **Profiles per 3-Player Hour** | 343 profiles | 343 profiles ($7^3$) | [`src/game/strategic_solver.py:519`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_solver.py#L519) | **VERIFIED** |
| **Profiles per 2-Player Hour** | 49 profiles | 49 profiles ($7^2$) | [`src/game/strategic_solver.py:519`](file:///d:/5thSem/GT%20project/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/strategic_solver.py#L519) | **VERIFIED** |
| **Total Pure Nash Equilibria** | 315,280 PNE | 315,280 PNE | Sum of `num_pne` in `reports/phase8c_hourly_equilibria.csv` | **VERIFIED** |
| **Strict Pure Nash Equilibria** | 1,224 strict PNE | 1,224 strict PNE | Sum of `num_strict_pne` in `reports/phase8c_hourly_equilibria.csv` | **VERIFIED** |
| **Weak Pure Nash Equilibria** | 314,056 weak PNE | 314,056 weak PNE | Sum of `num_weak_pne` in `reports/phase8c_hourly_equilibria.csv` | **VERIFIED** |
| **Pareto-Undominated PNE** | 312,810 PNE | 312,810 PNE | Sum of `num_pareto_undominated_pne` in `reports/phase8c_hourly_equilibria.csv` | **VERIFIED** |
| **Pareto-Dominated PNE** | 2,470 "submaximal traps" | 2,470 Pareto-dominated PNE | $315,280 - 312,810 = 2,470$ in `reports/phase8c_hourly_equilibria.csv` | **VERIFIED WITH CAVEAT** |
| **Hours with No PNE** | 0 hours | 0 hours | All rows have `no_pne_status == False` | **VERIFIED** |
| **Active Player Breakdown** | 1,751 3-player; 1 2-player | 1,751 3-player; 1 2-player | `num_active_players` in `reports/phase8c_hourly_equilibria.csv` | **VERIFIED** |
| **One-Sided Market Hours** | 16 all-seller; 237 all-buyer | **59 all-seller; 827 all-buyer** | Cross-tabulation of `reports/phase8c_hourly_equilibria.csv` | **CONTRADICTED** |
| **Tradeable Hours** | 866 hours | 866 hours | `selected_traded_volume_kwh > 0` | **VERIFIED** |
| **Non-Tradeable Hours** | 886 hours | 886 hours ($827 + 59$) | `selected_traded_volume_kwh == 0` | **VERIFIED** |
| **Total Stochastic P2P Volume** | 121.611449 kWh | 121.611449 kWh | Sum of single-sided P2P cleared volume | **VERIFIED** |
| **Total Community Welfare** | AUD 26.754519 | AUD 26.754519 | Exact $0.22 \times 121.611449\text{ kWh}$ | **VERIFIED** |
| **Buyer Payments = Seller Revenues**| Exact equality | Exact equality ($0.0\text{ AUD}$ leakage)| Verified across all transactions | **VERIFIED** |
| **Phase 8D Selection Invariance** | Volume & welfare invariant | Volume & welfare invariant (13 configs)| Cumulative total across full 1,752 h period | **VERIFIED** |
| **Phase 8E Implementation** | Implied in dashboard plan | **NOT IMPLEMENTED** | Zero code present in repository | **NOT IMPLEMENTED** |

---

## 12. Frontend Display Recommendations

### Category 1: Verified Research Results (Safe to Display Now)
- Physical energy flows (actual/forecast demand, solar generation, battery SOC, charged/discharged kWh, grid imports/exports).
- Microgrid trading liquidity (866 tradeable hours, 886 non-tradeable hours, unmatched surplus/deficit).
- Discrete strategic action grid: `[0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30]` AUD/kWh.
- Total evaluated profiles: 600,642 profiles ($1,751 \times 343 + 1 \times 49$).
- Pure Nash equilibria counts: 315,280 total PNE, 1,224 strict PNE, 314,056 weak PNE.
- Pareto frontier: 312,810 Pareto-undominated PNE.
- Phase 8D Strategy comparison (Strategies A through F, invariant total volume 121.61 kWh, invariant welfare \$26.75 AUD, Gini coefficients, household benefit allocations).
- Cumulative cost savings vs Standalone: \$26.75 AUD (3.43% reduction for Stochastic MPC).

### Category 2: Historical Audit Metadata (Display Only as Fixed Baseline)
- Precomputed Deliverable 1 invariant residuals (demand conservation, financial balance, SOC boundaries).
- Historical test passing counter (250 tests passed in Deliverable 1 baseline; active repository has 283 tests).
- Hardware battery specifications (5.0 kWh capacity, 2.5 kW power, 90.25% roundtrip efficiency).

### Category 3: Not Implemented / Future Work (Must Not Be Displayed as Implemented)
- Phase 8E ex-ante stochastic bidding game.
- Expected stochastic strategic payoffs across Monte Carlo scenarios.
- Two-sided contingent 49-action bidding spaces.
- Bilevel MPC game feedback (Phase 8F).

---

## 13. Final Verdict

$$\mathbf{RECONCILED\ WITH\ CAVEATS\ —\ FRONTEND\ CAN\ PROCEED\ WITH\ SPECIFIED\ RESTRICTIONS}$$

### Verdict Justification:
1. **Mathematical Soundness Established:** All underlying physical, financial, and game-theoretic identities have been validated to machine precision. There are zero blocking mathematical defects.
2. **Discrepancies Fully Resolved:** The actual action grid (`[0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30]`), profile count (`600,642`), and one-sided hours (`59` all-seller, `827` all-buyer) have been mathematically proven from source files and must be used in place of earlier erroneous narrative approximations.
3. **Strict Scope Enforcement:** The frontend must disclose that Phase 8E is unimplemented future work.

---

## 14. Changed-Files List

The only file created during this audit is:
- `reports/dashboard_step3b_reconciliation_audit.md`

No other repository files, source codes, datasets, or test configurations were created, modified, or deleted.

