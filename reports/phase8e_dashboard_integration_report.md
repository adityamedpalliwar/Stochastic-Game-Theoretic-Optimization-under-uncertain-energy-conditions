# Phase 8E — Backend API and Dashboard Integration Report

**Project:** Stochastic Game-Theoretic Optimization Under Uncertain Energy Conditions  
**Phase:** Phase 8E Step 3 — Backend API & Dashboard Integration  
**Date:** 2026-11-01  
**Status:** COMPLETE & VERIFIED  

---

## 1. Executive Summary

Phase 8E Step 3 successfully integrates the **Stochastic Expected-Payoff Pure Strategy Nash Equilibrium (PNE) Engine** into the interactive web application. The implementation provides:
1. A dedicated backend REST API endpoint: `GET /api/strategic-market/stochastic-hourly?timestamp=...`.
2. High-performance in-memory caching ensuring sub-5ms repeated query latency.
3. A fully interactive dashboard tab (`#pane-stochastic`) in the strategic energy market dashboard.
4. Comprehensive side-by-side comparison between Phase 8C deterministic ex-post benchmark and Phase 8E stochastic expected outcomes, directly verifying Jensen's inequality and role-conflict order clamping.
5. Interactive inspection of participating prosumer scenario distributions, role-conflict frequencies, Pareto-undominated equilibria, and the full combinatorial 343-profile expected payoff table.
6. A rigorous test suite (`tests/test_stochastic_dashboard_integration.py` passing 8/8) with 100% preservation of all Phase 7.1, Phase 8C, and Phase 8D algorithms and frozen CSV benchmark artifacts.

---

## 2. Modified & Created Files

| File | Status | Description |
|---|---|---|
| `dashboard/app.py` | Modified | Added endpoint `GET /api/strategic-market/stochastic-hourly` with parameter validation, error responses (400, 404, 500), and docstrings. |
| `dashboard/data_service.py` | Modified | Added `get_stochastic_market_hourly()` with in-memory caching (`_stochastic_cache`), lazy initialization of forecaster/residual pool/Phase 7 dispatch provider, side-by-side comparison generator, and battery dispatch payload. |
| `dashboard/templates/index.html` | Modified | Added Phase 8E navigation tab, active badge, modeling disclosure callout, KPI cards, prosumer scenario cards container, side-by-side comparison table, Pareto frontier table, and 343-profile expected payoff matrix table. |
| `dashboard/static/css/dashboard.css` | Modified | Added styles for `.role-dist-bar`, `.role-dist-seller`, `.role-dist-buyer`, `.role-dist-inactive`, `.comparison-card-grid`, `.comparison-card`, `.comparison-subgrid`, and `.selected-payoff-row`. |
| `dashboard/static/js/strategic_market.js` | Modified | Added Phase 8E state management (`stochTimestamp`, `stochData`, `isStochLoading`), event listeners for presets/custom inputs/jump button, API fetch handler, and dedicated renderers for KPIs, prosumer cards, comparison grid/table, Pareto candidates, and payoff table. |
| `tests/test_stochastic_dashboard_integration.py` | Created | 8 automated end-to-end integration tests verifying HTTP status codes (200, 400, 404), schema compliance, mathematical conservation identities, cache hit speed, side-by-side comparison, zero-trade handling, and frontend assets. |
| `reports/phase8e_dashboard_integration_report.md` | Created | This authoritative integration report. |

*Strict Boundary Verification:* No files in `src/game/` (Phase 8C/8D), `src/stochastic/strategic_expected_solver.py` (Phase 8E engine), or frozen CSV benchmark files (`reports/phase8c_hourly_equilibria.csv`, `reports/phase8d_hourly_selection.csv`) were modified.

---

## 3. Backend API Route Specification

### 3.1 Endpoint Definition
- **Route:** `GET /api/strategic-market/stochastic-hourly`
- **Controller:** `dashboard.app.get_strategic_market_stochastic_hourly()`
- **Query Parameters:**
  - `timestamp` (string, required): Target hour formatted as `YYYY-MM-DD HH:MM:SS` or `YYYY-MM-DDTHH:MM:SS`. Must fall within the test horizon (`2013-04-19 00:00:00` to `2013-06-30 23:00:00`).

