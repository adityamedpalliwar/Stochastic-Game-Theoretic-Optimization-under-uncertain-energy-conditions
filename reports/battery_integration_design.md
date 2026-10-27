# Battery Storage Integration Design Note (Phase 5A)

**Project:** Stochastic Game-Theoretic Optimization under Uncertain Energy Conditions  
**Phase:** 5A — Residential Battery Storage Integration (Two-Household Architecture)  
**Date:** October 2026  
**Status:** Design Proposal & Architectural Specification  

---

## 1. Executive Summary & Objective

In Phases 1 through 4, the microgrid prototype established:
1. LSTM deterministic forecasts and Protocol B Monte Carlo scenario generation (1,000 paired realizations).
2. Physical energy balance conservation across 3 households (H001 seller, H002 buyer, H003).
3. A two-player normal-form game with actions `['OFFER_P2P', 'EXPORT_GRID']` and `['ACCEPT_P2P', 'GRID_IMPORT']`.
4. Incentive-compatible fixed tariffs: Retail Import = 0.30 AUD/kWh, Feed-in Credit = 0.08 AUD/kWh, Mid-Market P2P = 0.19 AUD/kWh.
5. 94 passing regression tests verifying mathematical, physical, and financial conservation.

The objective of **Phase 5A** is to integrate physical battery storage dispatch into the two-household energy accounting and payoff pipeline without breaking the validated baseline. This document audits the existing battery storage model, specifies the state-of-charge (SOC) transition mechanics, defines an explicit and transparent dispatch policy, establishes financial and energy conservation identities, and details the test architecture. Multi-household clearing is deferred to Phase 5B.

---

## 2. Audit of Existing Battery Storage Model (`src/energy/battery.py`)

### 2.1 Physics & State Transition Review
The existing `BatteryStorage` class models a residential battery with the following parameters:
- **Nominal Capacity ($E_{cap}$):** 5.0 kWh
- **Operational SOC limits:** $[\text{SOC}_{min}, \text{SOC}_{max}] = [0.10, 0.90]$, corresponding to energy limits $[E_{min}, E_{max}] = [0.50, 4.50]$ kWh.
- **Power limits:** $P_{ch,max} = 2.5$ kW, $P_{dis,max} = 2.5$ kW.
- **Efficiencies:** Charging efficiency $\eta_{ch} = 0.95$, discharging efficiency $\eta_{dis} = 0.95$ (implied round-trip efficiency $\eta_{rt} = \eta_{ch} \cdot \eta_{dis} = 0.9025$ or 90.25%).
- **Default Initial SOC:** $\text{SOC}_0 = 0.50$ ($E_0 = 2.50$ kWh).

### 2.2 Mathematical State Transition Verification
For a timestep of duration $\Delta t$ hours (with $\Delta t = 1.0$ h in hourly resolution):
Let $C[t]$ denote energy entering the battery terminals from the household/solar system (in kWh), and let $D[t]$ denote energy delivered from the battery terminals to the household load (in kWh).

The internal stored chemical energy $E[t]$ transitions according to:
$$E[t+1] = E[t] + \eta_{ch} \cdot C[t] - \frac{D[t]}{\eta_{dis}}$$

Inspecting `src/energy/battery.py`:
1. **Charging Update:**
   - Power constraint: $C[t] \le P_{ch,max} \cdot \Delta t = 2.5 \cdot \Delta t$.
   - Capacity headroom constraint: $E[t] + \eta_{ch} \cdot C[t] \le E_{max} \implies C[t] \le \frac{E_{max} - E[t]}{\eta_{ch}}$.
   - Actual energy drawn:
     $$C[t] = \max\left(0, \min\left(E_{available}, P_{ch,max} \cdot \Delta t, \frac{E_{max} - E[t]}{\eta_{ch}}\right)\right)$$
   - Stored energy update:
     $$E[t+1] = E[t] + \eta_{ch} \cdot C[t]$$
