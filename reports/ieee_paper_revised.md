# Stochastic Game-Theoretic Optimization for Peer-to-Peer Energy Trading in Residential Microgrids Under Forecast Uncertainty

**Abstract**—This paper presents a stochastic game-theoretic framework for peer-to-peer (P2P) energy management in a small residential microgrid. The system combines household demand and photovoltaic generation forecasting, residual-based Monte Carlo scenario generation, stochastic model predictive control (MPC) for battery dispatch, and a strategic double-auction model in which households select asking or bidding prices. The framework is evaluated using three households derived from the Ausgrid Solar Home Electricity dataset. On the held-out period from 19 April to 30 June 2013, the evaluation covers 1,752 hourly timestamps and 5,256 household-hour observations. Each stochastic market evaluation uses 1,000 scenarios. Demand and solar mean absolute errors are 0.4660 kWh and 0.0814 kWh, respectively; the corresponding 90% prediction-interval coverages are 81.91% and 89.42%. Across the full horizon, the deterministic ex-post market clears 121.6114 kWh, while the stochastic expected-payoff market clears 87.6472 kWh. A timestamp-level audit distinguishes overlapping and non-overlapping trading hours and quantifies the physical Jensen gap separately from role-conditioned order restrictions. The results demonstrate an end-to-end computational framework and identify the limits of interpreting ex-post and ex-ante market outcomes as directly equivalent. The study is a simulation-based prototype, not a field deployment.

**Keywords**—Peer-to-peer energy trading, residential microgrid, game theory, Nash equilibrium, stochastic optimization, Monte Carlo simulation, solar forecasting, model predictive control.

## I. INTRODUCTION
The increasing deployment of rooftop photovoltaic (PV) systems changes households from passive electricity consumers into prosumers that can both consume and export energy. At a given time, one household may have surplus solar generation while another experiences a demand deficit. Local peer-to-peer energy trading can create an opportunity to use part of this surplus within a community rather than relying entirely on grid export and grid import. However, household demand and solar generation are uncertain, and each participant may strategically choose the price at which it is willing to sell or buy energy.

This project studies the interaction between physical energy management and strategic market behaviour. Its central question is: how can a small community coordinate battery dispatch and P2P energy exchange when future demand and solar generation are uncertain and households choose their own trading prices? The proposed pipeline combines forecasting, scenario generation, stochastic battery control and non-cooperative game-theoretic market analysis.

The principal contributions are:
1. An integrated three-household simulation pipeline using real residential solar-home measurements.
2. Uncertainty representation through 1,000 synchronized Monte Carlo scenarios.
3. A strategic price-only double-auction game with deterministic and expected stochastic payoff analysis.
4. Full-horizon evaluation of physical, financial and equilibrium properties.
5. A quantitative decomposition that separates physical matching uncertainty, ex-ante role restrictions and observed market participation differences.

All reported results are simulation results on historical data; no live electricity network or market deployment is claimed.

## II. RELATED WORK
Peer-to-peer energy trading has been studied as a market arrangement that enables distributed energy resource owners to exchange electricity locally. Reviews identify market platforms, pricing, optimization, game theory and simulation as major research themes [1]. Game-theoretic formulations are particularly relevant when prosumers make strategic decisions and their outcomes depend on the actions of other participants. A clustered-microgrid study has, for example, applied game-theoretic optimization to P2P trading and participant payoff analysis [2].

Forecast uncertainty is also important in microgrid operation. Stochastic MPC methods represent uncertain load and renewable generation through scenarios and optimize decisions over a receding horizon [3]. Long short-term memory (LSTM) networks provide a recurrent neural architecture for learning temporal dependencies in sequences [4]. The present work combines these strands but focuses on the interaction between uncertain physical matching and strategic price selection in a small multi-household market.

## III. SYSTEM MODEL AND PROBLEM FORMULATION
### A. Residential Microgrid
The simulated community contains three households, denoted H001, H002 and H003. Each household has a demand time series and a rooftop PV generation time series.