### 3.2 HTTP Status Codes
- `200 OK`: Successful computation or cache retrieval. Returns JSON with status `"success"`.
- `400 Bad Request`: Missing `timestamp` parameter or unparseable date format.
- `404 Not Found`: Timestamp falls outside the held-out test evaluation panel.
- `500 Internal Server Error`: Unhandled calculation exception.

### 3.3 Authoritative JSON Response Payload (`2013-05-15 11:00:00`)
```json
{
  "status": "success",
  "data": {
    "timestamp": "2013-05-15 11:00:00",
    "engine": "Phase 8E Stochastic Expected-Payoff Nash Equilibrium Engine",
    "num_scenarios": 1000,
    "num_tradeable_scenarios": 486,
    "tradeable_scenario_percentage": 48.6,
    "ex_ante_roles": {
      "H001": "seller",
      "H002": "seller",
      "H003": "buyer"
    },
    "expected_net_positions_kwh": {
      "H001": -1.2004461288452148,
      "H002": -0.3146974742412567,
      "H003": 0.11618856340646744
    },
    "scenario_role_flip_counts": {
      "H001": { "seller": 941, "buyer": 59, "inactive": 0 },
      "H002": { "seller": 957, "buyer": 42, "inactive": 1 },
      "H003": { "seller": 513, "buyer": 486, "inactive": 1 }
    },
    "battery_dispatch": {
      "charge_kwh": { "H001": 0.0, "H002": 0.4337968338058853, "H003": 0.4154645188220978 },
      "discharge_kwh": { "H001": 0.0, "H002": 0.0, "H003": 0.0 }
    },
    "num_active_players": 3,
    "active_sellers": ["H001", "H002"],
    "active_buyers": ["H003"],
    "inactive_households": [],
    "num_profiles_evaluated": 343,
    "num_deviations_evaluated": 6174,
    "num_stochastic_pne": 11,
    "strict_pne_count": 1,
    "weak_pne_count": 10,
    "pareto_undominated_pne_count": 2,
    "market_summary": {
      "expected_traded_energy_kwh": 0.17083966770768166,
      "expected_community_welfare_aud": 0.03758472689568999,
      "expected_vwap_aud_per_kwh": 0.11106571379111009,
      "expected_household_payoffs_aud": {
        "H001": 0.0037809257340431198,
        "H002": 0.0015263304871320706,
        "H003": 0.03227747067451476
      },
      "welfare_conservation_verified": true
    },
    "selected_equilibrium": {
      "profile": { "H001": 0.12, "H002": 0.08, "H003": 0.12 },
      "expected_payoffs_aud": {
        "H001": 0.0037809257340431198,
        "H002": 0.0015263304871320706,
        "H003": 0.03227747067451476
      },
      "expected_traded_kwh": 0.17083966770768166,
      "expected_community_welfare_aud": 0.03758472689568999,
      "expected_vwap_aud_per_kwh": 0.11106571379111009,
      "classification": "strict",
      "selection_rationale": "Selected via deterministic 5-step heuristic on the Pareto-undominated expected PNE frontier: (1) Pareto-undominated filter, (2) Proximity of volume-weighted clearing price to reference price $0.1900/kWh, (3) Maximize community expected welfare, (4) Minimize price variance, (5) Lexicographical tie-break."
    },
    "pareto_undominated_equilibria": [
      {
        "profile": { "H001": 0.12, "H002": 0.08, "H003": 0.12 },
        "expected_traded_kwh": 0.17083966770768166,
        "expected_community_welfare_aud": 0.03758472689568999,
        "expected_vwap_aud_per_kwh": 0.11106571379111009,
        "expected_payoffs": { "H001": 0.0037809257340431198, "H002": 0.0015263304871320706, "H003": 0.03227747067451476 },
        "classification": "strict",
        "is_pareto_undominated": true
      },
      {
        "profile": { "H001": 0.08, "H002": 0.12, "H003": 0.12 },
        "expected_traded_kwh": 0.17083966770768166,
        "expected_community_welfare_aud": 0.03758472689568999,
        "expected_vwap_aud_per_kwh": 0.11106571379111009,
        "expected_payoffs": { "H001": 0.0025206171560287467, "H002": 0.0027866390651464433, "H003": 0.03227747067451476 },
        "classification": "weak",
        "is_pareto_undominated": true
      }
    ],
    "deterministic_comparison": {
      "traded_volume_kwh": {
        "deterministic_ex_post": 0.2264645083316803,
        "stochastic_expected": 0.17083966770768166,
        "absolute_diff_kwh": -0.05562484062399864,
        "percentage_diff": -24.562277344814845,
        "jensen_effect_observed": true
      },
      "community_welfare_aud": {
        "deterministic_ex_post": 0.0498221918329696,
        "stochastic_expected": 0.03758472689568999,
        "absolute_diff_aud": -0.012237464937279605,
        "percentage_diff": -24.56227734481469
      },
      "vwap_aud_per_kwh": {
        "deterministic_ex_post": 0.08,
        "stochastic_expected": 0.11106571379111009,
        "absolute_diff_aud": 0.03106571379111009
      },
      "household_payoffs": {
        "H001": { "deterministic_aud": 0.0, "stochastic_aud": 0.0037809257340431198, "diff_aud": 0.0037809257340431198, "pct_diff": null },
        "H002": { "deterministic_aud": 0.0, "stochastic_aud": 0.0015263304871320706, "diff_aud": 0.0015263304871320706, "pct_diff": null },
        "H003": { "deterministic_aud": 0.0498221918329696, "stochastic_aud": 0.03227747067451476, "diff_aud": -0.01754472115845484, "pct_diff": -35.214671440538076 }
      },
      "roles": {
        "deterministic": { "H001": "seller", "H002": "seller", "H003": "buyer" },
        "ex_ante_stochastic": { "H001": "seller", "H002": "seller", "H003": "buyer" }
      },
      "equilibrium_counts": {
        "deterministic": { "total_pne": 13, "strict_pne": 0, "weak_pne": 13, "pareto_undominated_pne": 7, "selected_profile": { "H001": 0.08, "H002": 0.08, "H003": 0.08 } },
        "stochastic": { "total_pne": 11, "strict_pne": 1, "weak_pne": 10, "pareto_undominated_pne": 2, "selected_profile": { "H001": 0.12, "H002": 0.08, "H003": 0.12 } }
      }
    },
    "expected_payoff_table": [ ... 343 profile records ... ],
    "modeling_metadata": {
      "action_space": "Option 1A: Seven-price role-conditioned bidding over [0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30] AUD/kWh",
      "scenario_sampling": "Option 2A: 1,000 synchronized Monte Carlo scenarios from validation residual pool",
      "battery_dispatch": "Option 3A: Frozen Phase 7.1 Stochastic MPC first-stage decisions",
      "role_conflict_policy": "Households submit no order in scenarios where realized net flow opposes ex-ante role",
      "disclaimer": "This is a role-conditioned expected-payoff game, not a full two-sided contingent bidding game.",
      "zero_trade_equilibria_note": "In hours with zero tradeable scenarios, all 343 profiles yield identical zero payoffs and form weak equilibria.",
      "scenario_seed": 737877
    }
  }
}
```

