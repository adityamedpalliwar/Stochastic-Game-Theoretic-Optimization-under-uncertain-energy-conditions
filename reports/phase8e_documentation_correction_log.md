# Phase 8E — Documentation Correction Log

**Document ID:** `reports/phase8e_documentation_correction_log.md`  
**Phase:** Phase 8E Step 5 — Documentation Finalization  
**Date:** 2026-11-01  
**Status:** COMPLETED & VERIFIED  

---

## 1. Overview & Objective

Following the read-only Phase 8E cross-layer mathematical audit (`reports/phase8e_final_consistency_audit.md`), this log documents all targeted, documentation-only corrections applied to eliminate previously identified drafting discrepancies, align reporting with the authoritative frozen benchmarks and live API outputs, and clearly communicate academic modeling boundaries.

**Strict Preservation Rules Maintained:**
- **Zero code changes:** No files in `src/`, `dashboard/`, or `tests/` were modified during Step 5.
- **Zero benchmark changes:** Frozen benchmark CSVs (`reports/phase8c_hourly_equilibria.csv`, `reports/phase8d_hourly_selection.csv`, `reports/phase7_hourly_records.csv`) remain completely untouched.
- **Evidence-based corrections:** Every updated numerical value is independently verified against authoritative engine output or frozen benchmark records.

---

## 2. Detailed Log of Corrections

### Correction 1: Authoritative Live JSON Payload in Dashboard Integration Report
- **File:** `reports/phase8e_dashboard_integration_report.md`
- **Section:** Section 3.3 ("Authoritative JSON Response Payload (`2013-05-15 11:00:00`)")
- **Authoritative Evidence Source:** Live API query to `GET /api/strategic-market/stochastic-hourly?timestamp=2013-05-15%2011:00:00` and engine sample archive `reports/phase8e/stochastic_equilibria_sample.json.gz`.
- **Nature of Correction:** Replaced illustrative/mock draft schema with the exact verified live payload.

| Field | Previous Draft Mock Value | Corrected Authoritative Live Value | Evidence / Explanation |
|---|---|---|---|
| `ex_ante_roles` | H1: Seller, H2: Buyer, H3: Buyer | **H1: Seller, H2: Seller, H3: Buyer** | Post-battery net positions: $\mathbb{E}[n_1]=-1.2004, \mathbb{E}[n_2]=-0.3147, \mathbb{E}[n_3]=+0.1162$ |
| `expected_net_positions_kwh` | H1: -0.4578, H2: +0.4496, H3: +0.3601 | **H1: -1.200446, H2: -0.314697, H3: +0.116189** | Synchronized 1,000 Monte Carlo scenario expectations |
| `scenario_role_flip_counts` | H1: 709S/291B, H2: 204S/796B, H3: 0S/1000B | **H1: 941S/59B/0I, H2: 957S/42B/1I, H3: 513S/486B/1I** | Verified scenario realizations from residual pool |
| `battery_dispatch.charge_kwh` | All 0.0 | **H1: 0.0, H2: 0.433797, H3: 0.415465** | Authoritative Phase 7.1 Stochastic MPC first-stage records |
| `strict_pne_count` / `weak_pne_count` | 0 Strict, 11 Weak | **1 Strict, 10 Weak** | Profile `(0.12, 0.08, 0.12)` is strict; 10 weak PNE |
| `pareto_undominated_pne_count` | 11 Profiles | **2 Profiles** | Profiles `(0.12, 0.08, 0.12)` and `(0.08, 0.12, 0.12)` |
| `selected_equilibrium.profile` | `(0.22, 0.19, 0.19)` | **`(0.12, 0.08, 0.12)`** | Deterministic 5-step heuristic on Pareto frontier |
| `expected_vwap_aud_per_kwh` | $\$0.2052/\text{kWh}$ | **$\$0.1110657/\text{kWh}$** | Transaction-weighted expected value / expected volume |
| `deterministic_comparison.traded_volume_kwh` | Det: $0.4402\,\text{kWh}$, Diff: $-0.2694$ ($-61.20\%$) | **Det: $0.2264645\,\text{kWh}$, Diff: $-0.0556248$ ($-24.56\%$)** | Verified against `reports/phase8c_hourly_equilibria.csv` |

