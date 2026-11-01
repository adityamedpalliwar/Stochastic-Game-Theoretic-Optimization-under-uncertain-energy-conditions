# Phase 8D — Final Report Reconciliation Audit

**Audit Report ID:** `reports/phase8d_final_reconciliation_audit.md`  
**Target Document:** `reports/phase8d_fairness_analysis.md`  
**Underlying Authoritative Data:**
- `reports/phase8d_strategy_comparison.csv` (13 rows $\times$ 24 metrics)
- `reports/phase8d_hourly_selection.csv` (1,752 rows $\times$ 66 columns)
- `reports/phase8c_all_equilibria.json.gz` (Complete 315,280 PNE archive)
- `reports/phase8c_hourly_equilibria.csv` (Accepted Phase 7.1 / 8C hourly flows)
**Evaluation Dataset:** Complete Phase 7.1 held-out test period (1,752 hours, `2013-04-19 00:00:00` to `2013-06-30 23:00:00`)  
**Audit Status:** COMPLETE — ALL DISCREPANCIES RECONCILED  
**Regression Test Status:** 242 / 242 tests passing cleanly (100%)

---

## 1. Executive Summary & Audit Scope

Prior to freezing the Phase 8D research report and initiating Phase 8E, an independent numerical, mathematical, and documentation audit was conducted on `reports/phase8d_fairness_analysis.md`. The audit cross-examined every quantitative assertion, tabular figure, and qualitative policy deduction against the underlying raw simulation CSVs, mathematical source modules (`src/game/fairness_metrics.py`, `src/game/equilibrium_selection.py`, `src/game/phase8d_evaluation.py`), and the accepted Phase 7.1 baseline.

### Mandatory Audit Boundaries Enforced
- **Zero modification to Phase 1–8C.1 source code, algorithms, or baseline results.**
- **Zero modification to Phase 8D selection algorithms merely to match draft figures.**
- **Zero deletion or weakening of existing regression tests.**
- **All discrepancies reconciled using actual CSV files, raw archives, and source code.**

All seven required audit checks have been investigated, verified, reconciled, and reflected in the updated `reports/phase8d_fairness_analysis.md`.

---

## 2. Item-by-Item Reconciliation Audit

### Item 1: Strategy E versus Hybrid Fairness (Lowest Gini Identification)

- **Original Draft Claim:**  
  Section 1 and Section 7 asserted that *"Strategy E (Nash Social Welfare) achieves the lowest inequality of all strategies (mean normalized Gini = 0.8073, standard Gini = 0.5382)"*, while Section 6 reported that the hybrid sensitivity variant at $w_{	ext{fair}} = 1.0$ achieved a lower normalized Gini of $0.7982$.
- **Verified Values from Authoritative CSV (`phase8d_strategy_comparison.csv`):**
  - **Among the 6 Core Selection Strategies (A–F):**
    - Strategy A (Reference): $G = 0.5412$, $G_{	ext{norm}} = 0.8118$
    - Strategy B (Seller-Favouring): $G = 0.6350$, $G_{	ext{norm}} = 0.9525$
    - Strategy C (Buyer-Favouring): $G = 0.6254$, $G_{	ext{norm}} = 0.9381$
    - Strategy D (Max-Min Fair): $G = 0.5539$, $G_{	ext{norm}} = 0.8309$
    - **Strategy E (Nash Social Welfare): $G = 0.538180 \approx 0.5382$, $G_{	ext{norm}} = 0.807270 \approx 0.8073$ $\rightarrow$ Lowest inequality among all 6 core strategies.**
    - Strategy F (Hybrid $w=0.5$): $G = 0.5412$, $G_{	ext{norm}} = 0.8118$
  - **Across All 12 Unique Evaluated Configurations (Including Sensitivity Sweep):**
    - Hybrid $w_{	ext{fair}} = 0.6$: $G = 0.5375$, $G_{	ext{norm}} = 0.8062$
    - Hybrid $w_{	ext{fair}} = 0.8$: $G = 0.5327$, $G_{	ext{norm}} = 0.7991$
    - **Hybrid $w_{	ext{fair}} = 1.0$: $G = 0.532156 \approx 0.5322$, $G_{	ext{norm}} = 0.798234 \approx 0.7982$ $\rightarrow$ Lowest inequality across all evaluated configurations.**
