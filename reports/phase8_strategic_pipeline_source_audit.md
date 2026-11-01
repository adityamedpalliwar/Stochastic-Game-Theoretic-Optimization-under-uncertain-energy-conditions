# Source-Code Audit: Phase 8 Strategic Bidding and Nash Equilibrium Pipeline

**Report Document:** `reports/phase8_strategic_pipeline_source_audit.md`  
**Audit Type:** Read-Only Source-Code Verification & Architectural Trace  
**Audited Modules:** `src/game/`, `src/stochastic/monte_carlo.py`, `src/energy/`, and associated unit tests  
**Status:** COMPLETE AUDIT (No source code, test, or baseline modifications performed)  

---

## 1. Executive Summary & Verification Verdict

An exhaustive, read-only source-code inspection of the repository was conducted to verify the status of the Phase 8 strategic bidding, continuous double auction, and Nash equilibrium implementation. 

### Key Findings:

1. **A Three-Player Strategic Nash Equilibrium Game is Genuinely Implemented in `src/game/strategic_solver.py` and `src/game/strategic_market.py`:**
   - The repository contains a fully working, rigorous implementation of an ex-post deterministic continuous double auction and an exhaustive pure-strategy Nash equilibrium solver.
   - For all hours where H001, H002, and H003 are active, it evaluates all $7^3 = 343$ strategic price profiles on the discrete price grid $\mathcal{P} = \{0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30\}$ AUD/kWh.
   - For each profile, it executes the full continuous double auction (`clear_strategic_double_auction`), computes transaction-level allocations and midpoint prices, and checks all $343 \times 3 \times 6 = 6,174$ unilateral deviations per hour to detect pure-strategy Nash equilibria (PNE).
   - All 81 Phase 8 unit tests in `tests/test_phase8_strategic_market.py`, `tests/test_phase8_equilibrium.py`, `tests/test_phase8c_dataset_validation.py`, `tests/test_phase8d_dataset_validation.py`, `tests/test_phase8d_fairness.py`, and `tests/test_phase8d_selection.py` pass without errors.

2. **Severe Architectural Bifurcation — Legacy Phase 5/6 Modules are Completely Bypassed:**
   - The files `src/game/payoff_matrix.py`, `src/game/nash.py`, `src/game/best_response.py`, and `src/game/game.py` belong to the **legacy Phase 5/6 2-player binary participation game** (`OFFER_P2P` vs `EXPORT_GRID`, `ACCEPT_P2P` vs `GRID_IMPORT`).
   - These legacy files **do not support 3 players**, **do not support the 7-price action grid**, and **are completely bypassed by the Phase 8 solver**.
   - `src/game/strategic_solver.py` does not import or call any of these legacy files; it implements its own combinatorial profile loops, unilateral deviation checks, and Nash equilibrium detection directly.

3. **Financial Settlement Limitation in `src/game/utility.py`:**
   - `src/game/utility.py::compute_household_payoff()` accepts only a **single scalar price** `p2p_price_aud: float`. It **cannot directly handle multiple bilateral transactions with different midpoint prices** unless a pre-calculated volume-weighted average price (VWAP) is supplied.
   - Consequently, `src/game/strategic_market.py` **bypasses `compute_household_payoff()` entirely**, implementing transaction-level revenue, payment, and incremental welfare accounting directly inline with machine-precision conservation enforcement.

4. **The Stochastic Connection is Missing from Phase 8:**
   - The current Phase 8 implementation is **100% deterministic ex-post** (evaluated on historical post-battery physical positions from Phase 7.1).
   - Monte Carlo scenarios in `src/stochastic/monte_carlo.py` are **not connected** to the Phase 8 double auction or the strategic solver. In `monte_carlo.py`, `build_stochastic_payoff_matrix()` still targets the legacy 2-player binary game, while `run_stochastic_multi_household_clearing()` targets the Phase 5B rule-based market clearing (`src/energy/market_clearing.py`) at a fixed price of \$0.19/kWh.
   - An ex-ante stochastic strategic game—where households commit price bids before uncertainty is realized and expected payoffs $\mathbb{E}[U(a)]$ are evaluated across scenarios—**has not been implemented in code** (it was deferred to Phase 8E in `reports/phase8_mathematical_design.md`).