The selected household configurations used in the prototype are:
- H001: 3.78 kWp PV capacity
- H002: 1.00 kWp PV capacity
- H003: 1.00 kWp PV capacity

These are the configured participants in the experiment, not a claim that the three households represent the full Ausgrid population.

Each household is equipped with an identical residential battery energy storage system (BESS). The physical operational parameters implemented and enforced by the battery dispatch module (`src/energy/battery.py`) are:
- Rated battery storage capacity: 5.0 kWh per household
- Maximum charging power limit ($P_{\text{ch}}^{\max}$): 2.5 kW
- Maximum discharging power limit ($P_{\text{dis}}^{\max}$): 2.5 kW
- Charging efficiency ($\eta_{\text{ch}}$): 95% ($0.95$)
- Discharging efficiency ($\eta_{\text{dis}}$): 95% ($0.95$), yielding an effective round-trip efficiency of $\eta_{\text{rt}} = \eta_{\text{ch}} \times \eta_{\text{dis}} \approx 90.25\%$
- Operational state-of-charge (SoC) operating bounds: $\text{SoC}_{\min} = 10\%$ ($0.10$) and $\text{SoC}_{\max} = 90\%$ ($0.90$)
- Initial state-of-charge ($\text{SoC}_0$): 50% ($0.50$, corresponding to 2.5 kWh stored energy)

Let $D_i(t)$ and $S_i(t)$ denote the demand and solar generation of household $i$ at time $t$. Let $C_i(t)$ denote battery charging energy and $B_i(t)$ denote battery discharging energy.

The post-battery net position of household $i$ at time $t$ is defined as:
\[ n_i(t) = [D_i(t) + C_i(t)] - [S_i(t) + B_i(t)] \tag{1} \]

The sign of $n_i(t)$ governs the physical market role of household $i$:
- $n_i(t) < 0$ represents a household net surplus (available seller energy $s_i(t) = \max(0, -n_i(t))$).
- $n_i(t) > 0$ represents a household net deficit (unserved buyer load $d_i(t) = \max(0, n_i(t))$).

Across the residential microgrid of $N$ households ($N = 3$), the aggregate available community surplus $S(t)$ and aggregate energy deficit $D(t)$ at time $t$ are formally defined as:
\[ S(t) = \sum_{i=1}^N \max(0, -n_i(t)) \tag{2} \]
\[ D(t) = \sum_{i=1}^N \max(0, n_i(t)) \tag{3} \]

A feasible bilateral peer-to-peer traded quantity $Q_{\text{P2P}}(t)$ between aggregate surplus $S(t)$ and aggregate deficit $D(t)$ is strictly bounded by:
\[ Q_{\text{P2P}}(t) \le \min(S(t), D(t)) \tag{4} \]

### B. Grid Tariffs and Community Welfare
The prototype uses:
- Grid import tariff: AUD 0.30/kWh
- Grid export credit: AUD 0.08/kWh

The difference, AUD 0.22/kWh, is the maximum community value created when one kWh that would otherwise be exported by a seller and imported by a buyer is instead matched locally, before considering any additional network or platform costs:
\[ W(t) = (0.30 - 0.08) Q_{\text{P2P}}(t) \]
\[ W(t) = 0.22 Q_{\text{P2P}}(t) \tag{5} \]

Household utility is defined as the negative of net energy expenditure. Net expenditure includes grid purchases, grid export revenue, P2P purchase payments and P2P sale revenue.

An accounting invariant checks that the sum of household incremental benefits equals community welfare for the implemented settlement accounting:
\[ \sum_{i=1}^N U_i(t) = W(t) \]

### C. Strategic Price Action Space and Merit-Order Double Auction
The price-only auction uses the discrete action set:
\[ \mathcal{P} = \{0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30\} \]
All prices are in AUD/kWh.