---

## 4. Dashboard UI Features and Layout

The Phase 8E integration is exposed via a dedicated navigation tab (`#pane-stochastic`) in `index.html`:

1. **Header Badge & Academic Callout Box:**
   - Active status indicator: `✓ Stochastic Engine Active`.
   - Explanatory callout explicitly defining Option 1A (seven-price grid), Option 2A (synchronized Monte Carlo), Option 3A (frozen first-stage MPC battery dispatch), and the physical role-conflict clamping rule ($q=0$).
   - Academic disclaimer clarifying that Phase 8E is an ex-ante role-conditioned policy game, *not* a two-sided contingent Bayesian game.

2. **Interactive Controls Card:**
   - 5 Quick-jump representative buttons:
     - Midday Peak (`2013-05-15 11:00:00`)
     - Morning Ramp (`2013-05-15 08:00:00`)
     - Afternoon (`2013-05-15 14:00:00`)
     - Evening Peak (`2013-05-15 18:00:00`)
     - Night Baseline (`2013-05-15 02:00:00`)
   - Custom ISO timestamp input text box with `⚡ Calculate Equilibrium` button.
   - Synchronous loading spinner with status text (`Solving 343k clearings...`).
   - One-click jump button (`#btn-jump-to-stochastic`) located in the Phase 8D section that switches tabs and loads the stochastic view.

