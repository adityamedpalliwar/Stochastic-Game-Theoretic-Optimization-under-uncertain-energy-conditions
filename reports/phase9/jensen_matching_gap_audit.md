# Phase 9 — Jensen's Inequality and Matching Gap Audit

**Author:** Antigravity (Advanced Agentic Coding / Google DeepMind)  
**Date:** November 2026  
**Scope:** Full-Horizon (1,752-hour) Test Dataset Validation  
**Target Investigation:** Mathematical and empirical audit of the $-18.70\%$ volume reduction across the 473 overlapping tradeable timestamps between Phase 8C (Deterministic) and Phase 8E (Stochastic Expected-Payoff).

---

## 1. Executive Summary

In the Phase 9 validation reports, the $-18.70\%$ reduction in cleared energy volume ($78.3303\,\text{kWh} \to 63.6854\,\text{kWh}$) within the 473 timestamps where both Phase 8C and Phase 8E trade was originally attributed to **Jensen's inequality** on the concave bilateral matching operator $\min(S, D)$.

This audit performed an independent, scenario-level physical reconstruction across all 473 overlapping timestamps ($473 \times 1,000 = 473,000$ scenario evaluations) using synchronized Monte Carlo residual pools and frozen Phase 7.1 battery dispatch decisions to evaluate the validity of that attribution.

### Key Scientific Findings:
1. **Mathematical Jensen Inequality Holds 100% of the Time:**
   For every single one of the 473 timestamps ($100.0\%$), the physical Jensen gap:
   $$J_{\text{gap}} = \min\big(\mathbb{E}[S_s], \mathbb{E}[D_s]\big) - \mathbb{E}[\min(S_s, D_s)] \ge 0$$
   holds strictly positive ($\min J_{\text{gap}} = 0.000386\,\text{kWh} > 0$). Aggregated across all 473 hours, the pure physical Jensen gap accounts for a **$65.8524\,\text{kWh}$ ($42.24\%$) volume compression** from mean positions ($155.9049\,\text{kWh}$) to expected physical matching ($90.0524\,\text{kWh}$).
2. **Phase 8C Deterministic Volume Is NOT $\min(\mathbb{E}[S], \mathbb{E}[D])$:**
   Phase 8C deterministic volume ($78.3303\,\text{kWh}$) is an ex-post equilibrium cleared on a single realized sample path. Crucially, the expected physical matching under uncertainty across all 1,000 scenarios is **$90.0524\,\text{kWh}$**, which is **$14.97\%$ HIGHER than Phase 8C volume** ($90.0524 > 78.3303\,\text{kWh}$).
3. **The $-18.70\%$ Volume Reduction Is NOT a Jensen Effect:**
   Attributing the difference between Phase 8C ($78.3303\,\text{kWh}$) and Phase 8E ($63.6854\,\text{kWh}$) to Jensen's inequality is a mathematical category error. If Jensen's inequality governed that gap, Phase 8C would have to represent the uncompressed upper bound $\min(\mathbb{E}[S], \mathbb{E}[D])$, and expected physical matching would have to be lower than Phase 8C. In reality, expected physical matching exceeds Phase 8C.
4. **Actual Causal Driver: Option 1A Role-Conflict Clamping:**
   The volume reduction from expected physical potential ($90.0524\,\text{kWh}$) to Phase 8E stochastic cleared volume ($63.6854\,\text{kWh}$) is entirely driven by **Option 1A role-conflict clamping** ($\mathbf{-26.3671\,\text{kWh}}$ or $\mathbf{-29.28\%}$), which suppresses orders when realized net positions oppose ex-ante roles.
5. **Zero Strategic Quantity Withholding in Selected Equilibria:**
   In all 473 overlapping hours, the strategic double-auction pricing mechanism in the selected pure Nash equilibria cleared **$100.0\%$** of the role-clamped orders. Strategic price competition caused **$0.0000\,\text{kWh}$ ($0.00\%$)** volume loss.

---

## 2. Mathematical Framework & Distinction of Quantities