---

### Correction 2: Deterministic Baseline & Side-by-Side Comparison in Dashboard Integration Report
- **File:** `reports/phase8e_dashboard_integration_report.md`
- **Section:** Section 5 ("Side-by-Side Comparison & Uncertainty Volume Analysis")
- **Authoritative Evidence Source:** `reports/phase8c_hourly_equilibria.csv` (`timestamp == "2013-05-15 11:00:00"`).
- **Nature of Correction:** Corrected deterministic benchmark metrics, updated comparison table, and added formal dual-driver decomposition.

| Metric | Previous Draft Table | Corrected Authoritative Table | Authoritative Benchmark Source |
|---|---|---|---|
| **Deterministic Traded Volume** | $0.4402\,\text{kWh}$ | **$0.2265\,\text{kWh}$ ($0.2264645\,\text{kWh}$)** | `phase8c_hourly_equilibria.csv:selected_traded_volume_kwh` |
| **Deterministic Welfare** | $\$0.0968\,\text{AUD}$ | **$\$0.0498\,\text{AUD}$ ($0.0498222\,\text{AUD}$)** | `phase8c_hourly_equilibria.csv:selected_community_welfare_aud` |
| **Deterministic VWAP** | $\$0.2050/\text{kWh}$ | **$\$0.0800/\text{kWh}$** | `phase8c_hourly_equilibria.csv:selected_weighted_average_price_aud` |
| **Volume Delta ($\Delta Q$)** | $-0.2694\,\text{kWh}$ ($-61.20\%$) | **$-0.0556\,\text{kWh}$ ($-24.56\%$)** | Exact difference: $0.1708397 - 0.2264645$ |
| **Welfare Delta ($\Delta W$)** | $-\$0.0592\,\text{AUD}$ ($-61.20\%$) | **$-\$0.0122\,\text{AUD}$ ($-24.56\%$)** | Exact difference: $\$0.0375847 - \$0.0498222$ |
| **Deterministic Profile** | `(0.22, 0.19, 0.19)` | **`(0.08, 0.08, 0.08)`** | Selected profile under seller price competition |

---

### Correction 3: Benchmark Reconciliation in Stochastic Equilibrium Report
- **File:** `reports/phase8e_stochastic_equilibrium_report.md`
- **Section:** Section 3 ("Detailed Analysis of Midday Peak") and Section 4 ("Deterministic vs. Stochastic Comparison & Uncertainty Decomposition")
- **Authoritative Evidence Source:** `reports/phase8c_hourly_equilibria.csv` and `reports/phase8e/stochastic_benchmark_metrics.csv`.
- **Nature of Correction:** Replaced outdated draft placeholder $0.2858\,\text{kWh}$ (which implied a $-40.24\%$ gap) with the authoritative Phase 8C frozen benchmark $0.2265\,\text{kWh}$ ($-24.56\%$ gap), and updated expected net positions from imprecise draft numbers to $-1.2004\,\text{kWh}, -0.3147\,\text{kWh}, +0.1162\,\text{kWh}$.

---