3. **Macroeconomic Financial KPI Grid:**
   - Expected Traded Energy $\mathbb{E}[Q_{\text{trade}}]$ (kWh).
   - Expected Community Welfare $\mathbb{E}[W]$ (AUD), verifying $\mathbb{E}[W] = 0.22 \times \mathbb{E}[Q]$.
   - Expected VWAP Price $\mathbb{E}[V] / \mathbb{E}[Q]$ (AUD/kWh).
   - Tradeable Scenarios count & percentage ($M_{\text{trade}} / 1000$).
   - Pure Nash Equilibria count breakdown (Strict, Weak, Pareto).
   - Selected Price Profile $(p_1, p_2, p_3)$.

4. **Participating Prosumer Scenario Distribution Cards:**
   - Household archetype and ex-ante role badge (`EX-ANTE SELLER`, `EX-ANTE BUYER`, `INACTIVE`).
   - Expected net position $\mathbb{E}[n_i]$ (kWh) and authoritative Phase 7.1 battery dispatch ($C_0, B_0$).
   - Expected incremental payoff $\mathbb{E}[U_i]$ (AUD).
   - Realized role-conflict clamping frequency (count and % of scenarios where realized role opposed ex-ante role and order was clamped to 0).
   - Visual segmented scenario distribution bar displaying green (seller surplus), blue (buyer deficit), and gray (inactive) frequencies across the 1,000 scenarios.

5. **Side-by-Side Comparison: Deterministic (Phase 8C) vs Stochastic (Phase 8E):**
   - 3 Summary cards comparing Traded Energy Volume, Community Welfare, and VWAP.
   - Comparison table displaying deterministic ex-post value, stochastic expected value, absolute difference, relative percentage difference, and uncertainty impact note.
   - Jensen's Inequality Callout explaining why $\mathbb{E}[\min(S, D)] \le \min(\mathbb{E}[S], \mathbb{E}[D])$ and how forecast variance reduces cleared volume compared to assuming perfect foresight.

6. **Pareto-Undominated Stochastic Equilibria Frontier:**
   - Candidate frontier table highlighting the selected equilibrium with a `★ Selected Equilibrium` badge and listing candidate profiles, payoffs, traded volume, welfare, and classification (`STRICT_PNE` vs `WEAK_PNE`).

7. **Combinatorial Expected Payoff Matrix Table ($7^3 = 343$ Profiles):**
   - Scrollable table displaying all 343 strategy profiles evaluated across 1,000 scenarios.
   - Highlights the selected equilibrium row (`selected-payoff-row`).

---

## 5. Side-by-Side Comparison & Uncertainty Volume Analysis

For midday peak hour `2013-05-15 11:00:00`:

| Metric | Phase 8C Deterministic Ex-Post Benchmark | Phase 8E Stochastic Expected Game ($M=1,000$) | Absolute Delta | Relative Diff (%) | Governing Physical / Economic Principle |
|---|---|---|---|---|---|
| **Traded Energy Volume** | 0.2265 kWh ($0.2264645\,\text{kWh}$) | 0.1708 kWh ($0.1708397\,\text{kWh}$) | -0.0556 kWh | **-24.56%** | Concave min matching + role-conflict clamping |
| **Community Welfare** | $0.0498 AUD ($0.0498222\,\text{AUD}$) | $0.0376 AUD ($0.0375847\,\text{AUD}$) | -$0.0122 AUD | **-24.56%** | Linear welfare identity: $W = 0.22 \times Q$ |
| **Weighted Average Price (VWAP)** | $0.0800/kWh | $0.1111/kWh ($0.1110657/\text{kWh}$) | +$0.0311/kWh | +38.83% | Midpoint bilateral clearing |
| **H001 Incremental Payoff** | $0.0000 AUD | $0.0038 AUD ($0.0037809\,\text{AUD}$) | +$0.0038 AUD | N/A | Ex-ante seller captures P2P surplus over export credit |
| **H002 Incremental Payoff** | $0.0000 AUD | $0.0015 AUD ($0.0015263\,\text{AUD}$) | +$0.0015 AUD | N/A | Ex-ante seller captures P2P surplus over export credit |
| **H003 Incremental Payoff** | $0.0498 AUD ($0.0498222\,\text{AUD}$) | $0.0323 AUD ($0.0322775\,\text{AUD}$) | -$0.0175 AUD | -35.21% | Ex-ante buyer surplus scales with cleared volume |
| **PNE Count (Strict / Weak / Pareto)** | 13 Total (0 Strict, 13 Weak, 7 Pareto) | 11 Total (1 Strict, 10 Weak, 2 Pareto) | -2 PNE | N/A | Expected payoff averaging sharpens deviation gradients |
| **Selected Price Profile** | `(H001: 0.08, H002: 0.08, H003: 0.08)` | `(H001: 0.12, H002: 0.08, H003: 0.12)` | Distinct | N/A | Heuristic selects profile closest to $0.1900/kWh reference |