Let $i \in \{1, 2, 3\}$ index households (H001, H002, H003) and $s \in \{1, \dots, M\}$ index Monte Carlo weather scenarios ($M = 1,000$).  
For each scenario $s$, the post-battery net position is:
$$n_i(s) = \big(D_i(s) + C_{0,i}\big) - \big(S_i(s) + B_{0,i}\big)$$
where $C_{0,i}, B_{0,i} \ge 0$ are the frozen first-stage battery charge and discharge decisions from Phase 7.1 Stochastic MPC.

We define five distinct volumetric quantities:

### 2.1 Pure Physical Quantities (Unconstrained Bilateral Matching)
- **Scenario Physical Surplus and Deficit:**
  $$S_s = \sum_{i=1}^3 \max(0, -n_i(s)), \quad D_s = \sum_{i=1}^3 \max(0, n_i(s))$$
- **Expected Physical Matching Quantity:**
  $$Q_{\text{phys, exp}} = \mathbb{E}[\min(S_s, D_s)] = \frac{1}{M} \sum_{s=1}^M \min(S_s, D_s)$$
- **Matching Quantity at Expected Physical Positions:**
  $$Q_{\text{mean, pos}} = \min\big(\mathbb{E}[S_s], \mathbb{E}[D_s]\big) = \min\left(\frac{1}{M}\sum_{s=1}^M S_s, \frac{1}{M}\sum_{s=1}^M D_s\right)$$
- **The Physical Jensen Gap:**
  Since $f(x, y) = \min(x, y)$ is concave on $\mathbb{R}^2$, Jensen's inequality guarantees:
  $$J_{\text{gap}} = Q_{\text{mean, pos}} - Q_{\text{phys, exp}} = \min\big(\mathbb{E}[S_s], \mathbb{E}[D_s]\big) - \mathbb{E}[\min(S_s, D_s)] \ge 0$$

### 2.2 Role-Constrained Quantities (Option 1A Policy)
Under Option 1A, households are classified ex-ante based on their expected net position $\mathbb{E}[n_i] = \frac{1}{M}\sum_{s=1}^M n_i(s)$:
- Ex-ante Seller $\mathcal{S}_{\text{ex}} = \{i \mid \mathbb{E}[n_i] < -\epsilon\}$
- Ex-ante Buyer $\mathcal{B}_{\text{ex}} = \{i \mid \mathbb{E}[n_i] > +\epsilon\}$
- Inactive $\mathcal{I}_{\text{ex}} = \{i \mid |\mathbb{E}[n_i]| \le \epsilon\}$

In each scenario $s$, orders conflicting with ex-ante roles are clamped to zero:
$$S_{\text{clamp}, s} = \sum_{i \in \mathcal{S}_{\text{ex}}} \max(0, -n_i(s)), \quad D_{\text{clamp}, s} = \sum_{i \in \mathcal{B}_{\text{ex}}} \max(0, n_i(s))$$
- **Expected Role-Clamped Matching Quantity:**
  $$Q_{\text{clamp, exp}} = \mathbb{E}[\min(S_{\text{clamp}, s}, D_{\text{clamp}, s})] = \frac{1}{M}\sum_{s=1}^M \min(S_{\text{clamp}, s}, D_{\text{clamp}, s})$$
  Because $S_{\text{clamp}, s} \le S_s$ and $D_{\text{clamp}, s} \le D_s$, it is mathematically guaranteed that:
  $$Q_{\text{clamp, exp}} \le Q_{\text{phys, exp}}$$
  The quantity $\Delta Q_{\text{clamp}} = Q_{\text{phys, exp}} - Q_{\text{clamp, exp}} \ge 0$ measures the **Option 1A role-clamping loss**.

### 2.3 Strategic Double Auction Quantities
- **Phase 8E Expected Auction Cleared Volume:**
  $$Q_{\text{stoch}} = \mathbb{E}[Q_{\text{auction}}(a^*, \omega_s)]$$
  where $a^*$ is the selected pure Nash equilibrium price profile. Since the auction clears matched orders subject to bid-ask price crossing ($p_{\text{bid}} \ge p_{\text{ask}}$), cleared quantity cannot exceed submitted orders:
  $$Q_{\text{stoch}} \le Q_{\text{clamp, exp}}$$
  The quantity $\Delta Q_{\text{pricing}} = Q_{\text{clamp, exp}} - Q_{\text{stoch}} \ge 0$ measures the **strategic pricing quantity withholding**.

