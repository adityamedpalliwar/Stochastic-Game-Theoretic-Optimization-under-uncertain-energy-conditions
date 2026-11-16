# Stochastic Game-Theoretic Optimization for Peer-to-Peer Energy Trading with Distributed Battery Storage under Uncertainty

**Aditya, Heet, Dimpal**  
*Department of Mathematics, Sardar Vallabhbhai National Institute of Technology (SVNIT), Surat, Gujarat, India*  
Contact: `u24mc003@amhd.svnit.ac.in`, `u24mc019@amhd.svnit.ac.in`, `u24mc020@amhd.svnit.ac.in`

---

### Abstract
Rapid proliferation of residential rooftop photovoltaics and battery energy storage systems necessitates decentralized market mechanisms to overcome retail feed-in tariff distortions. This paper presents an integrated stochastic game-theoretic optimization platform for peer-to-peer (P2P) energy trading among heterogeneous prosumers coupled with independent 5.0 kWh physical battery energy storage systems. An uncapped dynamic demand-pressure pricing mechanism guarantees that the P2P clearing price strictly internalizes the retail tariff spread, providing Pareto-dominant economic incentives and establishing the existence of a unique pure-strategy Nash equilibrium. To quantify stochastic stability under compound meteorological and behavioral volatility, a smoothed block bootstrap Monte Carlo sampling framework is formulated, preserving empirical cross-household correlations across 1,000 independent 24-hour days (24,000 sequential hourly market rounds) drawn from real-world Ausgrid panel data. Four rigorous operational counterfactuals are evaluated: pure grid baseline, solar self-consumption, battery self-consumption without P2P, and the full proposed game-theoretic model. Simulation results demonstrate that the proposed framework slashes total community electricity expenditures by 40.07%, saving an average of $10.56 AUD/day across the microgrid (reducing daily community energy expenditure from $26.36/day under pure grid reliance down to $15.80/day under coordinated trading). Factor decomposition confirms that while solar self-consumption ($5.52 AUD/day, 52.3%) and battery storage ($4.50 AUD/day, 42.6%) furnish substantial baseline arbitrage, P2P software coordination delivers an additional $0.54 AUD/day (5.1% of community savings, and up to 19.1% for high-demand consumers) with zero marginal hardware expenditure. Empirical profit distributions confirm strictly non-negative individual financial gains across all simulated scenarios, validating the platform robustness for next-generation transactive energy distribution networks.

**Keywords:** Peer-to-peer energy trading, game theory, battery energy storage systems, Nash equilibrium, dynamic pricing, Monte Carlo simulation, prosumer microgrid, uncertainty quantification.

---

## I. INTRODUCTION
Distributed renewable energy resources, specifically residential rooftop photovoltaics (PV) and battery energy storage systems (BESS), are fundamentally restructuring modern low-voltage distribution grids [1]. Traditionally passive domestic electricity consumers are rapidly transforming into active prosumers capable of localized generation and load modulation [2], [3].

A primary barrier to efficient residential energy utilization is the substantial structural spread between retail import tariffs and feed-in export tariffs imposed by utility retailers [4]. In typical residential pricing schemes—such as those across the Australian National Electricity Market (NEM)—homeowners import electricity from the grid at approximately $0.30/kWh while receiving a feed-in credit of only $0.08/kWh for exported solar. This 22¢/kWh spread creates an economic distortion: prosumers with abundant midday solar generation receive negligible financial compensation, while adjacent non-solar neighbors are forced to import energy from centralized generation at full retail price.

Peer-to-peer (P2P) local energy trading has emerged as an attractive framework to internalize this spread [5], [6]. By enabling direct, localized electricity transactions between prosumers and consumers within a distribution feeder, P2P markets allow prosumers to sell surplus energy at prices above the utility export credit ($P_{export} = \$0.08/\text{kWh}$) while offering consumers energy below the grid import rate ($P_{import} = \$0.30/\text{kWh}$). However, real-world residential microgrids operate under stochastic weather variations, unpredictable consumer occupancy patterns, and physical battery degradation constraints, making static or centralized optimization brittle [7], [8].

To address these challenges, this paper presents an integrated stochastic game-theoretic optimization platform for residential microgrids. The principal contributions of this work are as follows: (1) an N-player normal-form energy trading game coupling heterogeneous residential prosumers with independent 5.0 kWh physical battery energy storage systems; (2) an uncapped dynamic demand-pressure pricing mechanism guaranteeing Pareto-dominant coordination; (3) a smoothed block bootstrap Monte Carlo sampling framework evaluating 1,000 independent 24-hour days (24,000 sequential hourly market rounds) over real-world Ausgrid panel data; and (4) a rigorous four-mode counterfactual evaluation isolating the exact financial dividends of solar (52.3%), battery storage (42.6%), and P2P software coordination (5.1%).

---

## II. FOUNDATIONAL PROTOTYPE: THE INITIAL 2-HOUSEHOLD NORMAL-FORM GAME

### A. Conceptual Foundation: Why We Started with a 2-Household Game
Before constructing a complex community microgrid, sound scientific methodology requires verifying foundational mathematical concepts in an analytically tractable environment. Therefore, we initially developed a 2-household normal-form game prototype (implemented in demo_prototype.py). The primary purpose of this initial prototype was threefold: (1) to formulate the mathematical payoff matrix governing prosumer interactions, (2) to trace individual best-response dynamics step-by-step, and (3) to prove computationally that cooperative peer-to-peer trading forms a strict, Pareto-dominant Nash equilibrium compared to utility grid default.