2. **Discharging Update:**
   - Power constraint: $D[t] \le P_{dis,max} \cdot \Delta t = 2.5 \cdot \Delta t$.
   - Capacity footroom constraint: $E[t] - \frac{D[t]}{\eta_{dis}} \ge E_{min} \implies D[t] \le (E[t] - E_{min}) \cdot \eta_{dis}$.
   - Actual energy delivered:
     $$D[t] = \max\left(0, \min\left(E_{requested}, P_{dis,max} \cdot \Delta t, (E[t] - E_{min}) \cdot \eta_{dis}\right)\right)$$
   - Stored energy update:
     $$E[t+1] = E[t] - \frac{D[t]}{\eta_{dis}}$$
3. **Mutual Exclusion:**
   - `BatteryStorage.step` raises `ValueError` if both $E_{available} > 0$ and $E_{requested} > 0$, enforcing $C[t] \cdot D[t] = 0$.

### 2.3 Findings & Adjustments Required
The existing class accurately respects the required physics and efficiency definitions. However, for full integration into the two-household pipeline:
1. `BatteryStorage` modifies internal state in-place. For reproducible Monte Carlo and scenario evaluations, we need a clean mechanism to snapshot/reset state or evaluate stateless transitions given initial energy $E_t$.
2. Energy accounting requires tracking both initial SOC ($E[t]$) and final SOC ($E[t+1]$) in the balance records to guarantee transparency and prevent artificial gains from unmetered depletion.
3. Power limits must explicitly incorporate the interval duration $\Delta t$ hours.

---

## 3. Dispatch Policy & Order of Operations

### 3.1 Transparent Baseline Policy (Behind-The-Meter Priority)
We specify a deterministic, rule-based baseline policy. This policy does **not** assume an optimal foresight dynamic program or an arbitrage solver; it reflects standard residential self-consumption priority (Behind-The-Meter / BTM):

```
┌────────────────────────────────────────────────────────┐
│ 1. Local Solar Self-Consumption                        │
│    E_self = min(Demand, Solar)                         │
│    Unmet Demand  ΔD = max(0, Demand - Solar)           │
│    Surplus Solar ΔG = max(0, Solar - Demand)           │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ 2. Behind-The-Meter (BTM) Battery Dispatch             │
│    If ΔG > 0: Charge battery with available surplus    │
│               C = min(ΔG, Headroom, P_ch_max * Δt)     │
│               Remaining surplus: S_post = ΔG - C       │
│    If ΔD > 0: Discharge battery to meet unmet demand   │
│               D = min(ΔD, Stored_avail, P_dis_max * Δt)│
│               Remaining deficit: L_post = ΔD - D       │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ 3. Bilateral Peer-to-Peer (P2P) Market Clearing        │
│    Traded quantity on post-battery surplus/deficit:    │
│    Q_P2P = min(S_1_post, L_2_post)  if (OFFER, ACCEPT) │
│    Q_P2P = 0.0                      otherwise          │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ 4. Central Grid Residual Balancing                     │
│    Grid Import:  L_post - Q_P2P_bought                 │
│    Grid Export:  S_post - Q_P2P_sold                   │
└────────────────────────────────────────────────────────┘
```

### 3.2 Impact of Dispatch Ordering: BTM-First vs P2P-First
An explicit design choice is the ordering of battery dispatch versus P2P market clearing:

1. **Policy Option A (BTM-First, Implemented Baseline):**
   - *Logic:* The prosumer uses their battery to maximize local self-sufficiency first. Any remaining surplus is offered to the P2P market; any remaining deficit is requested from the P2P market.
   - *Implication on P2P Market:*
     - The seller charges their own battery before offering surplus. This **reduces** the surplus $S_{1}^{post}$ available to trade.
     - The buyer discharges their own battery before seeking external energy. This **reduces** the deficit $L_{2}^{post}$ needed from the market.
     - Consequently, feasible P2P trading volume $Q_{P2P} = \min(S_1^{post}, L_2^{post})$ is generally lower than in a battery-free microgrid.
   - *Rationale:* In residential settings, avoiding the retail import tariff (0.30 AUD/kWh) via local battery discharge is economically superior to buying P2P at 0.19 AUD/kWh. Storing solar for later self-consumption (avoiding 0.30 AUD/kWh minus efficiency losses) also beats exporting at 0.08 AUD/kWh and can compete with P2P export at 0.19 AUD/kWh.

