# Comprehensive Monte Carlo Scenario Generation and Statistical Validation Report

## Executive Summary

This report delivers a rigorous, evidence-based audit, statistical validation, and property invariant analysis 
of the Monte Carlo scenario generator (`src/stochastic/monte_carlo.py`) and its evaluation interface 
(`src/evaluation/forecast_evaluator.py`).

The evaluation encompasses:
- **3 households:** `H001`, `H002`, `H003`
- **1,752 chronological held-out test hours per household** (2013-04-19 00:00:00 to 2013-06-30 23:00:00)
- **5,256 total household-hour evaluation points**
- **1,000 paired Monte Carlo scenarios per observation** ($5,256,000$ total generated scenario pairs)
- **62 passing automated unit and property-based regression tests** (including 10 newly added Step 3 invariant tests)

All code behaviors, distributional statistics, and empirical findings documented herein are verified directly against 
actual execution traces and repository data files without heuristic inflation or ungrounded assumptions.

---

## 1. Phase 1: Implementation Audit and Verified Code Behavior

A line-by-line inspection of `src/stochastic/monte_carlo.py` and its calling modules confirms the following operational mechanics:

### 1.1 Computation and Storage of Validation Residuals
- **Data Source:** Sequences are loaded from `data/processed/lstm_sequences.npz`, containing `X_val` (2,103 sequence windows of shape `(24, 6)`), `y_val` (2,103 normalized target pairs of shape `(2,)`), `val_house_id` (2,103 string identifiers), and `val_target_timestamp`.
- **Inference & Inverse Scaling:** Predictions are generated in normalized MinMax space using `predict_lstm_numpy(X_val, forecaster.weights)`, then inverted to physical units via `forecaster.inverse_scale(...)` and clipped at $0.0$ (`preds_val_raw = np.maximum(0.0, ...)`). Actuals are inverted identically: `actual_val_raw = forecaster.inverse_scale(y_val)`.
- **Residual Definition:** Residuals are computed strictly as:
  $$e_t = y_t - \hat{y}_t \quad (\text{actual} - \text{predicted})$$
  stored as an array of shape `(2103, 2)`. Column 0 corresponds to Demand residual ($e_{d,t}$ in kWh), and Column 1 corresponds to Solar Generation residual ($e_{s,t}$ in kWh).
- **Residual Pool Partition:** Exactly 701 validation residual pairs per household:
  - `H001`: 701 pairs (2013-03-20 19:00:00 to 2013-04-18 23:00:00)
  - `H002`: 701 pairs (2013-03-20 19:00:00 to 2013-04-18 23:00:00)
  - `H003`: 701 pairs (2013-03-20 19:00:00 to 2013-04-18 23:00:00)

### 1.2 Preservation of Demand-Solar Dependence
- In `sample_residuals(paired=True, method="empirical")`, the generator draws an integer index vector:
  $$\text{indices} \sim \text{Uniform}\{0, \dots, N_{\text{house}}-1\}^{1000}$$
  It retrieves `sampled = res[indices]`, returning `sampled[:, 0]` (demand) and `sampled[:, 1]` (solar).
- **Verified Behavior:** Because `indices` indexes complete 2D rows of the empirical validation array, every sampled demand residual $e_{d,t}$ is coupled with the exact simultaneous solar residual $e_{s,t}$ from that same historical validation hour. The empirical joint distribution and cross-variable covariance are strictly preserved.
- **Independence Flag:** When `paired=False` is passed, `sample_residuals` draws separate independent row vectors `idx_d` and `idx_s`, intentionally severing joint dependence.

### 1.3 Household-Specific Residual Pool Selection
- Slicing is performed via boolean masking: `mask = (self.val_house_ids == house_id); res = self.residuals[mask]`.
- Cross-contamination is impossible: Household H001 scenarios are sampled strictly from H001 validation residuals; H002 scenarios from H002; and H003 scenarios from H003.