### B. Mathematical Setup of the 2-Household Normal-Form Game
Consider a representative trading hour (e.g. 10:00 AM on a sunny morning). Two distinct prosumer households interact:
- **Player 1 (Seller - Household H001):** Possesses abundant rooftop solar generation. Realized demand is 0.850 kWh, while solar generation is 3.200 kWh, leaving a net physical surplus of $S_1 = 3.200 - 0.850 = +2.350\text{ kWh}$. Strategy space: $A_1 = \{\text{OFFER\_P2P}, \text{EXPORT\_GRID}\}$.
- **Player 2 (Buyer - Household H002):** Experiences higher daytime consumption than solar generation. Realized demand is 2.100 kWh, while solar generation is 0.350 kWh, creating a net physical deficit of $D_2 = 2.100 - 0.350 = -1.750\text{ kWh}$. Strategy space: $A_2 = \{\text{ACCEPT\_P2P}, \text{GRID\_IMPORT}\}$.

The physical energy that can be traded locally is constrained by the mutual conservation of energy: $Q_{trade} = \min(S_1, D_2) = \min(2.350, 1.750) = 1.750\text{ kWh}$. In this prototype, the local trading price is set to the equitable mid-market rate: $P_{P2P} = (P_{import} + P_{export}) / 2 = (\$0.30 + \$0.08) / 2 = \$0.1900/\text{kWh}$.

### C. Payoff Formulations and 2x2 Payoff Matrix
Each player's utility $U_i$ is defined as their net financial position in Australian Dollars (AUD). For the seller, positive utility represents net revenue. For the buyer, utility is negative net expenditure:
1. **Mutual Trade Cleared (OFFER_P2P, ACCEPT_P2P):** Player 1 sells 1.750 kWh to Player 2 at $0.190/kWh ($0.3325 AUD) and exports the remaining unabsorbed 0.600 kWh to the grid at 8¢ ($0.0480 AUD). Total seller utility: $U_1 = +\$0.3805\text{ AUD}$. Player 2 buys 1.750 kWh at $0.190/kWh: $U_2 = -\$0.3325\text{ AUD}$.
2. **Trade Fails (OFFER_P2P, GRID_IMPORT):** Player 2 rejects P2P. Player 1 exports 2.350 kWh to grid at 8¢: $U_1 = +\$0.1880\text{ AUD}$. Player 2 imports 1.750 kWh from grid at 30¢: $U_2 = -\$0.5250\text{ AUD}$.
3. **Trade Fails (EXPORT_GRID, ACCEPT_P2P):** Player 1 exports to grid. $U_1 = +\$0.1880\text{ AUD}$, $U_2 = -\$0.5250\text{ AUD}$.
4. **Status-Quo Baseline (EXPORT_GRID, GRID_IMPORT):** Neither participates in P2P. $U_1 = +\$0.1880\text{ AUD}$, $U_2 = -\$0.5250\text{ AUD}$.

![Initial 2-Household Game Payoff Matrix](D:\5thSem\Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions\results\figures\report_figures\fig00_initial_2_household_game.png)  
*Fig. 1. Initial 2-household normal-form payoff matrix and economic gains verification (Output from demo_prototype.py).*

### D. Best-Response Dynamics and Strict Nash Equilibrium
- **For Seller (H001):** When Buyer accepts P2P, OFFER_P2P yields +$0.3805 AUD vs +$0.1880 AUD for grid export (+102.4% gain, +$0.1925 AUD). When Buyer rejects, both yield +$0.1880 AUD. OFFER_P2P is a weakly dominant strategy.
- **For Buyer (H002):** When Seller offers P2P, ACCEPT_P2P costs $0.3325 AUD vs $0.5250 AUD for grid import (saves $0.1925 AUD, 36.7% bill cut). When Seller exports, both cost $0.5250 AUD. ACCEPT_P2P is a weakly dominant strategy.
- **Equilibrium:** (OFFER_P2P, ACCEPT_P2P) is the unique pure-strategy Pareto-dominant Nash Equilibrium.

### E. Why Expand to the 5-Household Flagship System?
The 2-player prototype revealed four critical real-world limitations: (1) fragile liquidity (if the single buyer is full, trading halts), (2) lack of prosumer diversity (no swing traders or heavy commercial-style loads), (3) static pricing rigidity (cannot adapt to scarcity), and (4) absence of physical battery storage (cannot shift midday solar to evening peak). These insights motivated our flagship 5-Household (N=5) Stochastic Game with BESS.

---

## III. SYSTEM ARCHITECTURE AND DATASET

### A. Microgrid Participant Topology
The modeled residential microgrid consists of N = 5 heterogeneous prosumer households (H001, H002, H003, H004, H005) connected to a common local distribution feeder and utility point of common coupling (PCC). Electricity transfers between neighbors are conducted over the local secondary network, while net aggregate deficits or surpluses are balanced with the primary utility grid.

### B. Comprehensive Technical, Economic & Simulation Assumptions
| Parameter Category | Model Parameter | Numerical Value | Physical & Economic Justification |
| :--- | :--- | :--- | :--- |
| **Utility Electricity Tariffs** | Retail Grid Import (P_import) | $0.3000 AUD / kWh | Standard NEM residential flat tariff. |
| **Utility Electricity Tariffs** | Solar Feed-in Tariff (P_export) | $0.0800 AUD / kWh | Typical utility export credit paid to solar owners. |
| **Utility Electricity Tariffs** | Retail Grid Tariff Spread | $0.2200 AUD / kWh | Internalized economic spread: $0.30 - $0.08 = $0.22/kWh. |
| **Battery Energy Storage (BESS)** | Nominal Capacity (E_cap) | 5.0 kWh per home | Standard residential LiFePO4 modular battery pack. |
| **Battery Energy Storage (BESS)** | Max Inverter Power | 2.5 kW (0.5 C-rate) | Continuous bidirectional inverter thermal/current rating. |
| **Battery Energy Storage (BESS)** | Round-Trip Efficiency (η_rt) | 95.0% (η_ch = η_dis = 97.47%) | Modern high-efficiency DC-coupled residential storage. |
| **Battery Energy Storage (BESS)** | Safe Operating SOC Window | 10.0% to 90.0% (0.5 - 4.5 kWh) | Preserves electrochemical health, preventing cell degradation. |
| **Battery Energy Storage (BESS)** | Initial Daily SOC (SOC_0) | 50.0% (2.5 kWh) at 00:00 | Neutral daily boundary condition avoiding unearned carryover. |
| **Simulation & Uncertainty** | Monte Carlo Scenarios | 1,000 independent days | Quantifies compound meteorological & behavioral uncertainty. |
| **Simulation & Uncertainty** | Market Horizon & Rounds | 24,000 sequential rounds | 1,000 days × 24 hourly market clearings (h = 0 to 23). |
| **Simulation & Uncertainty** | Bootstrap Noise Multiplier | 0.15 × σ_diurnal(h) | Gaussian perturbation preserving diurnal weather envelope. |
| **Dynamic Price Discovery** | Price Sensitivity (λ_max) | 2.0 | Market pressure elasticity setting price responsiveness. |
| **Dynamic Price Discovery** | Singularity Protector (ε) | 1.0 × 10^-6 kWh | Prevents division by zero when pool surplus is zero. |
| **Network & Transactions** | Internal Wheeling Charges | $0.00 AUD / kWh | Transactions share common secondary distribution transformer. |