A seller selects an asking price from $\mathcal{P}$ and a buyer selects a bidding price from $\mathcal{P}$. The auction executes bilateral matching using a merit-order double-auction mechanism:
1. **Order Book Construction and Sorting:** Seller ask orders are sorted in ascending merit order of asking price (lowest ask price first; ties broken deterministically by household ID). Buyer bid orders are sorted in descending merit order of bidding price (highest bid price first; ties broken deterministically by household ID).
2. **Crossing and Eligibility Condition:** An eligible matching round occurs if and only if the highest available buyer bid is at least the lowest available seller ask ($b_{\max} \ge a_{\min}$). If $b_{\max} < a_{\min}$, the order books do not cross and auction matching terminates.
3. **Midpoint Transaction Pricing:** For each matched transaction between seller $i$ and buyer $j$, the cleared unit price is set to the exact midpoint of their submitted prices:
\[ p_{ij} = \frac{a_{\min} + b_{\max}}{2} \]
4. **Tie Handling and Pro-Rata Rationing:** When multiple sellers submit the same minimum ask price ($\mathcal{S}_{\text{tied}}$) or multiple buyers submit the same maximum bid price ($\mathcal{B}_{\text{tied}}$), the cleared volume at that price step is $Q_{\text{trade}} = \min(\sum_{i \in \mathcal{S}_{\text{tied}}} s_i^{\text{rem}}, \sum_{j \in \mathcal{B}_{\text{tied}}} d_j^{\text{rem}})$. Volume is allocated among tied participants strictly pro-rata according to their remaining available quantities:
\[ q_i^{\text{alloc}} = Q_{\text{trade}} \times \frac{s_i^{\text{rem}}}{\sum_{k \in \mathcal{S}_{\text{tied}}} s_k^{\text{rem}}}, \quad \forall i \in \mathcal{S}_{\text{tied}} \]
\[ q_j^{\text{alloc}} = Q_{\text{trade}} \times \frac{d_j^{\text{rem}}}{\sum_{k \in \mathcal{B}_{\text{tied}}} d_k^{\text{rem}}}, \quad \forall j \in \mathcal{B}_{\text{tied}} \]
Bilateral trades between tied sellers and buyers are decomposed proportionally as $q_{ij} = (q_i^{\text{alloc}} \cdot q_j^{\text{alloc}}) / Q_{\text{trade}}$.
5. **Iterative Clearing:** Available quantities are decremented by allocated volumes ($s_i^{\text{rem}} \leftarrow s_i^{\text{rem}} - q_i^{\text{alloc}}$, $d_j^{\text{rem}} \leftarrow d_j^{\text{rem}} - q_j^{\text{alloc}}$), and the algorithm iterates until no eligible matching pairs remain.

This discrete action space makes exhaustive unilateral-deviation analysis tractable for the three-player game. The model studies strategic price selection; it does not model strategic quantity offers as independent actions.

## IV. PROPOSED METHODOLOGY
### A. Data Processing and Forecasting
The source is the Ausgrid Solar Home Electricity dataset, which records residential electricity consumption and rooftop solar generation [5].
The project uses the 2012–2013 data and constructs hourly series from the half-hourly source records. General consumption (GC), controlled load (CL) and gross generation (GG) are used in the data preparation pipeline.
A three-household hourly dataset is prepared for forecasting and market simulation.
An LSTM model forecasts demand and solar generation from a sequence of recent observations and temporal features. The feature set used by the implemented model includes:
- Demand
- Solar generation
- Hour-of-day sine and cosine terms
- Day-of-week sine and cosine terms

The model predicts the next demand and solar values. Forecast errors are evaluated on a held-out chronological test period; the test period is not used as the training target for the reported evaluation.

### B. Residual-Based Monte Carlo Scenarios
Forecasts provide point estimates but do not describe all possible future outcomes. The stochastic layer samples historical forecast residuals to construct 1,000 demand and solar scenarios for each timestamp.
The implementation uses synchronized cross-household scenario sampling so that household residuals retain their common timestamp alignment. A deterministic timestamp-specific seed supports reproducible scenario construction within the pinned software and numerical environment.
The scenario generation equations are:
\[ D_i^{(s)}(t) = \max(0, \hat{D}_i(t) + \epsilon_{D,i}^{(s)}) \tag{6} \]
\[ S_i^{(s)}(t) = \max(0, \hat{S}_i(t) + \epsilon_{S,i}^{(s)}) \]
Here:
- $s$ indexes the Monte Carlo scenario.
- Hats denote point forecasts.
- $\epsilon$ denotes sampled residuals.
- Non-negativity is enforced for physical demand and generation.