### 2.4 Ex-Post Deterministic Benchmark Quantity
- **Phase 8C Deterministic Cleared Volume:**
  $$Q_{\text{det}} = Q_{\text{auction}}(a_{\text{det}}^*, \omega_{\text{actual}})$$
  $Q_{\text{det}}$ is an ex-post equilibrium cleared on the single realized meter point $\omega_{\text{actual}}$. It possesses **no mathematical inequality relationship** with $\min(\mathbb{E}[S], \mathbb{E}[D])$ or $\mathbb{E}[\min(S, D)]$.

---

## 3. Full-Horizon Empirical Audit Across 473 Overlapping Hours

The audit evaluated all 473 timestamps where both Phase 8C and Phase 8E clear positive bilateral trade ($Q_{\text{det}} > 0$ and $Q_{\text{stoch}} > 0$).

### 3.1 Verification of Jensen's Inequality
| Metric | Value | Status |
|---|:---:|:---:|
| Total Overlapping Timestamps Evaluated | **473** | Complete |
| Timestamps Satisfying $J_{\text{gap}} \ge -10^{-9}\,\text{kWh}$ | **473 (100.0%)** | **Fully Verified** |
| Timestamps Violating Jensen's Inequality | **0 (0.0%)** | None |
| Minimum Measured $J_{\text{gap}}$ | $+0.000386\,\text{kWh}$ | Strictly Positive |
| Maximum Measured $J_{\text{gap}}$ | $+0.325207\,\text{kWh}$ | Significant Dispersion |
| Mean Measured $J_{\text{gap}}$ per Timestamp | $+0.139223\,\text{kWh}$ | Consistently Positive |

> **Conclusion on Mathematical Validity:** Jensen's inequality holds strictly and unequivocally on physical matching across all 473 timestamps without a single exception.

---

### 3.2 Aggregate Volumetric Breakdown (473 Overlapping Hours)

The exact measured aggregate sums across the 473 overlapping hours are presented below:

```
[Layer 0: Expected Position Matching]
      Q_mean_pos = 155.904859 kWh
           │
           │  Pure Physical Jensen Gap: -65.852438 kWh (-42.24%)
           ▼
[Layer 1: Expected Physical Matching]
      Q_phys_expected = 90.052420 kWh
           │                                 ┌───────────────────────────────────┐
           │                                 │ Phase 8C Deterministic Ex-Post    │
           │                                 │ Q_det = 78.330286 kWh             │
           │                                 │ (Single actual realization path)  │
           │                                 └───────────────────────────────────┘
           │  Option 1A Role Clamping: -26.367053 kWh (-29.28%)
           ▼
[Layer 2: Role-Clamped Expected Matching]
      Q_clamp_expected = 63.685367 kWh
           │
           │  Strategic Pricing Withholding: -0.000000 kWh (0.00%)
           ▼
[Layer 3: Phase 8E Stochastic Auction Cleared]
      Q_stoch = 63.685367 kWh
```

### Detailed Numerical Summary Table:

| Layer / Metric | Formula / Source | Aggregate Volume (kWh) | Share / Delta |
|---|---|:---:|:---:|
| **Matching at Mean Positions ($Q_{\text{mean, pos}}$)** | $\min(\mathbb{E}[S_s], \mathbb{E}[D_s])$ | **155.904859** | 100.00% (Baseline) |
| **Expected Physical Matching ($Q_{\text{phys, exp}}$)** | $\mathbb{E}[\min(S_s, D_s)]$ | **90.052420** | 57.76% of $Q_{\text{mean, pos}}$ |
| **True Physical Jensen Gap ($J_{\text{gap}}$)** | $Q_{\text{mean, pos}} - Q_{\text{phys, exp}}$ | **65.852438** | **-42.24%** (Jensen effect) |
| **Option 1A Role-Clamped Matching ($Q_{\text{clamp, exp}}$)** | $\mathbb{E}[\min(S_{\text{clamp}}, D_{\text{clamp}})]$ | **63.685367** | 70.72% of $Q_{\text{phys, exp}}$ |
| **Option 1A Role-Clamping Loss ($\Delta Q_{\text{clamp}}$)** | $Q_{\text{phys, exp}} - Q_{\text{clamp, exp}}$ | **26.367053** | **-29.28%** of $Q_{\text{phys, exp}}$ |
| **Phase 8E Stochastic Cleared Volume ($Q_{\text{stoch}}$)** | Cleared Auction Quantity | **63.685367** | 100.00% of $Q_{\text{clamp, exp}}$ |
| **Strategic Pricing Loss ($\Delta Q_{\text{pricing}}$)** | $Q_{\text{clamp, exp}} - Q_{\text{stoch}}$ | **0.000000** | **0.00%** (No withholding) |
| **Phase 8C Deterministic Cleared Volume ($Q_{\text{det}}$)** | Phase 8C Ex-Post Cleared | **78.330286** | Comparison Benchmark |
| **Reported Phase 8C vs 8E Difference ($\Delta Q$)** | $Q_{\text{stoch}} - Q_{\text{det}}$ | **-14.644919** | **-18.70%** of $Q_{\text{det}}$ |