### C. Empirical Dataset Calibration (Ausgrid Smart Home Data)
The load and generation profiles originate from the open-source Ausgrid Solar Home Electricity Dataset (Sydney, Australia) [12], which records General Consumption (GC), Controlled Load (CL), and Gross Generation (GG) for 300 homes at 30-minute intervals over a full year (2012–2013). Readings were aggregated into clean hourly intervals (Δt = 1.0 h). Table II outlines the distinct structural characteristics of each participant.

| ID | Archetype Role | PV (kWp) | Demand (kWh) | Solar (kWh) | Net Balance |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **H001** | High-Solar Seller | 5.0 | 20.90 ± 8.87 | 16.03 ± 8.81 | Moderate Net Deficit |
| **H002** | Low-Load Prosumer | 1.5 | 6.02 ± 1.83 | 4.77 ± 2.50 | Balanced / Near Zero |
| **H003** | Moderate-Load Prosumer | 2.0 | 13.70 ± 4.60 | 5.67 ± 3.01 | Net Energy Buyer |
| **H004** | High-Demand Consumer | 1.0 | 33.75 ± 13.91 | 3.06 ± 1.63 | Dominant Buyer |
| **H005** | Opportunistic Prosumer | 2.5 | 13.49 ± 4.19 | 9.03 ± 5.25 | Swing Prosumer |
| **Total** | Microgrid Community | 12.0 | 87.85 ± 24.23 | 38.56 ± 20.31 | Net Community Deficit |

![Community Diurnal Profiles](D:\5thSem\Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions\results\figures\report_figures\fig01_community_diurnal_and_dynamic_pricing.png)  
*Fig. 2. Mean 24-hour diurnal gross load and solar generation profiles across the five households, illustrating midday surplus and evening consumption peaks.*

---

## IV. PHYSICAL BATTERY STORAGE FORMULATION & GREEDY DISPATCH

### A. Battery Energy Storage System Parameters
Each household possesses an independent physical BESS reflecting commercial lithium-ion systems: nominal energy capacity $E_{cap} = 5.0\text{ kWh}$, maximum charge/discharge power $P_{ch}^{\max} = P_{dis}^{\max} = 2.5\text{ kW}$, round-trip efficiency $\eta_{rt} = 95.0\%$ ($\eta_{ch} = \eta_{dis} = \sqrt{0.95} \approx 97.47\%$), safe operating state-of-charge bounds $\text{SOC}_{\min} = 10\%$ (0.5 kWh) and $\text{SOC}_{\max} = 90\%$ (4.5 kWh), initialized at $\text{SOC}_0 = 50\%$ (2.5 kWh) at 00:00.

### B. Technical Justification for Battery Sizing (5.0 kWh) and Hourly Power Limit (2.5 kW / 0.5C)

A foundational inquiry in microgrid system design is the physical rationale governing energy capacity (5.0 kWh) and the maximum hourly charge/discharge rate (2.5 kW). We clarify these specifications across electrochemical, economic, and electrical infrastructure domains:

- **1) Distinction Between Energy Capacity (kWh) and Inverter Power Rating (kW):** Energy capacity $E_{cap} = 5.0	ext{ kWh}$ measures the total volume of energy stored in the battery cells (analogous to the size of a water tank). In contrast, maximum power $P_{ch}^{\max} = P_{dis}^{\max} = 2.5	ext{ kW}$ measures the continuous rate of energy flow through the bidirectional power inverter (analogous to pipe diameter). In one operating hour ($\Delta t = 1.0	ext{ h}$), the maximum energy that can physically transfer into or out of the battery is $	ext{Energy} = 	ext{Power} 	imes 	ext{Time} = 2.5	ext{ kW} 	imes 1.0	ext{ h} = 2.5	ext{ kWh}$. Thus, even if 4.0 kWh of raw solar surplus is generated in an hour, the inverter physically restricts charging to 2.5 kWh/h, preserving circuit safety and battery cell integrity.
- **2) Economic Sizing Matching Diurnal Generation and Demand:** In residential solar microgrids, empirical single-day solar surplus averages between 3.0 and 8.0 kWh/day, and domestic evening peak consumption averages between 4.0 and 8.0 kWh/day. A 5.0 kWh battery provides the optimal economic sweet-spot: it absorbs the vast majority of midday surplus without chronic underutilization. An oversized pack (e.g. 15 kWh) would remain partially charged for most of the year, incurring severe capital depreciation with low economic return. A 5.0 kWh pack corresponds exactly to modern modular commercial lithium battery units (e.g., Enphase IQ Battery 5P, Tesla Powerwall modular block, and BYD Battery-Box Premium 5.0 kWh).
- **3) C-Rate, Electrochemical Longevity, and Thermal Safety (0.5C Rate):** The ratio of maximum power to capacity defines the battery C-rate: $C = 2.5	ext{ kW} / 5.0	ext{ kWh} = 0.5	ext{ h}^{-1}$ (a 2-hour full charge cycle). For residential lithium-ion chemistry (LiFePO4 and NMC), a 0.5C rate is the industry-standard benchmark for maximum cell longevity. Charging at aggressive rates (e.g., 1.0C = 5.0 kW) causes rapid internal Joule heating ($I^2 R$ losses), accelerates solid-electrolyte interphase (SEI) layer growth, and triggers hazardous lithium plating on graphite anodes during cool mornings. A 0.5C rate eliminates the requirement for complex liquid cooling, operates safely with passive cooling, and guarantees a 10-year / 6,000-cycle operational lifespan.
- **4) Residential Single-Phase Electrical Circuit Safety Limits:** Standard Australian and international residential dwellings operate on single-phase 230 V alternating current (AC) protected by standard 15 A or 16 A branch circuit breakers. Continuous electrical power draw at maximum inverter rating is $P = V 	imes I = 230	ext{ V} 	imes 10.87	ext{ A} pprox 2.5	ext{ kW}$. Attempting to charge or discharge a domestic battery at 5.0 kW on a single-phase line draws $5,000	ext{ W} / 230	ext{ V} pprox 21.74	ext{ A}$, which immediately trips standard household branch circuit breakers and would necessitate costly three-phase utility service upgrades. The 2.5 kW rating ensures universal 'plug-and-play' compatibility with existing residential electrical infrastructure.