2. **Policy Option B (P2P-First):**
   - *Logic:* Households trade all raw surplus and deficit on the P2P market first, then use batteries to absorb or supply the leftover energy before hitting the grid.
   - *Implication on P2P Market:* P2P volume is maximized, but battery dispatch becomes secondary and might displace high-value local self-consumption.

**Design Decision:** Option A (BTM-First) is adopted as the primary physical baseline. It reflects standard inverter logic and autonomous residential battery controllers. In Section 5 of the validation report, we explicitly document this trade-off.

### 3.3 Explicit Exclusions for Phase 5A
To maintain transparency and prevent unvalidated complexity:
- **No grid charging:** The battery charges only from local surplus solar generation. It does not charge from the central grid.
- **No dynamic battery arbitrage:** The battery does not speculate on price spreads across time steps.
- **No multi-period lookahead LP/MIP:** Dispatch is purely causal (timestep by timestep).

---

## 4. Energy Conservation and Balance Accounting

For any household $i$ at interval $t$ with demand $D_i$ and solar generation $G_i$:

### 4.1 Component Invariants
1. **Self-consumption:**
   $$E_{self,i} = \min(D_i, G_i)$$
2. **Battery flows:**
   - Charging input $C_i \ge 0$, Discharging output $D_i \ge 0$, with $C_i \cdot D_i = 0$.
   - Stored energy update:
     $$E_{stored,i}[t+1] = E_{stored,i}[t] + \eta_{ch} \cdot C_i - \frac{D_i}{\eta_{dis}}$$
3. **P2P trade flows:**
   - P2P bought $q_{buy,i} \ge 0$, P2P sold $q_{sell,i} \ge 0$, with $q_{buy,i} \cdot q_{sell,i} = 0$.
   - $q_{buy,i} \le L_{post,i}$ and $q_{sell,i} \le S_{post,i}$.
4. **Grid interaction:**
   - Grid import: $GridImport_i = L_{post,i} - q_{buy,i} \ge 0$.
   - Grid export: $GridExport_i = S_{post,i} - q_{sell,i} \ge 0$.
   - Complementarity: $GridImport_i \cdot GridExport_i = 0$.

### 4.2 Household-Level Conservation Laws
- **Demand Conservation:**
  Every unit of household demand must be supplied by direct solar, battery discharge, P2P import, or grid import:
  $$D_i = E_{self,i} + D_i + q_{buy,i} + GridImport_i$$
- **Solar Conservation:**
  Every unit of solar generation must be self-consumed, charged to battery, sold to P2P, or exported to grid:
  $$G_i = E_{self,i} + C_i + q_{sell,i} + GridExport_i$$
- **Net Balance Identity:**
  $$(D_i - G_i) = (GridImport_i - GridExport_i) + (q_{buy,i} - q_{sell,i}) + (D_i - C_i)$$

### 4.3 Community-Level Conservation
Summing across all households in the microgrid:
$$\sum_i q_{buy,i} = \sum_i q_{sell,i} = Q_{P2P}$$
$$\sum_i (D_i - G_i) = \sum_i (GridImport_i - GridExport_i) + \sum_i (D_i - C_i)$$
The community grid net imbalance equals total consumer net demand offset by net battery delivery into the households.

---

## 5. Financial Accounting & Payoff Structure

### 5.1 Cash Flows and Utility Definition
For household $i$, financial cash flows consist of:
- **Grid Import Cost:** $GridImport_i \cdot p_{import}$ (AUD)
- **Grid Export Revenue:** $GridExport_i \cdot p_{export}$ (AUD)
- **P2P Purchase Payment:** $q_{buy,i} \cdot p_{p2p}$ (AUD)
- **P2P Sales Revenue:** $q_{sell,i} \cdot p_{p2p}$ (AUD)

Net electricity expenditure is:
$$C_i^{net} = (GridImport_i \cdot p_{import} + q_{buy,i} \cdot p_{p2p}) - (GridExport_i \cdot p_{export} + q_{sell,i} \cdot p_{p2p})$$

Utility is defined strictly as negative net expenditure:
$$U_i = -C_i^{net}$$

