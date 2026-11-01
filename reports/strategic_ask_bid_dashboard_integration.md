# Strategic Ask-Bid Dashboard Integration Report
## Deliverable 2 — Step 4

**Date:** 2026-11-01  
**Status:** Implemented

---

## 1. What Was Previously Disconnected

The Phase 8 strategic double-auction engine (`src/game/strategic_market.py`) and the Phase 8D equilibrium selection results (`reports/phase8d_hourly_selection.csv`) were computed and stored but not connected to the dashboard API layer. The dashboard had existing endpoints for:
- Nash equilibrium counts and overall household roles/quantities (`/api/nash_hour`)
- Fairness strategy comparison summaries (`/api/fairness_summary`, `/api/fairness_hourly`)

However, none of these endpoints exposed:
- The actual selected ASK/BID prices per household per strategy
- Bilateral transaction clearing results derived from selected equilibrium prices
- Household-level transaction revenues, payments, and incremental economic benefits
- Community welfare traceable to specific selected profile + physical quantities

---

## 2. Existing Components Reused

| Component | Location | How Reused |
|-----------|----------|------------|
| `clear_strategic_double_auction()` | `src/game/strategic_market.py` | Called to reconstruct bilateral transactions from stored selected prices and physical quantities |
| `MarketOrder`, `MarketRole`, `StrategicMarketResult` | `src/game/strategic_market.py` | Used to build orders and interpret clearing output |
| `STRATEGIC_PRICE_GRID` | `src/game/strategic_market.py` | Exposed as-is in API response |
| `DEFAULT_GRID_IMPORT_TARIFF_AUD`, `DEFAULT_GRID_EXPORT_CREDIT_AUD` | `src/game/strategic_market.py` | Used for benefit calculations |
| `phase8d_hourly_selection.csv` | `reports/` | Primary source of selected strategy price profiles |
| `phase8c_hourly_equilibria.csv` | `reports/` | Source of physical household roles and quantities |
| `sanitize_value()` | `dashboard/data_service.py` | Used for JSON serialization of all outputs |
| Existing response envelope (`success_response`, `error_response`) | `dashboard/app.py` | Used for all new endpoints |

**No new Nash solver, equilibrium enumeration, or market engine was created.**

---

## 3. New Data-Service Functions

### `DashboardDataService.get_strategic_market_hourly(timestamp, strategy)`

Returns the complete strategic workflow for one hour and one selected Phase 8D strategy:

- Reads physical roles and quantities from `phase8c_hourly_equilibria.csv`
- Reads selected price profile for the requested strategy from `phase8d_hourly_selection.csv`
- Reconstructs bilateral transactions by calling the existing `clear_strategic_double_auction()` function with the stored selected prices and physical quantities (not a new Nash solve)
- Returns household orders (with ASK/BID distinction), bilateral transactions with midpoint prices, household incremental benefits, and community welfare

**Transaction source:** Reconstructed via existing clearing function — `clear_strategic_double_auction` — applied to the already-selected Phase 8D profile. This is deterministic and does not run a new Nash equilibrium search.

### `DashboardDataService.get_strategic_market_strategies(timestamp)`

Returns all 6 Phase 8D strategy choices for a given hour with their price profiles, payoffs, VWAP, welfare, and fairness metrics. Allows the user to compare strategies before drilling into the full clearing view.

---

## 4. New or Extended API Endpoints

### `GET /api/strategic-market/hourly`

**Parameters:**
- `timestamp` (required): ISO timestamp string, e.g. `2013-04-19 00:00:00`
- `strategy` (optional, default `strat_a`): Phase 8D strategy key

**Returns:**
- `selected_strategy`: strategy key, label, price profile, stored payoffs
- `hour_metadata`: sellers, buyers, inactive counts, market status, auction status
- `household_orders`: per-household role, quantity, ASK/BID price, matched/unmatched quantities, revenue/payment, incremental benefit
- `transactions`: bilateral transaction list with seller ask, buyer bid, midpoint price, matched quantity, seller revenue, buyer payment
- `financial_summary`: total traded volume, VWAP, total payments, total revenues, community welfare
- `household_financial_outcomes`: per-household benefit summary
- `nash_equilibrium_context`: Phase 8C counts (profiles evaluated, PNE count, strict/weak/Pareto breakdown)
- `strategic_price_grid`: exact 7-action grid `[0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30]`
- `transaction_source`: documents reconstruction method
- `phase_8e_status`: explicitly states Phase 8E is NOT IMPLEMENTED

**Error handling:** 400 for missing/invalid timestamp or strategy; 404 for timestamp not in dataset.

### `GET /api/strategic-market/strategies`

**Parameters:**
- `timestamp` (required): ISO timestamp string

**Returns:** All 6 strategy choices with price profiles, payoffs, VWAP, welfare, and fairness metrics.

**Error handling:** 400 for missing timestamp; 404 for timestamp not in dataset.

---

## 5. Test Coverage Summary

`tests/test_strategic_bid_ask_integration.py` — 10 test groups, 28 tests total:

| Group | Tests | What is verified |
|-------|-------|-----------------|
| 1. Role Exposure | 4 | Seller→ASK, Buyer→BID, Inactive→NONE, no role swap |
| 2. Clearing Integration | 5 | Correct prices fed to clearing, bid≥ask, midpoint price, energy balance, financial balance |
| 3. No-Trade Hours | 1 | Empty transactions, null VWAP when no trade |
| 4. Strategy Switching | 2 | Different strategy → different profile, key echoed correctly |
| 5. Household Benefits | 2 | Benefits trace to clearing function, welfare identity 0.22×Q |
| 6. API Endpoints | 7 | HTTP 200/400/404 for both endpoints, response structure |
| 7. Phase 7 Preservation | 2 | Existing endpoints still return correct data |
| 8. Phase 8E Absence | 2 | NOT_IMPLEMENTED declared, no forbidden stochastic phrases |
| 9. Price Grid | 2 | Exact grid [0.08…0.30], all prices on grid |
| 10. Transaction Source | 1 | Reconstruction method documented |