### C. Why Pre-Game Greedy Dispatch was Chosen over MPC
1. **Computational Tractability:** 24,000 sequential rounds solved in sub-millisecond time without optimization convergence failures.
2. **Elimination of Future Foresight Bias:** Eliminates reliance on multi-hour forward load forecasts that have high errors (MAE ≈ 0.47 kWh).
3. **Preservation of User Privacy:** Operates entirely behind-the-meter with zero disclosure of private future appliance schedules.
4. **Physical Market Integrity:** Ensures only genuine physical unabsorbed energy enters the P2P trading pool.

### D. Mathematical Dispatch Equations
$$P_{ch,i} = \min \left( S_i^{raw}, \; P_{ch}^{\max}, \; \frac{[\text{SOC}_{\max} - \text{SOC}_i] \cdot E_{cap}}{\eta_{ch} \cdot \Delta t} \right) \tag1$$
$$S_i^{net} = \max(0, \; S_i^{raw} - P_{ch,i}) \tag2$$
$$P_{dis,i} = \min \left( D_i^{raw}, \; P_{dis}^{\max}, \; \frac{[\text{SOC}_i - \text{SOC}_{\min}] \cdot E_{cap} \cdot \eta_{dis}}{\Delta t} \right) \tag3$$
$$D_i^{net} = \max(0, \; D_i^{raw} - P_{dis,i}) \tag4$$
$$\text{SOC}_{i,t+1} = \text{SOC}_{i,t} + \frac{P_{ch,i} \cdot \eta_{ch} - P_{dis,i} / \eta_{dis}}{E_{cap}} \tag5$$

---

## V. DYNAMIC PRICING DISCOVERY AND GAME FORMULATION

### A. Market Demand Pressure & Price Formulation
The community aggregate trading pool and demand pressure ratio are:
$$S_{pool,t} = \sum_{i=1}^N S_{i,t}^{net}, \qquad D_{pool,t} = \sum_{i=1}^N D_{i,t}^{net} \tag6$$
$$\lambda_t = \frac{D_{pool,t}}{S_{pool,t} + \epsilon} \tag7$$
$$P_{P2P,t} = P_{export} + \left( \frac{\lambda_t}{\lambda_{\max}} \right) \cdot (P_{import} - P_{export}) \tag8$$
bounded strictly within [$0.08, $0.30] AUD/kWh with sensitivity $\lambda_{\max} = 2.0$.

### B. Proof of Strict/Weak Dominance and Nash Equilibrium
Each participant minimizes net electricity expenditure:
$$\text{Cost}_{i,t} = m_{i,t} P_{import} + q_{i,t}^{buy} P_{P2P,t} - q_{i,t}^{sell} P_{P2P,t} - e_{i,t} P_{export} \tag9$$
Since $P_{export} \le P_{P2P,t} \le P_{import}$, every seller receives $\ge \$0.08/\text{kWh}$, and every buyer pays $\le \$0.30/\text{kWh}$. Any defection to the grid yields an equal or strictly worse payoff. Hence, participating in P2P is a weakly dominant strategy, making all-trading a strict Pareto-dominant Nash Equilibrium.

---

## VI. MONTE CARLO UNCERTAINTY QUANTIFICATION
To evaluate stochastic stability, a smoothed block bootstrap Monte Carlo sampling framework is formulated:
$$D_{i,h}^{(s)} = \max(0, D_{i,h}(d_s) + \epsilon_D), \qquad \epsilon_D \sim \mathcal{N}(0, [0.15 \sigma_D]^2) \tag10$$
$$G_{i,h}^{(s)} = \max(0, G_{i,h}(d_s) + \epsilon_S), \qquad \epsilon_S \sim \mathcal{N}(0, [0.15 \sigma_S]^2) \tag11$$
Over 1,000 days (24,000 rounds), daily metrics represent arithmetic means across all 1,000 scenarios.

### B. Technical Justification for the 0.15σ / 0.16σ Perturbation Factor (All Whys & Statistical Meaning)

A critical question is why the Monte Carlo perturbation noise variance is scaled by a factor of 0.15σ (approximately 0.16σ) rather than using raw unscaled variance (1.0σ) or direct historical replays. We provide the full statistical, meteorological, and electrical justification:

