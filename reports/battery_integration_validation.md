# Battery Storage Integration and Physical Feasibility Validation Report (Phase 5A)

**Project:** Stochastic Game-Theoretic Optimization under Uncertain Energy Conditions  
**Phase:** 5A — Residential Battery Storage Integration (Two-Household Architecture)  
**Date:** October 2026  
**Status:** Validated & Verified (104/104 Passing Tests)  

---

## 1. Executive Summary & Scope

Phase 5A integrates residential battery energy storage systems (BESS) into the two-household energy accounting, game-theoretic market clearing, and Monte Carlo stochastic evaluation pipeline.

The integration was accomplished strictly under the Phase 5A constraints:
1. **Preserved Baseline:** Retained the validated two-player game architecture (H001 seller, H002 buyer) and fixed tariff structure (Retail Import = 0.30 AUD/kWh, Feed-in Credit = 0.08 AUD/kWh, Mid-Market P2P = 0.19 AUD/kWh).
2. **Physical Battery Integrity:** Modelled exact state-of-charge (SOC) dynamics, efficiency losses ($\eta_{ch} = \eta_{dis} = 0.95$), power limits (2.5 kW / 2.5 kWh per 1-h step), and capacity constraints ($0.50 \le E \le 4.50$ kWh, $10\% \le \text{SOC} \le 90\%$).
3. **Transparent Baseline Policy:** Implemented an explicit Behind-The-Meter (BTM) self-consumption priority dispatch.
4. **Zero Regressions:** All 94 pre-existing tests continue to pass without modification. 10 new rigorous unit and integration tests were introduced, bringing the passing test suite to **104 tests**.
5. **No Speculative Arbitrage:** No unapproved dynamic pricing, grid charging, or multi-period optimization solvers were introduced.

---

## 2. Implemented Equations and State Transitions

### 2.1 State-of-Charge (SOC) Dynamics
For interval duration $\Delta t$ hours (with $\Delta t = 1.0$ h), let:
- $E[t]$ denote stored chemical energy at the start of the interval (kWh).
- $C[t]$ denote electrical energy entering the battery terminals from solar surplus (kWh).
- $D[t]$ denote electrical energy delivered from the battery terminals to household load (kWh).
- $\eta_{ch} = 0.95$ denote one-way charging efficiency.
- $\eta_{dis} = 0.95$ denote one-way discharging efficiency.

The stored energy state transition is:
$$E[t+1] = E[t] + \eta_{ch} \cdot C[t] - \frac{D[t]}{\eta_{dis}}$$

The state of charge is defined as:
$$\text{SOC}[t] = \frac{E[t]}{E_{cap}}$$
where nominal capacity $E_{cap} = 5.0$ kWh.

### 2.2 Operational Constraints
1. **Capacity Boundaries:**
   $$E_{min} \le E[t] \le E_{max} \quad \Longleftrightarrow \quad 0.50 \text{ kWh} \le E[t] \le 4.50 \text{ kWh}$$
   $$\text{SOC}_{min} \le \text{SOC}[t] \le \text{SOC}_{max} \quad \Longleftrightarrow \quad 10\% \le \text{SOC}[t] \le 90\%$$
2. **Terminal Power Limits:**
   $$0 \le C[t] \le P_{ch,max} \cdot \Delta t = 2.50 \text{ kWh}$$
   $$0 \le D[t] \le P_{dis,max} \cdot \Delta t = 2.50 \text{ kWh}$$
3. **Headroom and Footroom Bounds:**
   $$C[t] \le \frac{E_{max} - E[t]}{\eta_{ch}} = \frac{4.50 - E[t]}{0.95}$$
   $$D[t] \le (E[t] - E_{min}) \cdot \eta_{dis} = (E[t] - 0.50) \cdot 0.95$$
4. **Mutual Exclusion (No Simultaneous Charging & Discharging):**
   $$C[t] \cdot D[t] = 0$$