---

## 2. File-by-File Source Code Inspection

### 2.1 `src/game/strategic_market.py`
- **File Length:** 719 lines.
- **Role:** Phase 8B.1 Price-Only Strategic Double-Auction Market Clearing Engine.
- **Key Entities:**
  - `MarketRole(str, Enum)`: `SELLER`, `BUYER`, `INACTIVE` (lines 43–49).
  - `STRATEGIC_PRICE_GRID`: `(0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30)` (line 36).
  - `MarketOrder`: Dataclass validating household order, role, price belonging to discrete grid, and positive physical quantity (lines 226–280).
  - `StrategicTransaction`: Dataclass recording bilateral trade details: seller, buyer, ask, bid, midpoint price $p_{ij} = (a_i + b_j)/2$, volume $q_{ij}$, revenue, payment (lines 281–315).
  - `StrategicMarketResult`: Dataclass capturing transaction ledgers, allocations, revenues, payments, incremental benefits, unmatched volumes, and conservation residuals (lines 318–396).
  - `clear_strategic_double_auction()`: Main clearing entry point (lines 440–719).
- **Clearing Mechanics:**
  - Sorts sellers in merit order (lowest ask first, tie-break by `household_id`).
  - Sorts buyers in merit order (highest bid first, tie-break by `household_id`).
  - Checks crossing condition ($b_j \ge a_i$).
  - Bilinear pro-rata rationing for tied price groups: $q_{ij} = (q_i^{\text{alloc}} \cdot q_j^{\text{alloc}}) / Q_{\text{trade}}$.
  - Transaction pricing: midpoint $p_{ij} = (a_i + b_j) / 2$.
  - Invariants: Verifies energy conservation ($\sum q_i^{\text{sold}} == \sum q_j^{\text{bought}}$), financial payment balance ($\sum \text{Pmt} == \sum \text{Rev}$), and welfare identity ($\Delta W == 0.22 \times Q_{\text{P2P}}$) within numerical tolerance $10^{-6}$.

### 2.2 `src/game/utility.py`
- **File Length:** 245 lines.
- **Role:** Utility and payoff functions (Phase 4/5 baseline).
- **Key Entities:**
  - `P2PTransaction`: Dataclass representing a peer-to-peer transfer (lines 27–70).
  - `HouseholdPayoff`: Dataclass capturing detailed financial accounting (lines 72–112).
  - `compute_household_payoff()` (lines 114–245):
    - Signature: `compute_household_payoff(house_id: str, deficit_kwh: float, surplus_kwh: float, grid_import_price_aud: float, grid_export_credit_aud: float, p2p_energy_sold_kwh: float = 0.0, p2p_energy_bought_kwh: float = 0.0, p2p_price_aud: float = 0.0, battery_charged_kwh: float = 0.0, battery_discharged_kwh: float = 0.0, battery_initial_soc: float = 0.0, battery_final_soc: float = 0.0, battery_degradation_cost_per_kwh: float = 0.0) -> HouseholdPayoff`.
    - Computes:
      - `p2p_payment = p2p_bought * p2p_price_aud` (line 216).
      - `p2p_revenue = p2p_sold * p2p_price_aud` (line 217).
      - `utility = -net_expenditure` (line 226).
- **Critical Observation:** Only accepts a single scalar `p2p_price_aud`. It cannot represent multiple transactions with differing midpoint prices without external price averaging. It is **not called anywhere in the Phase 8 pipeline**.

### 2.3 `src/game/payoff_matrix.py`
- **File Length:** 222 lines.
- **Role:** Normal-form payoff matrix builder for 2-household binary trading.
- **Key Entities:**
  - `GamePayoffMatrix`: Dataclass storing `payoffs_p1: np.ndarray`, `payoffs_p2: np.ndarray` (lines 23–56).
  - `build_two_household_payoff_matrix()`: Fixed action sets (lines 151–152):
    - `actions_p1 = ["OFFER_P2P", "EXPORT_GRID"]`
    - `actions_p2 = ["ACCEPT_P2P", "GRID_IMPORT"]`
