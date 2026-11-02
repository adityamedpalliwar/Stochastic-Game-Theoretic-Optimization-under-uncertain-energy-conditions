# Stochastic Game-Theoretic Optimization under Uncertain Energy Conditions

A multi-agent microgrid peer-to-peer (P2P) energy trading platform that integrates:
1. **5-Household ($N=5$) Multi-Agent Game-Theoretic Market**: Prosumers dynamically trade rooftop solar generation.
2. **Battery Energy Storage Systems (BESS)**: 5.0 kWh storage per household with greedy pre-game charge/discharge dispatch and state-of-charge tracking.
3. **Dynamic P2P Price Discovery**: Market clearing based on real-time aggregate trading pool demand pressure $\lambda = D_{\text{pool}} / S_{\text{pool}}$.
4. **1,000-Day Monte Carlo Uncertainty Quantification**: 24,000 hourly game rounds preserving weather correlation and renewable volatility.
5. **Four Operational Modes / Counterfactual Analysis**: Isolates the exact financial dividends of solar, batteries, and P2P game coordination.

---

## 🚀 Quick Start: Running the 5-Household Flagship System

The primary simulation executes 1,000 Monte Carlo simulated days (24,000 hourly market rounds) across the 5 households:

```bash
# Run full 1,000-day Monte Carlo simulation (computes all financial metrics & generates publication plots)
python main.py

# Run with customized scenario counts or random seed
python main.py --scenarios 500 --seed 42

# Generate high-resolution publication plots only
python generate_monte_carlo_plots.py
```

---

## 📊 Four Operational Counterfactual Modes

To rigorously evaluate the system, the platform compares 4 distinct operating regimes:

1. **Mode 1: Pure Grid Baseline**: 100% of demand imported from utility grid at $\$0.30/\text{kWh}$ (no solar, no batteries).
2. **Mode 2: Solar + Grid-Only**: Solar panels installed for self-consumption; all deficits imported at $\$0.30/\text{kWh}$, surpluses exported at $\$0.08/\text{kWh}$ (no battery, no P2P).
3. **Mode 3: Battery + Grid-Only**: Solar + 5.0 kWh battery per home for local storage arbitrage, but strictly NO P2P trading allowed with neighbors.
4. **Mode 4: Proposed P2P Game + Battery**: Full multi-agent game-theoretic market with dynamic pricing and battery dispatch.

---

## 📈 Key Findings & Financial Profit Decomposition (1,000 Days)

From `results/tables/monte_carlo_1000_scenarios_summary.csv`:

| Participant | Pure Grid Cost | Solar+Grid Cost | Battery+Grid Cost | **P2P Game Cost** | **Total Savings** | **Bill Reduction** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **H001 (Seller)** | $\$6.27/\text{day}$ | $\$4.34/\text{day}$ | $\$3.11/\text{day}$ | **$\$2.98/\text{day}$** | $+\$3,285.63$ | **$52.4\%$** |
| **H002** | $\$1.80/\text{day}$ | $\$1.17/\text{day}$ | $\$0.60/\text{day}$ | **$\$0.59/\text{day}$** | $+\$1,216.78$ | **$67.4\%$** |
| **H003** | $\$4.11/\text{day}$ | $\$3.28/\text{day}$ | $\$2.49/\text{day}$ | **$\$2.48/\text{day}$** | $+\$1,633.30$ | **$39.7\%$** |
| **H004 (Buyer)** | $\$10.12/\text{day}$ | $\$9.32/\text{day}$ | $\$8.59/\text{day}$ | **$\$8.23/\text{day}$** | $+\$1,898.61$ | **$18.8\%$** |
| **H005** | $\$4.05/\text{day}$ | $\$2.72/\text{day}$ | $\$1.56/\text{day}$ | **$\$1.52/\text{day}$** | $+\$2,525.34$ | **$62.4\%$** |
| **COMMUNITY TOTAL** | **$\$26.36/\text{day}$** | **$\$20.83/\text{day}$** | **$\$16.34/\text{day}$** | **$\$15.80/\text{day}$** | **$+\$10,559.67$** | **$40.07\%$** |

### Profit Breakdown:
Across 1,000 days, the community earns **$\$10,559.67\text{ AUD}$** in total financial benefit:
* **Solar Self-Consumption**: $\$5,522.87$ ($52.3\%$)
* **Battery Arbitrage**: $\$4,496.47$ ($42.6\%$)
* **P2P Market Trading**: **$\$540.34$ ($5.1\%$)** *(Pure software coordination dividend with zero extra hardware cost!)*

---

## 🖼️ Publication Figures

Generated into `results/figures/simulate_five_house_monte_carlo/`:
* `01_daily_cost_comparison_across_modes.png`: Daily electricity costs across the 4 operational modes.
* `02_total_profit_and_cost_difference.png`: Baseline vs optimized costs & total profit earned per household.
* `03_p2p_profit_distribution_1000_scenarios.png`: Box plots and Kernel Density Estimation (KDE) probability density of daily profits.
* `04_hourly_average_community_profit.png`: Diurnal 24-hour profile highlighting the peak midday trading window (11:00 to 15:00).
* `05_cumulative_community_savings_over_1000_days.png`: Cumulative financial savings trajectory over 1,000 simulated days.
* `06_total_profit_difference_decomposition.png`: Stacked bar chart decomposing profit into Solar, Battery, and P2P Trading.
* `07_savings_portion_by_factor.png`: Proportional factor breakdown across households.

---

## 🧪 Running Tests

Execute the test suite via pytest:

```bash
pytest tests/test_n_player_game_with_battery.py
```

---

## 📦 Appendix: Legacy Initial 2-Player Prototype (Kept Aside)

The initial 2-player prototype (`demo_prototype.py`, H001 vs H002) was developed early in the project as a preliminary pedagogical proof-of-concept. It is kept aside for historical reference:

```bash
python main.py --legacy-2player
```