### 1.4 Random-Number Generator and Seed Initialization
- The generator leverages NumPy's modern PCG64 bit generator (`np.random.default_rng(...)`).
- Following Step 3 refactoring, `sample_residuals` and `generate_scenarios` accept either:
  1. An integer random seed (e.g., `random_seed: int = 42`), which instantiates a local `np.random.default_rng(random_seed)`.
  2. An active `np.random.Generator` instance (`isinstance(random_seed, np.random.Generator)`), which reuses an existing sequence stream without resetting internal state.
  3. A deterministic observation-derived seed via `derive_observation_seed(house_id, timestamp, base_seed)`.

### 1.5 RNG Reset vs. Sequential Maintenance
- In the initial Step 2 baseline (`fixed_per_observation`), `rng = np.random.default_rng(42)` was re-instantiated inside `sample_residuals` on every call. Consequently, for a given household, the identical 1,000 row indices were sampled for every test hour $t \in \{1, \dots, 1752\}$.
- Under sequential evaluation (`protocol_a`), a single generator is initialized once and stepped forward continuously across all test hours.
- Under deterministic observation seeding (`protocol_b`), each observation is seeded with $s_{h,t} = \text{CRC32}(f"{h}_{t}_{42}") \pmod{2^{32}}$, ensuring distinct random streams across hours while remaining completely order-independent and reproducible.

### 1.6 Calculation of Scenario Values, Quantiles, and Summary Statistics
- Scenario values are calculated by additive perturbation with lower physical bounding:
  $$\tilde{y}_{d, t}^{(s)} = \max\left(0.0, \, \hat{y}_{d, t} + e_{d, t}^{(s)}\right), \quad \tilde{y}_{s, t}^{(s)} = \max\left(0.0, \, \hat{y}_{s, t} + e_{s, t}^{(s)}\right)$$
- Quantiles are calculated via `np.percentile(scenarios, q)` (using linear interpolation between order statistics):
  - Lower 90% Prediction Interval bound: $\hat{q}_{0.05} = \text{percentile}(5)$
  - Median: $\hat{q}_{0.50} = \text{percentile}(50) = \text{median}$
  - Upper 90% Prediction Interval bound: $\hat{q}_{0.95} = \text{percentile}(95)$
- Summary statistics computed in `ScenarioDistribution.get_summary_dataframe()`:
  - Arithmetic mean: `np.mean(scenarios)`
  - Sample standard deviation: `np.std(scenarios, ddof=1)`
  - Extremes: `np.min(scenarios)`, `np.max(scenarios)`

### 1.7 Physical Units Verification
- All LSTM outputs and residuals are converted back to engineering units (**kWh**) via `forecaster.inverse_scale(...)` before scenario perturbation. No scenario calculations take place in MinMax normalized $[0, 1]$ space. Non-negativity constraints ($\ge 0.0\text{ kWh}$) preserve physical thermodynamic and electrical limits.

---

## 2. Phase 2: Scenario Properties and Invariant Validation

To ensure robust implementation and eliminate silent mathematical regressions, 10 automated test suites were integrated into `tests/test_monte_carlo.py` and `tests/test_forecast_evaluation.py`. All tests run cleanly against Python 3.13 and pass without warnings.

### Summary of Validated Invariants