- **Critical Observation:** Hard-coded for exactly 2 players with binary decisions. Incapable of supporting 3 players or the 7-price discrete action grid. Completely disconnected from Phase 8.

### 2.4 `src/game/nash.py`
- **File Length:** 168 lines.
- **Role:** Pure-strategy Nash equilibrium solver for 2-player normal-form games.
- **Key Entities:**
  - `NashEquilibrium` (lines 22–45).
  - `EquilibriumAnalysisResult` (lines 46–70).
  - `find_pure_nash_equilibria(matrix: GamePayoffMatrix, tolerance: float = 1e-6)` (lines 71–168).
- **Critical Observation:** Strictly operates on `GamePayoffMatrix` ($2 \times 2$ matrix). Disconnected from Phase 8.

### 2.5 `src/game/best_response.py`
- **File Length:** 111 lines.
- **Role:** Best-response analysis for 2-player normal-form games.
- **Key Entities:**
  - `BestResponseDetail` (lines 21–34).
  - `compute_detailed_best_responses(matrix: GamePayoffMatrix, tolerance: float = 1e-6)` (lines 35–111).
- **Critical Observation:** Strictly operates on `GamePayoffMatrix` ($2 \times 2$ matrix). Disconnected from Phase 8.

### 2.6 `src/game/game.py`
- **File Length:** 199 lines.
- **Role:** Two-household game runner comparing uncoordinated baseline against $2 \times 2$ equilibrium.
- **Key Entities:**
  - `GameComparisonResult` (lines 15–79).
  - `run_two_household_game(balance_p1, balance_p2, ...)` (lines 81–199).
- **Critical Observation:** Strictly 2-player binary participation model. Disconnected from Phase 8.

### 2.7 `src/stochastic/monte_carlo.py`
- **File Length:** 742 lines.
- **Role:** Monte Carlo simulation for forecast uncertainty and scenario generation.
- **Key Entities:**
  - `estimate_expected_payoff_matrix()` / `build_stochastic_payoff_matrix()` (lines 335–532): Evaluates expected payoffs across 1,000 scenarios, but populates `GamePayoffMatrix` for the 2-player binary game.
  - `run_stochastic_multi_household_clearing()` (lines 561–742): Evaluates scenario-by-scenario clearing across 1,000 scenarios, but calls `src/energy/market_clearing.py::clear_multi_household_market()` with fixed price \$0.19 AUD/kWh and priority/pro-rata matching.
- **Critical Observation:** Contains no connection to strategic bidding, discrete price grids, or the strategic double auction solver.

### 2.8 Additional Connected Modules
- **`src/game/strategic_solver.py` (759 lines):**  
  The actual Phase 8C deterministic Nash equilibrium solver. Implements `solve_deterministic_nash_equilibrium()` and `solve_nash_from_physical_flows()`. Handles $N$ players, dynamic roles, combinatorial price profiles ($7^3 = 343$), unilateral deviation verification ($6,174$ deviations), strict/weak classification, Pareto-undominated filtering, and 5-step representative equilibrium selection.
- **`src/game/dataset_evaluation.py` (372 lines):**  
  Batch runner executing `solve_deterministic_nash_equilibrium` across all 1,752 hours of Phase 7 test data from `reports/phase7_hourly_records.csv`.
- **`src/game/equilibrium_selection.py` (499 lines):**  
  Phase 8D selection strategies on the Pareto frontier: Reference (A), Seller-favouring (B), Buyer-favouring (C), Max-Min fair (D), Nash Social Welfare (E), and Hybrid (F).
- **`src/game/fairness_metrics.py` (297 lines):**  
  Distributional fairness metrics: standard Gini, normalized Gini ($G_{\text{norm}} \in [0, 1]$), participant benefit shares, Max-Min payoff, benefit range, and log Nash Social Welfare.
- **`src/game/phase8d_evaluation.py` (585 lines):**  
  Dataset-wide evaluation engine generating `reports/phase8d_hourly_selection.csv` and `reports/phase8d_strategy_comparison.csv`.

---

## 3. Detailed Call Chain & Execution Flow Analysis