- **Explanation & Mathematical Resolution:**  
  The apparent conflict arose from conflating the **six core selection strategies** with the **extended parameter sweep**. Strategy E maximizes the Nash Social Welfare product:
  $$\max_{e \in E_{\text{Pareto}}} \sum_{i \in \mathcal{N}_{\text{active}}} \log(U_i(e) + \epsilon)$$
  which balances proportional fairness and total efficiency. In contrast, `Hybrid_w_fair_1.0` ($w_{\text{ref}}=0, w_{\text{fair}}=1$) directly minimizes active-participant $G_{\text{norm}}$ as its exclusive objective function:
  $$\min_{e \in E_{\text{Pareto}}} G_{\text{norm}}(U_{\text{active}}(e))$$
  Consequently, `Hybrid_w_fair_1.0` mathematically achieves the lowest normalized Gini ($0.7982$), while Strategy E achieves the lowest normalized Gini among the 6 named core strategies ($0.8073$). Both claims have been precisely partitioned and documented in the updated report.

---

### Item 2: Recalculation of Seller and Buyer Surplus Division

- **Original Draft Discrepancy:**  
  In the initial draft of `reports/phase8d_fairness_analysis.md`, Table 5.1 listed:
  - Strategy A Seller Benefit: $13.568600 AUD (50.72%)
  - Strategy A Buyer Benefit: $13.185919 AUD (49.28%)  
  Simultaneously, Section 1 and Section 8 asserted that sellers captured **63.6%** of available surplus under Strategy A, creating an apparent contradiction.
- **Verified Values from Authoritative Data:**
  - In `reports/phase8d_strategy_comparison.csv` and hourly evaluation:
    - **Total Seller Benefit (Strategy A):** **$17.017553 AUD**
    - **Total Buyer Benefit (Strategy A):** **$9.736965 AUD**
    - **Total Community Welfare:** **$26.754519 AUD**
    - **Seller Benefit Share:** $\frac{17.017553}{26.754519} = \mathbf{63.6063\% \approx 63.61\%}$
    - **Buyer Benefit Share:** $\frac{9.736965}{26.754519} = \mathbf{36.3937\% \approx 36.39\%}$
  - In unit price spread analysis:
    - Volume-Weighted Average Price (VWAP): $p_{\text{vwap}} = 0.219934\text{ AUD/kWh}$
    - Retail tariff bounds: $p_{\text{exp}} = 0.0800\text{ AUD/kWh}$, $p_{\text{imp}} = 0.3000\text{ AUD/kWh}$
    - Total unit spread: $0.3000 - 0.0800 = 0.2200\text{ AUD/kWh}$
    - **Seller unit-spread margin share:**
      $$\frac{p_{\text{vwap}} - p_{\text{exp}}}{p_{\text{imp}} - p_{\text{exp}}} = \frac{0.219934 - 0.080000}{0.220000} = \frac{0.139934}{0.220000} = \mathbf{63.6063\% \approx 63.61\%}$$
    - **Buyer unit-spread margin share:**
      $$\frac{p_{\text{imp}} - p_{\text{vwap}}}{p_{\text{imp}} - p_{\text{exp}}} = \frac{0.300000 - 0.219934}{0.220000} = \frac{0.080066}{0.220000} = \mathbf{36.3937\% \approx 36.39\%}$$
  - For Strategy B (Seller-Favouring):
    - Seller Benefit = **$23.287341 AUD (87.04%)**, Buyer Benefit = **$3.467177 AUD (12.96%)**, VWAP = **$0.271490 AUD/kWh**.
  - For Strategy C (Buyer-Favouring):
    - Seller Benefit = **$11.097911 AUD (41.48%)**, Buyer Benefit = **$15.656607 AUD (58.52%)**, VWAP = **$0.171257 AUD/kWh**.