### 5.2 Battery Accounting & Valuation of Stored Energy
A known pitfall in storage analysis is reporting "cost savings" that actually stem from depleting stored energy that was paid for or stored in prior intervals:
1. **Initial & Final SOC Reporting:** Every simulation and test must explicitly report:
   - Initial stored energy $E_{initial}$ and $\text{SOC}_{initial}$.
   - Final stored energy $E_{final}$ and $\text{SOC}_{final}$.
   - Net stored energy change $\Delta E_{stored} = E_{final} - E_{initial}$.
2. **Degradation Cost Modeling:**
   - In Phase 5A baseline, physical battery cell degradation is assumed to be zero ($c_{deg} = 0.0$ AUD/kWh throughput) to maintain a transparent, unencumbered baseline.
   - However, our software interface will provide an explicit parameter `degradation_cost_per_kwh: float = 0.0` so that future degradation models can be activated without breaking function signatures.
3. **Terminology:** The sum $U_1 + U_2$ will continue to be reported as **Combined Household Utility** (avoiding the label "total social welfare", as fixed tariffs omit producer/retailer surplus and network distribution tariffs).

---

## 6. Implementation Architecture

### 6.1 Modules to Extend / Introduce
1. **`src/energy/battery.py`:**
   - Retain full backward compatibility with existing tests.
   - Add explicit support for initial charge parameterization, resetting, and copy helpers.
   - Add helper `dispatch_step(demand_deficit_kwh, solar_surplus_kwh, duration_hours)` returning a clean, validated `BatteryDispatchResult`.
2. **`src/energy/energy_balance.py`:**
   - Retain existing `EnergyBalance` and `PostTradeEnergyBalance` classes unaltered (preserving all 94 existing tests).
   - Introduce `BatteryAwareEnergyBalance` and `BatteryAwarePostTradeBalance` (or a unified builder `compute_battery_aware_balance` and `compute_battery_post_trade_balance`) that encapsulate solar, battery charge/discharge, initial/final SOC, and remaining surplus/deficit.
3. **`src/game/payoff_matrix.py` & `src/game/game.py`:**
   - Update `build_two_household_payoff_matrix` and `run_two_household_game` to accept either battery-aware balances or pre-adjusted surplus/deficits.
   - Record battery state and initial/final SOC in game comparison records.
4. **`src/stochastic/monte_carlo.py`:**
   - Provide battery-aware stochastic simulation methods that track battery state transitions across scenarios or given an initial SOC distribution.

---

## 7. Test Strategy & Verification Plan (Stage 5)

We will introduce `tests/test_battery_integration.py` covering all 10 specific requirements:
1. **SOC Boundary Conditions:** Empty permitted battery ($\text{SOC}=0.10$), full permitted battery ($\text{SOC}=0.90$), and intermediate SOC ($0.50$).
2. **Charge and Discharge Power Limits:** 2.5 kW power limit enforced across varying durations $\Delta t$.
3. **Efficiency Transitions:** Verified calculation of $\eta_{ch}=0.95$ and $\eta_{dis}=0.95$ loss mechanics.
4. **Insufficient Solar Surplus:** Battery charge request clamped to available solar.
5. **Insufficient Stored Energy:** Battery discharge request clamped to available energy above $E_{min}$.
6. **Mutual Exclusion:** Guarantee no simultaneous charging and discharging under any condition.
7. **Physical Energy Conservation:** Strict checks on $D = E_{self} + D_{bat} + q_{buy} + GridImport$ and $G = E_{self} + C_{bat} + q_{sell} + GridExport$.
8. **Financial Payoff Consistency:** Verified across all four strategy profiles `(OFFER, ACCEPT)`, `(OFFER, GRID)`, `(EXPORT, ACCEPT)`, `(EXPORT, GRID)`.
9. **Monte Carlo Reproducibility:** Deterministic Protocol B seed generation with battery integration.
10. **Baseline Compatibility:** Battery-disabled run ($\text{capacity}=0$ or idle battery) matches original battery-free baseline results to within $10^{-9}$.

---

## 8. Summary Recommendation
This design note establishes the mathematical, physical, and financial foundation for Stage 2 through Stage 6. It maintains complete consistency with existing unit conventions (kWh, kW, hours, AUD, AUD/kWh) and preserves 100% of validated baseline behavior.
