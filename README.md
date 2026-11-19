# Stochastic Game-Theoretic Optimization under Uncertain Energy Conditions

A multi-agent microgrid peer-to-peer (P2P) energy trading platform that integrates:
1. **5-Household ($N=5$) Multi-Agent Game-Theoretic Market**: Prosumers dynamically trade rooftop solar generation.
2. **Battery Energy Storage Systems (BESS)**: 5.0 kWh storage per household with greedy pre-game charge/discharge dispatch and state-of-charge tracking.
3. **Dynamic P2P Price Discovery**: Market clearing based on real-time aggregate trading pool demand pressure $\lambda = D_{\text{pool}} / S_{\text{pool}}$.
4. **1,000-Day Monte Carlo Uncertainty Quantification**: 24,000 hourly game rounds preserving weather correlation and renewable volatility.
5. **Four Operational Modes / Counterfactual Analysis**: Isolates the exact financial dividends of solar, batteries, and P2P game coordination.
6. **Interactive Web Dashboard & IEEE Report**: Full-stack visualization dashboard and automated IEEE-style publication exporter (DOCX / PDF / HTML).

* **GitHub Repository**: [https://github.com/adityamedpalliwar/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions.git](https://github.com/adityamedpalliwar/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions.git)
* **Dataset Source**: [https://pierreh.eu/downloads/Ausgrid_solar_home_data.zip](https://pierreh.eu/downloads/Ausgrid_solar_home_data.zip)

---

## 🛠️ Installation & Environment Setup

Supported Python versions: **Python 3.10, 3.11, 3.12, 3.13**

```bash
# Clone repository
git clone https://github.com/adityamedpalliwar/Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions.git
cd Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions

# Install core dependencies
pip install -r requirements.txt
```

---

## 💾 Dataset & Empirical Data Source

The empirical evaluation uses half-hourly residential electricity smart-meter data from Ausgrid (New South Wales, Australia):
* **Dataset Download**: [https://pierreh.eu/downloads/Ausgrid_solar_home_data.zip](https://pierreh.eu/downloads/Ausgrid_solar_home_data.zip)
* **Description**: Contains 300 residential homes monitored over 3 years (2010–2013) with separate channels for gross household consumption and rooftop photovoltaic generation.
* **Microgrid Archetypes ($N=5$)**: Extracted five distinct prosumer load and solar generation profiles (H001 net seller, H004 net buyer, and H002, H003, H005 balanced/opportunistic prosumers) to capture realistic meteorological and behavioral cross-correlations.

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

## 🖥️ Interactive Web Dashboard

Launch the local full-stack web dashboard to visualize household profiles, diurnal battery dispatch, dynamic pricing, and simulation analytics in real time:

```bash
# Start the Flask web dashboard
python dashboard/app.py
```

Then open your browser and navigate to: **`http://localhost:5000`**

### Dashboard Functionality & Features:
1. **Project Aim & 4-Step Pipeline**: Overview of the mathematical optimization pipeline and persona cards for all 5 participants (H001–H005) detailing solar capacity, average load, and trading behavior.
2. **Scenario & Trajectory Generation**: Interactive 24-hour diurnal trajectories displaying gross load, solar PV generation, and realized net energy surplus or deficit per household.
3. **Battery Dispatch & Dynamic Price Discovery**:
   - Physical BESS greedy pre-game dispatch tracking state of charge ($10\% \le \text{SOC} \le 90\%$) under charge/discharge power limits ($2.5\text{ kW}$) and $95\%$ efficiency.
   - Real-time clearing price calculation $P_{\text{P2P}} = P_{\text{export}} + (\lambda / \lambda_{\max}) \cdot (P_{\text{import}} - P_{\text{export}})$ governed by pool demand pressure $\lambda = D_{\text{pool}} / S_{\text{pool}}$.
4. **Four Operational Modes & Savings Comparison**: Side-by-side cost comparisons, daily savings, and percentage bill reduction across Pure Grid, Solar+Grid, Battery+Grid, and Game P2P.
5. **Publication Figures Gallery**: High-resolution viewer displaying all 7 Monte Carlo publication plots.
6. **REST API**: Built-in backend endpoints (`/api/system_overview`, `/api/customer_profiles`, `/api/diurnal_trajectories`, `/api/modes_comparison`, `/api/figures_catalog`) for programmatic data queries.

---

## 📄 IEEE Academic Paper & Report Generation

The project includes an automated IEEE-format publication generator and interactive report:

| Format | File / Command | Description |
| :--- | :--- | :--- |
| **Interactive HTML** | `reports/ieee_paper_revised.html` | Two-column IEEE format with embedded high-resolution plots. Open in any browser. |
| **Microsoft Word (DOCX)** | `python reports/export_docx.py` | Generates `reports/ieee_paper_revised.docx` with two-column text and full-width figures (6.85 in). |
| **PDF Export (Headless)** | `python reports/export_pdf.py` | Generates `reports/ieee_paper_revised.pdf` via Chrome / Edge headless rendering. |
| **DOCX + PDF in One Step** | `python reports/export_docx.py --pdf` | Generates both DOCX and PDF simultaneously. |

---

## 📊 Four Operational Counterfactual Modes

To rigorously evaluate the system, the platform compares 4 distinct operating regimes:

1. **Mode 1: Pure Grid Baseline**: 100% of demand imported from utility grid at $\$0.30/\text{kWh}$ (no solar, no batteries).
2. **Mode 2: Solar + Grid-Only**: Solar panels installed for self-consumption; all deficits imported at $\$0.30/\text{kWh}$, surpluses exported at $\$0.08/\text{kWh}$ (no battery, no P2P).
3. **Mode 3: Battery + Grid-Only**: Solar + 5.0 kWh battery per home for local storage arbitrage, but strictly NO P2P trading allowed with neighbors.
4. **Mode 4: Proposed P2P Game + Battery**: Full multi-agent game-theoretic market with dynamic pricing and battery dispatch.

---

## 📈 Key Findings & Financial Profit Decomposition (1,000 Days)

## Monte Carlo Simulation Results (1,000 Scenarios)

The following table summarizes the financial performance of five participants under four energy configurations, based on the Monte Carlo simulation.

| Participant | Pure Grid Cost | Solar+Grid Cost | Battery+Grid Cost | **P2P Game Cost** | **Total Savings** | **Bill Reduction** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **H001 (Seller)** | $6.27/day | $4.34/day | $3.11/day | **$2.98/day** | +$3,285.63 | **52.4%** |
| **H002** | $1.80/day | $1.17/day | $0.60/day | **$0.59/day** | +$1,216.78 | **67.4%** |
| **H003** | $4.11/day | $3.28/day | $2.49/day | **$2.48/day** | +$1,633.30 | **39.7%** |
| **H004 (Buyer)** | $10.12/day | $9.32/day | $8.59/day | **$8.23/day** | +$1,898.61 | **18.8%** |
| **H005** | $4.05/day | $2.72/day | $1.56/day | **$1.52/day** | +$2,525.34 | **62.4%** |
| **COMMUNITY TOTAL** | **$26.36/day** | **$20.83/day** | **$16.34/day** | **$15.80/day** | **+$10,559.67** | **40.07%** |

*Note: Community totals and percentages are calculated using unrounded simulation values. Consequently, minor differences may occur when summing individually rounded participant values.*

### Financial Benefit Breakdown

Across the 1,000-day evaluation period, the community achieves a total reported financial benefit of **AUD $10,559.67**, distributed across three sources:

| Benefit Source | Financial Benefit (AUD) | Contribution |
| :--- | :---: | :---: |
| Solar Self-Consumption | $5,522.87 | 52.3% |
| Battery Arbitrage | $4,496.47 | 42.6% |
| P2P Market Trading | **$540.34** | **5.1%** |
| **Total** | **$10,559.67** | **100.0%** |

**Key Finding:** P2P market trading contributes an additional reported $540.34 (5.1%) to the community's financial benefit through software-based energy coordination, without requiring additional hardware investment for the trading mechanism itself.

*Note: The displayed benefit components sum to $10,559.68 due to rounding. The reported total is retained from the simulation results.*
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

Execute the test suite using Python's module runner (cross-platform compatible):

```bash
# Run the flagship 5-household battery game test
python -m pytest tests/test_n_player_game_with_battery.py

# Run the full project test suite
python -m pytest
```

---

## 📁 Repository Structure

```
├── dashboard/                     # Full-stack Flask web dashboard
│   ├── app.py                     # Dashboard server and REST API
│   └── data_service.py            # High-performance analytical data caching service
├── data/                          # Preprocessed Ausgrid solar & load dataset
├── notebooks/                     # Exploratory research notebooks
├── reports/                       # IEEE-style paper, DOCX/PDF exporters, and templates
│   ├── ieee_paper_revised.html    # Interactive IEEE two-column report
│   ├── export_docx.py             # DOCX exporter (full-width figures, two-column layout)
│   └── export_pdf.py              # Chrome/Edge headless PDF exporter
├── results/                       # Simulation outputs
│   ├── figures/                   # High-resolution publication plots (01–07)
│   └── tables/                    # Authoritative Monte Carlo summary metrics (CSV)
├── src/                           # Core algorithmic and game engine packages
│   ├── battery/                   # Physical BESS state-of-charge tracking & dispatch
│   └── game/                      # N-player normal-form game, Nash equilibrium, dynamic pricing
├── tests/                         # Comprehensive pytest test suite
├── generate_monte_carlo_plots.py  # Standalone publication figure renderer
├── main.py                        # Primary entrypoint CLI for Monte Carlo simulation
├── requirements.txt               # Production Python dependencies
└── simulate_five_house_monte_carlo.py # Flagship 1,000-scenario Monte Carlo simulation
```

---

## 📦 Appendix: Legacy Initial 2-Player Prototype (Kept Aside)

The initial 2-player prototype (`demo_prototype.py`, H001 vs H002) was developed early in the project as a preliminary pedagogical proof-of-concept. It is kept aside for historical reference:

```bash
python main.py --legacy-2player
```