Scenario generation represents uncertainty using an empirical residual distribution; it does not guarantee calibrated probability distributions, as reflected by the measured prediction-interval coverage.

### C. Stochastic MPC Battery Dispatch
The battery controller uses stochastic MPC to make an operational charging and discharging decision while accounting for uncertain net demand and PV generation.
The first-stage battery decisions are frozen across the scenario set for the subsequent stochastic strategic game.
This non-anticipativity condition ensures that the household does not choose a different already-committed battery action after learning which future scenario occurred.
The market analysis therefore evaluates strategic trading conditional on the selected battery dispatch, rather than jointly re-optimizing battery actions for every price deviation.

### D. Deterministic and Stochastic Strategic Games
In the deterministic ex-post formulation (Phase 8C), the game is evaluated using the realized historical physical conditions at each timestamp.
Each household selects an action from its role-appropriate price set, and the solver enumerates action profiles and unilateral deviations to identify pure Nash equilibria (PNE).
A PNE is a profile in which no single player can improve its payoff by changing its own action while the other players' actions remain fixed.
The stochastic expected-payoff formulation (Phase 8E) evaluates each candidate action profile over all 1,000 scenarios.
Expected payoff is the arithmetic mean of scenario payoffs, including scenarios with no trade.
The implemented role-conditioned action rule determines each household's ex-ante role from its expected post-battery net position. Sellers choose an ask and buyers choose a bid; if a household's realized scenario role conflicts with its ex-ante role, it submits no order in that scenario.
This is a restricted ex-ante policy class, not a fully contingent two-sided bidding policy.
The expected payoff is calculated as:
\[ \bar{U}_i(a) = \frac{1}{1000}\sum_{s=1}^{1000}U_i(a;s) \tag{7} \]
The stochastic solver searches for PNE using expected payoffs and records strict and weak equilibria.
Weak equilibria permit payoff-indifferent deviations; therefore, a large number of weak PNE in a zero-trade hour should not be interpreted as meaningful price discovery.
Pareto-undominated equilibrium profiles are also identified to support equilibrium selection. The fairness-aware deterministic selection module is retained as a separate comparison stage.

## V. EXPERIMENTAL SETUP
The full-horizon evaluation uses the held-out interval from 19 April 2013, 00:00 to 30 June 2013, 23:00.
This interval contains 1,752 hourly timestamps. With three households, the evaluation contains:
\[ 1,752 \times 3 = 5,256 \]
household-hour observations.
The stochastic market uses 1,000 scenarios per timestamp.
The deterministic and stochastic market outputs are compared on the same historical evaluation horizon, while recognizing that they represent different information structures: ex-post realized conditions versus ex-ante expected payoffs under uncertainty.

| Experimental Item | Configured Value |
|---|---|
| Households | H001, H002, H003 |
| PV capacities | 3.78 kWp, 1.00 kWp, 1.00 kWp |
| Battery capacity & limits | 5.0 kWh capacity, 2.5 kW max charge/discharge, SoC in [0.10, 0.90] |
| Held-out horizon | 2013-04-19 00:00 to 2013-06-30 23:00 |
| Hourly timestamps | 1,752 |
| Household-hour evaluations | 5,256 |
| Monte Carlo scenarios | 1,000 per timestamp |
| Grid import / export | AUD 0.30 / 0.08 per kWh |
| Price actions | 0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30 AUD/kWh |
| Auction settlement price | Midpoint of compatible ask and bid with merit-order pro-rata clearing |

## VI. RESULTS AND DISCUSSION
### A. Forecast Accuracy and Prediction Intervals
Across the 5,256 household-hour observations, demand MAE is 0.4660 kWh and RMSE is 0.7834 kWh. Solar MAE is 0.0814 kWh and RMSE is 0.1600 kWh.
The 90% prediction-interval coverage is 81.91% for demand and 89.42% for solar.
Thus, the solar interval coverage is close to its nominal level, whereas the demand interval under-covers the nominal 90% target. These results indicate that the residual-based uncertainty model is more reliable for solar than for demand under this evaluation setup.