### 5.1 Contributing Mechanisms for the Uncertainty Volume Difference
The observed $-24.56\%$ reduction in cleared energy volume ($\Delta Q = -0.0556248\,\text{kWh}$) between deterministic ex-post foresight and stochastic ex-ante commitment is governed by multiple distinct phenomena:

1. **Concave Bilateral Matching Operator (Theoretical Jensen Gap):**  
   The microgrid double auction clearing quantity is determined by the bilateral matching operator:
   $$Q(S, D) = \min(S, D)$$
   Because the minimum operator is concave, Jensen's inequality dictates:
   $$\mathbb{E}[\min(S, D)] \le \min\big(\mathbb{E}[S], \mathbb{E}[D]\big)$$
   Forecast variance in physical supply and demand across Monte Carlo realizations naturally compresses expected matched volume relative to point evaluations at the scenario mean.

2. **Physical Role-Conflict Order Clamping (Restricted Option 1A Policy):**  
   Under the approved Option 1A policy, households commit price bids conditionally on their ex-ante expected net positions:
   - H003 is classified as an ex-ante **BUYER** ($\mathbb{E}[n_3] = +0.1162\,\text{kWh} > 0$).
   - However, in **514 out of 1,000 scenarios**, realized solar generation exceeds demand, causing H003 to experience realized net surplus ($n_3(s) \le 0$).
   - Because Option 1A prohibits players from submitting orders opposing their ex-ante role, H003's buy order is physically clamped to zero ($q_3 = 0$) in those 514 scenarios.
   - Since H001 and H002 are both sellers, and H003 is the microgrid's sole buyer, **zero bilateral trade is physically possible** across all 514 role-conflict realizations.
   - Consequently, bilateral trading occurs in only **486 out of 1,000 scenarios (48.6%)**.

3. **Different Equilibrium Price Profiles:**  
   The deterministic ex-post game selects profile `(0.08, 0.08, 0.08)` under perfect foresight, whereas the stochastic expected-payoff game selects `(0.12, 0.08, 0.12)`. Different strategic price commitments interact with clearing order eligibility and midpoints.

> [!IMPORTANT]
> **Methodological Disclosure on Attribution:**  
> Jensen's inequality alone does **not** mathematically prove or explain the entire observed $-24.56\%$ reduction. The current analysis identifies plausible contributing mechanisms (concave matching, role-conflict order clamping, distinct equilibrium profiles, and single-point realized vs. multi-scenario expected evaluation) but does **not** assert a numerical causal decomposition partitioning exact percentage shares among them.

### 5.2 Academic Limitations & Modeling Disclosures
1. **Role-Conditioned vs. Full Bayesian Game:** Option 1A is a restricted ex-ante role-conditioned bidding game. It is not a fully contingent two-sided strategy (Option 1B, where players submit both ask and bid curves).
2. **Ex-Post vs. Ex-Ante Comparison:** Phase 8C is an ex-post deterministic benchmark evaluating what could have occurred under perfect foresight for a single realized meter condition, whereas Phase 8E represents non-anticipative causal decision-making under uncertainty using expected payoffs across Monte Carlo draws.
3. **Equilibrium Multiplicity & Weak PNE:** Weak pure Nash equilibria in zero-trade hours or uncrossed scenarios reflect payoff indifference (where zero transactions occur regardless of price), not active economic price discovery.