---

## 4. Multi-Layer Attribution and Root Cause Analysis

### 4.1 Why the $-18.70\%$ Difference Is Not a Jensen Effect
1. **Directional Incompatibility:**
   Jensen's inequality proves that $\mathbb{E}[\min(S, D)] \le \min(\mathbb{E}[S], \mathbb{E}[D])$. If the $-18.70\%$ drop from Phase 8C to Phase 8E were caused by Jensen's inequality, then Phase 8C would have to correspond to $\min(\mathbb{E}[S], \mathbb{E}[D])$, and Phase 8E would correspond to $\mathbb{E}[\min(S, D)]$.
   However:
   $$Q_{\text{phys, exp}} = 90.0524\,\text{kWh} > Q_{\text{det}} = 78.3303\,\text{kWh} \quad (+11.7221\,\text{kWh}, \text{ or } +14.97\%)$$
   Expected physical matching across the Monte Carlo distribution is actually **greater** than the deterministic ex-post volume.
2. **Category Error:**
   $Q_{\text{det}}$ is the auction-cleared volume on the single historical ex-post weather trajectory $\omega_{\text{actual}}$. It is not an expectation $\min(\mathbb{E}[S], \mathbb{E}[D])$. Comparing an ex-post realization $Q_{\text{det}}$ to an ex-ante expectation $Q_{\text{stoch}}$ confuses an empirical realization sample path with an analytical upper bound.

### 4.2 What Actually Explains the $-18.70\%$ Difference?
The drop from Phase 8C ($78.3303\,\text{kWh}$) to Phase 8E ($63.6854\,\text{kWh}$) is a compound effect of two factors:
1. **Option 1A Role-Conflict Clamping (Dominant Driver):**
   In Phase 8E, market participants commit to fixed roles (seller or buyer) based on $\mathbb{E}[n_i]$. When individual scenarios generate weather realizations that flip a participant's position (e.g. an ex-ante seller experiences high demand or sudden cloud cover and has a deficit), Option 1A forbids them from submitting an order on the opposing side. This suppresses **$26.3671\,\text{kWh}$** of potential matching that would otherwise clear physically.
   Phase 8C suffers no such suppression: because Phase 8C has ex-post perfect foresight, participants trade their exact realized position without role-conflict restrictions.
2. **Sample Realization Path vs. Monte Carlo Distribution:**
   The actual ex-post test horizon drew weather conditions that yielded $78.3303\,\text{kWh}$ of ex-post tradeable volume, whereas the synthetic residual pool generated an expected physical potential of $90.0524\,\text{kWh}$.

### 4.3 Strategic Pricing Mechanism in Selected Equilibria
A crucial scientific result of this audit is that **strategic double auction pricing did not cause any volume reduction** in the 473 overlapping hours:
$$Q_{\text{stoch}} = Q_{\text{clamp, exp}} = 63.685367\,\text{kWh} \implies \Delta Q_{\text{pricing}} = 0.000000\,\text{kWh}$$
In every one of the 473 overlapping hours, the selected pure Nash equilibrium profiles crossed bids and asks such that all submitted role-clamped orders cleared. There was zero equilibrium quantity rationing or uncrossed bid-ask spread deadlock.

---

## 5. Preservation Audit

