# Phase 8D — Pure Nash Equilibrium (PNE) Welfare Invariance Audit

**Report ID:** `reports/phase8d_pne_welfare_invariance_audit.md`  
**Evaluation Scope:** Complete held-out dataset of 1,752 hours (`2013-04-19 00:00:00` to `2013-06-30 23:00:00`)  
**Data Source:** Authoritative Phase 8C archive `reports/phase8c_all_equilibria.json.gz` (315,280 pure Nash equilibria) and `reports/phase8c_hourly_equilibria.csv`.

---

## 1. Executive Summary

A critical question in the strategic game formulation is whether all Pure Nash Equilibria (PNE) achieve the same physical trading volume and community economic welfare, or whether equilibrium selection entails a fundamental trade-off between economic efficiency and distributional fairness.

This audit evaluated all **315,280 pure Nash equilibria** across all **1,752 hours** of the Phase 7.1 held-out test period to establish the empirical and mathematical truth regarding physical volume and welfare invariance.

### Key Empirical Findings

1. **Across the FULL Set of Pure Nash Equilibria ($E_{\text{PNE}}$):**
   - **Welfare and volume DO VARY dramatically.** In **866 out of 1,752 hours (49.43% overall, and 100.00% of mixed-market tradeable hours)**, physical trading volume and community welfare vary widely across different equilibria.
   - Specifically, every tradeable hour exhibits **submaximal equilibria**:
     - **Zero-Trade Coordination Traps ($Q = 0$):** Uncrossed profiles (e.g. seller asks $\$0.30$, buyers bid $\$0.08$) form weak PNE where no single buyer or seller can unilaterally create a profitable trade.
     - **Partial-Trade Monopolistic Traps ($0 < Q < Q^*$, 1,604 instances):** One buyer or seller is priced out of the market by an extreme boundary bid/ask, leaving unmatched supply and unmet demand.
2. **Across the PARETO-UNDOMINATED Equilibrium Set ($E_{\text{Pareto}}$):**
   - **Welfare and physical volume are 100.00% INVARIANT.**
   - In **zero hours (0.00%)** do Pareto-undominated equilibria vary in physical volume or community welfare.
   - In **100.00% of hours (1,752 / 1,752)**, every Pareto-undominated equilibrium achieves **exactly the maximum physically feasible volume** $Q^*(t) = \min(\sum s_i, \sum d_j)$ and **maximum community welfare** $\Delta W^*(t) = \$0.22 \times Q^*(t)$.
   - All 2,470 submaximal equilibria (866 zero-trade + 1,604 partial-trade) are strictly Pareto-dominated by crossing equilibria that clear the entire short side of the market.
3. **Core Conclusion for Phase 8D:**
   - Because all six candidate selection strategies in Phase 8D select strictly from the **Pareto-undominated set** ($E_{\text{Pareto}}$), **all selection strategies achieve identical physical volume ($121.611449\text{ kWh}$) and identical total community welfare ($\$26.754519\text{ AUD}$)**.
   - **Fairness is an orthogonal distributional choice on the Pareto frontier.** Selecting an equilibrium alters the division of surplus across households without sacrificing any feasible physical energy trading or aggregate economic efficiency.

---

## 2. Dataset-Wide Quantitative Statistics