The prompt specifies an expected conceptual call chain:
$$\text{Physical surplus/deficit} \to \text{MarketOrder creation} \to \texttt{clear\_strategic\_double\_auction()} \to \text{Transaction results} \to \text{Household utility calculation} \to \text{Strategic payoff matrix/tensor} \to \text{Best-response calculation} \to \text{Nash equilibrium detection}$$

Here is the exact source-code trace through the repository:

```
[Hourly Physical Meter Position]
  (Demand, Solar, Battery Charge/Discharge)
         │
         ▼
[compute_physical_net_position()] (src/game/strategic_market.py:165)
         │
         ▼
[solve_deterministic_nash_equilibrium()] (src/game/strategic_solver.py:364)
  - Identifies active roles: Seller (surplus > 0), Buyer (deficit > 0), Inactive
  - Generates 343 price tuples: itertools.product(STRATEGIC_PRICE_GRID, repeat=3)
         │
         ▼
[MarketOrder Creation in Combinatorial Loop] (src/game/strategic_solver.py:534-542)
  - Constructs MarketOrder for each active household and price
         │
         ▼
[clear_strategic_double_auction()] (src/game/strategic_market.py:440)
  - Merit-order sorting: sellers ascending, buyers descending
  - Midpoint price: p_ij = (a_i + b_j)/2
  - Pro-rata volume rationing for ties
  - Physical and financial conservation checks
         │
         ▼
[StrategicMarketResult & Transaction Ledger] (src/game/strategic_market.py:700)
  - Contains StrategicTransaction list, revenues, payments
         │
         ▼
[Incremental Benefit Calculation (Inline Utility)] (src/game/strategic_solver.py:553-561)
  - Seller: ΔU_i = sum q_ij * (p_ij - p_exp)
  - Buyer:  ΔU_j = sum q_ij * (p_imp - p_ij)
  (BYPASSES src/game/utility.py::compute_household_payoff)
         │
         ▼
[Combinatorial Payoff Dictionary: cleared_cache] (src/game/strategic_solver.py:526, 562)
  - Hash map: (p_1, p_2, p_3) -> (StrategicMarketResult, payoffs_dict)
  (NO 3D NUMPY TENSOR OR GamePayoffMatrix USED)
         │
         ▼
[Unilateral Deviation Loop (Inline Best-Response)] (src/game/strategic_solver.py:567-600)
  - Evaluates all alternative prices on grid for each active player
  - Tests whether ΔU_dev > ΔU_orig + tol
  (BYPASSES src/game/best_response.py)
         │
         ▼
[Pure Nash Equilibrium Detection] (src/game/strategic_solver.py:601-634)
  - Retains profiles where no profitable deviation exists
  - Classifies STRICT vs WEAK
  (BYPASSES src/game/nash.py)
         │
         ▼
[Pareto Frontier & Representative Selection] (src/game/strategic_solver.py:653-694)
  - identify_pareto_undominated()
  - select_representative_equilibrium()
```

### Traceability Matrix for the Connections:

