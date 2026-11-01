# Deliverable 2: Interactive Web Prototype Implementation Plan
## Stochastic Game-Theoretic Renewable Energy Management under Uncertain Energy Conditions

**Document Identifier:** `reports/deliverable2_web_prototype_plan.md`  
**Date:** November 1, 2026  
**Status:** APPROVED (Updated with Authoritative Audited Corrections)  
**Target Audience:** Academic Evaluators, Thesis Supervisors, Project Review Committee  
**Authors:** 5th Semester Game Theory & Energy Optimization Research Group  

---

## 1. Executive Summary & Objectives

Deliverable 2 transitions the verified, audited, and mathematically proven computational framework established in Deliverable 1 into a **high-impact, interactive academic research web dashboard**. 

The primary design goal is to deliver a **professional, university-grade demonstration dashboard** that an evaluating professor or peer researcher can use to independently explore, verify, and understand the entire project lifecycle—from hourly processed grid-solar measurements (aggregated from Ausgrid half-hourly records during data preprocessing), through deep learning forecasting and Monte Carlo uncertainty quantification, to stochastic Model Predictive Control (MPC) battery dispatch, and culminating in peer-to-peer (P2P) double auctions and fairness-aware Pure Nash Equilibrium (PNE) selection.

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 DELIVERABLE 2 WEB ARCHITECTURE                                  │
│                                                                                                 │
│  ┌──────────────────────┐      ┌───────────────────────────────┐      ┌──────────────────────┐  │
│  │   Frozen Datasets    │      │    Lightweight Data Service   │      │ Responsive Academic  │  │
│  │   & Verified Models  │─────▶│       (Flask 3.1.0 REST)      │─────▶│   Web Dashboard UI   │  │
│  │  (CSV, JSON.GZ, PKL) │      │  - In-memory DataFrame Cache │      │ (HTML5, Modern CSS,  │  │
│  │  103k+ rows / 1.4MB  │      │  - Fast Sub-ms Query Endpoints│      │ Plotly.js / KaTeX)   │  │
│  └──────────────────────┘      └───────────────────────────────┘      └──────────────────────┘  │
│             ▲                                                                                   │
│             └─────── STRICT RULE: READ-ONLY ACCESS (ZERO RECOMPUTATION) ────────────────────────┘
```

### Key Highlights of the Web Prototype Plan:
1. **Zero Recomputation & 100% Truth Preservation:** The web application acts strictly as an exploratory and analytical visualization harness over the frozen baseline datasets (`data/processed/`, `reports/phase7_*`, `reports/phase8c_*`, `reports/phase8d_*`).
2. **Comprehensive Scope Coverage:** Full visual representation across all 8 functional domains:
   - Household demand and solar generation profiles based on hourly processed panel data.
   - Battery state-of-charge (SOC) dynamics and physical conservation balance.
   - Honest point forecast evaluation (highlighting that Persistence outperforms LSTM for demand MAE, while LSTM achieves superior solar MAE and demand RMSE).
   - Monte Carlo 90% prediction intervals and empirical calibration.
   - Multi-household P2P energy trading and microgrid liquidity.
   - Discrete-strategy double auctions and pure Nash equilibrium multiplicity.
   - Phase 8D fairness policies (Strategies A through F and hybrid sensitivity sweeps).
   - Household economic benefits, social welfare invariance, and financial reconciliation.
3. **Turnkey Local Deployment:** Built natively on `Flask 3.1.0` (already installed in the local Python 3.13 environment) paired with a responsive modern frontend leveraging `Plotly.js` and `KaTeX` via local or CDN assets, enabling one-click local startup with zero build-toolchain overhead.

---

## 2. Strict Adherence to Project Governance Rules

To guarantee research integrity and uphold previous audit validations, Deliverable 2 strictly complies with the five inviolable governance rules:

| Governance Rule | Project Compliance Mechanism |
| :--- | :--- |
| **Rule 1: Do not modify existing Python computational engine** | Source modules in `src/` (`src/energy/`, `src/forecasting/`, `src/stochastic/`, `src/optimization/`, `src/game/`, `src/evaluation/`) remain completely untouched and unmodified. All 250/250 passing tests continue to pass identically. |
| **Rule 2: Do not change frozen datasets, models, or outputs** | All files in `data/` and `reports/` (including `phase7_benchmark_metrics.csv`, `phase7_hourly_records.csv`, `phase8c_all_equilibria.json.gz`, `phase8c_hourly_equilibria.csv`, `phase8d_hourly_selection.csv`, and `phase8d_strategy_comparison.csv`) are opened in **read-only mode**. No file will be overwritten, modified, or re-cleared. |
| **Rule 3: Do not introduce new algorithms** | No new optimization algorithms, neural architectures, sampling procedures, or game-theoretic solvers will be written. All displayed equilibria, payoffs, welfare values, and battery trajectories are the exact values generated during Phase 7.1, Phase 8C, and Phase 8D. |
| **Rule 4: Existing Python system remains source of truth** | If mathematical formulas or metrics are displayed on the frontend, their definitions and values are anchored strictly to the verified implementations in `src/game/fairness_metrics.py`, `src/energy/energy_balance.py`, and `src/evaluation/metrics.py`. |
| **Rule 5: Visualize existing results rather than independently recompute** | The web server loads the precomputed results at launch into memory (< 2.0s initial load). Client queries (filters, household selection, timeline scrubbing) are resolved instantly from in-memory cached DataFrames. |

---

## 3. Comprehensive Repository Data & Artifact Inventory

The repository contains a rich, complete set of processed datasets, model archives, and simulation records. An exhaustive inspection yielded the following catalog:

### 3.1 Data & Report Files Catalog

| Category | File Path | Format & Compression | Disk Size | Records / Rows | Columns | Purpose in Dashboard |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Customer Metadata** | `data/processed/customer_id_mapping.csv` | CSV | 278 B | 3 | 5 | Household specifications (PV capacity, postcode, criteria). |
| **Tariff Configuration** | `data/processed/energy_price_scenarios.csv` | CSV | 711 B | 3 | 7 | Retail price benchmarks ($0.30/kWh grid, $0.08/kWh feed-in). |
| **Annual Hourly Panel** | `data/processed/three_house_hourly_lstm_ready.csv` | CSV | 2.51 MB | 26,280 | 12 | Full 1-year historical hourly demand and solar generation curves (8,760 hrs $\times$ 3 households). |
| **Test Predictions** | `data/processed/test_predictions.csv` | CSV | 382 KB | 5,256 | 6 | Point forecast comparisons: actual vs. predicted demand and solar. |
| **Baseline Metrics** | `data/processed/evaluation_metrics.csv` | CSV | 1.1 KB | 16 | 8 | Model scorecard: MAE and RMSE for LSTM vs. Persistence. |
| **Interval Summary** | `data/processed/test_forecast_interval_summary.csv` | CSV | 1.0 KB | 8 | 13 | 90% prediction interval coverage, mean/median width. |
| **Row-Level Intervals** | `data/processed/test_interval_evaluations_row_level.csv` | CSV | 967 KB | 5,256 | 21 | Observation-level upper/lower bounds and coverage indicators. |
| **Model Weights** | `data/processed/lstm_model.keras` | Keras HDF5/Zip | 68.8 KB | 1 model | - | Deep learning architecture documentation and layer inspection. |
| **Model Scaler** | `data/processed/lstm_scaler.joblib` | Joblib Pickle | 1.1 KB | 1 scaler | - | MinMaxScaler feature range parameter display. |
| **Phase 6A Metrics** | `reports/phase6a_simulation_metrics.csv` | CSV | 1.2 KB | 3 | 36 | Controller benchmark: Greedy vs. Realistic MPC vs. Perfect MPC. |
| **Phase 6B.2 Metrics** | `reports/phase6b_2_simulation_metrics.csv` | CSV | 2.1 KB | 3 | 46 | Controller benchmark: Oracle Greedy, Forecast Greedy, Det & Stoch MPC. |
| **Phase 6B.2 Hourly** | `reports/phase6b_2_hourly_records.csv` | CSV | 3.52 MB | 21,024 | 22 | Hourly battery SOC, charge/discharge, and costs (Phase 6B.2). |
| **Phase 7.1 Benchmarks**| `reports/phase7_benchmark_metrics.csv` | CSV | 7.9 KB | 32 | 30 | Standalone vs. P2P energy balances, grid imports, and net costs. |
| **Phase 7.1 Hourly** | `reports/phase7_hourly_records.csv` | CSV | 8.87 MB | 42,048 | 29 | Comprehensive hourly simulation across 4 controllers and 2 modes. |
| **Phase 7.1 Liquidity** | `reports/phase7_1_liquidity_metrics.csv` | CSV | 884 B | 4 | 23 | Microgrid coincidence of surplus/deficit, unmatched energy. |
| **Phase 8C Hourly PNE** | `reports/phase8c_hourly_equilibria.csv` | CSV | 325 KB | 1,752 | 33 | Hourly representative pure Nash equilibrium (Strategy A reference). |
| **Phase 8C Complete PNE**| `reports/phase8c_all_equilibria.json.gz` | Gzip JSON | 1.34 MB | 1,752 hrs | 315,280 PNE | Complete enumeration archive of all pure Nash equilibria. |
| **Phase 8D Hourly** | `reports/phase8d_hourly_selection.csv` | CSV | 948 KB | 1,752 | 66 | Hourly selection across all 6 core policies (A, B, C, D, E, F_05). |
| **Phase 8D Comparison** | `reports/phase8d_strategy_comparison.csv` | CSV | 3.4 KB | 13 | 24 | Macroeconomic summary across 6 core strategies + 7 hybrid weights. |
| **Phase 8D Charts** | `reports/phase8d_visualizations/*.png` | PNG Images | ~1.6 MB | 8 charts | - | Publication-quality static reference plots for verification. |

> [!NOTE]
> The raw 300-customer Ausgrid file `data/raw/Solar home 2012-2013.csv` (268,558 half-hourly rows) was preprocessed offline into the clean hourly panel `data/processed/three_house_hourly_lstm_ready.csv` (26,280 rows). In accordance with Deliverable 2 scope, the dashboard visualizes the clean hourly processed panel, avoiding slow client-side parsing of the 268k-row raw file.

---

## 4. Functional Domain Output Mapping

Each of the 8 required functional areas is fully supported by existing frozen repository outputs:

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 FUNCTIONAL DOMAIN MAPPING PIPELINE                                    │
│                                                                                                       │
│   [ 1. Demand & Solar ] ──▶ [ 2. Battery & Balance ] ──▶ [ 3. Forecasts ] ──▶ [ 4. Monte Carlo ]      │
│   three_house_hourly        phase7_hourly_records        test_predictions     test_interval_eval      │
│   (26,280 hrs full year)    (42,048 hrs across modes)    (5,256 hrs test)     (90% PI calibration)    │
│                                                                                                       │
│   [ 5. P2P Trading ]   ──▶ [ 6. Nash Equilibria ]   ──▶ [ 7. Fairness A-F ] ──▶ [ 8. Benefits & Welfare]│
│   phase7_benchmark          phase8c_all_equilibria       phase8d_hourly_sel   phase8d_strategy_comp   │
│   (Standalone vs P2P)       (315,280 PNE archive)        (6 policy profiles)  (Identities & Gini)     │
└───────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Detailed Mapping Matrix & Mathematical Verification

| Functional Domain | Authoritative Existing Data Files | Key Metrics & Information Represented |
| :--- | :--- | :--- |
| **1. Household Demand & Solar Generation** | `data/processed/customer_id_mapping.csv`<br>`data/processed/three_house_hourly_lstm_ready.csv` | - 3 households: H001 (Customer 1, 3.78 kWp), H002 (Customer 3, 1.0 kWp), H003 (Customer 4, 1.0 kWp).<br>- Hourly demand (General Consumption + Controlled Load) and Solar PV generation across full 8,760 hours per house (26,280 total records).<br>- Seasonal patterns, summer peak solar, winter evening heating demand spikes. |
| **2. Battery Operation & Energy Balance** | `reports/phase6b_2_hourly_records.csv`<br>`reports/phase7_hourly_records.csv`<br>`reports/phase7_benchmark_metrics.csv` | - Physical battery limits: $E \in [0.5, 4.5]\text{ kWh}$ ($\text{SOC} \in [0.10, 0.90]$), $P_{\max} = 2.5\text{ kW}$, $\eta = 0.95$.<br>- Mutual exclusion: $C_t \cdot D_t = 0$.<br>- **Verified Physical Formulas (`src/energy/energy_balance.py`):**<br>&nbsp;&nbsp;*Self-consumption:* $E_{\text{self}} = \min(D_i, G_i)$<br>&nbsp;&nbsp;*Raw deficit/surplus:* $E_{\text{raw\_deficit}} = \max(0, D_i - G_i)$, $E_{\text{raw\_surplus}} = \max(0, G_i - D_i)$<br>&nbsp;&nbsp;*Post-battery balance:*<br>&nbsp;&nbsp;&nbsp;&nbsp;$d_i^{\text{post}}(t) = \max(0, E_{\text{raw\_deficit}} - D_{i, \text{bat}}) = \max(0, D_i - E_{\text{self}} - D_{i, \text{bat}})$<br>&nbsp;&nbsp;&nbsp;&nbsp;$s_i^{\text{post}}(t) = \max(0, E_{\text{raw\_surplus}} - C_{i, \text{bat}}) = \max(0, G_i - E_{\text{self}} - C_{i, \text{bat}})$<br>&nbsp;&nbsp;*Demand conservation:* $D_i = E_{\text{self}} + D_{i, \text{bat}} + d_i^{\text{post}}$<br>&nbsp;&nbsp;*Solar conservation:* $G_i = E_{\text{self}} + C_{i, \text{bat}} + s_i^{\text{post}}$<br>&nbsp;&nbsp;*Net flow identity:* $(D_i - G_i) = (d_i^{\text{post}} - s_i^{\text{post}}) + (D_{i, \text{bat}} - C_{i, \text{bat}})$<br>- Physical conservation residuals strictly $< 5 \times 10^{-7}\text{ kWh}$ (verified zero leakage). |
| **3. Actual vs. Predicted Forecasting** | `data/processed/test_predictions.csv`<br>`data/processed/evaluation_metrics.csv` | - Held-out test period: 1,752 hours (April 19, 2013 to June 30, 2013) $\times$ 3 households = 5,256 evaluations.<br>- **Honest Benchmark Comparison:**<br>&nbsp;&nbsp;*Solar Generation:* LSTM MAE **0.0814 kWh** vs. Persistence **0.0864 kWh** (LSTM superior); LSTM RMSE **0.1600 kWh** vs. Persistence **0.2001 kWh**.<br>&nbsp;&nbsp;*Total Demand:* Persistence MAE **0.4310 kWh** vs. LSTM MAE **0.4660 kWh** (Persistence superior on MAE due to load spikes); LSTM achieves lower RMSE: **0.7834 kWh** vs. **0.8557 kWh**. |
| **4. Monte Carlo Uncertainty Intervals** | `data/processed/test_interval_evaluations_row_level.csv`<br>`data/processed/test_forecast_interval_summary.csv` | - 1,000 paired residual resamples per observation using deterministic Protocol B seeds ($\text{CRC32}$).<br>- 90% Nominal Prediction Intervals: Solar achieves 89.42% empirical coverage (-0.58% error); Demand achieves 81.91% coverage (-8.09% error).<br>- Lower and upper bound trajectories with visual out-of-interval indicators. |
| **5. Peer-to-Peer (P2P) Energy Trading** | `reports/phase7_benchmark_metrics.csv`<br>`reports/phase7_1_liquidity_metrics.csv`<br>`reports/phase7_hourly_records.csv` | - Microgrid liquidity: 866 tradeable hours (simultaneous surplus & deficit), 59 sellers-only hours, 827 buyers-only hours.<br>- Total P2P physical volume cleared: **121.611449 kWh**.<br>- Comparative performance: Standalone mode ($780.09 community cost) vs. P2P mode ($753.34 community cost), yielding $26.75 community savings. |
| **6. Pure Nash Equilibria (PNE)** | `reports/phase8c_all_equilibria.json.gz`<br>`reports/phase8c_hourly_equilibria.csv`<br>`reports/phase8c_dataset_evaluation.md` | - Discrete 7-point action grid: $\mathcal{P} = \{0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30\}\text{ AUD/kWh}$.<br>- Complete enumeration of **315,280 PNE** across 1,752 hours.<br>- Multiplicity: 10 to 14 PNE per mixed-market hour.<br>- Pareto dominance filtering: Eliminates 2,470 submaximal profiles (zero-trade/partial-trade traps), preserving the Pareto frontier ($E_{\text{Pareto}}$).<br>- Empirical invariance: Every Pareto equilibrium clears exactly maximum physical volume $Q^*(t)$ and maximum community welfare $\Delta W^*(t)$. |
| **7. Fairness Strategies A through F** | `reports/phase8d_hourly_selection.csv`<br>`reports/phase8d_strategy_comparison.csv`<br>`reports/phase8d_fairness_analysis.md` | - Policy comparison across 6 core strategies: Reference (A), Seller-Favouring (B), Buyer-Favouring (C), Max-Min Fair (D), Nash Social Welfare (E), and Hybrid Loss (F).<br>- Volume-Weighted Average Price (VWAP): Strategy B ($0.2715) vs. Strategy C ($0.1713) vs. Strategy A ($0.2199).<br>- Hybrid sensitivity sweep ($w_{\text{fair}} \in [0.0, 1.0]$) demonstrating the discrete 2-regime step response at $w=0.5$. |
| **8. Household Benefits & Community Welfare** | `reports/phase8d_strategy_comparison.csv`<br>`reports/phase8d_hourly_selection.csv`<br>`reports/financial_payoff_nash_verification.md` | - Individual payoff distribution across households: H001 (solar exporter), H002 (flexible prosumer), H003 (net buyer).<br>- Community welfare identity verified to $< 10^{-14}\text{ AUD}$: $\Delta W = U_{\text{seller}} + U_{\text{buyer}} = 0.22 \times Q = \$26.754519\text{ AUD}$.<br>- Financial bilateral payment-revenue conservation verified to $0.000\text{ AUD}$ (exact zero financial leakage). |

---

## 5. Exact Column Specifications and Data Dtypes

Below are the exact schemas, column headers, datatypes, and non-null guarantees across all authoritative data sources powering the dashboard.

### 5.1 `data/processed/customer_id_mapping.csv` (3 rows $\times$ 5 cols)
- `house_id` (`object`): Internal household identifier (`H001`, `H002`, `H003`).
- `source_customer_id` (`int64`): Ausgrid customer ID (`1`, `3`, `4`).
- `postcode` (`int64`): Location postcode (`2076`, `2263`, `2220`).
- `generator_capacity_kwp` (`float64`): Rooftop solar PV installed capacity (`3.78`, `1.00`, `1.00`).
- `selection_criteria` (`object`): Data completeness validation tag (`365 complete actual days for GC, CL, and GG`).

### 5.2 `data/processed/energy_price_scenarios.csv` (3 rows $\times$ 7 cols)
- `scenario_id` (`object`): Scenario key (`HYPOTHETICAL_LOW`, `HYPOTHETICAL_BASE`, `HYPOTHETICAL_HIGH`).
- `scenario_label` (`object`): Display name (`Illustrative base flat tariff`).
- `import_price_aud_per_kwh` (`float64`): Grid import tariff ($0.18, $0.30, $0.45).
- `solar_export_credit_aud_per_kwh` (`float64`): Grid feed-in tariff ($0.03, $0.08, $0.12).
- `price_source` (`object`): Source attribution string.
- `is_observed_tariff` (`bool`): Flag denoting benchmark vs. empirical (`False`).
- `notes` (`object`): Explanatory caveats.

### 5.3 `data/processed/test_predictions.csv` (5,256 rows $\times$ 6 cols)
- `house_id` (`object`): Household ID (`H001`, `H002`, `H003`).
- `forecast_timestamp` (`object`): ISO timestamp (`2013-04-19 00:00:00` to `2013-06-30 23:00:00`).
- `actual_demand_kwh` (`float64`): Ground truth total demand load (kWh).
- `predicted_demand_kwh` (`float64`): LSTM next-hour point demand prediction (kWh).
- `actual_solar_generation_kwh` (`float64`): Ground truth solar PV generation (kWh).
- `predicted_solar_generation_kwh` (`float64`): LSTM next-hour point solar prediction (kWh).

### 5.4 `data/processed/test_interval_evaluations_row_level.csv` (5,256 rows $\times$ 21 cols)
- `house_id` (`object`), `forecast_timestamp` (`object`), `month` (`int64`).
- `actual_demand_kwh` (`float64`), `predicted_demand_kwh` (`float64`), `demand_error_kwh` (`float64`).
- `demand_pi_lower_kwh` (`float64`), `demand_pi_upper_kwh` (`float64`), `demand_interval_width_kwh` (`float64`).
- `demand_covered` (`bool`), `demand_below_lower` (`bool`), `demand_above_upper` (`bool`).
- `actual_solar_kwh` (`float64`), `predicted_solar_kwh` (`float64`), `solar_error_kwh` (`float64`).
- `solar_pi_lower_kwh` (`float64`), `solar_pi_upper_kwh` (`float64`), `solar_interval_width_kwh` (`float64`).
- `solar_covered` (`bool`), `solar_below_lower` (`bool`), `solar_above_upper` (`bool`).

### 5.5 `reports/phase7_benchmark_metrics.csv` (32 rows $\times$ 30 cols)
- `controller` (`object`): Controller algorithm (`Oracle_Greedy`, `Forecast_Greedy`, `Deterministic_MPC`, `Stochastic_MPC`).
- `enable_p2p` (`bool`): Peer-to-peer trading toggle (`True`, `False`).
- `mode` (`object`): Text label (`P2P`, `Standalone`).
- `household` (`object`): Entity scope (`H001`, `H002`, `H003`, `COMMUNITY`).
- `hours` (`int64`): Evaluated period duration (`1752`).
- `total_demand_kwh` (`float64`), `total_solar_kwh` (`float64`).
- `battery_charged_kwh` (`float64`), `battery_discharged_kwh` (`float64`).
- `battery_initial_soc` (`float64`), `battery_final_soc` (`float64`), `battery_delta_stored_kwh` (`float64`).
- `p2p_bought_kwh` (`float64`), `p2p_sold_kwh` (`float64`).
- `grid_imported_kwh` (`float64`), `grid_exported_kwh` (`float64`).
- `grid_import_cost_aud` (`float64`), `grid_export_credit_aud` (`float64`).
- `p2p_payment_aud` (`float64`), `p2p_revenue_aud` (`float64`).
- `realized_net_cost_aud` (`float64`), `terminal_adjustment_aud` (`float64`), `adjusted_net_cost_aud` (`float64`).
- `soc_boundary_violations` (`int64`), `simultaneous_charge_discharge_violations` (`int64`).
- `max_energy_balance_residual_kwh` (`float64`), `solver_failures` (`int64`), `avg_solve_time_ms` (`float64`).
- `tradeable_hours` (`int64`), `no_trade_hours` (`int64`).

### 5.6 `reports/phase7_hourly_records.csv` (42,048 rows $\times$ 29 cols)
- `house_id` (`object`), `step_index` (`int64`), `timestamp` (`object`).
- `actual_demand_kwh` (`float64`), `actual_solar_kwh` (`float64`), `forecast_demand_kwh` (`float64`), `forecast_solar_kwh` (`float64`).
- `battery_initial_soc` (`float64`), `battery_final_soc` (`float64`), `battery_initial_kwh` (`float64`), `battery_final_kwh` (`float64`).
- `charged_kwh` (`float64`), `discharged_kwh` (`float64`).
- `post_battery_surplus_kwh` (`float64`), `post_battery_deficit_kwh` (`float64`).
- `p2p_sold_kwh` (`float64`), `p2p_bought_kwh` (`float64`).
- `grid_imported_kwh` (`float64`), `grid_exported_kwh` (`float64`).
- `grid_import_cost_aud` (`float64`), `grid_export_credit_aud` (`float64`).
- `p2p_payment_aud` (`float64`), `p2p_revenue_aud` (`float64`), `net_cost_aud` (`float64`).
- `energy_balance_residual_kwh` (`float64`), `solver_success` (`bool`), `solver_time_sec` (`float64`).
- `controller` (`object`), `enable_p2p` (`bool`).

### 5.7 `reports/phase8c_hourly_equilibria.csv` (1,752 rows $\times$ 33 cols)
- `timestamp` (`object`), `H001_surplus_kwh` (`float64`), `H002_surplus_kwh` (`float64`), `H003_surplus_kwh` (`float64`).
- `H001_deficit_kwh` (`float64`), `H002_deficit_kwh` (`float64`), `H003_deficit_kwh` (`float64`).
- `H001_role` (`object`), `H002_role` (`object`), `H003_role` (`object`).
- `num_active_players` (`int64`), `num_active_sellers` (`int64`), `num_active_buyers` (`int64`), `num_inactive_households` (`int64`).
- `num_profiles_evaluated` (`int64`), `num_deviations_evaluated` (`int64`).
- `num_pne` (`int64`), `num_strict_pne` (`int64`), `num_weak_pne` (`int64`), `num_pareto_undominated_pne` (`int64`), `no_pne_status` (`bool`).
- `selected_price_profile` (`object`), `H001_selected_price_aud` (`float64`), `H002_selected_price_aud` (`float64`), `H003_selected_price_aud` (`float64`).
- `selected_payoff_vector` (`object`), `H001_payoff_aud` (`float64`), `H002_payoff_aud` (`float64`), `H003_payoff_aud` (`float64`).
- `selected_traded_volume_kwh` (`float64`), `selected_weighted_average_price_aud` (`float64`), `selected_community_welfare_aud` (`float64`), `selected_num_transactions` (`int64`).

### 5.8 `reports/phase8d_hourly_selection.csv` (1,752 rows $\times$ 66 cols)
- Metadata: `timestamp` (`object`), `num_active_players` (`int64`), `num_active_sellers` (`int64`), `num_active_buyers` (`int64`), `is_mixed_market` (`bool`), `num_pareto_undominated` (`int64`).
- Policy-specific columns replicated across 6 strategies (`strat_a`, `strat_b`, `strat_c`, `strat_d`, `strat_e`, `strat_f_05`):
  - `strat_{x}_price_profile` (`object`)
  - `strat_{x}_vwap_aud` (`float64`, null in non-tradeable hours)
  - `strat_{x}_volume_kwh` (`float64`)
  - `strat_{x}_welfare_aud` (`float64`)
  - `strat_{x}_H001_payoff` (`float64`), `strat_{x}_H002_payoff` (`float64`), `strat_{x}_H003_payoff` (`float64`)
  - `strat_{x}_standard_gini` (`float64`, null in non-tradeable hours)
  - `strat_{x}_normalized_gini` (`float64`, null in non-tradeable hours)
  - `strat_{x}_min_benefit` (`float64`, null in non-tradeable hours)

### 5.9 `reports/phase8d_strategy_comparison.csv` (13 rows $\times$ 24 cols)
- `strategy_id` (`object`), `strategy_name` (`object`), `strategy_type` (`object`: `core` or `sensitivity`).
- `total_p2p_volume_kwh` (`float64` $\equiv 121.611449$).
- `total_community_welfare_aud` (`float64` $\equiv 26.754519$).
- `volume_weighted_price_aud_per_kwh` (`float64`: $0.1713$ to $0.2715$).
- `total_seller_benefit_aud` (`float64`), `total_buyer_benefit_aud` (`float64`).
- `H001_benefit_aud` (`float64`), `H002_benefit_aud` (`float64`), `H003_benefit_aud` (`float64`).
- `H001_benefit_share_pct` (`float64`), `H002_benefit_share_pct` (`float64`), `H003_benefit_share_pct` (`float64`).
- `mean_standard_gini_mixed` (`float64`), `mean_normalized_gini_mixed` (`float64`).
- `mean_min_active_benefit_aud` (`float64`), `mean_max_active_benefit_aud` (`float64`), `mean_benefit_range_aud` (`float64`).
- `concordance_with_strategy_a_pct` (`float64`), `hours_identical_to_strategy_a` (`int64`).
- `max_hourly_accounting_residual_aud` (`float64` $\le 4.2 \times 10^{-17}$), `aggregate_welfare_residual_aud` (`float64` $\le 4.3 \times 10^{-14}$), `runtime_ms` (`float64`).

---

## 6. Safe Python Serving Interface

To ensure safety, performance, and clean separation between computational models and UI presentation:

### 6.1 Data Serving Principles
1. **Read-Only Data Service Module:** Create a dedicated data adapter `dashboard/data_service.py` that loads and indexes the CSV and Gzip JSON archives into memory during web server startup.
2. **Sub-Millisecond Query Response:** Benchmark tests prove that all 16 CSV files (103,453 total rows) load into memory in **0.28 seconds**, and the complete 1,752-hour Gzip JSON equilibrium archive loads in **1.76 seconds**. The entire repository state occupies < 85 MB RAM. Subsequent user filtering and slicing take < 1 ms.
3. **No Execution of Solvers or Retraining:** The web server performs **zero calls** to `solve_milp()`, `predict_lstm_numpy()`, or `solve_deterministic_nash_equilibrium()`. All displayed values are read directly from authoritative outputs.

### 6.2 Proposed REST API Endpoints (`dashboard/app.py`)

| Endpoint | Method | Parameters | Response Description |
| :--- | :---: | :--- | :--- |
| `/api/system_status` | `GET` | None | System readiness, regression test pass count (250/250), test period timestamps, active households metadata. |
| `/api/customer_profiles` | `GET` | None | Household IDs, solar PV capacities, postcodes, tariff assumptions. |
| `/api/forecast_data` | `GET` | `house_id`, `start_date`, `end_date` | Actuals, LSTM predictions, 90% prediction intervals, and empirical coverage flags. |
| `/api/forecast_scorecard`| `GET` | None | Overall and per-household MAE, RMSE, and bias for LSTM vs. Persistence baseline (honestly reporting persistence demand MAE lead). |
| `/api/battery_dispatch` | `GET` | `controller`, `house_id`, `start_date`, `end_date` | Hourly battery SOC, charge/discharge powers, grid flows, net costs, and conservation residuals. |
| `/api/p2p_benchmarks` | `GET` | None | Standalone vs. P2P summary metrics across 4 controllers (grid imports, battery utilization, cost savings). |
| `/api/liquidity_metrics`| `GET` | `controller` | Coincidence of surplus/deficit, tradeable hours, unmatched seller/buyer energy. |
| `/api/nash_hour` | `GET` | `timestamp` or `hour_index` | Complete details for a single hour: active player roles, quantities, all PNE profiles, Pareto subset, Strategy A selection. |
| `/api/fairness_summary` | `GET` | None | Complete 13-row macroeconomic strategy comparison table (volume, welfare, VWAP, benefits, Gini). |
| `/api/fairness_hourly` | `GET` | `start_date`, `end_date` | Hourly VWAP, Gini coefficients, and household payoffs across Strategies A through F. |
| `/api/precomputed_ledger`| `GET` | None | Precomputed audit ledger: energy conservation max residual ($< 5\times 10^{-7}$ kWh), financial residual ($0.000$), payoff identity verification ($< 5\times 10^{-17}$ AUD). |

---

## 7. Recommended Frontend and Backend Architecture

### 7.1 Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              SYSTEM ARCHITECTURE TOPOLOGY                              │
│                                                                                        │
│  [ FRONTEND (Client Browser) ]                                                         │
│  ├── Framework: Single-Page Dashboard Architecture (Modular Vanilla JS ES6+)          │
│  ├── Styling: Professional Academic Theme (TailwindCSS via CDN + Custom Typography)   │
│  ├── Interactive Visualizations: Plotly.js (Zoom, Pan, Tooltips, Synchronized Crosshairs)│
│  └── Mathematical Notation: KaTeX (LaTeX equation rendering for game theory formulas)  │
│                                        │                                               │
│                                   HTTP / JSON                                          │
│                                        ▼                                               │
│  [ BACKEND (Python Web Server) ]                                                       │
│  ├── Framework: Flask 3.1.0 (Native Python 3.13 environment)                           │
│  ├── Architecture: Blueprint-based REST API + Jinja2 Base Shell                        │
│  ├── Memory Cache: In-Memory Pandas DataFrames & Indexed JSON Dict (Zero disk I/O lag) │
│  └── Source of Truth: Read-Only Access to `data/processed/` and `reports/`             │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Why Flask + Modern Modular Frontend is Optimal:
1. **Natively Installed:** Flask 3.1.0, Jinja2 3.1.5, and Werkzeug 3.1.3 are already installed in the user's active Python 3.13.6 environment. No extra package installations or permissions are required.
2. **Zero Build Step:** By using ES6 modules with standard HTML5 and Plotly.js, the project requires **no Node.js build process, no Webpack/Vite compilation, and no `node_modules` clutter**. It runs directly from Python.
3. **Academic Aesthetics:** Allows building a customized, elegant research dashboard matching top academic conference tools (IEEE PES, ACM e-Energy) with sidebar navigation, metric callout badges, mathematical notation, and interactive data tables.
4. **Performance:** Unlike Streamlit (which re-executes Python scripts from scratch on every slider change), Flask + client-side Plotly.js delivers 60 FPS client-side interactivity, instant tab switching, and seamless filtering without network bottlenecks.

---

## 8. Dashboard Structure & Interactive Visualization Plan

The proposed dashboard is organized into **7 structured academic views**, accessible via a clean persistent sidebar:

```
┌─────────────────┬────────────────────────────────────────────────────────────────────────────┐
│ ANTIGRAVITY     │ PAGE HEADER & GLOBAL TIMELINE SCRUBBER                                     │
│ Energy Lab      │ Active Period: 2013-04-19 to 2013-06-30 (1,752 Test Hours) | 3 Households  │
├─────────────────┼────────────────────────────────────────────────────────────────────────────┤
│ 1. Overview     │                                                                            │
│ 2. Forecasting  │                           MAIN INTERACTIVE VIEW                            │
│ 3. Battery & PV │                                                                            │
│ 4. P2P Market   │  [ KPI Metric Cards ]                                                      │
│ 5. Nash Multi.  │  [ Interactive Plotly Scientific Charts ]                                  │
│ 6. Fairness A-F │  [ Tabular Drilldown / Parameter Filters ]                                 │
│ 7. Audit Ledger │                                                                            │
└─────────────────┴────────────────────────────────────────────────────────────────────────────┘
```

### 8.1 Page 1: Executive Overview & System Architecture
- **Purpose:** Provide the evaluating professor with an immediate executive summary of the research questions, methodologies, and macroeconomic conclusions.
- **Top Metric Cards:**
  - *Evaluation Period:* 1,752 Hours (73 Days, April–June 2013).
  - *Community Participants:* 3 Prosumers (H001: 3.78 kWp PV, H002: 1.0 kWp, H003: 1.0 kWp).
  - *Physical Volume Traded:* 121.61 kWh.
  - *Community Social Welfare Created:* $26.75 AUD (+3.43% cost reduction over standalone).
  - *Regression Test Verification:* 250 / 250 Tests Passing (100%).
- **Interactive Visualizations:**
  - *Pipeline Flow Diagram:* Visual interactive workflow showing data progression from Raw Ausgrid data $\rightarrow$ LSTM $\rightarrow$ Monte Carlo $\rightarrow$ Stochastic MPC $\rightarrow$ Double Auction $\rightarrow$ Nash Solver $\rightarrow$ Fairness Selection.
  - *Household Profiles Card:* Technical specifications table with generator capacities, battery parameters ($5.0\text{ kWh}, 2.5\text{ kW}, \eta=0.95$), and retail tariff benchmarks.
  - *Executive Summary Accordion:* Mathematical design notes and audit conclusions.

### 8.2 Page 2: Forecasting & Uncertainty Quantification (Phases 2 & 3)
- **Purpose:** Demonstrate machine learning point accuracy and empirical uncertainty calibration.
- **Interactive Controls:**
  - Household selector (`H001`, `H002`, `H003`, `ALL`).
  - Target variable toggle (`Total Demand`, `Solar Generation`).
  - Date range zoom scrubber (hourly slider, 24h, 7-day, or full 73-day view).
- **Interactive Visualizations:**
  - *Fan Chart (Actual vs. Predicted with 90% Prediction Intervals):* Ground truth actual line, LSTM point prediction line, and shaded semi-transparent ribbon representing the 90% Monte Carlo interval $[q_{0.05}, q_{0.95}]$.
  - *Out-of-Interval Highlight:* Visual scatter markers indicating points where actual realization breached the prediction interval.
  - *Forecast Scorecard Table:* Side-by-side comparison of LSTM vs. Persistence baseline (MAE, RMSE, Mean Bias), honestly documenting that Persistence achieves lower demand MAE (0.4310 vs. 0.4660 kWh), while LSTM achieves lower demand RMSE (0.7834 vs. 0.8557 kWh) and superior solar prediction across all metrics (MAE 0.0814 vs. 0.0864 kWh).
  - *Calibration Gauge & Width Metrics:* Nominal 90% vs. Empirical coverage gauge (Demand: 81.91%, Solar: 89.42%) and interval width distributions.

### 8.3 Page 3: Battery Operation & Microgrid Energy Balance (Phases 6A & 6B.2)
- **Purpose:** Validate physical feasibility, operational constraints, and battery dispatch under deterministic and stochastic controllers.
- **Interactive Controls:**
  - Controller selector (`Oracle Greedy`, `Forecast Greedy`, `Deterministic MPC`, `Stochastic MPC`).
  - Household selector (`H001`, `H002`, `H003`).
- **Interactive Visualizations:**
  - *Battery State-of-Charge (SOC) Dynamics:* Time-series chart showing battery SOC bounded strictly within $[0.10, 0.90]$ ($0.5\text{ kWh} \le E_t \le 4.5\text{ kWh}$).
  - *Charge / Discharge Power Flow:* Bar chart showing battery charging $C_t \ge 0$ (positive) and discharging $D_t \ge 0$ (negative), demonstrating strictly enforced mutual exclusion ($C_t \cdot D_t = 0$).
  - *Microgrid Energy Balance Breakdown:* Stacked area chart showing local demand met by self-consumption, battery discharge, P2P import, and grid import.
  - *Physical Conservation Residual Telemetry:* Scatter plot showing balance residual across all hours, verifying compliance with the zero-leakage threshold ($< 10^{-6}\text{ kWh}$).

### 8.4 Page 4: P2P Market Clearing & Community Liquidity (Phase 7.1)
- **Purpose:** Illustrate peer-to-peer double-auction matching and compare standalone operation against microgrid integration.
- **Interactive Controls:**
  - Controller selector for macroeconomic comparison.
  - Granularity switch (Hourly, Daily aggregate, Test-period cumulative).
- **Interactive Visualizations:**
  - *Standalone vs. P2P Benchmark Comparison:* Grouped bar charts showing community grid imports (reduced from 333.8 kWh to 212.2 kWh under Stochastic MPC) and financial net costs (reduced from $780.09 to $753.34 AUD).
  - *Community Liquidity & Market State Matrix:* Donut chart and hourly heatmap showing distribution of hours: 866 tradeable hours (simultaneous surplus and deficit), 59 sellers-only hours, and 827 buyers-only hours.
  - *Household Role Trajectories:* Timeline heatmap showing each household's hourly market state (`Seller`, `Buyer`, or `Inactive`), illustrating role dynamism (H001 selling in 366 hrs, H002 selling in 509 hrs, H003 buying in 301 hrs).

### 8.5 Page 5: Game Theory & Pure Nash Equilibrium Multiplicity (Phase 8C)
- **Purpose:** Provide an in-depth academic tool to inspect game formulation, strategy spaces, equilibrium multiplicity, and the Pareto dominance frontier.
- **Interactive Controls:**
  - Timestamp picker / dropdown of all 866 tradeable hours.
  - Quick-filter for hours with 10, 11, 12, 13, or 14 pure Nash equilibria.
- **Interactive Visualizations:**
  - *Single-Hour Double Auction Clearing Diagram:* Bid/ask merit-order curves (sellers sorted lowest ask first, buyers sorted highest bid first) with crossing point and midpoint cleared price.
  - *Pure Nash Equilibrium Multiplicity Table:* Full list of all pure Nash equilibria discovered in the selected hour from `reports/phase8c_all_equilibria.json.gz`, displaying player price vectors $(p_1^*, p_2^*, p_3^*)$, individual payoffs $(U_1, U_2, U_3)$, traded volume $Q$, and welfare $\Delta W$.
  - *Pareto Dominance Frontier Classification:* Visual badge highlighting profiles that are Pareto-undominated ($E_{\text{Pareto}}$) versus submaximal coordination traps (zero-trade uncrossed bids or partial-trade traps).
  - *Pareto Invariance Demonstration Card:* Proof callout showing that across all Pareto equilibria in the chosen hour, physical volume cleared $Q^*(t)$ and community welfare $\Delta W^*(t) = 0.22 \times Q^*(t)$ are identical down to machine precision.

### 8.6 Page 6: Fairness-Aware Equilibrium Selection (Phase 8D)
- **Purpose:** Explore the core research findings of Phase 8D—how social choice criteria distribute community surplus among prosumers without compromising macroeconomic welfare.
- **Interactive Controls:**
  - Strategy selector: All 6 core policies (Strategy A: Reference, Strategy B: Seller-Favouring, Strategy C: Buyer-Favouring, Strategy D: Max-Min Fair, Strategy E: Nash Social Welfare, Strategy F: Hybrid).
  - Hybrid weight slider ($w_{\text{fair}} \in [0.0, 1.0]$) to inspect the 7 sensitivity sweep configurations.
- **Interactive Visualizations:**
  - *Comprehensive Macroeconomic Comparison Table:* Full 13-row interactive data table with sorting, search, and conditional formatting directly from `reports/phase8d_strategy_comparison.csv`.
  - *Surplus Distribution Comparison (Stacked & Grouped Bars):* Dollar benefits captured by H001, H002, and H003 under each policy, highlighting extreme contrast between Strategy B (H001 captures 45.4% / $12.16 AUD) and Strategy C (H003 captures 40.0% / $10.69 AUD).
  - *Inequality Metric Comparison (Gini Coefficients):* Side-by-side bar chart of Standard Gini vs. Normalized Gini across policies, demonstrating that Strategy E (Nash Social Welfare) achieves lowest inequality among core strategies (Gini = 0.8073).
  - *Volume-Weighted Average Price (VWAP) Radar / Bar Chart:* Visualizing market clearing prices across policies ($0.1713 AUD/kWh for Strategy C to $0.2715 AUD/kWh for Strategy B).
  - *Hybrid Step-Response Scatter Plot:* Plot of concordance with Strategy A against $w_{\text{fair}}$, showing 100% concordance for $w \le 0.5$ and discrete step-transitions for $w > 0.5$.

### 8.7 Page 7: Precomputed Verification Ledger & Architecture Audit
- **Purpose:** Give the evaluating professor full transparency into mathematical verification, double-entry financial accounting, and regression test coverage without executing offline solvers.
- **Precomputed Verification Ledger:**
  - *Regression Test Verification:* Complete scorecard of 250/250 passing unit tests categorized by subsystem.
  - *Precomputed Numerical Conservation Ledger:* Authoritative audit summary table:
    - Pre-trade energy conservation residual: $\max |(D-G) - (d-s)| < 5 \times 10^{-16}\text{ kWh}$.
    - Monte Carlo scenario conservation residual: $\max |\cdot| < 4.8 \times 10^{-7}\text{ kWh}$.
    - Bilateral P2P payment-revenue equality: $\sum \text{Payments} - \sum \text{Revenues} \equiv 0.000\text{ AUD}$ across all 1,272 transactions.
    - Household payoff identity: $\max |U_i - \text{formula}| < 5 \times 10^{-17}\text{ AUD}$.
    - Community welfare identity: $|\sum U_i - 0.22 \times Q| < 5 \times 10^{-14}\text{ AUD}$.
- **Web Application Runtime Status:**
  - Explicitly separated indicator showing live web server status, dataset cache state (records in memory, RAM usage), and sub-millisecond REST query response times.
- **Audit Document Viewer:**
  - Quick-access markdown viewer for `reports/final_computational_audit.md`, `reports/phase8d_fairness_analysis.md`, and `reports/financial_payoff_nash_verification.md`.

---

## 9. Local Execution and Demonstration Protocol

The web prototype is designed for immediate, robust local execution on Windows, Linux, or macOS.

### 9.1 Launching the Prototype Locally

To run the web prototype:

```powershell
# From the repository root:
python dashboard/app.py
```

The Flask server will start locally and serve on:
```
http://127.0.0.1:5000/
```

### 9.2 Execution Technical Parameters
- **Host Binding:** `127.0.0.1` (or `0.0.0.0` if specified).
- **Default Port:** `5000` (configurable via environment variable `PORT=5000` or CLI argument `--port 5000`).
- **Startup Latency:** ~1.8 seconds (one-time preload of all CSVs and Gzip JSON archives into RAM).
- **Memory Footprint:** ~85 MB resident memory.
- **Dependencies Required:** `Flask>=3.0.0`, `pandas>=2.0.0`, `numpy>=1.24.0` (all verified present).

### 9.3 Recommended Live Demonstration Script (5-Minute Professor Walkthrough)

| Step | Time | Dashboard Page | Key Action & Academic Talking Points |
| :---: | :---: | :--- | :--- |
| **1** | 0:00–0:45 | **Overview** | Show system KPIs, describe 3-prosumer setup (H001 high solar, H002 flexible prosumer, H003 net consumer), highlight 250/250 tests passing. |
| **2** | 0:45–1:45 | **Forecasting** | Toggle between Solar and Demand. Show how LSTM achieves lower RMSE and superior solar prediction (MAE 0.081 vs 0.086 kWh). Display 90% Monte Carlo prediction intervals and empirical calibration (89.4% solar coverage). Honestly discuss persistence lead on demand MAE. |
| **3** | 1:45–2:45 | **Battery & Energy** | Demonstrate battery SOC constrained strictly to $[0.10, 0.90]$. Point out mutual exclusion of charging and discharging. Show physical energy balance residual ($< 10^{-6}$ kWh). |
| **4** | 2:45–3:45 | **P2P & Nash Multiplicity** | Show P2P market liquidity (866 tradeable hours, 121.61 kWh traded). Pick a tradeable hour on Page 5; reveal the 10–14 Pure Nash Equilibria; show why submaximal profiles are Pareto-dominated; demonstrate empirical invariance of welfare on the Pareto frontier ($Q^* = \min(S, D)$, $\Delta W = 0.22 \times Q$). |
| **5** | 3:45–4:30 | **Fairness A–F** | Compare Strategy B (Seller-Favouring, $0.2715 VWAP) vs. Strategy C (Buyer-Favouring, $0.1713 VWAP) vs. Strategy D (Max-Min) and E (Nash Social Welfare). Explain that welfare is constant ($26.75 AUD), but distribution changes radically. |
| **6** | 4:30–5:00 | **Verification Ledger** | Review the precomputed verification ledger: zero physical leakage, bilateral payment equality ($0.000 AUD), machine-precision payoff identities ($< 10^{-16}$ AUD). |

---

## 10. Phased Implementation Roadmap & Verification Checklist

The implementation is structured across five sequential steps:

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                        DELIVERABLE 2 IMPLEMENTATION STEPS                         │
│                                                                                   │
│  [Step 1: Data Service] ──▶ [Step 2: Flask API] ──▶ [Step 3: UI Shell & Pages]    │
│  dashboard/data_service.py   dashboard/app.py        dashboard/templates/         │
│  (In-memory caching)         (11 REST endpoints)     (Modular academic layout)    │
│                                                              │                    │
│                                                              ▼                    │
│  [Step 5: Final Validation] ◀── [Step 4: Interactive Charts & Visualizations]     │
│  End-to-end audit, local run     dashboard/static/js/ (Plotly.js scientific plots)│
└───────────────────────────────────────────────────────────────────────────────────┘
```

### Step 1: In-Memory Data Service Layer (`dashboard/data_service.py`)
- Implement a thread-safe, singleton data loader class that ingests all frozen CSV and Gzip JSON datasets into memory.
- Provide clean querying, filtering, and aggregation utility methods with zero solver recomputation.
- Ensure type-safe JSON conversion for all NumPy/Pandas datatypes (`np.float64` $\rightarrow$ `float`, `NaN` $\rightarrow$ `None`).
- Author comprehensive unit tests for `dashboard/data_service.py` to verify data completeness, filtering correctness, and sub-millisecond query performance.

### Step 2: RESTful Flask API Backend (`dashboard/app.py`)
- Implement the 11 REST API endpoints specified in Section 6.2.
- Add error handling, CORS headers, and route testing.
- Include a health check route (`/api/health`) and precomputed verification ledger endpoint.

### Step 3: Base Academic Template & Responsive Layout
- Implement `dashboard/templates/index.html` with clean academic sidebar navigation, header status badge, and theme styling.
- Structure the 7 modular view panels (Overview, Forecasting, Battery, P2P Market, Nash Multiplicity, Fairness, Precomputed Ledger).
- Integrate Plotly.js and KaTeX math rendering libraries.

### Step 4: Interactive Frontend Modules (`dashboard/static/js/`)
- Implement modular ES6 JavaScript controllers:
  - `overview.js`: KPI cards, architecture flow.
  - `forecasting.js`: Fan charts, LSTM vs. baseline scorecard, coverage gauges.
  - `battery.js`: SOC trajectories, power flows, energy balance stacked area plots.
  - `p2p_market.js`: Standalone vs. P2P bar charts, liquidity heatmaps, role distributions.
  - `nash.js`: Hourly equilibrium explorer, double auction crossing curves, Pareto filter.
  - `fairness.js`: Strategy comparison table, surplus distribution charts, Gini comparison, hybrid sweep slider.
  - `audit.js`: Precomputed verification ledger, residual metrics, invariant validation proofs.

### Step 5: End-to-End Verification & Demonstration Readiness
- Verify that `python dashboard/app.py` boots in < 2 seconds and responds to all API calls.
- Verify that all existing regression tests (`pytest -v`) continue to pass 250/250 without any side effects.
- Verify in browser that all charts render cleanly, responsiveness is fluid, tooltips work, and zero console errors occur.
- Produce final walkthrough documentation and screenshot captures for user review.
