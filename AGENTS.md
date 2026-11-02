# AGENTS.md: Developer & Agent Guidelines

## ⚠️ CRITICAL DIRECTIVE: PRIMARY GAME ARCHITECTURE VS. LEGACY TOY PROTOTYPE

When answering questions, modifying code, or performing analysis on this repository:

1. **THE PRIMARY FLAGSHIP SYSTEM IS THE 5-HOUSEHOLD (N=5) STOCHASTIC GAME**:
   - **Main Simulation File**: [`simulate_five_house_monte_carlo.py`](file:///d:/5thSem/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/simulate_five_house_monte_carlo.py)
   - **Main Game Engine**: [`src/game/game.py`](file:///d:/5thSem/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/game.py) (`run_n_player_game`)
   - **Payoff Matrix & Battery Dispatch**: [`src/game/payoff_matrix.py`](file:///d:/5thSem/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/payoff_matrix.py) (`build_n_player_payoff_matrix`, `dispatch_battery_pre_game`)
   - **Dynamic Pricing Discovery**: [`src/game/pricing.py`](file:///d:/5thSem/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/src/game/pricing.py) (`DynamicPricingModel`)
   - **Visualization Script**: [`generate_monte_carlo_plots.py`](file:///d:/5thSem/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/generate_monte_carlo_plots.py)
   - **Authoritative Results**:
     - Summary table: [`results/tables/monte_carlo_1000_scenarios_summary.csv`](file:///d:/5thSem/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/results/tables/monte_carlo_1000_scenarios_summary.csv)
     - High-resolution figures: [`results/figures/simulate_five_house_monte_carlo/`](file:///d:/5thSem/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/results/figures/simulate_five_house_monte_carlo/) (Plots 01 through 07)

2. **KEEP THE 2-PLAYER GAME ASIDE**:
   - The 2-player game ([`demo_prototype.py`](file:///d:/5thSem/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions/demo_prototype.py), `run_two_household_game`) was an **initial toy prototype** used for basic conceptual verification early in the project.
   - **NEVER** present, default to, or focus on the 2-player game when the user asks about "the game", "how the game works", or project results.
   - Only mention the 2-player model if the user explicitly asks about the "initial prototype" or "legacy 2-player version".

---

## System Overview & Key Concepts

### 1. Market Participants ($N=5$)
* **H001**: High rooftop solar, net energy seller during peak midday hours.
* **H002**: Low load prosumer, well-balanced self-consumption.
* **H003**: Moderate load prosumer, regular net buyer.
* **H004**: High demand prosumer, dominant net energy buyer.
* **H005**: Moderate solar & load, opportunistic trading behavior.

### 2. Physical Battery Energy Storage Systems (BESS)
* Each household possesses an independent battery:
  - Capacity: $5.0\text{ kWh}$
  - Charge / Discharge Power: $2.5\text{ kW}$
  - Round-trip efficiency: $95\%$
  - Operating SOC range: $10\% \le \text{SOC} \le 90\%$
  - Pre-game greedy dispatch: Surplus solar charges battery first; demand deficits draw from battery first. Unabsorbed surplus ($S_i^{\text{net}}$) or unmet deficit ($D_i^{\text{net}}$) enters the P2P trading pool.

### 3. Dynamic Price Discovery
* Aggregate pool demand pressure: $\lambda = \frac{D_{\text{pool}}}{S_{\text{pool}} + \epsilon}$
* Uncapped dynamic pricing model: $P_{\text{P2P}} = P_{\text{export}} + \left(\frac{\lambda}{\lambda_{\max}}\right) \cdot (P_{\text{import}} - P_{\text{export}})$
* Guaranteed incentive compatibility: $P_{\text{export}} \le P_{\text{P2P}} \le P_{\text{import}}$ under typical operational regimes, providing Pareto-dominant coordination.

### 4. Four Operational Counterfactuals
1. **Pure Grid**: 100% Demand imported from grid at $\$0.30/\text{kWh}$ (no solar, no battery).
2. **Solar + Grid-Only**: Solar self-consumption; deficits bought at $\$0.30/\text{kWh}$, surpluses sold at $\$0.08/\text{kWh}$ (no battery, no P2P).
3. **Battery + Grid-Only**: Solar + 5 kWh battery storage for self-consumption, but NO P2P trading with neighbors.
4. **P2P Game + Battery**: Full proposed multi-agent P2P game with dynamic pricing and battery storage.

### 5. 1,000-Scenario Monte Carlo Findings
* **Baseline Pure Grid Cost**: $\$26.36/\text{day}$ ($\$26,355$ over 1,000 days).
* **Game Coordinated Cost**: $\$15.80/\text{day}$ ($\$15,795$ over 1,000 days).
* **Total Community Profit**: **$\$10,559.67\text{ AUD}$ ($40.07\%$ total bill reduction)**.
* **Profit Breakdown**:
  - Solar self-consumption: $\$5,522.87$ ($52.3\%$)
  - Battery arbitrage: $\$4,496.47$ ($42.6\%$)
  - P2P Trading Game: $\$540.34$ ($5.1\%$ pure software coordination gain).

---

## Execution Commands

```bash
# Run flagship 5-household Monte Carlo simulation (1,000 scenarios / 24,000 rounds)
python main.py

# Run simulation with custom scenario count
python main.py --scenarios 500 --seed 42

# Generate high-resolution publication plots
python generate_monte_carlo_plots.py

# Run legacy initial 2-player prototype (kept aside for reference)
python main.py --legacy-2player
```