| Pipeline Step | Caller / Callee File & Function | Signatures & Source Lines | Status | Details |
| :--- | :--- | :--- | :--- | :--- |
| **1. Net Position $\to$ Orders** | **Caller:** `solve_nash_from_physical_flows` or `solve_deterministic_nash_equilibrium`<br/>**Callee:** `compute_physical_net_position` & `MarketOrder` | `compute_physical_net_position(...) -> Tuple[float, float, float]` (`strategic_market.py:165-224`)<br/>`MarketOrder(...)` (`strategic_market.py:226-280`) | **Implemented** | Post-battery flows converted to `surplus`, `deficit`, and `MarketRole`. Orders instantiated. |
| **2. Orders $\to$ Market Clearing** | **Caller:** `solve_deterministic_nash_equilibrium` (`strategic_solver.py:544`)<br/>**Callee:** `clear_strategic_double_auction` | `clear_strategic_double_auction(orders, grid_import_tariff_aud, grid_export_credit_aud, all_households, tolerance, price_grid) -> StrategicMarketResult` (`strategic_market.py:440-719`) | **Implemented** | Double auction executed for each candidate profile. Merit order and pro-rata rationing enforced. |
| **3. Clearing $\to$ Transactions** | **Caller:** `clear_strategic_double_auction` (`strategic_market.py:596-608`)<br/>**Callee:** `StrategicTransaction` | `StrategicTransaction(transaction_id, seller_id, buyer_id, seller_ask_aud_per_kwh, buyer_bid_aud_per_kwh, price_aud_per_kwh, traded_energy_kwh, seller_revenue_aud, buyer_payment_aud)` (`strategic_market.py:281-315`) | **Implemented** | Granular bilateral trade ledger with midpoint prices and conservation verification. |
| **4. Transactions $\to$ Household Utility** | **Caller:** `strategic_market.py:615-616` and `strategic_solver.py:553-561`<br/>**Callee:** Inline calculation | `seller_benefits[s_id] += q_ij * (tx_price - p_exp)`<br/>`buyer_benefits[b_id] += q_ij * (p_imp - tx_price)` | **Partially Implemented (Bypassed)** | Computes incremental welfare gain $\Delta U_i \ge 0$. `src/game/utility.py::compute_household_payoff` is **bypassed**. |
| **5. Utility $\to$ Payoff Tensor** | **Caller:** `solve_deterministic_nash_equilibrium` (`strategic_solver.py:526, 562`)<br/>**Callee:** `cleared_cache[p_tup] = (res, payoffs)` | In-memory `Dict[Tuple[float, ...], Tuple[StrategicMarketResult, Dict[str, float]]]` | **Partially Implemented (Bypassed)** | Payoff data stored in Python dictionary. Formal 3D tensor or `GamePayoffMatrix` abstraction is **missing**. |
| **6. Tensor $\to$ Best-Response** | **Caller:** `solve_deterministic_nash_equilibrium` (`strategic_solver.py:573-599`)<br/>**Callee:** Inline deviation check | `for alt_price in grid_prices: ... if dev_payoff > orig_payoff + tol: is_pne = False` | **Partially Implemented (Bypassed)** | Unilateral deviations checked inline. Explicit $BR_i(a_{-i})$ correspondence and `src/game/best_response.py` are **bypassed**. |
| **7. Best-Response $\to$ Nash Detection** | **Caller:** `solve_deterministic_nash_equilibrium` (`strategic_solver.py:601-634`)<br/>**Callee:** Inline classification & record creation | `NashEquilibriumRecord(...)` (`strategic_solver.py:78-106`) | **Implemented (Bypassed)** | Pure Nash equilibria detected and classified. `src/game/nash.py` is **bypassed**. |

---

## 4. Verification of the Three-Player Game

The existing code was evaluated against all eight structural requirements for the 3-player game:

1. **H001, H002, and H003 as Players:**  
   **CONFIRMED.** Supported in `strategic_solver.py` via `all_households: Sequence[str] = ("H001", "H002", "H003")` (line 368). All 3 households are tracked across physical flows, order generation, market results, and payoff vectors.

2. **Dynamic Hourly Buyer/Seller Roles:**  
   **CONFIRMED.** Supported in `strategic_solver.py` (lines 443–472). Roles are assigned dynamically from net meter flow:
   - Surplus $> 10^{-6}$ kWh $\implies$ `MarketRole.SELLER`
   - Deficit $> 10^{-6}$ kWh $\implies$ `MarketRole.BUYER`
   - Inactive $\le 10^{-6}$ kWh $\implies$ `MarketRole.INACTIVE` (action space $A_i = \{\emptyset\}$)
   - Simultaneous surplus and deficit raises `ValueError`.

3. **Seven-Price Action Grid:**  
   **CONFIRMED.** Strictly enforces `STRATEGIC_PRICE_GRID = (0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30)` AUD/kWh. Validated by `validate_price_grid()` (`strategic_market.py:51–96`).

4. **All 343 Price Profiles When All Three Players are Active:**  
   **CONFIRMED.** When 3 households are active (e.g. 1 seller + 2 buyers, or 2 sellers + 1 buyer):
   - `itertools.product(grid_prices, repeat=3)` generates all $7^3 = \mathbf{343}$ joint strategy profiles (`strategic_solver.py:519`).
   - In the 1,752-hour dataset, exactly 1,751 hours have 3 active players, and all 343 profiles are evaluated for each hour.