This investigation adhered strictly to all preservation rules:
- **Core Engine Files (`src/`):** 0 files modified.
- **Dashboard Application (`dashboard/`):** 0 files modified.
- **Test Suite (`tests/`):** 0 tests modified.
- **Frozen Benchmark Artifacts (`reports/phase6_*.csv`, `reports/phase7_*.csv`, `reports/phase8c_*.csv`, `reports/phase8d_*.csv`, `reports/phase8e_*.csv`):** 0 files modified.
- **Phase 9 Numerical CSV Files (`reports/phase9/*.csv`):** 0 files modified.
- **Phase 9 Existing Markdown Reports:** 0 files modified.
- **Scratch Scripts:** Persisted exclusively in the brain scratch directory (`scratch/compute_jensen.py`, `scratch/jensen_audit_results.csv`).

---

## 6. Exact Recommended Wording Corrections

Per the user's instructions, no existing report has been edited. Below are the exact surgical text replacements recommended for review.

### 6.1 Recommended Corrections for `reports/phase9/final_research_integrity_audit.md`

#### A. Executive Summary Table (Row 2, Page 1)
- **Current Text:**
  ```markdown
  | **Rule 2: Jensen Inequality & Volume Attribution** | Volume Delta $= -33.9642\,\text{kWh}$ ($-27.93\%$) verified. 144-hour shift decomposed into 473 mutually traded, 393 8C-only, 249 8E-only, 637 zero-trade hours. Jensen inequality applies on intensive margin. | **PARTIALLY VERIFIED** |
  ```
- **Recommended Replacement:**
  ```markdown
  | **Rule 2: Jensen Inequality & Volume Attribution** | Volume Delta $= -33.9642\,\text{kWh}$ ($-27.93\%$) verified. 144-hour shift decomposed into 473 mutually traded, 393 8C-only, 249 8E-only, 637 zero-trade hours. Mathematical Jensen inequality verified ($J_{\text{gap}} \ge 0$ in 473/473 hours), but audit proves the $-18.70\%$ volume drop is driven by Option 1A role clamping, not Jensen's inequality. | **CORRECTED** |
  ```

#### B. Section 3.3 (Point 2: Role of Jensen's Inequality)
- **Current Text:**
  ```markdown
  2. **Role of Jensen's Inequality:**
     - Jensen's inequality ($\mathbb{E}[\min(S, D)] \le \min(\mathbb{E}[S], \mathbb{E}[D])$) applies strictly to the **intensive margin** within the **473 overlapping hours** where both models clear trade. Within these 473 hours, volume falls from $78.3303\,\text{kWh}$ to $63.6854\,\text{kWh}$ (a pure dispersion compression of **$-18.70\%$**).
  ```
- **Recommended Replacement:**
  ```markdown
  2. **Role of Jensen's Inequality and Matching Decomposition:**
     - Mathematical Jensen's inequality ($\mathbb{E}[\min(S, D)] \le \min(\mathbb{E}[S], \mathbb{E}[D])$) holds in 100% of the 473 overlapping hours, compressing volume from mean positions ($155.9049\,\text{kWh}$) to expected physical matching ($90.0524\,\text{kWh}$), a true Jensen gap of $65.8524\,\text{kWh}$ ($-42.24\%$).
     - However, the $-18.70\%$ reduction from Phase 8C ($78.3303\,\text{kWh}$) to Phase 8E ($63.6854\,\text{kWh}$) cannot be attributed to Jensen's inequality because expected physical matching ($90.0524\,\text{kWh}$) actually exceeds Phase 8C deterministic volume ($78.3303\,\text{kWh}$).
     - Instead, the drop to $63.6854\,\text{kWh}$ is driven by **Option 1A role-conflict clamping** ($-26.3671\,\text{kWh}$ or $-29.28\%$), while strategic pricing withholding is exactly $0.0000\,\text{kWh}$ ($0.00\%$).
  ```