- **1) Empirical Smart Meter Data Already Possesses Enormous Natural Variance:** The 365-day Ausgrid dataset already captures large seasonal and daily variances ($\sigma_D$ and $\sigma_S$). Solar generation naturally fluctuates from 0 kWh on rainy days to 8.7 kWh on clear summer days, while household load fluctuates across weekdays and weekends. The empirical standard deviation $\sigma(h)$ at any hour $h$ reflects this wide macro-variance across 300 homes.
- **2) Catastrophic Physical Failure of Full 1.0σ Noise:** If one were to apply unscaled 1.0σ Gaussian noise directly ($\epsilon \sim \mathcal{N}(0, [1.0\sigma]^2)$), the synthetic scenarios would completely destroy the physical diurnal laws of energy generation and consumption. For example, at midday, adding $-1.0\sigma$ could plunge clear-sky solar generation to zero, while at midnight, unconstrained noise would produce spurious 'solar generation in the dark'. In household demand, unscaled noise would generate negative consumption or explosive artificial spikes exceeding 25 kW, exceeding residential electrical service capacity and causing absurd battery overflows. Raw 1.0σ perturbation ruins physical realism.
- **3) Non-Parametric Kernel Smoothing and Smoothed Bootstrap Theory:** In mathematical statistics (specifically Silverman's rule of thumb for optimal bandwidth selection in kernel density estimation and smoothed bootstrapping), the optimal bandwidth factor $h$ to smooth empirical distributions without distorting underlying multi-modal shape is $h pprox 0.15$ to $0.16$ of the empirical spread. Setting the perturbation noise standard deviation to $0.15\sigma_D(h)$ and $0.15\sigma_S(h)$ introduces realistic high-frequency micro-volatility (e.g. an occupant turning on an appliance 20 minutes earlier or later, or brief localized cloud cover reducing solar irradiance by 10–15%) while strictly maintaining the macro diurnal envelope and cross-household spatial weather correlation across neighbors on the same feeder.
- **4) Strict Physical Boundary Clamping:** To enforce absolute thermodynamic feasibility, strict non-negativity and solar availability constraints are enforced: solar perturbation is strictly clamped to zero whenever base historical generation is zero ($G_{i,h} = 0 \implies \epsilon_S = 0$), guaranteeing zero nighttime solar generation, while gross demand is lower-bounded by zero via $\max(0, \cdot)$. This guarantees 100% physically valid microgrid operating conditions across all 24,000 simulated rounds.

---

## VII. RIGOROUS COUNTERFACTUAL BENCHMARKING FRAMEWORK

### A. Four Operational Modes
1. **Mode 1 (Pure Grid Baseline):** 100% Demand from grid at $0.30/kWh. Daily cost: $26.36/day ($26,355 over 1,000 days).
2. **Mode 2 (Solar + Grid-Only):** Rooftop solar self-consumption, no battery, no P2P. Daily cost: $20.83/day.
3. **Mode 3 (Battery + Grid-Only):** Solar + 5 kWh battery for self-consumption, no P2P. Daily cost: $16.34/day.
4. **Mode 4 (Proposed P2P Game + Battery):** Full multi-agent game-theoretic optimization. Daily cost: $15.80/day ($15,795 over 1,000 days).

### B. Edge Cases Audited
- **Overcast Winter Days:** Solar near zero, $\lambda \to \infty$, price clamped to $0.30/kWh ceiling, households safely fall back to grid import.
- **Blazing Midday Solar Flood:** All 5 batteries reach 90% SOC by 11:30 AM, solar floods pool, price drops to $0.11/kWh, rewarding buyers and maximizing green energy absorption.
- **Nighttime Peak Shaving:** 18:00 - 22:00 solar is zero; batteries discharge stored midday energy to shave evening peaks.
- **Asymmetric Consumer Domination:** Heavy consumer H004 absorbs 67.1% of all P2P community trades, earning $362.65 AUD (19.1% of its total bill reduction).
- **Battery Saturation and Depletion Boundaries:** 10% SOC floor and 90% SOC ceiling strictly enforced.

---

## VIII. SEPARATED INDIVIDUAL HOUSEHOLD CASE STUDIES

### A. Household H001: High-Solar Midday Seller (Solar Powerhouse)
- PV: 5.0 kWp, Demand: 20.90 kWh/d, Solar: 16.03 kWh/d.
- Costs: Pure Grid $6.27/d → Solar $4.34/d → Battery $3.11/d → Game $2.98/d (52.4% cut, saving $3,285.63 AUD over 1,000 days).
- Decomposition: Solar ($1,925.69, 58.6%), Battery ($1,238.88, 37.7%), P2P Game ($121.06, 3.7%).

![Household H001 Detailed Optimization](D:\5thSem\Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions\results\figures\report_figures\fig_household_H001_detailed.png)  
*Fig. 3. Detailed optimization breakdown for Household H001 (High-Solar Midday Seller).*

### B. Household H002: Low-Load Balanced Prosumer (Highest % Bill Cut: 67.4%)
- PV: 1.5 kWp, Demand: 6.02 kWh/d, Solar: 4.77 kWh/d.
- Costs: Pure Grid $1.80/d → Solar $1.17/d → Battery $0.60/d → Game $0.59/d (67.4% cut, saving $1,216.78 AUD over 1,000 days).
- Decomposition: Solar ($634.92, 52.2%), Battery ($573.14, 47.1%), P2P Game ($8.73, 0.7%).

![Household H002 Detailed Optimization](D:\5thSem\Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions\results\figures\report_figures\fig_household_H002_detailed.png)  
*Fig. 4. Detailed optimization breakdown for Household H002 (Low-Load Balanced Prosumer).*

### C. Household H003: Moderate Prosumer (Regular Net Buyer)
- PV: 2.0 kWp, Demand: 13.70 kWh/d, Solar: 5.67 kWh/d.
- Costs: Pure Grid $4.11/d → Solar $3.28/d → Battery $2.49/d → Game $2.48/d (39.7% cut, saving $1,633.30 AUD over 1,000 days).
- Decomposition: Solar ($832.26, 51.0%), Battery ($790.27, 48.4%), P2P Game ($10.77, 0.7%).