### Correction 4: Dual-Driver Volume Decomposition & Academic Disclosures
- **Files:** Both `reports/phase8e_dashboard_integration_report.md` (Section 5.1 & 5.2) and `reports/phase8e_stochastic_equilibrium_report.md` (Section 4.1 & 4.2).
- **Nature of Correction:** Explicitly clarified the multiple separate phenomena contributing to the observed volume reduction:
  1. **Concave Bilateral Matching Operator (Theoretical Jensen Gap):** Double auction matching follows $Q(S, D) = \min(S, D)$. Concavity dictates $\mathbb{E}[\min(S, D)] \le \min(\mathbb{E}[S], \mathbb{E}[D])$. Forecast variance across scenarios inherently compresses expected volume.
  2. **Physical Role-Conflict Order Clamping (Restricted Option 1A Policy):** Under Option 1A, households commit price bids conditionally on their ex-ante expected role. In 514 out of 1,000 scenarios, H003 (ex-ante buyer) experiences realized net surplus, causing its order to be clamped to zero ($q_3 = 0$). Since H003 is the sole buyer, all 514 realizations produce zero bilateral trades.
  3. **Distinct Strategic Price Profiles:** Phase 8C selects `(0.08, 0.08, 0.08)` under perfect ex-post foresight, whereas Phase 8E selects `(0.12, 0.08, 0.12)` under expected payoffs.
  4. **Attribution Notice:** Explicitly stated that Jensen's inequality alone does **not** mathematically prove or explain the entire observed volume reduction. The analysis identifies plausible contributing mechanisms but does **not** assert an isolated numerical causal decomposition partitioning exact percentage shares among them.
  5. **Academic Limitations:** Documented that Option 1A is a restricted ex-ante role-conditioned game (not a full two-sided contingent bidding game); Phase 8C is an ex-post benchmark with perfect foresight while Phase 8E represents non-anticipative expected-payoff decision-making; and weak PNE in zero-trade hours represent payoff indifference rather than active economic price discovery.

---

### Correction 5: Section 6 Runtime Benchmark Table PNE Multiplicity Disaggregation
- **File:** `reports/phase8e_dashboard_integration_report.md`
- **Section:** Section 6 ("Runtime Performance & Caching Benchmarks")
- **Authoritative Evidence Source:** `reports/phase8e/stochastic_benchmark_metrics.csv` and `reports/phase8e/stochastic_equilibria_sample.json.gz`.
- **Nature of Correction:** Replaced the informal, blanket placeholder entry "11 Weak PNE" with the verified, exact total, strict, and weak pure Nash equilibrium counts for each representative timestamp:
  - `2013-05-15 11:00:00`: **11 Total (1 Strict, 10 Weak)**
  - `2013-05-15 08:00:00`: **11 Total (2 Strict, 9 Weak)**
  - `2013-05-15 14:00:00`: **11 Total (2 Strict, 9 Weak)**
  - `2013-05-15 18:00:00`: **11 Total (2 Strict, 9 Weak)**
  - `2013-05-15 02:00:00`: **343 Total (0 Strict, 343 Weak)**

---

## 3. Post-Correction Validation Results

1. **Contradiction Scan:** Full-text scan across all reports in `reports/` confirmed that obsolete figures ($0.2858\,\text{kWh}$, $0.4402\,\text{kWh}$, $-40.24\%$, $-61.20\%$) appear only as documented historical errata notes and are nowhere asserted as true results.
2. **Authoritative Consistency:** The live backend API (`GET /api/strategic-market/stochastic-hourly?timestamp=2013-05-15%2011:00:00`), the engine sample archive (`reports/phase8e/stochastic_equilibria_sample.json.gz`), and both reports now present 100% identical values:
   - Ex-ante roles: H001 Seller, H002 Seller, H003 Buyer
   - Expected net positions: H001 $-1.2004\,\text{kWh}$, H002 $-0.3147\,\text{kWh}$, H003 $+0.1162\,\text{kWh}$
   - Tradeable scenarios: 486 / 1,000 (48.6%)
   - PNE count: 11 total (1 strict, 10 weak)
   - Pareto-undominated equilibria: 2
   - Selected profile: `(H001: 0.12, H002: 0.08, H003: 0.12)`
   - Expected traded energy: $0.1708397\,\text{kWh}$
   - Expected community welfare: $\$0.0375847\,\text{AUD}$
   - Expected VWAP: $\$0.1110657/\text{kWh}$
   - Phase 8C deterministic volume: $0.2264645\,\text{kWh}$
   - Volume difference: $-0.0556248\,\text{kWh}$ ($-24.56\%$)
3. **Integrity of Core Artifacts:** Verified via `git status` that no source files in `src/`, `dashboard/`, or `tests/` were modified.