- **Explanation & Mathematical Resolution:**  
  The figures $13.568600 (50.72%) and $13.185919 (49.28%) in the preliminary draft table were transcription errors from an earlier draft script. Under VWAP single-clearing pricing, multiplying the unit spread by the cleared volume ($Q = 121.611449\text{ kWh}$) yields:
  $$\text{Seller Dollar Surplus} = 121.611449 \times (0.219933811 - 0.08) = 17.01755349\text{ AUD}$$
  $$\text{Buyer Dollar Surplus} = 121.611449 \times (0.30 - 0.219933811) = 9.73696524\text{ AUD}$$
  Therefore, the **unit spread margin share (63.61%)** and the **realized aggregate dollar benefit share (63.61%)** are mathematically identical. Table 5.1 and Section 1 have been updated with the authoritative verified CSV figures.

---

### Item 3: Reconciliation of Max-Min Improvement Claims

- **Original Draft Claim:**  
  Section 1, Key Finding 2 stated: *"Strategy D (Max-Min Fair / Rawlsian): Protects the participant with the lowest hourly payoff, raising the mean minimum participant benefit by 14.6%..."*
- **Verified Values from Authoritative Data:**
  - **Metric 1: Hourly Mean Minimum Active Payoff (Rawlsian Hourly Objective):**
    - Strategy A: $0.00177415\text{ AUD/h}$
    - Strategy B: $0.00031888\text{ AUD/h}$
    - Strategy C: $0.00050844\text{ AUD/h}$
    - **Strategy D: $0.00227961\text{ AUD/h}$**
    - **Improvement over Strategy A:** $\frac{0.00227961 - 0.00177415}{0.00177415} = \mathbf{+28.49\%}$
    - **Improvement over Strategy B:** $\frac{0.00227961 - 0.00031888}{0.00031888} = \mathbf{+614.89\%}$
  - **Metric 2: Cumulative Test-Period Minimum Household Total Benefit:**
    - Strategy A: `H003` receives $\min(8.41, 11.09, 7.25) = \mathbf{7.251477\text{ AUD}}$
    - Strategy B: `H003` receives $\min(12.16, 10.75, 3.85) = \mathbf{3.851676\text{ AUD}}$
    - Strategy C: `H001` receives $\min(4.46, 11.61, 10.69) = \mathbf{4.455712\text{ AUD}}$
    - **Strategy D: `H001` receives $\min(7.45, 11.72, 7.58) = \mathbf{7.454905\text{ AUD}}$**
    - **Improvement over Strategy A:** $\frac{7.454905 - 7.251477}{7.251477} = \mathbf{+2.81\%}$
    - **Improvement over Strategy B:** $\frac{7.454905 - 3.851676}{3.851676} = \mathbf{+93.55\%}$
    - **Improvement over Strategy C:** $\frac{7.454905 - 4.455712}{4.455712} = \mathbf{+67.31\%}$
- **Explanation & Mathematical Resolution:**  
  The unverified "14.6%" figure was an artifact of a preliminary draft that did not match either definition. The report has been updated to provide both exact figures:
  1. Hourly mean minimum active payoff improves by **+28.49%** over Strategy A (+614.89% over Strategy B).
  2. Cumulative minimum household payoff improves by **+2.81%** over Strategy A (+93.55% over Strategy B).

---

### Item 4: Hybrid Sensitivity Step Response & Hour Concordance

- **Original Draft Claim:**  
  Section 1 and Section 7 described the hybrid sensitivity sweep as a *"smooth decrease in Gini inequality as $w_{\text{fair}}$ increases from 0.0 to 1.0"*.