---

## 6. Runtime Performance & Caching Benchmarks

Measurements conducted on the local development environment:

| Representative Timestamp | Operational Regime | First Solve Time | Cached Retrieval Time | Tradeable Scenarios | Traded Volume | Community Welfare | Stochastic PNE Multiplicity |
|---|---|---|---|---|---|---|---|
| `2013-05-15 11:00:00` | Midday Solar Peak | 25.06s* | **2.03 ms** | 486 / 1000 (48.6%) | 0.1708 kWh | $0.0376 AUD | **11 Total (1 Strict, 10 Weak)** |
| `2013-05-15 08:00:00` | Morning Solar Ramp | 22.25s | **4.24 ms** | 837 / 1000 (83.7%) | 0.1611 kWh | $0.0354 AUD | **11 Total (2 Strict, 9 Weak)** |
| `2013-05-15 14:00:00` | Afternoon Solar | 12.28s | **2.58 ms** | 486 / 1000 (48.6%) | 0.0782 kWh | $0.0172 AUD | **11 Total (2 Strict, 9 Weak)** |
| `2013-05-15 18:00:00` | Evening Demand Peak | 14.66s | **2.54 ms** | 583 / 1000 (58.3%) | 0.0659 kWh | $0.0145 AUD | **11 Total (2 Strict, 9 Weak)** |
| `2013-05-15 02:00:00` | Nighttime Baseline | 0.06s** | **3.30 ms** | 0 / 1000 (0.0%) | 0.0000 kWh | $0.0000 AUD | **343 Total (0 Strict, 343 Weak)** |

*\* First solve includes cold-start initialization of the LSTM forecaster and validation residual pool.*  
*\*\* Zero-trade hour executes the optimized fast-path in 60 ms without redundant clearing calls.*

---

## 7. Verification & Regression Test Results

All test suites passed cleanly with zero regressions:

1. **Phase 8E Dashboard Integration Suite (`tests/test_stochastic_dashboard_integration.py`):**
   - `test_stochastic_endpoint_missing_timestamp`: **PASSED** (HTTP 400 error message verified)
   - `test_stochastic_endpoint_invalid_timestamp_format`: **PASSED** (HTTP 400 error message verified)
   - `test_stochastic_endpoint_out_of_range_timestamp`: **PASSED** (HTTP 404 error message verified)
   - `test_stochastic_endpoint_success_and_payload_structure`: **PASSED** (HTTP 200, schema, welfare conservation verified)
   - `test_stochastic_cache_hit_performance`: **PASSED** (sub-50ms cache response confirmed)
   - `test_deterministic_vs_stochastic_comparison`: **PASSED** (Jensen inequality impact confirmed)
   - `test_zero_trade_hour_stochastic_handling`: **PASSED** (343 weak PNE and zero volume confirmed)
   - `test_dashboard_html_and_js_elements`: **PASSED** (UI tabs, containers, and JS hooks confirmed)
   - **Result: 8 / 8 passing (100%) in 35.26s.**

2. **Strategic Bid-Ask Integration Regression Suite (`tests/test_strategic_bid_ask_integration.py`):**
   - **Result: 28 / 28 passing (100%) in 8.64s.**
   - Confirms that Phase 8D endpoints still report `"phase_8e_status": "NOT_IMPLEMENTED..."` and maintain strict regression isolation.

3. **Dashboard Data Service Suite (`tests/test_dashboard_data_service.py`):**
   - **Result: 13 / 13 passing (100%) in 7.02s.**

4. **Phase 8E Engine Suite (`tests/test_stochastic_expected_solver.py`):**
   - **Result: 13 / 13 passing (100%).**

---

## 8. Conclusion

Phase 8E Step 3 is fully operational, mathematically verified, and documented. The web prototype now transparently demonstrates how solar forecast uncertainty and non-anticipative battery dispatch impact strategic energy bidding, equilibrium prices, and community welfare in peer-to-peer microgrids.