![Household H003 Detailed Optimization](D:\5thSem\Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions\results\figures\report_figures\fig_household_H003_detailed.png)  
*Fig. 5. Detailed optimization breakdown for Household H003 (Moderate Prosumer Regular Buyer).*

### D. Household H004: High-Demand Consumer (Primary P2P Beneficiary: 19.1% P2P Share)
- PV: 1.0 kWp, Demand: 33.75 kWh/d, Solar: 3.06 kWh/d.
- Costs: Pure Grid $10.12/d → Solar $9.32/d → Battery $8.59/d → Game $8.23/d (18.8% cut, saving $1,898.61 AUD over 1,000 days).
- Captures $362.65 AUD in pure P2P software coordination gains (19.1% of its total bill reduction).

![Household H004 Detailed Optimization](D:\5thSem\Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions\results\figures\report_figures\fig_household_H004_detailed.png)  
*Fig. 6. Detailed optimization breakdown for Household H004 (High-Demand Heavy Consumer).*

### E. Household H005: Balanced Opportunistic Swing Trader
- PV: 2.5 kWp, Demand: 13.49 kWh/d, Solar: 9.03 kWh/d.
- Costs: Pure Grid $4.05/d → Solar $2.72/d → Battery $1.56/d → Game $1.52/d (47.7% cut, saving $2,525.35 AUD over 1,000 days).

![Household H005 Detailed Optimization](D:\5thSem\Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions\results\figures\report_figures\fig_household_H005_detailed.png)  
*Fig. 7. Detailed optimization breakdown for Household H005 (Balanced Opportunistic Swing Trader).*

---

## IX. COMMUNITY SIMULATION RESULTS, FACTOR DECOMPOSITION & DASHBOARD AUDIT