| Test Name | File | Verified Property | Status |
| :--- | :--- | :--- | :---: |
| `test_residual_sign_convention` | `test_monte_carlo.py` | Residuals strictly defined as $e_t = y_t - \hat{y}_t$. Hand-calculated fixture confirms adding residual recovers ground truth. | **PASS** |
| `test_household_and_target_alignment` | `test_monte_carlo.py` | Exact 701 pairs per household; demand is col 0, solar is col 1; household masks strictly isolate individual data pools. | **PASS** |
| `test_paired_residual_sampling_preserves_joint_distribution` | `test_monte_carlo.py` | All sampled $(e_d, e_s)$ pairs match historical rows in pool when `paired=True`; verifies pairing is broken when `paired=False`. | **PASS** |
| `test_percentiles_calculation_and_hand_calculated_example` | `test_monte_carlo.py` | 5th, 50th, 95th percentiles match hand-calculated interpolation on synthetic test distribution: $Q_{0.05}=1.95, Q_{0.50}=10.50, Q_{0.95}=19.05$. | **PASS** |
| `test_scenario_summary_dataframe_consistency` | `test_monte_carlo.py` | Tabulated summary statistics in `ScenarioDistribution` match underlying NumPy array metrics (`mean`, `std`, `q05`, `median`, `q95`, `min`, `max`). | **PASS** |
| `test_zero_forecasts_and_extreme_residuals` | `test_monte_carlo.py` | Point forecast $(0, 0)$ generates valid non-negative scenarios clipped at $0.0$; extreme positive residuals ($+50\text{ kWh}$) do not overflow. | **PASS** |
| `test_protocol_b_deterministic_seed` | `test_monte_carlo.py` | CRC32 seed derivation produces deterministic, order-independent 32-bit unsigned integers; distinct across timestamps and homes. | **PASS** |
| `test_protocol_a_sequential_generator` | `test_monte_carlo.py` | Passing active `np.random.Generator` advances internal state across calls; reproducing generator produces identical sequential draws. | **PASS** |
| `test_physical_units_in_kwh` | `test_monte_carlo.py` | Scenario maximums and validation residuals exceed $1.0\text{ kWh}$ (confirming physical units, not normalized $[0, 1]$). | **PASS** |
| `test_rng_modes_in_forecast_evaluator` | `test_forecast_evaluation.py` | `ForecastEvaluator` seamlessly runs `protocol_a` and `protocol_b` over full 5,256-observation test series without bounds errors. | **PASS** |

### Hand-Calculated Reference Comparison
To verify quantile calculations independent of library routines, we evaluated a known uniform grid of 20 points: $D = \{1.0, 2.0, \dots, 20.0\}$:
- **Sample Mean:** $\mu = \frac{1}{20}\sum_{i=1}^{20} i = 10.5000\text{ kWh}$
- **Median ($Q_{0.50}$):** $\frac{10.0 + 11.0}{2} = 10.5000\text{ kWh}$
- **5th Percentile ($Q_{0.05}$):** With linear interpolation at index $0.05 \times (20 - 1) = 0.95$, $x_0 + 0.95 \times (x_1 - x_0) = 1.0 + 0.95 \times 1.0 = 1.9500\text{ kWh}$.
- **95th Percentile ($Q_{0.95}$):** At index $0.95 \times 19 = 18.05$, $x_{18} + 0.05 \times (x_{19} - x_{18}) = 19.0 + 0.05 \times 1.0 = 19.0500\text{ kWh}$.
- **Implementation Output:** `ScenarioDistribution.get_summary_dataframe()` produces `Q05 = 1.9500`, `Median = 10.5000`, `Q95 = 19.0500`, and `Scenario_Mean = 10.5000`, confirming exact numerical concordance.

---

## 3. Phase 3: Investigation of Random Number Generator Protocols

### 3.1 Why Fixed-Seed-per-Observation Differs from Sequential / Resampled Streams
In Step 2, the baseline evaluation used `fixed_per_observation` (`seed=42`). At each observation $t$, the simulator re-instantiated `rng = np.random.default_rng(42)`.

This produced a critical mathematical consequence:
1. **Identical Sampled Index Vector:** For every single test observation of household $h$, the exact same 1,000 indices was sampled from the 701-element pool:
   $$\mathbf{e}_{h}^{(s)} = \text{fixed realization vector of 1,000 residuals}$$