- **Verified Values from Authoritative Data:**
  - Table of sensitivity sweep across all 1,752 hours:
    | Configuration | Fairness Weight ($w_{\text{fair}}$) | Reference Weight ($w_{\text{ref}}$) | Hours Identical to Strat A | Hours Differing from Strat A | Concordance (%) | Mean Norm Gini ($G_{\text{norm}}$) | VWAP (AUD/kWh) |
    | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
    | `Hybrid_w_fair_0.0` | 0.0 | 1.0 | 1,752 | **0** | **100.00%** | 0.8118 | $0.219934 |
    | `Hybrid_w_fair_0.2` | 0.2 | 0.8 | 1,752 | **0** | **100.00%** | 0.8118 | $0.219934 |
    | `Hybrid_w_fair_0.4` | 0.4 | 0.6 | 1,752 | **0** | **100.00%** | 0.8118 | $0.219934 |
    | `Strategy_F_Hybrid_w0.5` | 0.5 | 0.5 | 1,752 | **0** | **100.00%** | 0.8118 | $0.219934 |
    | `Hybrid_w_fair_0.6` | 0.6 | 0.4 | 1,727 | **25** | **98.57%** | 0.8062 | $0.219949 |
    | `Hybrid_w_fair_0.8` | 0.8 | 0.2 | 1,676 | **76** | **95.66%** | 0.7991 | $0.218925 |
    | `Hybrid_w_fair_1.0` | 1.0 | 0.0 | 1,653 | **99** | **94.35%** | **0.7982** | $0.217990 |
- **Explanation & Mathematical Resolution:**  
  Because candidate equilibrium profiles on the Pareto frontier $E_{\text{Pareto}}$ form a discrete finite set (between 10 and 14 profiles per mixed hour), the scalarized loss:
  $$\mathcal{L}(e) = (1 - w_{\text{fair}}) \frac{|p_{\text{vwap}} - 0.19|}{0.11} + w_{\text{fair}} G_{\text{norm}}(e)$$
  does not vary continuously. For all $w_{\text{fair}} \le 0.5$, the price tracking penalty dominates, yielding a completely flat response (0 differing hours, 100.00% concordance). Only when $w_{\text{fair}} > 0.5$ does the fairness penalty overcome price tracking in select hours (25 hours at 0.6, 76 at 0.8, 99 at 1.0), producing a discrete step response. The report has been revised to document this two-regime step response.

---

### Item 5: Numerical Precision and Machine Epsilon Reconciliation

- **Original Draft Discrepancy:**  
  The draft report claimed *"error = $0.000000$ down to double-precision machine epsilon across all 1,752 hours"* while simultaneously reporting scientific-notation residuals on the order of $10^{-17}$ and $10^{-14}$.
- **Verified Values from Authoritative Data:**
  - Maximum hourly payoff residual:
    $$\max_{t=1,\dots,1752} \left| \sum_{i=1}^3 U_i(t) - \Delta W(t) \right| = 5.551115 \times 10^{-17}\text{ AUD}$$
    (Strategy E exhibits $5.55 \times 10^{-17}$ AUD; all other 12 configurations exhibit $2.78 \times 10^{-17}$ AUD).
  - Aggregate cumulative welfare residual across all 1,752 hours:
    $$\left| \sum_{t=1}^{1752} \sum_{i=1}^3 U_i(t) - \sum_{t=1}^{1752} \Delta W(t) \right| = 1.776357 \times 10^{-14}\text{ AUD}$$
    (Strategy D exhibits $1.78 \times 10^{-14}$ AUD, Strategy C exhibits $1.42 \times 10^{-14}$ AUD, Strategy A/E/F exhibit $3.55 \times 10^{-15}$ AUD, Strategy B exhibits $0.00 \times 10^{0}$ AUD).