5. **Actual Strategic Double-Auction Clearing for Every Profile:**  
   **CONFIRMED.** `clear_strategic_double_auction()` is called 343 times per 3-player hour (`strategic_solver.py:544`). In each clearing, merit-order sorting, crossing conditions, bilateral midpoint pricing, and pro-rata rationing are executed.

6. **Three Separate Household Payoffs for Each Profile:**  
   **CONFIRMED.** For every profile, separate payoffs are recorded for H001, H002, and H003 (`strategic_solver.py:553–561`) and stored in `cleared_cache`.

7. **Unilateral Deviation and Best-Response Calculations for All Three Players:**  
   **CONFIRMED (Unilateral Deviations) / PARTIALLY IMPLEMENTED (Explicit BR Object):**  
   - For every candidate profile, each active player is tested across all 6 alternative grid prices (`strategic_solver.py:573–599`).
   - Total deviations evaluated per 3-player hour: $343 \times 3 \times 6 = \mathbf{6,174}$ deviations.
   - However, explicit best-response correspondences $BR_i(a_{-i}) \subseteq \mathcal{P}$ are not exposed as independent objects.

8. **Pure Nash Equilibrium Detection for a Three-Player Game:**  
   **CONFIRMED.** A profile is accepted as a PNE if and only if no player can unilaterally increase payoff ($U_i(\text{dev}) \le U_i(\text{orig}) + 10^{-6}$). Classified as `STRICT` or `WEAK`. Multiple equilibria are preserved, Pareto dominance is evaluated, and the 5-step representative selection heuristic is applied.

---

## 5. Detailed Financial Settlement Audit

### 5.1 Inspection of `compute_household_payoff()` (`src/game/utility.py`)

A critical inspection of `compute_household_payoff()` reveals why it cannot be used directly in a continuous double auction with heterogeneous midpoint prices:

```python
# Lines 216-217 of src/game/utility.py
p2p_payment = p2p_bought * p2p_price_aud
p2p_revenue = p2p_sold * p2p_price_aud
```

- **Single Scalar Price Limitation:** The function takes `p2p_price_aud: float = 0.0`. If a seller sells $1.0$ kWh to Buyer 1 at midpoint price $\$0.17/\text{kWh}$ and $2.0$ kWh to Buyer 2 at midpoint price $\$0.155/\text{kWh}$, passing either price into `compute_household_payoff()` violates financial accounting.
- **Pre-Averaging Requirement:** The only way `compute_household_payoff()` can produce the correct cash flows is if the caller externally computes the volume-weighted average price (VWAP):
  $$\bar{p}_s = \frac{1.0 \times 0.17 + 2.0 \times 0.155}{3.0} = \$0.1600/\text{kWh}$$
  and passes `p2p_price_aud = 0.16`.
- **No Transaction List Ingestion:** `compute_household_payoff()` does not accept `List[StrategicTransaction]` or explicit total payments/revenues.

### 5.2 How Financial Settlement is Handled in Phase 8

Because of this limitation, `src/game/strategic_market.py` implemented financial accounting directly at the transaction level:

1. **Buyer Payment & Seller Revenue:**
   - Every transaction $k$ defines $V_k = q_k \cdot p_k^{\text{tx}}$.
   - `seller_revenues[s_id] += tx_value` (`strategic_market.py:612`).
   - `buyer_payments[b_id] += tx_value` (`strategic_market.py:613`).
   - Financial conservation: $\sum \text{Buyer Payments} == \sum \text{Seller Revenues}$ is verified to machine precision ($10^{-6}$ AUD) at line 673.

2. **Grid Settlement for Unmatched Residuals:**
   - Residual surplus: $s_i^{\text{rem}} = \max(0, s_i - q_i^{\text{sold}})$, exported to the central grid at $p_{\text{exp}} = \$0.08/\text{kWh}$ (`strategic_market.py:631`).
   - Residual deficit: $d_j^{\text{rem}} = \max(0, d_j - q_j^{\text{bought}})$, imported from the central grid at $p_{\text{imp}} = \$0.30/\text{kWh}$ (`strategic_market.py:632`).