### 2.3 Thermal / Conversion Energy Losses
Total internal conversion losses during the interval are:
$$\text{Losses}[t] = (1 - \eta_{ch}) \cdot C[t] + \left(\frac{1}{\eta_{dis}} - 1\right) \cdot D[t]$$
Round-trip efficiency across a full charge-discharge cycle is:
$$\eta_{rt} = \eta_{ch} \cdot \eta_{dis} = 0.95 \cdot 0.95 = 0.9025 \quad (90.25\%)$$

---

## 3. Dispatch Policy and Order of Operations

### 3.1 Transparent Baseline Policy (Behind-The-Meter Priority)
A deterministic, rule-based dispatch policy is enforced:

```
Step 1: Direct Local Solar Self-Consumption
   E_self = min(Demand, Solar)
   Raw Deficit: ΔD = max(0, Demand - Solar)
   Raw Surplus: ΔG = max(0, Solar - Demand)

Step 2: Behind-The-Meter (BTM) Battery Dispatch
   If ΔG > 0 (Solar Surplus):
      C = min(ΔG, 2.5 * Δt, (4.50 - E_t) / 0.95)
      D = 0
      Remaining Post-Battery Surplus: S_post = ΔG - C
      Remaining Post-Battery Deficit: L_post = 0

   If ΔD > 0 (Unmet Demand Deficit):
      D = min(ΔD, 2.5 * Δt, (E_t - 0.50) * 0.95)
      C = 0
      Remaining Post-Battery Deficit: L_post = ΔD - D
      Remaining Post-Battery Surplus: S_post = 0

   If ΔG == 0 and ΔD == 0:
      C = 0, D = 0, S_post = 0, L_post = 0

Step 3: Bilateral Peer-to-Peer (P2P) Clearing
   Under (OFFER_P2P, ACCEPT_P2P):
      Q_P2P = min(S_1_post, L_2_post)
   Under all other strategy profiles:
      Q_P2P = 0.0

Step 4: Central Grid Residual Balancing
   Seller Grid Export: S_1_post - Q_P2P
   Buyer Grid Import:  L_2_post - Q_P2P
```

### 3.2 Dispatch Order Trade-Off Analysis
- **Why BTM First?**
  1. Residential inverters prioritize behind-the-meter load matching because retail grid purchase (30¢/kWh) is significantly more expensive than P2P purchase (19¢/kWh). Discharging a home battery to avoid a 30¢/kWh retail charge yields an immediate savings of 30¢/kWh (less round-trip efficiency penalty), whereas buying P2P costs 19¢/kWh.
  2. Storing excess solar locally preserves energy worth 30¢/kWh for evening peak use, which economically outperforms selling to the P2P market at 19¢/kWh or exporting to the grid at 8¢/kWh.
- **Impact on P2P Market Liquidity:**
  Because the solar seller charges its battery first, less surplus $S_1^{post}$ is offered to the market. Because the buyer discharges its battery first, less deficit $L_2^{post}$ is demanded. As demonstrated in Section 4, feasible P2P volume in any single hour decreases, but overall prosumer self-sufficiency increases and central grid stress drops to zero.

---

## 4. Empirical Validation: Battery-Free vs Battery-Aware Results

### 4.1 Target Test Hour Data Tracing & Reconciliation (`2013-06-08 10:00:00`)

To ensure absolute scientific reproducibility, we trace the exact inputs for timestamp **`2013-06-08 10:00:00`** directly from the source datasets used by the program (`data/processed/three_house_hourly_lstm_ready.csv` and `data/processed/test_predictions.csv`):

#### Source Data Comparison Across Data Channels
| Channel / Source | H001 Demand | H001 Solar | H001 Surplus | H002 Demand | H002 Solar | H002 Deficit |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Actual Ground-Truth Observation** (Row 8218 / 16978) | **0.137 kWh** | **1.382 kWh** | **1.245 kWh** | **1.838 kWh** | **0.375 kWh** | **1.463 kWh** |
| **LSTM Point Forecast $\hat{y}_t$** (`test_predictions.csv`) | 0.2569 kWh | 0.9532 kWh | 0.6963 kWh | 0.3380 kWh | 0.3484 kWh | 0.0000 kWh |
| **Monte Carlo Scenario Means $\mathbb{E}[y]$** (Protocol B, $N=1000$) | 0.5138 kWh | 1.0130 kWh | 0.4992 kWh | 0.1726 kWh | 0.3198 kWh | 0.0000 kWh |