- **Explanation & Mathematical Resolution:**  
  In IEEE 754 double precision (`float64`), unit roundoff is $\epsilon_{\text{mach}} \approx 2.22 \times 10^{-16}$. Rounding errors in summation across 1,752 hours naturally accumulate to $10^{-14}\text{ AUD}$. When rounded to standard micro-AUD reporting (6 decimal places), the error is identically **$0.000000 AUD**. Both representations are mathematically correct: the scientific notation reflects raw floating-point precision, while "$0.000000 AUD" reflects practical currency precision. The text has been clarified to state both: zero error to 6 decimal places ($0.000000 AUD), bounded by machine precision ($\le 5.55 \times 10^{-17}$ hourly, $\le 1.78 \times 10^{-14}$ aggregate), well below numerical tolerance ($10^{-10}$ AUD).

---

### Item 6: Unique Strategy Configuration Count

- **Original Draft Ambiguity:**  
  Section 1 and Section 5 referred ambiguously to "13 strategy configurations" without clearly explaining the relationship between core strategies and sensitivity sweep points.
- **Verified Configuration Structure:**
  - **Core Selection Strategies (6 unique):**
    1. Strategy A: Reference Selection (Phase 8C 5-step heuristic)
    2. Strategy B: Seller-Favouring Selection
    3. Strategy C: Buyer-Favouring Selection
    4. Strategy D: Max-Min Fair Selection
    5. Strategy E: Nash Social Welfare Selection
    6. Strategy F: Hybrid Reference-Fairness Selection ($w_{\text{fair}} = 0.5, w_{\text{ref}} = 0.5$)
  - **Hybrid Sensitivity Variants (7 evaluation points):**
    - $w_{\text{fair}} \in \{0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0\}$
    - Crucially, the sweep point $w_{\text{fair}} = 0.5$ evaluates the **exact same mathematical selection rule** as Strategy F.
  - **Summary:** There are **12 unique mathematical strategy configurations**, reported across **13 tabular entries** in `reports/phase8d_strategy_comparison.csv` (where Strategy F serves as the core strategy anchor and `Hybrid_w_fair_0.5` is included in the sensitivity table for systematic completeness).
- **Explanation & Mathematical Resolution:**  
  This distinction is now explicitly stated in Section 1, Section 5, and Section 6 of `reports/phase8d_fairness_analysis.md`.

---

### Item 7: Qualitative Policy Recommendations & Empirical Grounding

- **Original Draft Issue:**  
  Section 8 contained speculative qualitative assertions regarding "real-time price elasticity" and behavioral load-shifting that were not evaluated or supported by the deterministic ex-post price-only game model.
- **Verified Model Boundaries:**
  - **Physical Dispatch:** Frozen strictly to the accepted Phase 7.1 Stochastic MPC battery dispatches.
  - **Trading Action Space:** Discrete price-only bidding $\mathcal{P} = \{0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30\}$.
  - **Quantity Withholding:** Prohibited; all prosumers submit their full physical surplus $s_i$ or deficit $d_j$.
  - **Elasticity:** Zero real-time physical demand elasticity modeled in Phase 8D.
- **Explanation & Mathematical Resolution:**  
  All references to dynamic real-time price elasticity were removed. Section 8 was reframed strictly around empirical findings:
  1. Midday solar scarcity gives sellers structural market power in unconstrained Nash equilibria.
  2. Strategy E (Nash Social Welfare) and Strategy D (Max-Min) provide mathematically sound tie-breaking rules for a community market coordinator to protect vulnerable households and prevent monopolistic surplus extraction.
  3. Physical volume invariance ($121.611449\text{ kWh}$) is an exact mathematical property of the Pareto-undominated set $E_{\text{Pareto}}$ under fixed physical quantities.

---

## 3. Master Reconciliation Ledger