#### C. Section 5 (Recommended Correction 3)
- **Current Text:**
  ```markdown
  ### Recommended Correction 3: Causal Attribution of Volume Loss
  - **Target File:** `reports/phase9/full_horizon_validation_report.md`, Section 6.3.
  - **Current Text:** Describes Jensen's inequality as governing the $-27.93\%$ volume reduction.
  - **Recommended Text:** Clarify the intensive vs. extensive margin distinction:
    > *"Jensen's inequality applies strictly on the intensive margin within the 473 overlapping hours where both models clear trade, compressing volume by $-18.70\%$ ($78.33 \to 63.69\,\text{kWh}$). The remaining difference is driven by the extensive margin ($43.28\,\text{kWh}$ lost across 393 Deterministic-Only hours vs. $23.96\,\text{kWh}$ gained across 249 Stochastic-Only hours). No aggregate numerical percentage decomposition among mechanisms is asserted."*
  ```
- **Recommended Replacement:**
  ```markdown
  ### Recommended Correction 3: Causal Attribution of Volume Loss
  - **Target File:** `reports/phase9/full_horizon_validation_report.md`, Section 6.2 and Section 6.3.
  - **Current Text:** Attributes the $-18.70\%$ intensive-margin volume reduction to Jensen's inequality.
  - **Recommended Text:** Replace with rigorous 4-layer attribution:
    > *"Within the 473 overlapping hours, mathematical Jensen's inequality holds in 100% of timestamps, reducing expected physical matching from mean positions ($155.90\,\text{kWh} \to 90.05\,\text{kWh}$, $-42.24\%$). However, expected physical matching ($90.05\,\text{kWh}$) exceeds Phase 8C deterministic volume ($78.33\,\text{kWh}$). The observed $-18.70\%$ drop ($78.33 \to 63.69\,\text{kWh}$) is caused by Option 1A role-conflict clamping (suppressing $26.37\,\text{kWh}$ of cross-role trades), whereas strategic double auction pricing causes zero quantity loss ($0.00\,\text{kWh}$) in selected equilibria. The remaining $-19.32\,\text{kWh}$ aggregate difference is governed by the extensive margin ($43.28\,\text{kWh}$ lost across 393 Deterministic-Only hours vs. $23.96\,\text{kWh}$ gained across 249 Stochastic-Only hours)."*
  ```

---

### 6.2 Recommended Corrections for `reports/phase9/full_horizon_validation_report.md`

#### A. Section 6.2 (Jensen's Inequality Formulation)
- **Current Text:**
  ```markdown
  ### 6.2 Fundamental Mathematical Distinction: Jensen's Inequality
  The bilateral double-auction clearing quantity follows the matching function:
  $$Q(S, D) = \min(S, D)$$

  Because the bivariate minimum operator $f(S, D) = \min(S, D)$ is concave, Jensen's inequality dictates:
  $$\mathbb{E}[\min(S, D)] \le \min\big(\mathbb{E}[S], \mathbb{E}[D]\big)$$

  This mathematical inequality guarantees that evaluating supply and demand variance under Monte Carlo realizations will weakly depress expected volume compared to evaluating at the deterministic point expectation.
  ```
- **Recommended Replacement:**
  ```markdown
  ### 6.2 Fundamental Mathematical Distinction: Jensen's Inequality vs. Realized Benchmarks
  The unconstrained bilateral matching potential follows the function:
  $$Q(S, D) = \min(S, D)$$

  Because the bivariate minimum operator $f(S, D) = \min(S, D)$ is concave, Jensen's inequality guarantees:
  $$\mathbb{E}[\min(S_s, D_s)] \le \min\big(\mathbb{E}[S_s], \mathbb{E}[D_s]\big)$$

  An empirical audit across all 473 overlapping tradeable hours verifies that this inequality holds in 100% of timestamps, compressing volume from mean positions ($155.9049\,\text{kWh}$) to expected physical matching ($90.0524\,\text{kWh}$), a true Jensen gap of $65.8524\,\text{kWh}$ ($-42.24\%$).

  Crucially, Phase 8C deterministic volume ($78.3303\,\text{kWh}$) is an ex-post equilibrium outcome on a single realized sample path, not the mean position expectation $\min(\mathbb{E}[S], \mathbb{E}[D])$. In fact, expected physical matching under uncertainty ($90.0524\,\text{kWh}$) is $14.97\%$ higher than Phase 8C volume. Therefore, Jensen's inequality cannot be directly equated with the empirical difference between Phase 8C and Phase 8E.
  ```