> [!NOTE]
> **Data Mode Clarification:**
> - Section 4 evaluates the **actual realized ground-truth observation** for held-out test hour `2013-06-08 10:00:00` (identical to `demo_prototype.py` Stage 2 and `tests/test_game.py:93`).
> - Stochastic Monte Carlo scenario distributions for this hour are evaluated separately in `reports/monte_carlo_validation_report.md` and `demo_prototype.py` Stage 1.

#### Resolution of the Stated Demand/Solar Discrepancy
- **The Discrepancy:** An earlier drafting note in this report erroneously stated: *"Seller (H001): Gross Demand = 0.537 kWh, Gross Solar = 2.016 kWh, Raw Surplus = 1.479 kWh"*.
- **Root Cause Analysis:** A repository-wide audit revealed that the numbers 0.537 kWh and 2.016 kWh originated from an unrelated historical row in the raw dataset (`Solar home 2012-2013.csv`, record row 16382) that was mistakenly transcribed into the markdown narrative during preliminary drafting.
- **Verification:** The underlying Python codebase, data loaders, test files (`tests/test_battery_integration.py`, `tests/test_game.py`), and the comparative table below have **always** executed on the true source data:
  - H001: Gross Demand = **0.137 kWh**, Gross Solar = **1.382 kWh**.
  - Direct self-consumption: $\min(0.137, 1.382) = \mathbf{0.137\text{ kWh}}$.
  - Genuine Physical Surplus: $1.382 - 0.137 = \mathbf{1.245\text{ kWh}}$.
  - H002: Gross Demand = **1.838 kWh**, Gross Solar = **0.375 kWh**.
  - Direct self-consumption: $\min(1.838, 0.375) = \mathbf{0.375\text{ kWh}}$.
  - Genuine Physical Deficit: $1.838 - 0.375 = \mathbf{1.463\text{ kWh}}$.

---

### 4.2 Comprehensive Recalculation Across All Strategy Profiles

Using the exact verified inputs, retail import tariff $p_{\text{import}} = 0.30\text{ AUD/kWh}$, feed-in tariff $p_{\text{export}} = 0.08\text{ AUD/kWh}$, mid-market P2P price $p_{p2p} = 0.19\text{ AUD/kWh}$, and battery configuration (Capacity = 5.0 kWh, $\text{SOC}_0 = 50\%$, $E_0 = 2.50\text{ kWh}$, $\eta_{ch} = \eta_{dis} = 0.95$, $P_{\max} = 2.5\text{ kW}$), all energy and financial flows are recalculated below.

#### Case A: Battery-Free Operation (Baseline)
Pre-trade state:
- H001: Demand = 0.137 kWh, Solar = 1.382 kWh, Direct Self-Cons = 0.137 kWh, Surplus = 1.245 kWh, Deficit = 0.000 kWh.
- H002: Demand = 1.838 kWh, Solar = 0.375 kWh, Direct Self-Cons = 0.375 kWh, Surplus = 0.000 kWh, Deficit = 1.463 kWh.