| Forecast Target | MAE (kWh) | RMSE (kWh) | 90% PI Coverage | Mean PI Width (kWh) |
|---|:---:|:---:|:---:|:---:|
| Demand | 0.4660 | 0.7834 | 81.91% | 1.2340 |
| Solar | 0.0814 | 0.1600 | 89.42% | 0.3625 |

Forecast bias is reported using:
\[ \text{Bias} = \operatorname{mean}(\text{prediction} - \text{actual}) \]
Under this convention, demand bias is −0.133982 kWh and solar bias is +0.030114 kWh.
This means that the model underpredicts demand on average and overpredicts solar generation on average.
Earlier residual summaries used the opposite operand order, mean(actual − prediction), which reverses the signs but not the underlying prediction errors.

### B. Full-Horizon Market Outcomes
Across the full 1,752-hour horizon, Phase 8C records 866 tradeable hours and 886 zero-trade hours. Phase 8E records 722 tradeable hours and 1,030 zero-trade hours.
Total bilateral energy is 121.611449 kWh for Phase 8C and 87.647245 kWh for Phase 8E, a difference of −33.964203 kWh (−27.93%).
Corresponding community welfare is AUD 26.754519 and AUD 19.282394, respectively.
These are empirical differences between two formulations, not a controlled causal estimate of the effect of uncertainty alone.

| Metric | Phase 8C deterministic ex-post | Phase 8E stochastic expected |
|---|:---:|:---:|
| Tradeable hours | 866 (49.43%) | 722 (41.21%) |
| Zero-trade hours | 886 (50.57%) | 1,030 (58.79%) |
| Total bilateral energy | 121.611449 kWh | 87.647245 kWh |
| Total community welfare | AUD 26.754519 | AUD 19.282394 |
| H001 incremental payoff | AUD 8.413031 | AUD 5.340941 |
| H002 incremental payoff | AUD 11.090010 | AUD 8.521557 |
| H003 incremental payoff | AUD 7.251477 | AUD 5.419896 |

The full-horizon participation difference is not a set of 144 identical hours.
The timestamp-level contingency table contains:
- 473 hours in which both formulations trade.
- 393 deterministic-only trading hours.
- 249 stochastic-only trading hours.
- 637 hours in which neither trades.

The net difference in tradeable-hour counts is:
\[ 866 - 722 = 144 \]
However, it arises from offsetting changes in both directions.

| Participation Regime | Hours | Share |
|---|:---:|:---:|
| Both formulations trade | 473 | 26.99% |
| Phase 8C only | 393 | 22.43% |
| Phase 8E only | 249 | 14.21% |
| Neither trades | 637 | 36.36% |
| Total | 1,752 | 100.00% |

### C. Household Benefit Distribution
Under Phase 8C, H001, H002 and H003 receive 31.45%, 41.45% and 27.10% of total incremental household benefit, respectively.
Under Phase 8E, the shares are 27.70%, 44.19% and 28.11%.
The distribution changes between formulations, even though the sum of household incremental benefits remains consistent with aggregate community welfare under the implemented accounting identity.
This is relevant because total welfare alone does not describe how the economic gains are distributed among participants.

### D. Equilibrium Results
Across the full horizon, the solver records 315,280 PNE for Phase 8C and 361,507 PNE for Phase 8E.
Strict PNE increase from 1,224 to 1,825 (+49.10%), while weak PNE increase from 314,056 to 359,682.
Pareto-undominated profiles number 312,810 and 356,107, respectively.
The average number of PNE per tradeable hour is 13.48 for Phase 8C and 11.38 for Phase 8E.
The increase in strict PNE is an observed empirical result; the analysis does not establish a causal mechanism such as larger unilateral deviation gaps from scenario averaging.