| Metric | All PNE ($E_{\text{PNE}}$) | Pareto-Undominated PNE ($E_{\text{Pareto}}$) | Mathematical Status |
| :--- | :---: | :---: | :--- |
| **Total Evaluated Hours** | 1,752 | 1,752 | Complete period coverage |
| **Mixed-Market Hours ($N_S \ge 1, N_B \ge 1$)** | 866 | 866 | Active P2P trading hours |
| **One-Sided Hours ($N_S = 0$ or $N_B = 0$)** | 886 | 886 | No feasible P2P trade ($Q^* = 0$) |
| **Total Equilibria Evaluated** | **315,280** | **312,810** (99.22%) | 2,470 Pareto-dominated equilibria |
| **Equilibria with Zero Traded Volume** | 304,386 | 303,520 | 886 one-sided hrs + uncrossed mixed |
| **Equilibria with Partial Traded Volume ($0 < Q < Q^*$)** | **1,604** | **0** (0.00%) | All partial traps Pareto-dominated |
| **Equilibria with Full Feasible Volume ($Q = Q^* > 0$)** | 9,290 | 9,290 (100.0%) | 100% of positive Pareto equilibria |
| **Hours where Volume Varies Across Equilibria** | **866 (49.43%)** | **0 (0.00%)** | 100% of mixed hours vary in $E_{\text{PNE}}$; 0% in $E_{\text{Pareto}}$ |
| **Hours where Welfare Varies Across Equilibria** | **866 (49.43%)** | **0 (0.00%)** | 100% of mixed hours vary in $E_{\text{PNE}}$; 0% in $E_{\text{Pareto}}$ |
| **Hours Achieving Max Feasible Volume $Q^*(t)$** | 886 (50.57%) | **1,752 (100.00%)** | Representative & Pareto always hit $Q^*$ |

---

## 3. Detailed Answers to Mandatory Audit Questions

### Question 1: Do all PNE in each mixed-market hour produce identical physical volume?
**NO.** In all 866 mixed-market hours (100.00%), the set of all PNE produces varying physical volumes:
$$Q_{\min}^{\text{PNE}}(t) = 0.000000\text{ kWh} < Q_{\max}^{\text{PNE}}(t) = Q^*(t)$$
Uncrossed price profiles (such as sellers asking $\$0.30$ and buyers bidding $\$0.08$) produce zero trade ($Q = 0$). Furthermore, in many hours, partial coordination equilibria produce intermediate volume ($0 < Q < Q^*$).

### Question 2: Do all PNE produce identical community welfare?
**NO.** Because community welfare in our double auction is strictly proportional to traded volume ($\Delta W = (p_{\text{imp}} - p_{\text{exp}}) Q = \$0.22 \times Q$), any equilibrium with submaximal volume yields submaximal welfare:
$$\Delta W_{\min}^{\text{PNE}}(t) = \$0.000000\text{ AUD} < \Delta W_{\max}^{\text{PNE}}(t) = 0.22 \times Q^*(t)$$

### Question 3: Can two Pareto-undominated PNE have different community welfare?
**NO.** Across all 1,752 hours in the dataset, **not a single pair of Pareto-undominated equilibria has different community welfare**.
Every single equilibrium in $E_{\text{Pareto}}$ achieves the exact maximum feasible physical volume $Q^*(t) = \min(\sum s_i, \sum d_j)$. Consequently, community welfare across all Pareto-undominated equilibria is strictly identical:
$$\Delta W(e) = 0.22 \times Q^*(t) \quad \forall e \in E_{\text{Pareto}}$$

### Question 4: Does the existing representative equilibrium always achieve maximum feasible physical volume?
**YES.** In **1,752 out of 1,752 hours (100.00%)**, the Phase 8C representative equilibrium achieves:
$$Q_{\text{selected}}(t) = Q^*(t) = \min\left(\sum_{i \in \text{Sellers}} s_i(t),\, \sum_{j \in \text{Buyers}} d_j(t)\right)$$
Over the full held-out test period, total physical volume cleared by the representative equilibrium is **121.611449 kWh**, matching the Phase 7.1 physical baseline to 12 decimal places ($0.000000\text{ kWh}$ error).

### Question 5: Is welfare invariance a mathematical property of this mechanism or only an observed property of the evaluated dataset?
**Across the full set of all PNE ($E_{\text{PNE}}$), welfare invariance is unequivocally FALSE both mathematically and empirically.** Coordination failure (zero-trade uncrossed profiles) and partial-trade boundary profiles are genuine weak PNE that destroy economic welfare.