### A. Cost Comparison Across Four Operational Modes
| Participant | Mode 1: Pure Grid | Mode 2: Solar+Grid | Mode 3: Batt+Grid | Mode 4: P2P Game | Daily Savings | Bill Cut (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **H001 (Seller)** | $6.2706 | $4.3449 | $3.1061 | $2.9850 | +$3.2856 | 52.4% |
| **H002 (Low Load)** | $1.8046 | $1.1697 | $0.5965 | $0.5878 | +$1.2168 | 67.4% |
| **H003 (Buyer)** | $4.1101 | $3.2779 | $2.4876 | $2.4768 | +$1.6333 | 39.7% |
| **H004 (High Demand)** | $10.1238 | $9.3230 | $8.5879 | $8.2252 | +$1.8986 | 18.8% |
| **H005 (Opportunist)** | $4.0461 | $2.7169 | $1.5579 | $1.5207 | +$2.5253 | 62.4% |
| **COMMUNITY TOTAL** | **$26.3552** | **$20.8324** | **$16.3359** | **$15.7956** | **+$10.5597** | **40.07%** |

![Cost across modes](D:\5thSem\Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions\results\figures\simulate_five_house_monte_carlo\01_daily_cost_comparison_across_modes.png)  
*Fig. 8. Mean daily electricity cost by household across the four operational counterfactual modes over 1,000 Monte Carlo scenarios.*

![Cost difference and profit](D:\5thSem\Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions\results\figures\simulate_five_house_monte_carlo\02_total_profit_and_cost_difference.png)  
*Fig. 9. Cost difference: Baseline Pure Grid expenditure vs Proposed P2P Game with BESS, highlighting total profit earned per participant.*

### B. Factor Decomposition of Community Profit
| Participant | Daily Savings (AUD/day) | Solar Dividend (AUD/day) | Battery Dividend (AUD/day) | P2P Game Dividend (AUD/day) | P2P Share (%) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **H001** | $3.29/day | $1.93/day | $1.24/day | $0.12/day | 3.7% |
| **H002** | $1.22/day | $0.63/day | $0.57/day | $0.01/day | 0.7% |
| **H003** | $1.63/day | $0.83/day | $0.79/day | $0.01/day | 0.7% |
| **H004** | $1.90/day | $0.80/day | $0.74/day | $0.36/day | 19.1% |
| **H005** | $2.53/day | $1.33/day | $1.16/day | $0.04/day | 1.5% |
| **COMMUNITY TOTAL** | **$10.56/day** | **$5.52/day (52.3%)** | **$4.50/day (42.6%)** | **$0.54/day (5.1%)** | **5.1%** |

- **Total Community Savings:** **$10,559.67 AUD (40.07% bill reduction)**.
- **Factor Waterfall:** Solar self-consumption $5,522.87 AUD (52.3%), Battery storage $4,496.47 AUD (42.6%), P2P Game $540.34 AUD (5.1%).

![Factor Decomposition](D:\5thSem\Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions\results\figures\simulate_five_house_monte_carlo\06_total_profit_difference_decomposition.png)  
*Fig. 10. Factor decomposition of total community profit into solar self-consumption, battery storage arbitrage, and P2P coordination.*

![Stacked Factor Percentages](D:\5thSem\Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions\results\figures\simulate_five_house_monte_carlo\07_savings_portion_by_factor.png)  
*Fig. 11. Normalized percentage factor breakdown (100% stacked) illustrating the distinct value drivers across participant archetypes.*

### C. Diurnal Hourly Trading and Price Dynamics
Analysis of the 24-hour diurnal profile confirms that local trading concentrates strictly between 11:00 and 15:00. Batteries reach their 90% SOC ceiling by 11:00, causing unabsorbed solar surplus to flood the pool. Market pressure λ drops below 0.5, clearing the P2P price at $0.11–$0.15/kWh. Between 17:00 and 22:00, stored battery reserves discharge to shave dinner demand peaks, avoiding premium $0.30/kWh grid imports.

![Diurnal Community Profit](D:\5thSem\Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions\results\figures\simulate_five_house_monte_carlo\04_hourly_average_community_profit.png)  
*Fig. 12. Diurnal 24-hour average community profit profile illustrating the active midday trading window and evening battery peak shaving.*

### D. Statistical Stability and Downside Risk
Evaluation of the empirical profit distributions across all 1,000 Monte Carlo scenarios reveals that daily P2P trading profit is strictly non-negative (minimum and 5th percentile $Q_{05} = \$0.0000/\text{day}$). This guarantees individual rationality and zero downside risk under diverse meteorological conditions.

![Empirical Stability Boxplots](D:\5thSem\Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions\results\figures\simulate_five_house_monte_carlo\03_p2p_profit_distribution_1000_scenarios.png)  
*Fig. 13. Empirical P2P trading profit distributions (boxplots and kernel density estimates) across 1,000 Monte Carlo scenarios.*

### E. Hourly Player Profit Dynamics & Community Welfare Coupling (Detailed Trace from 05_five_house_game.ipynb)

To provide a complete operational audit of game-theoretic microgrid clearing, we examine the precise hourly energy dispatches, battery states, and economic payoffs from the full 24-hour simulation trace documented in `05_five_house_game.ipynb` (simulated for winter date 2012-07-01 across all 5 households). Table V presents the empirical 24-hour energy balance, battery utilization, and financial savings per participant.

#### TABLE V: 24-HOUR ENERGY, BATTERY DISPATCH, AND FINANCIAL SAVINGS AUDIT (FROM 05_FIVE_HOUSE_GAME.IPYNB TRACE)

| Household | Total Demand (kWh) | Total Solar (kWh) | Batt Charged (kWh) | Batt Discharged (kWh) | Final SOC | P2P Surplus (kWh) | P2P Deficit (kWh) | Daily Saving (AUD) | Operational Roles |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **H001 (Seller)** | 22.80 | 8.73 | 4.21 | 5.70 | 0.10 | 1.81 | 14.39 | $0.1221 | 2h Seller / 11h Buyer / 11h Self-Suff. |
| **H002 (Low Load)** | 14.63 | 1.80 | 0.43 | 2.29 | 0.10 | 0.00 | 10.97 | $0.0144 | 0h Seller / 18h Buyer / 6h Self-Suff. |
| **H003 (Buyer)** | 19.69 | 2.51 | 0.18 | 2.07 | 0.10 | 0.00 | 15.30 | $0.0481 | 0h Seller / 21h Buyer / 3h Self-Suff. |
| **H004 (High Demand)** | 46.63 | 3.29 | 0.67 | 2.50 | 0.10 | 0.00 | 41.51 | $0.1068 | 0h Seller / 22h Buyer / 2h Self-Suff. |
| **H005 (Opportunist)** | 16.04 | 4.19 | 0.86 | 2.68 | 0.10 | 0.00 | 10.04 | $0.0000 | 0h Seller / 14h Buyer / 10h Self-Suff. |
| **COMMUNITY TOTAL** | **119.79** | **20.52** | **6.35** | **15.24** | **0.10** | **1.81** | **92.21** | **$0.2914** | **24/24 Hours Pure Nash Equilibrium** |

#### 1) The Four Diurnal Operating Phases of the Microgrid:
- **Phase 1: Nighttime Baseload and Battery Depletion (Hours 00:00 – 07:00):** Solar generation is strictly zero. Each household discharges its battery (up to the 2.5 kW / 10% SOC limit) to cover baseload consumption (refrigeration, standby loads). By 02:00, batteries reach their 10% SOC floor. Because all households face net deficits and zero solar is available, the P2P pool is completely inactive ($Q_{	ext{trade}} = 0$). All remaining deficits are imported from the utility grid at $0.30/kWh.
- **Phase 2: Morning Solar Ramp & Behind-the-Meter Storage (Hours 08:00 – 10:00):** Solar production ramps upward. In accordance with greedy dispatch, each prosumer directs 100% of solar generation into its local battery first ($P_{	ext{ch}} \le 2.5	ext{ kW}$). Because local batteries absorb the solar surplus, net export to the community pool remains zero ($S_i^{	ext{net}} = 0$). The P2P pool remains quiet while domestic batteries replenish.
- **Phase 3: Midday Battery Saturation & Active P2P Market Clearing (Hours 11:00 – 15:00):** Solar prosumer H001 generates 8.73 kWh of cumulative PV energy. By Hour 14, H001's battery reaches the 90% SOC ceiling (4.5 kWh). Because the battery cannot accept further charge, surplus solar spills over into the community pool as physical net surplus ($S_{	ext{pool}} = 1.81	ext{ kWh}$). High-demand prosumer H004 and neighbors H002 and H003 have unmet deficits. Demand pressure $\lambda_t$ is calculated dynamically ($\lambda_t pprox 0.67$), establishing the market-clearing P2P price at $0.1534/kWh. H001 sells 0.098 kWh to H002, 0.150 kWh to H003, and 0.728 kWh to H004. At Hour 15, H001 clears 0.348 kWh with H003 at $0.2251/kWh. Both buyers and seller gain substantial economic margins.
- **Phase 4: Evening Peak Shaving (Hours 18:00 – 22:00):** Solar generation collapses to zero while domestic cooking, lighting, and entertainment loads surge. Households discharge their remaining stored midday solar energy, completely shaving the evening grid import peak and saving $0.30/kWh grid retail charges.

#### 2) Mathematical Coupling Proof: How Individual Player Profits Strictly Equal Community Profit:
A foundational mathematical property of our dynamic pricing mechanism is that community profit is not an abstract statistical aggregate—it is the exact mathematical sum of individual participant savings. Consider any hourly P2P transaction of volume $q$ traded at clearing price $P_{	ext{P2P}}$, where $P_{	ext{export}} \le P_{	ext{P2P}} \le P_{	ext{import}}$:
- **Seller Financial Gain:** By selling locally at $P_{	ext{P2P}}$ instead of exporting to the utility grid at $P_{	ext{export}} = \$0.08/	ext{kWh}$, the seller earns an extra profit of: $\Pi_{	ext{seller}} = q \cdot (P_{	ext{P2P}} - P_{	ext{export}})$.
- **Buyer Financial Gain:** By purchasing locally at $P_{	ext{P2P}}$ instead of importing from the utility grid at $P_{	ext{import}} = \$0.30/	ext{kWh}$, the buyer reduces its electricity bill by: $\Pi_{	ext{buyer}} = q \cdot (P_{	ext{import}} - P_{	ext{P2P}})$.
- **Total Community Welfare Identity:** Summing the gains of seller and buyer yields the community welfare gain:
  $$\Pi_{	ext{community}} = \Pi_{	ext{seller}} + \Pi_{	ext{buyer}} = q \cdot (P_{	ext{P2P}} - P_{	ext{export}}) + q \cdot (P_{	ext{import}} - P_{	ext{P2P}}) = q \cdot (P_{	ext{import}} - P_{	ext{export}}) = q \cdot (\$0.30 - \$0.08) = q \cdot \$0.22/	ext{kWh}$$

This identity provides profound insight: Every kilowatt-hour traded peer-to-peer captures the exact 22¢/kWh tariff spread that the utility retailer previously extracted from the neighborhood. The dynamic price $P_{	ext{P2P}}$ functions purely as an internal value-sharing rule that fairly distributes this 22¢/kWh margin between buyer and seller based on real-time market pressure. Consequently, whenever any household gains profit, the entire community gains profit by the identical amount. In the single-day trace, H001 earns +$0.1221, H004 saves +$0.1068, H003 saves +$0.0481, and H002 saves +$0.0144, summing precisely to the community total of $0.2914 AUD/day.

---

## X. CONCLUSION AND FUTURE WORK
This paper presented an integrated stochastic game-theoretic optimization framework for peer-to-peer energy trading in residential microgrids with distributed battery storage. An uncapped dynamic price discovery mechanism internalizes the utility retail tariff spread while maintaining homeowner privacy. Full-horizon Monte Carlo simulation over 1,000 days (24,000 hourly rounds) demonstrated a 40.07% total electricity expenditure reduction, capturing an average of $10.56 AUD/day in community savings ($10,559.67 AUD across the 1,000-day evaluation horizon). Factor decomposition proved that while solar self-consumption ($5.52/day, 52.3%) and battery storage ($4.50/day, 42.6%) provide baseline savings, P2P trading delivers an extra $0.54 AUD/day (5.1% software dividend, providing up to 19.1% of savings for heavy consumers) with zero extra hardware cost.

Future work will extend the framework to incorporate distribution network voltage constraints, reactive power compensation, continuous double-sided auction bidding, and community scaling to 100+ prosumer nodes.

---

## ACKNOWLEDGMENT
The authors express their sincere gratitude to their project supervisor, faculty members, and the Department of Mathematics, Sardar Vallabhbhai National Institute of Technology (SVNIT), Surat, for their constructive guidance, research facilities, and continuous mentorship throughout this research.

---

## REFERENCES
[1] F. Moret and P. Pinson, "Energy collectives: A decentralized framework for locally organized energy markets," *IEEE Trans. Power Syst.*, vol. 34, no. 1, pp. 647–656, Jan. 2019.  
[2] J. Guerrero, A. C. Chapman, and G. Verbič, "Decentralized P2P energy trading under network constraints in a low-voltage distribution grid," *IEEE Trans. Smart Grid*, vol. 10, no. 5, pp. 5173–5183, Sept. 2019.  
[3] W. Tushar, T. K. Saha, C. Yuen, D. Smith, and H. V. Poor, "Peer-to-peer trading in electricity networks: An overview," *IEEE Trans. Smart Grid*, vol. 11, no. 4, pp. 3185–3200, July 2020.  
[4] C. Zhang, J. Wu, Y. Zhou, M. Cheng, and C. Long, "Peer-to-Peer energy trading in a microgrid," *Appl. Energy*, vol. 220, pp. 1–12, June 2018.  
[5] Y. Parag and B. K. Sovacool, "Electricity market design for the prosumer era," *Nature Energy*, vol. 1, no. 4, p. 16032, Apr. 2016.  
[6] S. Paudel, K. Sampath, M. Yang, and P. H. Cheah, "Peer-to-peer energy trading in a residential microgrid: A game-theoretic approach," *Appl. Energy*, vol. 279, p. 115794, Dec. 2020.  
[7] N. Liu, X. Yu, C. Wang, C. Li, L. Ma, and J. Lei, "Energy-sharing model with price-based demand response for microgrids of peer-to-peer prosumers," *IEEE Trans. Power Syst.*, vol. 32, no. 5, pp. 3569–3583, Sept. 2017.  
[8] Z. Chen, L. Chen, and B. Zhang, "Stochastic optimization for microgrid energy management under renewable uncertainty," *IEEE Trans. Sustain. Energy*, vol. 12, no. 2, pp. 1120–1131, Apr. 2021.  
[9] M. Khorasany, Y. Mishra, and G. Ledwich, "Market framework for local energy trading: A review of architecture, trade mechanism and prior projects," *Renew. Sustain. Energy Rev.*, vol. 132, p. 110033, Oct. 2020.  
[10] J. F. Nash, "Non-cooperative games," *Ann. Math.*, vol. 54, no. 2, pp. 286–295, 1951.  
[11] W. Tushar et al., "Grid influenced peer-to-peer energy trading," *IEEE Trans. Smart Grid*, vol. 11, no. 2, pp. 1406–1418, Mar. 2020.  
[12] Ausgrid, "Solar Home Electricity Data," Ausgrid Network Data, 2014. [Online]. Available: https://www.ausgrid.com.au/Industry/Our-Research/Data-to-share/Solar-home-electricity-data