| Equilibrium Measure | Phase 8C | Phase 8E |
|---|:---:|:---:|
| Total PNE | 315,280 | 361,507 |
| Strict PNE | 1,224 | 1,825 |
| Weak PNE | 314,056 | 359,682 |
| Pareto-undominated profiles | 312,810 | 356,107 |
| Mean PNE per tradeable hour | 13.48 | 11.38 |

Zero-trade hours require careful interpretation.
In Phase 8E, a zero-trade hour can produce 343 weak PNE because all action profiles and unilateral deviations yield zero payoffs ($7^3 = 343$ action combinations).
These are indifference equilibria generated by payoff equivalence, not evidence that the market has discovered 343 economically meaningful prices.

### E. Physical Matching and Jensen-Gap Audit
Jensen's inequality for the concave matching function $\min(S, D)$ gives:
\[ \mathbb{E}[\min(S,D)] \le \min(\mathbb{E}[S], \mathbb{E}[D]) \]

A scenario-level audit was performed for the 473 timestamps where both Phase 8C and Phase 8E trade.
The aggregate matching quantity at expected physical positions is 155.9049 kWh, while expected physical matching across the 1,000 scenarios is 90.0524 kWh.
The resulting physical Jensen gap is 65.8524 kWh, or 42.24% of the mean-position matching quantity.
The inequality holds at all 473 timestamps; the smallest measured positive gap is 0.000386 kWh.

| Matching Stage | Aggregate Quantity |
|---|:---:|
| Matching at expected positions, $\min(\mathbb{E}[S], \mathbb{E}[D])$ | 155.9049 kWh |
| Expected physical matching, $\mathbb{E}[\min(S, D)]$ | 90.0524 kWh |
| Physical Jensen gap | 65.8524 kWh (42.24%) |
| Expected physical matching after role clamping | 63.6854 kWh |
| Actual Phase 8E expected auction clearing | 63.6854 kWh |
| Phase 8C ex-post cleared volume | 78.3303 kWh |

The role-conditioned order rule reduces expected physical matching from 90.0524 kWh to 63.6854 kWh, a reduction of 26.3671 kWh (29.28% of expected physical matching).
On these 473 overlapping hours, the selected Phase 8E equilibria clear the role-clamped quantity ($100.0\%$ execution, 0.0000 kWh strategic withholding).
This equality is specific to the audited sample and definition; it does not prove that strategic pricing can never reduce trading in other settings.
Phase 8C ex-post volume on the same 473 hours is 78.3303 kWh, whereas Phase 8E expected auction volume is 63.6854 kWh, a difference of −14.6449 kWh (−18.70%).
However, expected physical matching (90.0524 kWh) is itself 14.97% higher than the Phase 8C ex-post volume.
Therefore, the observed −18.70% Phase 8C-to-Phase 8E difference must not be labelled as the Jensen effect.
The Jensen gap compares mean-position matching with expected physical matching; role clamping is a separate restriction; and Phase 8C is an ex-post equilibrium on one realized historical trajectory.

The decomposition is:
\[ Q_{\text{stoch}} - Q_{\text{det}} = (Q_{\text{stoch}} - Q_{\text{physical expected}}) + (Q_{\text{physical expected}} - Q_{\text{det}}) \]
Substituting the measured values:
\[ 63.6854 - 78.3303 = (63.6854 - 90.0524) + (90.0524 - 78.3303) \]
\[ \mathbf{-14.6449 = -26.3671 + 11.7221\text{ kWh}} \]

The full-horizon difference of −27.93% additionally reflects extensive-margin participation changes across the 393 deterministic-only and 249 stochastic-only hours.
It is not a single Jensen effect.
This distinction prevents conflating physical uncertainty, ex-ante role restrictions and market participation changes.

### F. Physical and Financial Consistency
The Phase 9 validation reports zero physical constraint violations over the 1,752 timestamps.
Financial accounting identities pass across the evaluated records, with maximum reported identity errors below $10^{-15}$ AUD.
The welfare identity links community welfare to the tariff spread and locally traded quantity.
These checks support internal consistency of the simulated energy and settlement accounting; they do not by themselves validate distribution-network voltage, line-loss or protection constraints, which are outside the three-household model's stated scope.