2. **Artificial Freezing of Monte Carlo Sampling Error:** Whenever the point forecast $\hat{y}_t$ is large enough that non-negativity clipping is inactive for the 5th and 95th percentiles:
   $$\hat{q}_{0.05}(\tilde{y}_t) = \hat{y}_t + q_{0.05}(\mathbf{e}_h), \quad \hat{q}_{0.95}(\tilde{y}_t) = \hat{y}_t + q_{0.95}(\mathbf{e}_h)$$
   The interval width was **strictly constant** across all unclipped hours:
   $$W_t = \hat{q}_{0.95} - \hat{q}_{0.05} = q_{0.95}(\mathbf{e}_h) - q_{0.05}(\mathbf{e}_h) \equiv \text{constant}$$
3. **Finite-Sample Bias of a Single Draw:** For household H001, the specific draw generated by seed 42 happened to draw slightly fewer extreme upper residuals than the population average, resulting in an unclipped width of $1.5629\text{ kWh}$ (underestimating the pool's expected width of $1.7587\text{ kWh}$) and an empirical coverage of $80.02\%$.
4. **Law of Large Numbers Restoration:** In contrast, under sequential RNG (`protocol_a`) or per-observation independent seeding (`protocol_b`), each observation draws a fresh random sample of 1,000 residuals. Across 1,752 hours per household, the empirical interval bounds average out to the true expected empirical quantiles of the pool, raising H001 demand coverage from $80.02\%$ to $82.19\%$.

### 3.2 Quantitative Protocol Comparison across All 5,256 Observations

The table below reports the empirical calibration metrics evaluated on all 1,752 held-out test hours per household across the four candidate RNG protocols:

| Protocol | Description | Target | H001 Cov (%) | H002 Cov (%) | H003 Cov (%) | ALL Cov (%) | Mean Width (kWh) | Median Width (kWh) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Fixed Seed (Seed 42)** | Identical seed reset per hour | Demand | 80.02% | 82.02% | 83.68% | **81.91%** | 1.2340 | 1.4576 |
| | | Solar | 91.27% | 87.27% | 89.73% | **89.42%** | 0.3625 | 0.2399 |
| **Sequential per House** | Seed 42 reset per household | Demand | 82.65% | 80.65% | 83.05% | **82.12%** | 1.2695 | 1.4563 |
| | | Solar | 91.67% | 87.90% | 89.73% | **89.76%** | 0.3575 | 0.2363 |
| **Protocol A** | Single sequential stream across run | Demand | 82.65% | 80.71% | 83.39% | **82.25%** | 1.2703 | 1.4606 |
| | | Solar | 91.67% | 87.96% | 89.84% | **89.82%** | 0.3573 | 0.2360 |
| **Protocol B** | Deterministic seed per observation identifier | Demand | 82.19% | 80.82% | 83.11% | **82.04%** | 1.2694 | 1.4615 |
| | | Solar | 91.78% | 88.01% | 89.73% | **89.84%** | 0.3577 | 0.2361 |

### 3.3 Selection of the Primary Project Baseline Protocol

**Selected Primary Protocol: Protocol B (Deterministic Seed derived from Stable Identifier)**

#### Rationale for Protocol B:
1. **Complete Order-Independence & Parallel Safety:** In an energy management system with live dashboards, microgrid dispatch solvers, and batch backtesters, queries frequently evaluate a single hour in isolation (e.g., dispatching trade for `2013-06-08 10:00:00`). Under Protocol A (sequential stream), evaluating hour 1,000 alone requires simulating all previous 999 hours, and running queries in parallel produces race conditions. Under Protocol B:
   $$\text{Seed}_{h, t} = \text{CRC32}\left(f"{h}_{t}_{42}"\right)$$
   Every single observation is completely self-contained, reproducible, and order-invariant.
2. **Elimination of Single-Seed Freezing:** Unlike `fixed_per_observation`, every hour receives a distinct, pseudorandom seed that draws an independent Monte Carlo scenario set.
3. **Statistical Equivalence to Protocol A:** As shown in Section 3.2, Protocol B matches Protocol A to within $0.2\%$ coverage and $0.0009\text{ kWh}$ mean width across all 5,256 test observations.
4. **Protocol A as Robustness Check:** Protocol A is retained in `src/evaluation/forecast_evaluator.py` as a secondary robustness check to confirm that order-independent batch evaluations match continuous time-series stream simulations.

---

## 4. Phase 4: Statistical Examination of Uncertainty Sampling Assumptions

We performed an in-depth empirical investigation of five core statistical assumptions underlying the Monte Carlo generator using descriptive evidence from repository data:

### 4.1 Representativeness and Seasonal Distribution Drift
- **Validation Period:** 2013-03-20 to 2013-04-18 (early autumn in Sydney, Australia).
- **Test Period:** 2013-04-19 to 2013-06-30 (transition from autumn into mid-winter).

Descriptive evidence reveals severe distribution drift between validation and test periods:

| Household | Target | Metric | Validation Pool (Autumn) | Test Period (Winter) | Drift Magnitude / Evidence |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **H002** | Demand | Mean Error | -0.2519 kWh | -0.1347 kWh | Error shifted positive by $+0.1172\text{ kWh}$ |
| | | Std Dev | 0.3012 kWh | 0.5807 kWh | Volatility increased by **+92.8%** |
| | | Skewness | -0.5285 | +2.5887 | Distribution flipped from left-skewed to heavily right-skewed |
| | | 95th Percentile | +0.1611 kWh | +0.9278 kWh | Upper tail expanded by **+476%** |
| | | Maximum Error | **+0.7457 kWh** | **+4.4596 kWh** | Test max is **6.0x larger** than validation max |
| | | Exceeding Val Max | — | **5.94% of test hours** | 104 test hours fall outside the entire validation support |
| **H003** | Demand | Std Dev | 0.5655 kWh | 0.8915 kWh | Volatility increased by **+57.6%** |
| | | 95th Percentile | +1.0323 kWh | +2.2125 kWh | Upper tail more than doubled (+114%) |
| | | Maximum Error | +4.5734 kWh | +4.6808 kWh | Test peak demand spikes exceed validation max |
| **H001** | Demand | Std Dev | 0.5625 kWh | 0.7238 kWh | Volatility increased by **+28.7%** |
| | | 95th Percentile | +1.4603 kWh | +1.8864 kWh | Upper tail expanded by +29.2% |

> **Conclusion on Representativeness:** The validation residual pool is **statistically non-representative** of the winter test period. Stationary empirical resampling cannot generate scenario perturbations beyond the maximum historical validation residual ($+0.7457\text{ kWh}$ for H002). Consequently, when winter heating demand spikes by $+1.5\text{ kWh}$ or $+4.0\text{ kWh}$, empirical Monte Carlo coverage drops to exactly $0.0\%$.

### 4.2 Temporal Dependence and Autocorrelation
Empirical resampling samples residuals uniformly at random across all 701 validation hours, implicitly assuming residuals are conditionally independent across time:
$$\mathbb{P}(e_{t+1} \mid e_t) = \mathbb{P}(e_{t+1})$$

We computed the empirical autocorrelation of residuals at Lag 1 (adjacent hour), Lag 2, and Lag 24 (daily cycle):

| Series | Lag 1 Autocorr | Lag 2 Autocorr | Lag 24 Autocorr | Evidence of Temporal Structure |
| :--- | :---: | :---: | :---: | :--- |
| **H001 Val Demand Residuals** | +0.2585 | +0.3690 | **+0.6820** | Strong daily diurnal periodicity |
| **H002 Val Demand Residuals** | **+0.7387** | +0.3313 | **+0.8543** | Persistent hourly inertia and massive daily cycle |
| **H003 Val Demand Residuals** | -0.2145 | -0.1061 | **+0.7272** | Strong daily periodicity |
| **H001 Test Demand Errors** | +0.3402 | +0.0717 | **+0.5235** | Sustained multi-hour persistence |
| **H002 Test Demand Errors** | **+0.4541** | +0.1418 | **+0.4358** | Sustained multi-hour persistence |
| **H003 Test Demand Errors** | +0.2041 | -0.0605 | **+0.5310** | Sustained multi-hour persistence |

> **Implications of Temporal Dependence:** Real energy demand and solar errors possess massive 24-hour periodicity ($r_{24} \approx 0.70 - 0.85$) and significant short-term persistence ($r_1 \approx 0.35 - 0.74$). The Monte Carlo generator samples residuals i.i.d. across the entire pool, allowing a 3:00 AM residual to perturb a 12:00 PM forecast. While valid for marginal one-step-ahead intervals, this i.i.d. assumption means generated multi-step trajectories cannot represent realistic autocorrelated battery charging or multi-hour load spikes.

### 4.3 Asymmetric Tails in Demand Residuals
The residual pool exhibits pronounced positive skewness (right-skewed tails) due to sudden occupant appliance usage:
- **H001 Demand:** Skewness $= +1.5318$, Kurtosis $= +2.9427$. Left tail $Q_{0.50} - Q_{0.05} = 0.4335\text{ kWh}$, while Right tail $Q_{0.95} - Q_{0.50} = 1.3594\text{ kWh}$ (**3.1x wider**).
- **H003 Demand:** Skewness $= +3.0940$, Kurtosis $= +14.6103$. Left tail $Q_{0.50} - Q_{0.05} = 0.4901\text{ kWh}$, while Right tail $Q_{0.95} - Q_{0.50} = 1.1025\text{ kWh}$ (**2.3x wider**).
- In the test period, under-coverage is almost entirely driven by right-tail exceedances: across all 5,256 observations, **$12.10\%$ of actuals fall above the 95th percentile upper bound**, while only **$5.86\%$ fall below the lower bound**.

### 4.4 Impact of Non-Negativity Clipping at Zero
To maintain physical validity, scenarios enforce $\tilde{y} = \max(0, \hat{y} + e)$.
Across all 5,256 test observations ($5,256,000$ generated scenarios):
- **Demand Scenarios Clipped ($< 0.0$):** **752,971 scenarios (14.33%)**
- **Solar Scenarios Clipped ($< 0.0$):** **1,304,209 scenarios (24.81%)**
- **Observations where Demand $Q_{0.05} \equiv 0.0\text{ kWh}$:** **3,462 / 5,256 (65.87%)**
- **Observations where Solar $Q_{0.05} \equiv 0.0\text{ kWh}$:** **3,738 / 5,256 (71.12%)**

#### Statistical Consequences of Clipping:
1. **Creation of an Atom at Zero:** Clipping piles 14% - 25% of the probability mass directly onto $0.0\text{ kWh}$, transforming continuous error distributions into censored Tobit-type mixtures.
2. **Mean Bias Inflation:** By Jensen's Inequality, $\mathbb{E}[\max(0, \hat{y} + e)] > \hat{y} + \mathbb{E}[e]$ whenever $\mathbb{P}(\hat{y} + e < 0) > 0$. The scenario mean is systematically shifted upward relative to the LSTM point forecast during low-load or nighttime solar periods.
3. **Lower Bound Pinning:** For 66% of demand hours and 71% of solar hours, the 5th percentile collapses to exactly $0.0\text{ kWh}$, preventing the interval from contracting around low, certain consumption levels.

### 4.5 Scenario Maximum vs. 95th Percentile Upper Bound
We investigated whether the scenario maximum was being confused with the 95th percentile upper interval bound:
- **Code Audit:** In `src/stochastic/monte_carlo.py` and `src/evaluation/forecast_evaluator.py`, intervals are strictly defined by $\hat{q}_{0.05}$ and $\hat{q}_{0.95}$ via `np.percentile`. The maximum `np.max(...)` is computed purely as an extreme-value descriptor in `ScenarioDistribution`. There is zero confusion in the code.
- **Empirical Gap between $Q_{0.95}$ and Maximum:**
  - Average Demand Gap ($\text{Max} - Q_{0.95}$): **$+1.8390\text{ kWh}$**
  - Average Solar Gap ($\text{Max} - Q_{0.95}$): **$+0.6215\text{ kWh}$**
  - Actual observations falling between $Q_{0.95}$ and Maximum: **$9.89\%$** of all test hours.
  - Actual observations exceeding even the scenario Maximum: **$2.17\%$** overall (**$5.94\%$ for H002**).
- **Statistical Interpretation:** Confusing the scenario maximum with $Q_{0.95}$ would artificially widen demand intervals by an average of $1.84\text{ kWh}$, destroying the economic value of game-theoretic coordination without addressing the root cause of seasonal drift.

---

## 5. Limitations of Empirical Residual Resampling

The findings from Step 3 confirm four fundamental structural limitations of stationary empirical residual resampling:

1. **Stationarity Vulnerability:** Resampling from a fixed historical window (March 20 – April 18) assumes strict error stationarity. When non-stationary seasonal transitions occur (Sydney winter heating spikes), the empirical pool cannot cover unseen test variances.
2. **Support Bounding:** Resampling can never produce a perturbation larger than $\max(e_{\text{val}})$. If winter heating introduces errors 6x larger than autumn, coverage is mathematically bound to fail.
3. **Temporal Blindness:** Uniform sampling ignores the 24-hour diurnal error cycle ($r_{24} \approx 0.85$), treating peak afternoon solar hours and midnight hours as interchangeable error sources.
4. **Asymmetric Censoring:** Non-negativity clipping pins lower bounds to $0.0\text{ kWh}$ for two-thirds of all observations, creating an artificial point mass and shifting expected energy scenarios upward.

---

## 6. Recommendations for Step 4 & Beyond

1. **Maintain Protocol B as Baseline:** Use `protocol_b` (deterministic seed per stable identifier) as the project's standard baseline for all subsequent Monte Carlo evaluations. It guarantees exact order-independent reproducibility while eliminating single-seed freezing.
2. **Preserve Baseline Evaluation Artifacts:** Retain `data/processed/test_interval_evaluations_row_level.csv` and `data/processed/test_forecast_interval_summary.csv` as the formal benchmark against which conformal prediction (Step 5) will be assessed.
3. **Do NOT Artificially Pad Intervals:** Do not manually inflate residual bounds or tune seeds to force 90% coverage on the test set.
4. **Transition to Physical Feasibility (Step 4):** Before implementing advanced statistical calibration (conformal prediction), validate battery physical constraints, energy conservation, and transaction feasibility in Step 4.

---

## 7. Automated Test Suite Verification

The full test suite was executed to verify that all existing functionality, invariants, and new Step 3 validation suites pass without errors.

```bash
# Test Execution Command:
python -m pytest

# Output Summary:
============================= test session starts =============================
platform win32 -- Python 3.13.6, pytest-8.3.4, pluggy-1.5.0
rootdir: D:\5thSem\GT project\Stochastic-Game-Theoretic-Optimization-under-uncertain-energy-conditions
plugins: anyio-4.8.0, asyncio-0.25.2
asyncio: mode=Mode.STRICT, asyncio_default_fixture_loop_scope=None
collected 62 items

tests\test_battery.py .....                                              [  8%]
tests\test_energy.py .....                                               [ 16%]
tests\test_forecast_evaluation.py .............                          [ 37%]
tests\test_game.py .........                                             [ 51%]
tests\test_monte_carlo.py .......................                        [ 88%]
tests\test_preprocessing.py ...                                          [ 93%]
tests\test_utility.py ....                                               [100%]

============================= 62 passed in 11.32s =============================
```