| Strategy Profile $(A_1, A_2)$ | P2P Traded $Q_{P2P}$ | H001 Grid Export | H001 Grid Import | H001 Revenue / Cost | H001 Utility $U_1$ | H002 Grid Export | H002 Grid Import | H002 Revenue / Cost | H002 Utility $U_2$ | Combined Utility $(U_1 + U_2)$ | Conservation Residuals ($D_{res}, S_{res}$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **(OFFER_P2P, ACCEPT_P2P)** [Cleared] | **1.2450 kWh** | 0.0000 kWh | 0.0000 kWh | P2P: +0.2365 AUD | **+0.2365 AUD** | 0.0000 kWh | 0.2180 kWh | P2P: -0.2365 AUD<br>Grid: -0.0654 AUD | **-0.3020 AUD** | **-0.0654 AUD** | H001: 0.0, 0.0<br>H002: 0.0, 0.0 |
| **(OFFER_P2P, GRID_IMPORT)** [Fail] | 0.0000 kWh | 1.2450 kWh | 0.0000 kWh | Grid: +0.0996 AUD | **+0.0996 AUD** | 0.0000 kWh | 1.4630 kWh | Grid: -0.4389 AUD | **-0.4389 AUD** | **-0.3393 AUD** | H001: 0.0, 0.0<br>H002: 0.0, 0.0 |
| **(EXPORT_GRID, ACCEPT_P2P)** [Fail] | 0.0000 kWh | 1.2450 kWh | 0.0000 kWh | Grid: +0.0996 AUD | **+0.0996 AUD** | 0.0000 kWh | 1.4630 kWh | Grid: -0.4389 AUD | **-0.4389 AUD** | **-0.3393 AUD** | H001: 0.0, 0.0<br>H002: 0.0, 0.0 |
| **(EXPORT_GRID, GRID_IMPORT)** [Base] | 0.0000 kWh | 1.2450 kWh | 0.0000 kWh | Grid: +0.0996 AUD | **+0.0996 AUD** | 0.0000 kWh | 1.4630 kWh | Grid: -0.4389 AUD | **-0.4389 AUD** | **-0.3393 AUD** | H001: 0.0, 0.0<br>H002: 0.0, 0.0 |

*Conservation Notes:*
- P2P Transaction Symmetry: Buyer P2P Payment ($1.2450 \times 0.19 = 0.23655\text{ AUD}$) strictly equals Seller P2P Revenue ($0.23655\text{ AUD}$).
- Demand Conservation: H001 ($0.137 = 0.137$), H002 cleared ($1.838 = 0.375 + 1.245 + 0.218$), H002 grid ($1.838 = 0.375 + 1.463$).
- Solar Conservation: H001 cleared ($1.382 = 0.137 + 1.245$), H001 grid ($1.382 = 0.137 + 1.245$), H002 ($0.375 = 0.375$).

---

#### Case B: Battery-Aware Operation (Phase 5A Behind-The-Meter Priority)
Local BTM battery dispatch before market interaction:
- **H001 Battery Dispatch:**
  - Raw Surplus = 1.2450 kWh.
  - Charging headroom: $\min\left(2.5\text{ kW}\cdot 1\text{h}, \frac{5.0 \times 0.90 - 2.50}{0.95}\right) = \min(2.5, 2.1053) = 2.1053\text{ kWh}$.
  - Actual energy charged: $C_1 = \min(1.2450, 2.1053) = \mathbf{1.2450\text{ kWh}}$.
  - Discharged: $D_1 = 0.0000\text{ kWh}$ (mutual exclusion enforced).
  - Chemical energy stored: $1.2450 \times 0.95 = 1.18275\text{ kWh}$.
  - Final stored energy: $E_1^{\text{final}} = 2.50 + 1.18275 = \mathbf{3.6828\text{ kWh}}$ ($\text{SOC}_1 = 73.66\%$).
  - Post-battery surplus: $S_1^{\text{post}} = 1.2450 - 1.2450 = \mathbf{0.0000\text{ kWh}}$.
  - Post-battery deficit: $L_1^{\text{post}} = \mathbf{0.0000\text{ kWh}}$.

- **H002 Battery Dispatch:**
  - Raw Deficit = 1.4630 kWh.
  - Discharging footroom: $\min\left(2.5\text{ kW}\cdot 1\text{h}, (2.50 - 5.0 \times 0.10) \times 0.95\right) = \min(2.5, 1.9000) = 1.9000\text{ kWh}$.
  - Actual energy discharged: $D_2 = \min(1.4630, 1.9000) = \mathbf{1.4630\text{ kWh}}$.
  - Charged: $C_2 = 0.0000\text{ kWh}$ (mutual exclusion enforced).
  - Chemical energy drained: $1.4630 / 0.95 = 1.5400\text{ kWh}$.
  - Final stored energy: $E_2^{\text{final}} = 2.50 - 1.5400 = \mathbf{0.9600\text{ kWh}}$ ($\text{SOC}_2 = 19.20\%$).
  - Post-battery surplus: $S_2^{\text{post}} = \mathbf{0.0000\text{ kWh}}$.
  - Post-battery deficit: $L_2^{\text{post}} = 1.4630 - 1.4630 = \mathbf{0.0000\text{ kWh}}$.

- **Market Clearing & Grid Interactions:**
  - Feasible P2P trade: $Q_{P2P} = \min(S_1^{\text{post}}, L_2^{\text{post}}) = \min(0.0000, 0.0000) = \mathbf{0.0000\text{ kWh}}$.
  - H001 Grid Export: $S_1^{\text{post}} - q_{\text{sell}} = 0.0000 - 0.0000 = \mathbf{0.0000\text{ kWh}}$.
  - H002 Grid Import: $L_2^{\text{post}} - q_{\text{buy}} = 0.0000 - 0.0000 = \mathbf{0.0000\text{ kWh}}$.

| Strategy Profile $(A_1, A_2)$ | P2P Traded $Q_{P2P}$ | H001 Grid Export | H001 Grid Import | H001 Revenue / Cost | H001 Utility $U_1$ | H002 Grid Export | H002 Grid Import | H002 Revenue / Cost | H002 Utility $U_2$ | Combined Utility $(U_1 + U_2)$ | Conservation Residuals ($D_{res}, S_{res}$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **All 4 Strategy Profiles**<br>(OFFER/ACCEPT, OFFER/GRID,<br>EXPORT/ACCEPT, EXPORT/GRID) | **0.0000 kWh** | **0.0000 kWh** | **0.0000 kWh** | 0.0000 AUD | **0.0000 AUD** | **0.0000 kWh** | **0.0000 kWh** | 0.0000 AUD | **0.0000 AUD** | **0.0000 AUD** | H001: 0.0, 0.0<br>H002: 0.0, 0.0 |

> [!IMPORTANT]
> **Why Zero Grid Export Occurs (Physical Condition):**
> Zero grid export is reported here **because and only because** $S_1^{\text{post}} \equiv 0.0000\text{ kWh}$ (the local battery possessed sufficient headroom of 2.105 kWh to absorb all 1.245 kWh of raw surplus). If post-battery surplus remains positive (e.g. when battery is full or capped by power limit), the implementation **always exports the remainder to the grid** ($GridExport_i = S_i^{\text{post}} - q_{\text{sell},i} > 0$), as verified in unit test `test_insufficient_solar_surplus_clamping` and `test_energy_conservation_comprehensive_benchmark`.

---

### 4.3 Physical vs Financial vs Economic Accounting Reconciliation

To prevent misinterpretation of the results:

1. **Physical Energy Conservation vs Stored Energy:**
   - H001 generated 1.382 kWh of physical solar energy. 0.137 kWh directly powered local demand, and 1.245 kWh was charged into the battery. At 95% efficiency, 1.183 kWh was added to chemical storage ($E: 2.50 \to 3.683\text{ kWh}$), with 0.062 kWh dissipated as thermodynamic charging loss.
   - H002 consumed 1.838 kWh of physical electrical energy. 0.375 kWh was supplied by local solar, and 1.463 kWh was delivered by discharging the battery. Draining 1.463 kWh at 95% efficiency consumed 1.540 kWh of stored chemical energy ($E: 2.50 \to 0.960\text{ kWh}$), with 0.077 kWh dissipated as discharging loss.
   - Non-double counting is guaranteed: charging energy $C_{bat}$ is deducted from raw surplus before market clearing. It cannot be counted as stored energy and market/grid export simultaneously.

2. **Financial Out-of-Pocket Accounting ($U = -C_{net}$):**
   - In this single interval, neither household made or received any monetary cash transfers ($U_1 = 0.0000\text{ AUD}$, $U_2 = 0.0000\text{ AUD}$).
   - Compared to the battery-free baseline ($U_2 = -0.3020\text{ AUD}$), H002 avoided an immediate out-of-pocket electricity bill of 30.2¢.

3. **Economic Honest Accounting Principle:**
   - H002's avoided cash cost is **not "free energy"**. H002 consumed 1.540 kWh of stored chemical reserve, reducing its SOC from 50% down to 19.2% (close to the 10% minimum operational floor). In future hours, that depleted energy must be replenished through solar generation or grid purchase.
   - Conversely, H001 stored 1.183 kWh of energy ($\text{SOC}: 50\% \to 73.7\%$) that can displace future 30¢/kWh retail imports.
   - Transparent reporting requires tracking initial and final SOC whenever comparing household costs.

---

## 5. Physical and Financial Conservation Checks

### 5.1 Conservation Identities
The implementation enforces and validates five strict conservation laws at every interval:

1. **Household Demand Conservation:**
   $$D_i = E_{self,i} + D_{bat,i} + q_{buy,i} + GridImport_i \quad (\text{Residual} < 10^{-5} \text{ kWh})$$
2. **Household Solar Conservation:**
   $$G_i = E_{self,i} + C_{bat,i} + q_{sell,i} + GridExport_i \quad (\text{Residual} < 10^{-5} \text{ kWh})$$
3. **Net Energy Balance Identity:**
   $$(D_i - G_i) = (GridImport_i - GridExport_i) + (q_{buy,i} - q_{sell,i}) + (D_{bat,i} - C_{bat,i})$$
4. **P2P Transaction Conservation:**
   $$q_{buy,H002} \equiv q_{sell,H001} = Q_{P2P}$$
   $$\text{Payment}_{buyer} \equiv \text{Revenue}_{seller} = Q_{P2P} \cdot p_{p2p}$$
5. **Community Net Grid Conservation:**
   $$\sum_{i} (D_i - G_i) = \sum_{i} (GridImport_i - GridExport_i) + \sum_{i} (D_{bat,i} - C_{bat,i})$$

### 5.2 Verification Evidence from Full Audit
Running `python audit_physical_feasibility.py` confirmed:
- **Pre-trade balances evaluated:** 10,512 point balances across 1,752 chronological hours.
  - Non-finite values: **0**
  - Complementarity violations: **0**
  - Max conservation residual: **$4.44 \times 10^{-16}$ kWh**
- **Monte Carlo Joint Scenarios:** 1,752,000 joint scenario pairs ($8,760,000$ conservation checks).
  - Conservation violations ($|\text{residual}| > 10^{-5}$): **0**
  - Max scenario residual: **$4.77 \times 10^{-7}$ kWh**
- **Battery Storage Integration Audit:**
  - H001 charged 2.105 kWh (final SOC 90.0%), H002 discharged 1.900 kWh (final SOC 10.0%).
  - Post-battery P2P trade cleared 0.600 kWh.
  - Conservation satisfied 100% across all physical and financial channels.

---

## 6. Test Suite and Execution Evidence

### 6.1 Full Pytest Results
Command: `python -m pytest`
```
============================= test session starts =============================
platform win32 -- Python 3.13.6, pytest-8.3.4, pluggy-1.5.0
rootdir: D:\5thSem\GT project\Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions
plugins: anyio-4.8.0, asyncio-0.25.2
collected 104 items

tests\test_battery.py .....                                              [  4%]
tests\test_battery_integration.py ..........                             [ 14%]
tests\test_energy.py .....                                               [ 19%]
tests\test_financial_payoffs.py ............                             [ 30%]
tests\test_forecast_evaluation.py .............                          [ 43%]
tests\test_game.py .........                                             [ 51%]
tests\test_monte_carlo.py .......................                        [ 74%]
tests\test_physical_feasibility.py ....................                  [ 93%]
tests\test_preprocessing.py ...                                          [ 96%]
tests\test_utility.py ....                                               [100%]

============================= 104 passed in 10.43s =============================
```

### 6.2 Newly Added Battery Integration Tests (`tests/test_battery_integration.py`)
1. `test_battery_soc_boundary_states`: Empty permitted SOC (10%), full permitted SOC (90%), and intermediate SOC (50%).
2. `test_power_limits_across_durations`: 2.5 kW power limit with $\Delta t = 1.0$ h and $\Delta t = 0.5$ h.
3. `test_efficiency_losses_and_exact_soc_transitions`: Hand-calculated efficiency losses ($\eta_{ch} = \eta_{dis} = 0.95$).
4. `test_insufficient_solar_surplus_clamping`: Clamping when solar surplus is less than headroom.
5. `test_insufficient_stored_energy_clamping`: Clamping when stored energy above minimum is less than deficit.
6. `test_mutual_exclusion_enforcement`: Rejecting simultaneous charge and discharge across all guards.
7. `test_energy_conservation_comprehensive_benchmark`: Hand-calculated physical conservation across households and grid.
8. `test_financial_payoff_consistency_all_profiles`: Verified payoffs and P2P payment equality across all 4 strategy profiles.
9. `test_reproducible_battery_monte_carlo`: Protocol B deterministic reproducibility under battery dispatch.
10. `test_compatibility_with_battery_free_baseline`: Verifying exact bit-for-bit equivalence when batteries are omitted or idle.

### 6.3 Terminal Demo Execution (`demo_prototype.py`)
Command: `python demo_prototype.py`
Output highlights:
- Successfully executed all 6 interactive stages.
- Displayed Stage 6 direct comparison between battery-free baseline and battery-aware integration.
- Confirmed zero grid import and zero grid export for the target hour under battery storage.
- Exit code: **0**.

---

## 7. Limitations and Methodological Bounds

To maintain scientific integrity:
1. **Rule-Based Baseline Dispatch:** The BTM self-consumption dispatch policy is a transparent baseline heuristic. It is **not** claimed to be a globally optimal multi-period dynamic program. An optimal multi-period solver might decide to reserve battery capacity or discharge into the P2P market depending on future price forecasts.
2. **Fixed Retail Tariffs:** Calculations assume fixed flat tariffs (0.30 import, 0.08 export, 0.19 P2P). Under dynamic time-of-use (TOU) or real-time wholesale pricing, battery dispatch would include price arbitrage incentives.
3. **No Grid Charging:** Batteries are currently configured to charge exclusively from local solar surplus. Grid charging at off-peak rates is omitted for this phase.
4. **Degradation Costs Omitted:** Battery cycle degradation is set to $0.0$ AUD/kWh throughput in the baseline. The parameter `degradation_cost_per_kwh` is supported in code for future phases.
5. **Welfare Terminology:** Combined household utility ($U_1 + U_2$) represents the net financial savings of the two prosumer households and is not labeled as total social welfare.

---

## 8. Recommendation for Phase 5B (Multi-Household Market Clearing)

### Readiness Assessment
- **Physical Foundation:** Fully verified. All physical conservation, energy balance, and efficiency transition identities hold with zero discrepancies.
- **Financial Architecture:** Incentive-compatible, exact payment conservation, transparent initial/final SOC accounting.
- **Codebase Stability:** 104 passing tests, zero regressions, clean modular architecture.

### Recommendation
**The project is officially READY to proceed to Phase 5B: Multi-Household Market Clearing.**

In Phase 5B, the architecture can be extended from bilateral (2-household) trading to multi-household microgrid clearing (aggregating H001, H002, H003, and additional prosumers) using double auctions or cooperative game-theoretic surplus allocation.