3. **Incremental Household Benefits (Welfare):**
   - Seller incremental gain over grid export:
     $$\Delta U_i = \sum_{j} q_{ij} (p_{ij} - p_{\text{exp}})$$
   - Buyer incremental gain over grid import:
     $$\Delta U_j = \sum_{i} q_{ij} (p_{\text{imp}} - p_{ij})$$
   - Total community welfare identity:
     $$\Delta W = \sum_{i} \Delta U_i + \sum_{j} \Delta U_j = (p_{\text{imp}} - p_{\text{exp}}) Q_{\text{P2P}} = 0.22 \times Q_{\text{P2P}}$$
     Enforced to machine precision at line 679.

4. **Physical Energy Conservation:**
   - Enforced: $\sum q_i^{\text{sold}} == \sum q_j^{\text{bought}} == Q_{\text{P2P}}$ (line 661).
   - Infeasibility checks guarantee $q_i^{\text{sold}} \le s_i$ and $q_j^{\text{bought}} \le d_j$ (lines 686–697).

---

## 6. Stochastic vs Deterministic Demarcation

The prompt requires determining whether Monte Carlo scenarios are used to calculate expected strategic payoffs, with bids committed before uncertainty is realized.

### Verification Finding: The Stochastic Connection Does NOT Exist in Phase 8

| Dimension | Ex-Post Deterministic Benchmark (Implemented) | Ex-Ante Stochastic Game (Design Only / Deferred) |
| :--- | :--- | :--- |
| **Target Phase** | Phase 8B / 8C / 8D (Active in repo) | Phase 8E (Documented in design; unbuilt) |
| **Information State** | Perfect information; realized post-battery flows $s_i^{\text{act}}, d_i^{\text{act}}$ known. | Incomplete information; only forecasts $(\hat{D}, \hat{S})$ and scenarios $\Omega$ available. |
| **Bidding Quantities** | Fixed to actual physical flow ($q = \text{flow}^{\text{act}}$). | Causal ex-ante quantity policy $\bar{q} = f(\text{forecasts, scenarios})$; clamped ex-post $\min(\bar{q}, \text{flow}(\omega))$. |
| **Strategy Space** | 7 discrete prices per active player ($7^3 = 343$ profiles). | Contingent two-sided price-quantity bids ($49^3 = 117,649$ profiles). |
| **Payoff Evaluation** | Deterministic realization: $U_i(p_1, p_2, p_3)$. | Expected value across 1,000 scenarios: $\mathbb{E}_\omega [U_i(a_i, a_{-i}, \omega)]$. |
| **Repo Status** | **Fully implemented and validated across 1,752 hours.** | **NOT IMPLEMENTED.** `monte_carlo.py` has zero connections to `strategic_solver.py`. |

Inspection of `src/stochastic/monte_carlo.py` proves:
- `build_stochastic_payoff_matrix()` and `estimate_expected_payoff_matrix()` (lines 335–532) build a $2 \times 2$ matrix for the Phase 5/6 binary participation game.
- `run_stochastic_multi_household_clearing()` (lines 561–742) evaluates 3 households across scenarios, but uses the rule-based priority matching engine from `src/energy/market_clearing.py` with fixed price \$0.19/kWh.
- **There is no code in the repository that computes expected payoffs for the strategic double auction under Monte Carlo uncertainty.**

---

## 7. Conflicting and Duplicated Implementations

The audit identified three major structural duplications across the repository:

### 1. Two Unrelated Market Clearing Engines:
- **Engine A (`src/energy/market_clearing.py`):**  
  Rule-based heuristic matching (Priority Order, Largest Surplus First, Pro-Rata) at a fixed mid-market price ($0.19 AUD/kWh). Used in Phase 5B, Phase 6, Phase 7, and `monte_carlo.py`. Uses `HouseholdMarketBid` and calls `compute_household_payoff()`.
- **Engine B (`src/game/strategic_market.py`):**  
  Strategic double auction with merit-order continuous clearing, discrete 7-price bidding grid, bilateral midpoint pricing, and tie-breaking rationing. Used in Phase 8B, 8C, and 8D. Uses `MarketOrder` and computes cash flows inline.

### 2. Two Disconnected Game Theory Frameworks:
- **Framework 1 (`payoff_matrix.py`, `nash.py`, `best_response.py`, `game.py`):**  
  2-player, binary-action normal-form game. Hard-coded for 2 households.