---

## 6. What Was NOT Changed

> [!IMPORTANT]
> The following are strictly preserved:
> - `src/game/strategic_market.py` — untouched
> - All Phase 7 and Phase 8C/8D CSV reports — untouched
> - All existing `DashboardDataService` methods — untouched
> - All existing `app.py` routes — untouched
> - Phase 8E (stochastic strategic bidding) — **NOT IMPLEMENTED** (future work)

---

## 7. Data Flow Diagram

```
phase8c_hourly_equilibria.csv          phase8d_hourly_selection.csv
  ├── H001/H002/H003 roles                ├── strat_a_price_profile
  ├── surplus_kwh / deficit_kwh           ├── strat_b_price_profile
  └── num_active_sellers/buyers           └── ... (6 strategies)
            │                                        │
            └──────────────┬─────────────────────────┘
                           ▼
              get_strategic_market_hourly(timestamp, strategy)
                           │
                           ▼
              clear_strategic_double_auction()   ← existing function, no new solve
                           │
                           ▼
              ┌────────────────────────────────────────┐
              │  household_orders (ASK / BID / NONE)   │
              │  transactions (seller→buyer, midpoint)  │
              │  financial_summary (VWAP, welfare)      │
              │  household_financial_outcomes           │
              └────────────────────────────────────────┘
                           │
                           ▼
              GET /api/strategic-market/hourly
              GET /api/strategic-market/strategies
```

---

## 8. Explicit Distinction: Stored Phase 8D Payoffs vs. Reconstructed Transaction Benefits

To prevent presenting stored equilibrium payoffs and transaction-level financial accounting as interchangeable, the API response schema maintains strict structural and semantic separation:

1. **`selected_strategy.stored_payoffs`**:
   - Represents the frozen, precomputed equilibrium payoff vector loaded directly from `reports/phase8d_hourly_selection.csv` (columns `strat_x_H00y_payoff`).
   - Sourced from the Phase 8D selection evaluation and verified immutable.
2. **`household_financial_outcomes[*].incremental_benefit_aud`** and **`household_orders[*].incremental_benefit_aud`**:
   - Reconstructed dynamically through the existing deterministic clearing function (`clear_strategic_double_auction`).
   - Represents the physical transaction-clearing incremental surplus:
     $$\Delta U_i^{\text{seller}} = \sum_j q_{ij}(p_{ij} - p_{\text{exp}}), \quad \Delta U_j^{\text{buyer}} = \sum_i q_{ij}(p_{\text{imp}} - p_{ij})$$
   - Formally documented with `"transaction_source": "reconstructed_via_existing_clearing_function"`.

---

## 9. Verification of Strategy Choices & Profile Retrieval

All six Phase 8D selection strategies are exposed through `GET /api/strategic-market/strategies` and selectable in `GET /api/strategic-market/hourly`:
1. `strat_a`: Strategy A (Reference — Phase 8C 5-Step Heuristic)
2. `strat_b`: Strategy B (Seller-Favouring)
3. `strat_c`: Strategy C (Buyer-Favouring)
4. `strat_d`: Strategy D (Max-Min Fair)
5. `strat_e`: Strategy E (Nash Social Welfare)
6. `strat_f_05`: Strategy F (Hybrid $w=0.5$)

Automated validation verified that selecting any of the six strategies retrieves the exact corresponding stored price profile from `phase8d_hourly_selection.csv` without fallback or silent substitution.

---

## 10. Frontend Status

- **Backend Status:** The data service methods and Flask REST API endpoints (`/api/strategic-market/hourly` and `/api/strategic-market/strategies`) are fully implemented, verified, and passing all tests.
- **Frontend Status:** No HTML/JavaScript frontend files were modified or created. Visual dashboard UI integration (the proposed "Strategic Bidding & Auction Clearing" visual panel) remains **PENDING** as future work.

---

## 11. Investigation of Pytest Process Exit Code vs. PowerShell Exit Code

A rigorous investigation into process exit codes resolved two separate factors:
1. **PowerShell Stderr Redirection Artefact (`2>&1`):**
   When invoking `python -m pytest ... 2>&1`, PowerShell treats warnings emitted to `stderr` (specifically `pytest_asyncio`'s `PytestDeprecationWarning`) as an internal `NativeCommandError` `ErrorRecord`. When PowerShell completes a command string containing an uncaught pipeline `ErrorRecord`, PowerShell itself terminates with exit code `1`, even when the underlying Python/pytest process exited with code `0`.
2. **Pre-existing Flaky Performance Test Under Concurrency:**
   Under heavy CPU load when multiple background tasks ran concurrently, `tests/test_dashboard_data_service.py::test_sub_millisecond_query_performance` transiently took $7.83\text{ ms}$ (threshold $< 5.0\text{ ms}$), causing a genuine pytest failure (`PYTEST_PROCESS_EXIT_CODE=1`). When run without CPU contention or in isolation, this benchmark consistently passes ($\sim 1.5\text{–}3.2\text{ ms}$).
3. **Confirmed Clean Execution:**
   Running the complete test suite cleanly (`python -m pytest -q -W ignore`) confirms **311 passed in 80.00s**, with `PYTEST_EXIT_CODE=0` and PowerShell command exit code `0`.