| Audit Check | Original Draft Assertion | Authoritative Verified Data | Resolution & Document Updates |
| :--- | :--- | :--- | :--- |
| **Check 1: Lowest Inequality Strategy** | Strategy E stated as lowest inequality overall ($G_{\text{norm}} = 0.8073$). | Core 6: Strategy E is lowest ($G_{\text{norm}} = 0.8073$).<br/>All 12: `Hybrid_w_fair_1.0` is lowest ($G_{\text{norm}} = 0.7982$). | Clarified two-level hierarchy: Strategy E among core 6; `Hybrid_w_fair_1.0` across all 12. |
| **Check 2: Surplus Division Shares** | Table 5.1 draft had $13.568600 (50.72%) vs $13.185919 (49.28%), conflicting with 63.6% text. | Strat A Seller = **$17.017553 (63.61%)**.<br/>Strat A Buyer = **$9.736965 (36.39%)**.<br/>Unit spread share = **63.61%**. | Corrected Table 5.1. Verified exact equality between unit-spread share and dollar payoff share. |
| **Check 3: Max-Min Improvement** | Strategy D claimed to raise minimum benefit by unverified "14.6%". | Hourly mean minimum payoff: **+28.49%** vs Strat A (+614.89% vs B).<br/>Cumulative household min: **+2.81%** vs Strat A (+93.55% vs B). | Replaced "14.6%" with exact verified figures for both hourly and cumulative metrics. |
| **Check 4: Sensitivity Step Response** | Characterized as "smooth decrease in Gini inequality across [0, 1]". | Discrete step response:<br/>$w \le 0.5$: 0 hours differ (flat).<br/>$w=0.6$: 25 hrs, $w=0.8$: 76 hrs, $w=1.0$: 99 hrs. | Revised prose to explicitly document the discrete two-regime step response. |
| **Check 5: Numerical Precision** | Error claimed as "$0.000000 AUD" alongside $10^{-17} / 10^{-14}$ residuals. | Hourly residual $\le 5.55 \times 10^{-17}$ AUD.<br/>Aggregate residual $\le 1.78 \times 10^{-14}$ AUD.<br/>Zero at 6 decimal places ($0.000000 AUD). | Reconciled IEEE 754 precision with micro-AUD rounding; confirmed tolerance $< 10^{-10}$ AUD. |
| **Check 6: Unique Configurations** | Ambiguous reference to "13 strategy configurations". | 12 unique strategy configurations evaluated across 13 reporting entries (Strategy F duplicated at $w=0.5$). | Explicitly documented configuration taxonomy (6 core + 7 sensitivity = 12 unique). |
| **Check 7: Policy Claims & Scope** | Unsupported assertions on real-time price elasticity. | Deterministic ex-post price-only setup with frozen physical flows from Phase 7.1 MPC. | Removed elasticity claims; grounded all policy recommendations strictly in empirical data. |

---

## 4. Verification of Repository Test Suite

Following the documentation update, the entire regression test suite was executed across all phases:

```powershell
pytest -q
```

### Test Suite Execution Summary:
- `tests/test_phase8d_dataset_validation.py` (9 tests): **9 PASSED**
- `tests/test_phase8d_selection.py` (8 tests): **8 PASSED**
- `tests/test_phase8d_fairness.py` (9 tests): **9 PASSED**
- `tests/test_phase8c_dataset_validation.py` (8 tests): **8 PASSED**
- `tests/test_phase8_equilibrium.py` (15 tests): **15 PASSED**
- `tests/test_phase8_strategic_market.py` (25 tests): **25 PASSED**
- Phases 1–7.1 Test Suites (168 tests): **168 PASSED**
- **Total: 242 passed in 24.36 seconds (0 failures, 0 skipped, 0 regressions)**

---

## 5. Audit Conclusion

The Phase 8D Final Report Reconciliation Audit is **COMPLETE and FULLY RESOLVED**.
- All seven discrepancies have been rigorously investigated and mathematically reconciled against raw data.
- `reports/phase8d_fairness_analysis.md` is fully updated and frozen as an authoritative research deliverable.
- Physical volume and welfare invariance on the Pareto frontier are preserved down to double-precision machine epsilon across all 1,752 hours.
- The repository is clean, verified, and in a stable state ready for Phase 8E.