## VII. LIMITATIONS
The study is a three-household computational prototype and does not establish performance at feeder or city scale.
The market uses a discrete price-only action space and a restricted role-conditioned policy class.
Battery first-stage decisions are frozen across scenarios, so the strategic market does not jointly re-optimize storage for every scenario or price deviation.
Residual-based Monte Carlo sampling depends on the representativeness of the residual pool; demand prediction intervals under-cover the nominal 90% level.
The dataset does not provide a complete distribution-network model in this project configuration, so voltage, line thermal limits, network losses and local grid constraints are not evaluated.
Finally, the tariff spread and household configuration are simulation assumptions and should not be interpreted as current retail tariffs or a validated commercial settlement design.

## VIII. CONCLUSION AND FUTURE WORK
This paper presented an integrated stochastic game-theoretic framework for residential P2P energy management.
The pipeline combines LSTM-based household forecasting, residual-based Monte Carlo scenarios, stochastic MPC battery dispatch and strategic ask/bid selection.
Full-horizon evaluation over 1,752 hours demonstrated forecast performance, physical and financial consistency, and measurable differences between deterministic ex-post and stochastic expected-payoff market outcomes.
The quantitative matching audit is a key finding: Jensen's inequality holds for all 473 overlapping trading hours, with an aggregate physical gap of 65.8524 kWh between matching at expected positions and expected physical matching.
A further 26.3671 kWh reduction is associated with the implemented ex-ante role-conditioned order restriction.
The observed 18.70% difference between deterministic and stochastic cleared volume on the overlapping hours is not itself the Jensen gap.
Across the full horizon, market participation changes in both directions, so the 27.93% aggregate volume difference should be interpreted as an empirical comparison of two different information and strategy formulations.

Future work includes:
- Improving demand interval calibration.
- Testing conformal or adaptive uncertainty calibration.
- Expanding the number of households.
- Evaluating continuous or richer bidding policies.
- Modelling strategic quantity offers.
- Jointly optimizing storage and market decisions.
- Adding distribution-network constraints.

A larger-scale validation with contemporary data and realistic tariff structures would be required before considering operational deployment.

## ACKNOWLEDGMENT
The authors acknowledge [Project Guide's Full Name], [Designation], Department of [Department], SVNIT Surat, for guidance and feedback.
[Add any additional institutional, laboratory or funding acknowledgment here, or delete this paragraph if not applicable.]

## REFERENCES
[1] E. A. Soto, L. B. Bosman, E. Wollega, and W. D. Leon-Salas, “Peer-to-peer energy trading: A review of the literature,” *Applied Energy*, vol. 283, Art. no. 116268, Feb. 2021, doi: 10.1016/j.apenergy.2020.116268.

[2] L. Ali, S. M. Muyeen, H. Bizhani, and A. Ghosh, “A peer-to-peer energy trading for a clustered microgrid—Game theoretical approach,” *International Journal of Electrical Power & Energy Systems*, vol. 129, Art. no. 106797, 2021, doi: 10.1016/j.ijepes.2021.107307.

[3] Y. Zhang, F. Meng, R. Wang, W. Zhu, and X.-J. Zeng, “A stochastic MPC based approach to integrated energy management in microgrids,” *Sustainable Cities and Society*, vol. 41, pp. 349–362, Aug. 2018, doi: 10.1016/j.scs.2018.05.044.

[4] S. Hochreiter and J. Schmidhuber, “Long short-term memory,” *Neural Computation*, vol. 9, no. 8, pp. 1735–1780, 1997, doi: 10.1162/neco.1997.9.8.1735.

[5] Ausgrid, “Solar Home Electricity Data,” Ausgrid. [Online]. Available: https://www.ausgrid.com.au/Industry/Our-Research/Data-to-share/Solar-home-electricity-data. [Accessed: Nov. 1, 2026].

[6] J. F. Nash, “Equilibrium points in n-person games,” *Proceedings of the National Academy of Sciences*, vol. 36, no. 1, pp. 48–49, 1950, doi: 10.1073/pnas.36.1.48.