#### B. Section 6.3 (Contributing Mechanisms to Volume Differences)
- **Current Text:**
  ```markdown
  ### 6.3 Contributing Mechanisms to Volume Differences
  The observed $-27.93\%$ reduction in cleared energy volume ($\Delta Q = -33.9642\,\text{kWh}$) between Phase 8C ($121.6114\,\text{kWh}$) and Phase 8E ($87.6472\,\text{kWh}$) stems from three distinct interacting mechanisms:
  1. **Intensive-Margin Concave Matching (Jensen Gap):** Within the **473 overlapping hours** where both models clear bilateral trade, Jensen's inequality $\mathbb{E}[\min(S, D)] \le \min(\mathbb{E}[S], \mathbb{E}[D])$ directly explains an intensive-margin volume compression of **$-18.70\%$** ($78.3303\,\text{kWh} \to 63.6854\,\text{kWh}$).
  2. **Extensive-Margin Participation Shifts (Contingency Decomposition):** The net 144-hour difference between Phase 8C (866 hours) and Phase 8E (722 hours) is a net difference of aggregate counts, not a single monolithic set of 144 hours. Timestamp-level contingency analysis reveals that **473 hours** traded in both models, **393 hours** traded ex-post in Phase 8C but had zero expected trade in Phase 8E (representing $43.2812\,\text{kWh}$ of lost volume due to role-conflict order clamping and scenario realization variance), and **249 hours** had zero trade ex-post in Phase 8C but cleared positive expected trade in Phase 8E (representing $23.9619\,\text{kWh}$ of newly captured volume across realizations where solar surplus met demand deficit).
  3. **Equilibrium Price Commitment Shifts:** Ex-ante expected payoff maximization selects different equilibrium prices (often closer to the fair midpoint $0.19\,\text{AUD/kWh}$) than ex-post perfect foresight, altering merit-order crossing.
  ```
- **Recommended Replacement:**
  ```markdown
  ### 6.3 Contributing Mechanisms to Volume Differences
  The observed $-27.93\%$ reduction in cleared energy volume ($\Delta Q = -33.9642\,\text{kWh}$) between Phase 8C ($121.6114\,\text{kWh}$) and Phase 8E ($87.6472\,\text{kWh}$) decomposes into extensive-margin and intensive-margin components:
  1. **Intensive-Margin Role Clamping and Dispersion (473 Overlapping Hours):**
     Within the 473 hours where both models trade, volume drops by $-18.70\%$ ($78.3303\,\text{kWh} \to 63.6854\,\text{kWh}$, $\Delta Q = -14.6449\,\text{kWh}$). A scenario-level physical audit reveals:
     - **Physical Jensen Effect:** Compresses volume from mean positions ($155.90\,\text{kWh}$) to expected physical matching ($90.05\,\text{kWh}$) by $-42.24\%$.
     - **Option 1A Role-Conflict Clamping:** Suppresses $26.3671\,\text{kWh}$ ($-29.28\%$) of physical matching when realized weather flips a household's net position against their ex-ante role, bringing cleared volume down to $63.6854\,\text{kWh}$.
     - **Strategic Pricing Effect:** Accounts for $0.0000\,\text{kWh}$ ($0.00\%$) volume loss, as selected pure Nash equilibria clear 100% of role-clamped orders.
     - **Ex-Post Sample Path Gap:** The realized historical path yielded $78.3303\,\text{kWh}$, which is lower than the expected physical potential ($90.0524\,\text{kWh}$).
  2. **Extensive-Margin Market Participation Contingency:**
     The net 144-hour difference between Phase 8C (866 hours) and Phase 8E (722 hours) is not a monolithic group of hours, but an algebraic net count:
     - **393 Deterministic-Only hours** shut down in Phase 8E ($-43.2812\,\text{kWh}$) due to ex-ante role clamping and zero tradeable expectation.
     - **249 Stochastic-Only hours** opened in Phase 8E ($+23.9619\,\text{kWh}$) where uncertainty revealed expected tradeable value that was zero on the ex-post test path.
     - Net extensive-margin impact: $-19.3193\,\text{kWh}$.
  ```

---
*Report generated strictly pursuant to the Phase 9 Final Research Integrity guidelines.*