**Across the Pareto-undominated set ($E_{\text{Pareto}}$), welfare invariance is an EMPIRICAL RESULT rigorously established for this 1,752-hour dataset, NOT an unconditional universal theorem.**

#### Distinction Between Empirical Finding and General Theoretical Claim:
1. **Empirical Result (Verified across 1,752 hours):**
   In every one of the 866 mixed-market hours evaluated, every member of $E_{\text{Pareto}}$ achieves the exact maximum feasible volume $Q^*(t) = \min(\sum s_i, \sum d_j)$ and maximum community welfare $\Delta W^*(t) = \$0.22 \times Q^*(t)$. All 2,470 submaximal equilibria (866 zero-trade + 1,604 partial-trade) were strictly Pareto-dominated.
2. **Why Higher Volume Does Not Automatically Guarantee Pareto Dominance in General:**
   In general game theory, a profile $e'$ with higher physical volume ($Q(e') > Q(e)$) and higher total community welfare ($\Delta W(e') > \Delta W(e)$) does **NOT** automatically Pareto-dominate $e$. Pareto dominance requires that *every* active player is weakly better off ($U_i(e') \ge U_i(e) \; \forall i$) and at least one is strictly better off.
   In a general multi-player double auction, a seller could theoretically earn higher profit by selling a smaller quantity at a high monopoly price than by selling a larger quantity at a competitive price ($q_{\text{small}} \times (p_{\text{high}} - 0.08) > q_{\text{large}} \times (p_{\text{low}} - 0.08)$). If such a monopoly outcome were a Nash equilibrium and no full-crossing profile gave that seller at least as much payoff, the submaximal equilibrium would survive the Pareto filter, creating an efficiency-fairness trade-off.
3. **Conclusion for Phase 8D:**
   Because all 1,604 partial equilibria in our specific 1,752-hour dataset were Pareto-dominated by full-crossing profiles, welfare invariance on $E_{\text{Pareto}}$ is a **verified empirical property of this dataset and price grid**, providing the foundation for our comparative evaluation without making unproven universal claims.

---

## 4. Empirical Case Study: Anatomy of a Partial Coordination Trap

To illustrate why submaximal PNE exist and why the Pareto filter successfully eliminates them, consider **Timestamp `2013-04-19 02:00:00`**:

- **Physical Roles & Meter Flows:**
  - `H002` (Seller): Surplus $s = 0.149548\text{ kWh}$
  - `H001` (Buyer): Deficit $d = 0.690000\text{ kWh}$
  - `H003` (Buyer): Deficit $d = 0.054060\text{ kWh}$
  - Max Feasible Volume: $Q^* = \min(0.149548, 0.690000 + 0.054060) = 0.149548\text{ kWh}$
  - Max Community Welfare: $\Delta W^* = 0.22 \times 0.149548 = \$0.032900\text{ AUD}$

### Submaximal Equilibrium (Non-Pareto PNE)
- **Price Profile:** `H001` bids $\$0.08$, `H002` asks $\$0.30$, `H003` bids $\$0.30$.
- **Clearing Result:**
  - `H001` (bidding $\$0.08$) does not cross `H002` (asking $\$0.30$). `H001` is completely excluded from trade.
  - Only `H003` crosses `H002`. Cleared volume is limited to `H003`'s deficit: $Q = 0.054060\text{ kWh}$.
  - Transaction Price: $(0.30 + 0.30)/2 = \$0.30/\text{kWh}$.
  - Cleared Volume: $0.054060\text{ kWh}$ (Leaves $0.095488\text{ kWh}$ of solar surplus dumped to grid!).
  - Payoffs: $U_{\text{H001}} = \$0.00$, $U_{\text{H002}} = \$0.011893$, $U_{\text{H003}} = 0.054060 \times (0.30 - 0.30) = \$0.00$.
  - Community Welfare: $\Delta W = \$0.011893\text{ AUD}$ (Only 36.1% of potential welfare!).