- **Framework 2 (`strategic_solver.py`, `dataset_evaluation.py`, `equilibrium_selection.py`):**  
  3-player, 7-price discrete strategic double-auction game. Evaluates 343 profiles, 6,174 deviations, and selects representative equilibria. Completely bypasses Framework 1.

### 3. Two Incompatible Payoff Definitions:
- **Total Net Expenditure Utility (`src/game/utility.py`):**  
  $U_i = -C_i^{\text{net}} \le 0$ (negative net expenditure in AUD).
- **Incremental Economic Welfare Gain (`src/game/strategic_market.py`):**  
  $\Delta U_i \ge 0$ (incremental benefit over standalone grid baseline in AUD).  
  *Note:* While the argmax of both objective functions is identical for fixed physical flows, the numerical values differ ($U_i$ is negative, $\Delta U_i$ is positive).

---

## 8. Smallest Safe Implementation & Remediation Plan

To resolve these architectural inconsistencies without breaking existing baselines or invalidating validated research reports, the following staged plan is recommended:

```
[Phase 8 Audit Complete]
         │
         ▼
[Step 1: Codebase Documentation & Clarification]
  - Document that payoff_matrix.py, nash.py, best_response.py, game.py
    are Phase 5/6 legacy benchmarks.
  - Do NOT delete them (would break test_game.py and test_financial_payoffs.py).
         │
         ▼
[Step 2: Utility Function Harmonization (Optional / Non-Breaking)]
  - Enhance compute_household_payoff() in src/game/utility.py to optionally accept:
    * p2p_payment_aud: Optional[float]
    * p2p_revenue_aud: Optional[float]
    * transactions: Optional[Sequence[StrategicTransaction]]
  - Allows utility.py to be used seamlessly with variable midpoint prices
    without affecting legacy callers.
         │
         ▼
[Step 3: Strategic Tensor & Best-Response Bridge (Optional)]
  - Introduce NPlayerPayoffTensor dataclass and compute_3player_best_responses()
    if the project requires a formal BestResponse correspondence object.
         │
         ▼
[Step 4: Phase 8E Stochastic Strategic Game (Future Work - If Required)]
  - If ex-ante stochastic bidding is required:
    Build src/stochastic/strategic_stochastic_game.py:
    1. Sample S scenarios from ValidationResidualPool.
    2. Enforce ex-ante price bids committed before uncertainty materializes.
    3. Clamp quantities per scenario: q_s = min(q_bid, flow(s)).
    4. Clear strategic double auction scenario-by-scenario.
    5. Compute expected payoff E[U(a)].
    6. Solve for ex-ante Bayesian / Stochastic Nash Equilibrium.
         │
         ▼
[Step 5: Proceed to Deliverable 2 Step 3 (Dashboard Frontend)]
  - Dashboard frontend is already fully decoupled!
  - dashboard/data_service.py queries precomputed, frozen reports
    (reports/phase8c_hourly_equilibria.csv, reports/phase8d_hourly_selection.csv).
  - Web UI can proceed safely without touching Python game engines.
```

---

## 9. Conclusion & Recommendation

1. **Phase 8 Deterministic 3-Player Strategic Pipeline is Solid:**  
   The mathematical logic in `strategic_market.py` and `strategic_solver.py` is sound, mathematically verified, conservation-preserving, and thoroughly tested across all 1,752 hours of the held-out dataset.
2. **Legacy Modules Can Remain Preserved:**  
   `payoff_matrix.py`, `nash.py`, `best_response.py`, and `game.py` do not interfere with Phase 8 because Phase 8 deliberately bypasses them. They serve as regression baselines for the Phase 5/6 2-player binary participation model.
3. **No Unplanned Re-Architecture Needed for Deliverable 2:**  
   Because Deliverable 2 (Interactive Web Dashboard) is strictly a visualization layer querying frozen CSV/JSON datasets via `dashboard/data_service.py`, it does not depend on resolving the stochastic ex-ante game or refactoring legacy modules.
4. **Approval Request:**  
   No source code was modified during this audit. The findings are submitted for user review before any subsequent implementation steps.