- **Why is this a Nash Equilibrium?**
  - If `H001` unilaterally raises its bid to $\$0.30$, it trades at price $\$0.30$, giving payoff $(0.30 - 0.30) = \$0.00$ (no strict gain).
  - If `H003` lowers its bid, it ceases trading, giving payoff $\$0.00$ (no strict gain).
  - If `H002` changes ask, it cannot increase price above $\$0.30$.
  - Hence, no player has a strictly profitable unilateral deviation!

### Full-Crossing Equilibrium (Pareto-Undominated PNE)
- **Price Profile:** `H001` bids \$0.26, `H002` asks \$0.26, `H003` bids \$0.30.
- **Clearing Result:**
  - Both buyers cross seller `H002`. All $0.149547582019\text{ kWh}$ of seller surplus is cleared ($Q = Q^*$).
  - **Transaction 1 (`H002` $\to$ `H003`):** $0.054059572773\text{ kWh}$ at $p_{\text{tx}} = (0.26 + 0.30)/2 = \$0.280000/\text{kWh}$.
    - `H003` Buyer Benefit: $0.054059572773 \times (0.30 - 0.28) = \$0.001081191455\text{ AUD}$.
    - `H002` Seller Benefit: $0.054059572773 \times (0.28 - 0.08) = \$0.010811914555\text{ AUD}$.
  - **Transaction 2 (`H002` $\to$ `H001`):** $0.095488009246\text{ kWh}$ at $p_{\text{tx}} = (0.26 + 0.26)/2 = \$0.260000/\text{kWh}$.
    - `H001` Buyer Benefit: $0.095488009246 \times (0.30 - 0.26) = \$0.003819520370\text{ AUD}$.
    - `H002` Seller Benefit: $0.095488009246 \times (0.26 - 0.08) = \$0.017187841664\text{ AUD}$.
  - **Exact Net Household Payoffs:**
    - $U_{\text{H001}} = \$0.003819520370\text{ AUD}$
    - $U_{\text{H002}} = \$0.010811914555 + \$0.017187841664 = \$0.027999756219\text{ AUD}$
    - $U_{\text{H003}} = \$0.001081191455\text{ AUD}$
  - **Payoff Sum:** $0.003819520370 + 0.027999756219 + 0.001081191455 = \$0.032900468044\text{ AUD}$.
  - **Community Welfare:** $\Delta W = 0.22 \times 0.149547582019 = \$0.032900468044\text{ AUD}$.
  - **Conservation Residual:** $|\sum_{i=1}^3 U_i - \Delta W| = 0.000000000000\text{ AUD}$ (exact machine zero).
- **Pareto Dominance:**
  - $U(e^{\text{full}}) = (0.003820, 0.028000, 0.001081) > (0.0, 0.011893, 0.0) = U(e^{\text{sub}})$ for **all three households**.
  - Therefore, the submaximal equilibrium is strictly Pareto-dominated and eliminated by the Pareto filter.

---

## 5. Implications for Phase 8D Design and Implementation

1. **Validity of Pareto-Constrained Selection:**
   Every selection strategy in Phase 8D (Strategies A, B, C, D, E, F) operates strictly on $E_{\text{Pareto}}$. Because all members of $E_{\text{Pareto}}$ achieve maximum physical volume $Q^*(t)$ and maximum community welfare $\Delta W^*(t)$, **no selection strategy sacrifices physical trading volume or community welfare**.
2. **Clarification of Research Framing:**
   - **Full Game ($E_{\text{PNE}}$):** Demonstrates a severe risk of market coordination failure (zero-trade or partial-trade traps causing efficiency losses up to 100%).
   - **Pareto Policy ($E_{\text{Pareto}}$):** Resolves the efficiency failure entirely, turning equilibrium selection into a pure distributional optimization problem that determines fairness across households.
