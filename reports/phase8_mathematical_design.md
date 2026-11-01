# Phase 8 — Mathematical Game Formulation and Strategic Market Design

**Document ID:** `reports/phase8_mathematical_design.md`  
**Project:** Stochastic Game-Theoretic Renewable Energy Management under Uncertain Energy Conditions  
**Phase Target:** Phase 8 — Step 1.2: Final Mathematical Consistency Specification  
**Baseline Reference:** Phase 7.1 Independent Physical, Economic, and Market-Integration Audit (Accepted Baseline)  
**Status:** REVISED DESIGN SPECIFICATION (Step 1.2 Mathematical Consistency Revisions Applied)  

---

## Revision Note: Step 1.2 Mathematical Consistency Corrections

This specification incorporates the mandatory mathematical, computational, and conceptual consistency corrections required prior to Phase 8B implementation:

1. **Alignment of Action Space with Phase 8B Price-Only Bidding (Section 6.2):**  
   Formally aligns the Phase 8B deterministic strategy space to price-only bidding over $\mathcal{P} = \{0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30\}$ ($|\mathcal{P}| = 7$ actions per active player). Quantities are fixed to physical flow ($q_i^{\text{sell}} = s_i^{\text{act}}, q_j^{\text{buy}} = d_j^{\text{act}}$). For an hour with 3 active players, $|A| = 7^3 = 343$ strategy profiles with exactly 18 unilateral alternative deviations per profile. The 15-action / 3,375-profile / 42-deviation formulation is explicitly designated as deferred to a future joint price-quantity phase. A separate `NO_TRADE` action is excluded from the initial prototype. Action sets are generated dynamically based on actual physical roles, with inactive households assigned an empty action set ($A_i = \{\emptyset\}$).
2. **Causal Separation of Ex-Ante Quantities (Section 1.3 & Section 2.3):**  
   Strictly separates the deterministic ex-post benchmark ($q = \text{flow}^{\text{act}}$) from the deployable ex-ante game. In the ex-ante game, submitted quantities $\bar{q}_i = f(\text{forecasts, scenarios, available information})$ rely strictly on pre-realization information and are scenario-clamped post-realization via $\tilde{q}_i(\omega) = \min(\bar{q}_i, \text{flow}_i(\omega))$. The exact functional policy for $f(\cdot)$ is marked as a Phase 8E calibration decision.
3. **Corrected Benchmark Terminology (Section 1.3):**  
   Replaced "upper-bound analytical counterfactual" with "perfect-information analytical benchmark". Acknowledged that perfect information does not guarantee maximum community welfare due to non-cooperative pricing and uncrossed spreads.
4. **Exhaustive Equilibrium Solver Alignment (Section 6.3 & Section 6.4):**  
   The Phase 8B equilibrium solver executes the identical clearing, pricing, and pro-rata matching engine as the simulation environment. When no pure equilibrium exists, it deterministically outputs `NO_PURE_NASH_EQUILIBRIUM` without fabricating a profile.
5. **Deterministic Midpoint-Proximity Heuristic Selection (Section 6.4):**  
   Maintained midpoint proximity strictly as a reporting heuristic without removing other equilibria. Defined exact deterministic tie-breakers for equal proximity distances, zero-volume hours (where $\bar{p}_{\text{tx}}$ is undefined), and Pareto-undominated sets.
6. **Stochastic Action-Space Clarification (Section 8.1):**  
   Explicitly distinguished the 7-action deterministic ex-post game from the Phase 8E stochastic game, where two-sided contingent bids $a_i = (b_i^{\text{ask}}, b_i^{\text{bid}}) \in \mathcal{P} \times \mathcal{P}$ yield $|A_i^{\text{ex-ante}}| = 49$ actions per household and $49^3 = 117,649$ joint strategy profiles for 3 households.
7. **Tolerance-Based Conservation Preservation (Section 5.2):**  
   Replaced independent per-element float truncation with exact bilinear allocation and tolerance-based validation checks ($\epsilon = 10^{-6}$), guaranteeing strict transaction-level conservation.
8. **Clarification of Evaluation Metrics (Section 9):**  
   Defined the aggregate liquidity execution ratio ($\rho_{\text{exec}}^{\text{agg}}$) versus the average hourly ratio ($\bar{\rho}_{\text{exec}}$), handled zero-capacity edge cases, formulated individual rationality per household ($\rho_{\text{IR}, i}$) and across the portfolio ($\rho_{\text{IR}}^{\text{port}}$), and formalized Pareto improvement.

---

## 1. Existing System Architecture and Strategic Integration Point

### 1.1 Current Phase 7 Baseline Workflow

The end-to-end operation established and independently audited in Phase 7 executes sequentially across each simulation hour $k \in \{0, 1, \dots, 1751\}$:

```mermaid
flowchart TD
    subgraph Step_1 [1. Forecasting & Uncertainty]
        A["LSTM Forecaster<br/>predict_lstm_numpy()"] --> B["Point Forecasts (d_fc, s_fc)<br/>Horizon H = 24h"]
        B --> C["ValidationResidualPool<br/>Empirical Error Resampling"]
        C --> D["Scenario Generator<br/>S = 3 or 5 Scenarios"]
    end

    subgraph Step_2 [2. Battery Optimal Dispatch]
        D --> E["SingleHouseholdStochasticMPCController<br/>or DeterministicMPCController"]
        E --> F["First-Stage Decision (C_0, B_0)<br/>Non-Anticipativity Enforced"]
        F --> G["Physical Battery Execution<br/>BatteryStorage.step()"]
    end

    subgraph Step_3 [3. Physical Meter Flow]
        G --> H["Post-Battery Net Meter Position<br/>net_flow = (d_act + C_act) - (s_act + B_act)"]
        H --> I["Complementary Surplus & Deficit<br/>s_i = max(0, -net_flow)<br/>d_i = max(0, net_flow)"]
    end

    subgraph Step_4 [4. Strategic Layer (Phase 8 Entry Point)]
        I -.->|Phase 8 Strategic Bidding| J["Strategic Decision Layer<br/>Action a_i in A_i (Price Bids)"]
    end

    subgraph Step_5 [5. P2P Market Clearing]
        J --> K["clear_multi_household_market()<br/>Order Book Matching & Price Formation"]
        K --> L["Transaction Ledger<br/>Allocations (q_sold, q_bought, p_tx)"]
    end

    subgraph Step_6 [6. Grid Settlement & Financial Accounting]
        L --> M["Residual Grid Imports at p_import ($0.30)<br/>Residual Grid Exports at p_export ($0.08)"]
        M --> N["Financial Settlement<br/>U_i = -(Grid_Cost + P2P_Pmt) + (Grid_Rev + P2P_Rev)"]
    end
```

### 1.2 Existing Software Entities and Variables

Inspection of the codebase confirms the exact Python classes, methods, and variables governing this workflow:

| Subsystem | Source Module | Classes / Functions | Key Variables / Formulas |
| :--- | :--- | :--- | :--- |
| **Forecasting** | `src/forecasting/predict.py` | `EnergyForecaster`, `predict_lstm_numpy` | $\hat{D}_{i, k}, \hat{S}_{i, k}$ |
| **Uncertainty** | `src/stochastic/monte_carlo.py` | `ValidationResidualPool`, `derive_observation_seed` | $e_{D} = D - \hat{D}, e_{S} = S - \hat{S}$ |
| **Optimization** | `src/optimization/mpc_stochastic.py` | `SingleHouseholdStochasticMPCController`, `solve_milp` | $C_0, B_0, \text{SOC}_{t, \omega}$, terminal value $\lambda E_T$ |
| **Physical Metering** | `src/energy/market_integration.py` | `HouseholdStepRecord`, lines 464–471 | `net_flow = (d_act + actual_c) - (s_act + actual_d)` |
| **Market Clearing** | `src/energy/market_clearing.py` | `clear_multi_household_market`, `HouseholdMarketBid` | `surplus_kwh`, `deficit_kwh`, `p2p_price_aud`, `transactions` |
| **Financial Utility**| `src/game/utility.py` | `compute_household_payoff`, `HouseholdPayoff` | $U_i = -C_i^{\text{net}} = -(C_{\text{imp}} + P_{\text{p2p}} - R_{\text{exp}} - R_{\text{p2p}})$ |
| **Game Theory** | `src/game/game.py`, `nash.py` | `run_two_household_game`, `find_pure_nash_equilibria` | $2 \times 2$ participation game, `OFFER_P2P`, `ACCEPT_P2P` |

### 1.3 Strict Separation: Perfect-Information Analytical Benchmark vs Deployable Ex-Ante Game

To maintain scientific rigor and prevent information leakage, Phase 8 strictly demarcates two distinct problem settings:

#### Setting A: Deterministic Ex-Post Perfect-Information Game (Analytical Benchmark)
- **Role:** A **perfect-information analytical benchmark** evaluated on historical test data.
- **Information State:** Bids are submitted assuming actual realized post-battery net positions $n_{i, k}^{\text{act}} = (D_{i, k}^{\text{act}} + C_{i, k}) - (S_{i, k}^{\text{act}} + B_{i, k})$ are known.
- **Physical Quantities:** Traded quantities are fixed to actual physical flows:
  $$q_i^{\text{sell}} = s_i^{\text{act}} = \max(0, -n_{i, k}^{\text{act}}), \qquad q_j^{\text{buy}} = d_j^{\text{act}} = \max(0, n_{j, k}^{\text{act}})$$
- **Usage:** Primary focus of Phase 8B and 8C. Used to isolate double-auction market clearing mechanics, pro-rata tie-breaking, and pure Nash equilibrium computation without stochastic noise.
- **Demarcation:** Perfect information does **not** automatically imply maximum community welfare. Due to strategic bid shading or uncrossed bid-ask spreads, non-cooperative equilibria under perfect information may trade less energy and achieve lower welfare than a centralized cooperative dispatch. An actual social-optimum upper bound is defined separately by the centralized welfare program:
  $$\max Q_{\text{P2P}} = \min\left(\sum_{i \in N} s_i^{\text{act}}, \sum_{j \in N} d_j^{\text{act}}\right)$$

#### Setting B: Deployable Ex-Ante Strategic Game (Real-Time Decentralized Operation)
- **Role:** The deployable market protocol operating in causal real time.
- **Information State:** At hour $k$, households have access *only* to pre-realization information: local historical consumption, point forecasts $(\hat{D}_{i, k}, \hat{S}_{i, k})$, scenario residual pools $\Omega$, and battery state $\text{SOC}_{i, k}$.
- **Causality Invariant:** **Realized demand $D_{i, k}^{\text{act}}$ and solar $S_{i, k}^{\text{act}}$ are NEVER used to construct ex-ante bids.**
- **Quantity Policy:** Bidding quantities $\bar{q}_i^{\text{sell}}$ and $\bar{q}_i^{\text{buy}}$ are determined ex-ante from forecasts and uncertainty scenarios, and physically clamped ex-post (Section 2.3). Focus of Phase 8E.

---

## 2. Mathematical Game Formulation

We define the strategic interaction among residential prosumers as a normal-form game:

$$G = \left( N, (A_i)_{i \in N}, (U_i)_{i \in N}, \mathcal{M} \right)$$

### 2.1 Players and Dynamic Roles

The set of players is:

$$N = \{\text{H001}, \text{H002}, \text{H003}\}, \quad |N| = 3$$

Unlike classical wholesale markets where generators and loads have fixed roles, residential microgrid prosumers exhibit **dynamic role-switching**.

#### Dynamic Ex-Post Role Generation
In the deterministic ex-post benchmark, roles are determined dynamically at each hour $k$ by the net meter flow $n_i^{\text{act}}$:

$$\text{Role}(i) = \begin{cases}
\text{Seller } (i \in N_S) & \text{if } n_i^{\text{act}} < -\epsilon \\
\text{Buyer } (i \in N_B) & \text{if } n_i^{\text{act}} > +\epsilon \\
\text{Inactive / Balanced } (i \in N_0) & \text{if } |n_i^{\text{act}}| \le \epsilon
\end{cases}$$

where the zero-flow numerical threshold is $\epsilon = 10^{-6}\text{ kWh}$.

#### Handling Inactive Households
If $|n_i^{\text{act}}| \le \epsilon$, household $i$ is self-sufficient post-battery. It does not trade in the P2P market:
$$A_i = \{\emptyset\}, \quad |A_i| = 1$$
**Inactive households must not receive artificial seller or buyer actions.** They do not submit bids, cannot deviate, and do not expand the active strategic profile space.

---

### 2.2 Physical Energy Balance and Accounting Convention

For household $i$ at hour $k$:
- $D_i$: Household electrical consumption load (kWh).
- $S_i$: Rooftop solar photovoltaic generation (kWh).
- $C_i$: Energy delivered into the battery to charge (kWh, after efficiency $\eta_c = 0.95$).
- $B_i$: Energy supplied by the battery to discharge (kWh, before efficiency $\eta_d = 0.95$).

The physical net meter position is:

$$n_i = (D_i + C_i) - (S_i + B_i)$$

#### Physical Complementarity Invariant
A single physical meter cannot simultaneously import and export active power in the same interval:

$$s_i = \max(0, -n_i), \quad d_i = \max(0, n_i) \implies s_i \cdot d_i = 0 \quad \forall i \in N$$

---

### 2.3 Ex-Ante Quantity Causality and Strategy Spaces

#### Setting A: Phase 8B Deterministic Ex-Post Strategy Space (Price-Only Bidding)
In the Phase 8B deterministic benchmark, quantities are fixed to physical flows ($q_i^{\text{sell}} = s_i^{\text{act}}, q_j^{\text{buy}} = d_j^{\text{act}}$). The strategy space for each active player is strictly the discrete price set $\mathcal{P}$:

$$A_i = \begin{cases}
\mathcal{P} = \{0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30\} & \text{if } i \in N_S \text{ (Seller Ask } b_i^{\text{ask}} \in \mathcal{P}\text{)} \\
\mathcal{P} = \{0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30\} & \text{if } i \in N_B \text{ (Buyer Bid } b_i^{\text{bid}} \in \mathcal{P}\text{)} \\
\{\emptyset\} & \text{if } i \in N_0 \text{ (Inactive / Self-Sufficient)}
\end{cases}$$

- Each active household has exactly **7 discrete price actions** ($|A_i| = 7$).
- A separate `NO_TRADE` action is **excluded** from the initial Phase 8B prototype. Bidding uncompetitive prices (e.g., a seller asking $\$0.30/\text{kWh}$ or a buyer bidding $\$0.08/\text{kWh}$) serves as the non-trading boundary within the price space.

#### Setting B: Phase 8E Deployable Ex-Ante Game (Causal Quantities & Clamping)
In the deployable ex-ante game under uncertainty, actual realized physical flows are unknown at bid time. Submitted quantities must be determined using pre-realization information:

$$\bar{q}_i^{\text{sell}} = f(\hat{D}_{i, k}, \hat{S}_{i, k}, \Omega, \text{SOC}_{i, k}, C_{i, k}, B_{i, k})$$

$$\bar{q}_i^{\text{buy}} = g(\hat{D}_{i, k}, \hat{S}_{i, k}, \Omega, \text{SOC}_{i, k}, C_{i, k}, B_{i, k})$$

When scenario $\omega$ (or ground truth) materializes, physical feasibility is strictly enforced via scenario-wise physical clamping:

$$\tilde{q}_i^{\text{sell}}(\omega) = \min\big(\bar{q}_i^{\text{sell}}, \; s_i(\omega)\big)$$

$$\tilde{q}_i^{\text{buy}}(\omega) = \min\big(\bar{q}_i^{\text{buy}}, \; d_i(\omega)\big)$$

> [!NOTE]
> **Phase 8E Design Decision:** To avoid introducing unvalidated heuristics into the mathematical foundation, the exact functional specifications of $f(\cdot)$ and $g(\cdot)$ (e.g., expected forecast surplus $\hat{s}_i$, median scenario surplus, or risk-adjusted percentiles) are designated as a formal calibration decision in Phase 8E.

---

## 3. Evaluation of Candidate Strategic Game Designs

### 3.1 Model A: Binary Participation Game
Households choose $A_i = \{\text{PARTICIPATE}, \text{GRID\_ONLY}\}$ at the fixed price $p_{\text{p2p}} = \$0.19/\text{kWh}$. Participation is weakly dominant, collapsing identically to Phase 7. Provides no price formation.

### 3.2 Model B: Strategic Double Auction Bidding (Selected Architecture)
Households submit price bids into a continuous double auction.

#### Offered Capacity vs Executed Trading Volume
We strictly distinguish offered liquidity from executed trades:

$$\text{Offered Liquidity} = \sum_{i \in N_S} q_i^{\text{sell}} = \sum_{i \in N_S} s_i^{\text{act}}, \qquad \text{Requested Liquidity} = \sum_{j \in N_B} q_j^{\text{buy}} = \sum_{j \in N_B} d_j^{\text{act}}$$

$$\text{Executed Trading Volume } (Q_{\text{P2P}}) = \sum_{\text{tx}} q_{\text{tx}} \le \min\left(\sum_{i \in N_S} s_i^{\text{act}}, \sum_{j \in N_B} d_j^{\text{act}}\right)$$

If the lowest seller ask exceeds the highest buyer bid ($b_{(1)}^{\text{ask}} > b_{(1)}^{\text{bid}}$), the order books do not cross:
$$Q_{\text{P2P}} = 0\text{ kWh}$$
Total offered liquidity is unexecuted, and 100% of community energy reverts to standalone grid imports and exports.

---

### 3.3 Bilateral Midpoint Pricing and Strategic Rent Extraction

The market mechanism clears matched transactions at the bilateral midpoint:

$$p_{\text{tx}} = \frac{b_{\text{seller}}^{\text{ask}} + b_{\text{buyer}}^{\text{bid}}}{2}$$

#### Midpoint Pricing Does NOT Guarantee Equal Economic Welfare
Midpoint pricing divides the **submitted bid-ask spread** $(b_j^{\text{bid}} - b_i^{\text{ask}})$ symmetrically between buyer and seller. However, it **does NOT guarantee equal sharing of the total available economic surplus** $(p_{\text{imp}} - p_{\text{exp}} = \$0.22/\text{kWh})$, nor does it prevent monopoly rent extraction.

#### Analytical Example: Monopoly Rent Extraction Under Midpoint Pricing
Consider an hour where Household 1 is the sole seller ($s_1 = 1.0\text{ kWh}$) facing Buyer 2 ($d_2 = 1.0\text{ kWh}$):
- Retail grid tariffs: $p_{\text{imp}} = \$0.30/\text{kWh}$, $p_{\text{exp}} = \$0.08/\text{kWh}$. Total available community surplus = $\$0.22/\text{kWh}$.
- Buyer 2 submits a truthful bid near its grid ceiling: $b_2^{\text{bid}} = \$0.30/\text{kWh}$.
- Seller 1 exercises monopoly market power by asking: $b_1^{\text{ask}} = \$0.299/\text{kWh}$.

#### Market Clearing Calculation
1. **Transaction Price:**
   $$p_{\text{tx}} = \frac{0.299 + 0.300}{2} = \$0.2995/\text{kWh}$$
2. **Buyer Incremental Gain:**
   $$\Delta U_2 = q \cdot (p_{\text{imp}} - p_{\text{tx}}) = 1.0 \times (0.3000 - 0.2995) = \mathbf{+\$0.0005\text{ AUD}} \quad (0.23\% \text{ of total spread})$$
3. **Seller Incremental Gain:**
   $$\Delta U_1 = q \cdot (p_{\text{tx}} - p_{\text{exp}}) = 1.0 \times (0.2995 - 0.0800) = \mathbf{+\$0.2195\text{ AUD}} \quad (99.77\% \text{ of total spread})$$
4. **Total Community Welfare Gain:**
   $$\Delta W = \Delta U_1 + \Delta U_2 = 0.2195 + 0.0005 = \mathbf{+\$0.2200\text{ AUD}}$$

Even though the bilateral midpoint split the remaining $\$0.0010/\text{kWh}$ bid-ask spread symmetrically into $\$0.0005$ each, **the strategic seller captured $99.77\%$ of the microgrid's total economic surplus**.

---

## 4. Economically Consistent Payoff Functions

### 4.1 Economic Invariants and Existing Tariffs

All transactions operate within the commercial tariff envelope audited in Phase 7.1:

| Economic Parameter | Notation | Numerical Value | Description |
| :--- | :---: | :---: | :--- |
| **Retail Grid Import Tariff** | $p_{\text{imp}}$ | **\$0.3000 AUD/kWh** | Price paid to utility for electricity imported from central grid. |
| **Solar Grid Feed-in Credit** | $p_{\text{exp}}$ | **\$0.0800 AUD/kWh** | Credit received from utility for solar exported to central grid. |
| **Baseline Mid-Market P2P Price**| $p_{\text{p2p}}^{\text{base}}$ | **\$0.1900 AUD/kWh** | Symmetric midpoint tariff: $(0.30 + 0.08) / 2$. |
| **Avoided Grid Spread Markup** | $\Delta p_{\text{grid}}$| **\$0.2200 AUD/kWh** | Retail utility spread: $p_{\text{imp}} - p_{\text{exp}} = 0.30 - 0.08$. |

### 4.2 Transaction-Level Payoff Formulations

Because a household may participate in multiple bilateral trades at different transaction prices within the same hour, payoffs must be computed at **transaction-level granularity**.

Let $\mathcal{T}_k$ denote the set of cleared bilateral transactions at hour $k$. Each transaction $\text{tx} \in \mathcal{T}_k$ specifies: seller $i$, buyer $j$, cleared volume $q_{ij} > 0$ (kWh), and price $p_{ij} \in [0.08, 0.30]$ (AUD/kWh).

#### Seller Realized Financial Payoff
For seller $i \in N_S$ with physical surplus $s_i$:

$$q_i^{\text{sold}} = \sum_{j \in N_B} q_{ij}$$

$$U_i = \sum_{j \in N_B} q_{ij} p_{ij} + \big(s_i - q_i^{\text{sold}}\big) p_{\text{exp}}$$

Incremental Benefit relative to grid-only baseline ($U_i^{\text{grid-only}} = s_i \cdot p_{\text{exp}}$):

$$\Delta U_i = U_i - U_i^{\text{grid-only}} = \sum_{j \in N_B} q_{ij} \big(p_{ij} - p_{\text{exp}}\big)$$

#### Buyer Realized Financial Payoff
For buyer $j \in N_B$ with physical deficit $d_j$:

$$q_j^{\text{bought}} = \sum_{i \in N_S} q_{ij}$$

$$U_j = -\left( \sum_{i \in N_S} q_{ij} p_{ij} + \big(d_j - q_j^{\text{bought}}\big) p_{\text{imp}} \right)$$

Incremental Benefit relative to grid-only baseline ($U_j^{\text{grid-only}} = -d_j \cdot p_{\text{imp}}$):

$$\Delta U_j = U_j - U_j^{\text{grid-only}} = \sum_{i \in N_S} q_{ij} \big(p_{\text{imp}} - p_{ij}\big)$$

---

### 4.3 Financial Conservation and Wealth Transfers

1. **Physical Energy Conservation:**
   $$\sum_{i \in N_S} q_i^{\text{sold}} = \sum_{i \in N_S} \sum_{j \in N_B} q_{ij} = \sum_{j \in N_B} \sum_{i \in N_S} q_{ij} = \sum_{j \in N_B} q_j^{\text{bought}} = Q_{\text{P2P}}$$
2. **Payment Conservation (Zero-Sum Internal Transfers):**
   $$\sum_{j \in N_B} P_j^{\text{P2P}} = \sum_{j \in N_B} \sum_{i \in N_S} q_{ij} p_{ij} = \sum_{i \in N_S} \sum_{j \in N_B} q_{ij} p_{ij} = \sum_{i \in N_S} R_i^{\text{P2P}}$$
3. **Community Welfare Identity:**
   $$\sum_{i \in N} \Delta U_i = \sum_{i \in N_S} \sum_{j \in N_B} q_{ij} (p_{ij} - p_{\text{exp}}) + \sum_{j \in N_B} \sum_{i \in N_S} q_{ij} (p_{\text{imp}} - p_{ij}) = (p_{\text{imp}} - p_{\text{exp}}) Q_{\text{P2P}} = \Delta W_{\text{community}}$$
4. **Total Community Grid Expenditure:**
   $$C_{\text{grid}}^{\text{comm}} = \sum_{j \in N_B} (d_j - q_j^{\text{bought}}) p_{\text{imp}} - \sum_{i \in N_S} (s_i - q_i^{\text{sold}}) p_{\text{exp}}$$

---

## 5. Market-Clearing Mechanism Specification

### 5.1 Merit-Order Double Auction
1. **Order Book Sorting:**
   - Seller Asks: Ascending order of ask price $b_i^{\text{ask}}$ (merit order).
   - Buyer Bids: Descending order of bid price $b_j^{\text{bid}}$.
2. **Overlap Condition:** Trades clear while highest remaining buyer bid weakly exceeds lowest remaining seller ask: $b_{(1)}^{\text{bid}} \ge b_{(1)}^{\text{ask}}$.
3. **Transaction Price Formation:** $p_{ij} = (b_i^{\text{ask}} + b_j^{\text{bid}}) / 2$.

---

### 5.2 Deterministic Pro-Rata Tie-Breaking Specification

Tie-breaking among orders at identical price levels uses **pro-rata volume rationing**.

#### Case 1: Multiple Sellers with Tied Ask Prices Competing for Demand
Let $S_{\text{tied}} = \{ i \in N_S \mid b_i^{\text{ask}} = b^* \}$ be the set of sellers with identical ask $b^*$. Let $Q_{\text{tied}}^{\text{sell}} = \sum_{i \in S_{\text{tied}}} q_i^{\text{rem}}$ be their aggregate capacity. Let $q_j^{\text{rem}}$ be the buyer's requested demand at bid $b_j^{\text{bid}} \ge b^*$.

- If $Q_{\text{tied}}^{\text{sell}} \le q_j^{\text{rem}}$: All tied sellers clear 100% ($q_{ij} = q_i^{\text{rem}}$).
- If $Q_{\text{tied}}^{\text{sell}} > q_j^{\text{rem}}$: Proportional allocation across tied sellers:
  $$q_{ij} = q_i^{\text{rem}} \cdot \frac{q_j^{\text{rem}}}{Q_{\text{tied}}^{\text{sell}}}$$

#### Case 2: Multiple Buyers with Tied Bid Prices Competing for Supply
Let $B_{\text{tied}} = \{ j \in N_B \mid b_j^{\text{bid}} = b^* \}$ be the set of buyers with identical bid $b^*$. Let $Q_{\text{tied}}^{\text{buy}} = \sum_{j \in B_{\text{tied}}} q_j^{\text{rem}}$ be their aggregate demand. Let $q_i^{\text{rem}}$ be the seller's capacity at ask $b_i^{\text{ask}} \le b^*$.

- If $Q_{\text{tied}}^{\text{buy}} \le q_i^{\text{rem}}$: All tied buyers clear 100% ($q_{ij} = q_j^{\text{rem}}$).
- If $Q_{\text{tied}}^{\text{buy}} > q_i^{\text{rem}}$: Proportional allocation across tied buyers:
  $$q_{ij} = q_j^{\text{rem}} \cdot \frac{q_i^{\text{rem}}}{Q_{\text{tied}}^{\text{buy}}}$$

#### Case 3: Simultaneous Two-Sided Price Ties
If multiple sellers share ask $b_{\text{ask}}^*$ and multiple buyers share bid $b_{\text{bid}}^* \ge b_{\text{ask}}^*$:
1. Feasible volume: $Q_{\text{trade}} = \min(Q_{\text{tied}}^{\text{sell}}, Q_{\text{tied}}^{\text{buy}})$.
2. Allocated capacity per seller: $q_i^{\text{alloc}} = q_i^{\text{rem}} \cdot \frac{Q_{\text{trade}}}{Q_{\text{tied}}^{\text{sell}}}$.
3. Allocated volume per buyer: $q_j^{\text{alloc}} = q_j^{\text{rem}} \cdot \frac{Q_{\text{trade}}}{Q_{\text{tied}}^{\text{buy}}}$.
4. Bilinear bilateral allocation:
   $$q_{ij} = \frac{q_i^{\text{alloc}} \cdot q_j^{\text{alloc}}}{Q_{\text{trade}}}$$
   Notice that $\sum_{j} q_{ij} = q_i^{\text{alloc}}$ and $\sum_{i} q_{ij} = q_j^{\text{alloc}}$ algebraically.

#### Tolerance-Based Numerical Conservation Checks
To prevent breaking exact conservation, quantities are **never** truncated independently. Instead, floating-point balance is enforced using double-precision tolerance checks:
$$\left| \sum_{j \in N_B} q_{ij} - q_i^{\text{alloc}} \right| < 10^{-6}\text{ kWh} \quad \forall i \in N_S, \qquad \left| \sum_{i \in N_S} q_{ij} - q_j^{\text{alloc}} \right| < 10^{-6}\text{ kWh} \quad \forall j \in N_B$$
$$\left| \sum_{i \in N_S} q_i^{\text{sold}} - \sum_{j \in N_B} q_j^{\text{bought}} \right| < 10^{-6}\text{ kWh}, \qquad \left| \sum_{j \in N_B} P_j^{\text{P2P}} - \sum_{i \in N_S} R_i^{\text{P2P}} \right| < 10^{-6}\text{ AUD}$$

---

## 6. Nash Equilibrium Definition and Computation Method

### 6.1 Formal Definition of Pure-Strategy Nash Equilibrium

Let $a_i \in A_i$ denote the price bid of active household $i$, and $a_{-i} = (a_j)_{j \ne i}$ denote opponents' bids. A strategy profile $a^* = (a_1^*, \dots, a_N^*) \in \prod_{i \in N} A_i$ is a **Pure-Strategy Nash Equilibrium (PNE)** if:

$$U_i(a_i^*, a_{-i}^*) \ge U_i(a_i, a_{-i}^*) \quad \forall a_i \in A_i, \quad \forall i \in N$$

- **Strict Equilibrium:** $U_i(a_i^*, a_{-i}^*) > U_i(a_i, a_{-i}^*)$ for all feasible deviations $a_i \ne a_i^*$.
- **Weak Equilibrium:** Equality holds for at least one deviation $a_i' \ne a_i^*$.

---

### 6.2 Phase 8B Action-Space and Combinatorial Complexity

Phase 8B implements **price-only bidding** with quantities fixed to physical flows. Active players bid over:

$$\mathcal{P} = \{0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30\} \quad (|\mathcal{P}| = 7)$$

#### Strategy Profile Calculations for Phase 8B
The combinatorial profile space depends strictly on the number of active households ($|N_{\text{active}}|$):

| Market Configuration | Active Players | Strategy Profile Space ($|A|$) | Alternative Deviations per Profile | Computation Time per Hour |
| :--- | :---: | :---: | :---: | :---: |
| **3 Active Players** (e.g. 1 Seller, 2 Buyers) | 3 | $7 \times 7 \times 7 = \mathbf{343}$ | $3 \times (7 - 1) = \mathbf{18}$ | $\approx 0.008\text{ s}$ |
| **2 Active Players** (e.g. 1 Seller, 1 Buyer, 1 Inactive) | 2 | $7 \times 7 = \mathbf{49}$ | $2 \times (7 - 1) = \mathbf{12}$ | $\approx 0.001\text{ s}$ |
| **1 Active Player** (No counterparty) | 1 | $7$ | $0$ (No trade possible) | $< 0.0001\text{ s}$ |
| **0 Active Players** (All inactive / self-sufficient) | 0 | $1$ (Trivial empty profile) | $0$ | $< 0.0001\text{ s}$ |

> [!IMPORTANT]
> **Status of the 15-Action / 3,375-Profile Formulation:** The previously proposed 15-action grid ($1 \text{ No-Trade} + 2 \text{ Quantities} \times 7 \text{ Prices}$) and its corresponding 3,375 profile space belong to a **joint price-quantity bidding game**. This formulation is **explicitly deferred** to a future phase (Phase 8C/F) after the Phase 8B price-only benchmark is validated.

---

### 6.3 Exhaustive Equilibrium Solver Algorithm

The Phase 8B solver executes the identical clearing, pricing, and pro-rata allocation logic as the simulator:

```
Algorithm 1: Exhaustive Pure Nash Equilibrium Solver (Phase 8B)
-----------------------------------------------------------------------------------
Input: Surpluses (s_1, s_2, s_3), deficits (d_1, d_2, d_3), tariffs (p_imp, p_exp)
Output: List of verified PNE profiles, strictness flags, and community welfare

1. Determine active players:
     N_S = {i | s_i > 1e-6}, N_B = {j | d_j > 1e-6}
     If |N_S| == 0 or |N_B| == 0:
       Return {status: "NO_TRADE_HOUR", equilibria: []}

2. Assign action spaces:
     For i ∈ N_S: A_i = P (7 ask prices)
     For j ∈ N_B: A_j = P (7 bid prices)
     For k ∈ N_0: A_k = {None} (Inactive)

3. For each profile a ∈ prod_{i ∈ N_active} A_i:
     Execute market clearing M(a) -> get allocations and prices.
     Compute payoff vector U(a) using Eq. (14) & (18).
     Store in payoff tensor T.

4. Initialize equilibria list EQ = [].
5. For each profile a* ∈ prod_{i} A_i:
     is_nash = True
     is_strict = True
     
     For each active player i:
       current_payoff = U_i(a_i*, a_{-i}*)
       For each deviation a_i' ∈ A_i \ {a_i*}:
         dev_payoff = U_i(a_i', a_{-i}*)
         If dev_payoff > current_payoff + 1e-6:
           is_nash = False
           Break
         Else if abs(dev_payoff - current_payoff) <= 1e-6:
           is_strict = False
       If not is_nash:
         Break
         
     If is_nash:
       W = (p_imp - p_exp) * Q_P2P(a*)
       EQ.append({profile: a*, payoffs: U(a*), strict: is_strict, welfare: W})

6. If len(EQ) == 0:
     Return {status: "NO_PURE_NASH_EQUILIBRIUM", equilibria: []}
   Else:
     Calculate Pareto-undominated subset EQ_Pareto.
     Return {status: "SUCCESS", equilibria: EQ, pareto_equilibria: EQ_Pareto}
```

---

### 6.4 Reporting and Deterministic Representative Selection

#### Full Reporting Invariant
**Never remove equilibria from the reported results.** The simulation exports all detected equilibria, their strictness classifications, and their community welfare levels.

#### Deterministic Selection Heuristic for Single-Profile Reporting
When a single representative profile must be selected for downstream benchmark tables:
1. Filter to the Pareto-undominated set $\text{EQ}_{\text{Pareto}}$.
2. If $|\text{EQ}_{\text{Pareto}}| = 1$, select that profile.
3. If $|\text{EQ}_{\text{Pareto}}| > 1$, apply the **midpoint-proximity heuristic tie-breaker**:
   - For equilibria with $Q_{\text{P2P}} > 0$: compute volume-weighted price distance:
     $$D_{\text{mid}}(a^*) = \left| \bar{p}_{\text{tx}}(a^*) - \$0.1900 \right|$$
   - For equilibria with $Q_{\text{P2P}} = 0$ (where $\bar{p}_{\text{tx}}$ is undefined): set $D_{\text{mid}}(a^*) = +\infty$.
   - Select: $\arg\min_{a^* \in \text{EQ}_{\text{Pareto}}} D_{\text{mid}}(a^*)$.
4. If a tie persists (equal $D_{\text{mid}}$):
   - Tie-break 1: Select profile maximizing community welfare $\Delta W(a^*)$.
   - Tie-break 2: Select profile minimizing transaction price standard deviation $\text{Std}(p_{\text{tx}})$.
   - Tie-break 3: Deterministic lexicographical tie-break by player price indices.

---

## 7. Numerical Walkthroughs of the Strategic Game

### 7.1 Example 1: One Seller and Two Competing Buyers
- Seller (H001): $s_1 = 1.0\text{ kWh}$, ask $b_1^{\text{ask}} = \$0.16/\text{kWh}$.
- Buyer 1 (H002): $d_2 = 0.8\text{ kWh}$, bid $b_2^{\text{bid}} = \$0.26/\text{kWh}$.
- Buyer 2 (H003): $d_3 = 0.8\text{ kWh}$, bid $b_3^{\text{bid}} = \$0.22/\text{kWh}$.

#### Clearing:
- H002 bids higher than H003 ($\$0.26 > \$0.22$); H002 clears first.
- Match 1: $q_{12} = 0.8\text{ kWh} @ p_{12} = (0.16 + 0.26)/2 = \$0.210/\text{kWh}$. Payment = $\$0.168$.
- Match 2: $q_{13} = 0.2\text{ kWh} @ p_{13} = (0.16 + 0.22)/2 = \$0.190/\text{kWh}$. Payment = $\$0.038$.
- H003 imports remaining $0.6\text{ kWh}$ from grid at $\$0.30 = \$0.180$.
- Payoffs: $\Delta U_1 = +\$0.126\text{ AUD}$, $\Delta U_2 = +\$0.072\text{ AUD}$, $\Delta U_3 = +\$0.022\text{ AUD}$.
- Total Community Welfare: $\Delta W = \$0.126 + \$0.072 + \$0.022 = \$0.220\text{ AUD} = 1.0 \times (0.30 - 0.08)$.

---

### 7.2 Example 2: Competing Sellers and Pro-Rata Tie-Breaking
- Seller 1 (H001): $s_1 = 0.6\text{ kWh}$, ask $b_1^{\text{ask}} = \$0.16/\text{kWh}$.
- Seller 2 (H002): $s_2 = 0.6\text{ kWh}$, ask $b_2^{\text{ask}} = \$0.16/\text{kWh}$ (Tied ask price).
- Buyer (H003): $d_3 = 0.8\text{ kWh}$, bid $b_3^{\text{bid}} = \$0.22/\text{kWh}$.

#### Pro-Rata Clearing:
- Tied supply $Q_{\text{tied}}^{\text{sell}} = 1.2\text{ kWh} >$ demand $0.8\text{ kWh}$.
- Pro-rata factor: $\alpha = 0.8 / 1.2 = 2/3$.
- Each seller sells $0.6 \times (2/3) = 0.4\text{ kWh} @ p_{\text{tx}} = (0.16 + 0.22)/2 = \$0.190/\text{kWh}$.
- Both sellers export remaining $0.2\text{ kWh}$ to grid at $\$0.08/\text{kWh}$.
- Both sellers earn identical incremental benefits: $0.4 \times (0.19 - 0.08) = +\$0.044\text{ AUD}$.

---

## 8. Preserving Uncertainty for the Later Stochastic Game

In Phase 8E, the game extends to expected payoffs across Monte Carlo uncertainty realizations.

### 8.1 Stochastic Strategy Space and Complexity
In Phase 8E, households submit two-sided contingent price bids ex-ante:

$$a_i = (b_i^{\text{ask}}, b_i^{\text{bid}}) \in \mathcal{P} \times \mathcal{P}$$

With 7 price levels on each side:

$$|A_i^{\text{ex-ante}}| = 7 \times 7 = \mathbf{49 \text{ actions per household}}$$

For a 3-household microgrid:

$$|A^{\text{ex-ante}}| = 49 \times 49 \times 49 = \mathbf{117,649 \text{ joint strategy profiles}}$$

> [!IMPORTANT]
> **Action Space Demarcation:** The 49-action / 117,649-profile space applies exclusively to the Phase 8E stochastic game. It is completely separate from the 7-action / 343-profile deterministic ex-post game of Phase 8B.

### 8.2 Expected-Payoff Formulation
$$\bar{U}_i(a_i, a_{-i}) = \mathbb{E}_{\omega \sim \Omega} \left[ U_i\big(a_i, a_{-i}, \omega\big) \right] = \sum_{\omega \in \Omega} \pi_\omega U_i\big(a_i, a_{-i}, \omega\big)$$

By Jensen's inequality ($\mathbb{E}[\min(s, d)] \le \min(\mathbb{E}[s], \mathbb{E}[d])$), expected payoffs are evaluated scenario-by-scenario as $\mathbb{E}[U(\omega)]$, never as $U(\mathbb{E}[\omega])$.

---

## 9. Comprehensive Evaluation Metrics

We specify 16 formal metrics categorized into **Market Activity Metrics** and **Economic Welfare Metrics**:

### 9.1 Market Activity Metrics
1. **Total P2P Traded Volume ($Q_{\text{traded}}$):** $Q_{\text{traded}} = \sum_{k=1}^H \sum_{\text{tx}} q_{\text{tx}, k}$ (kWh).
2. **Tradeable Hours ($H_{\text{trade}}$):** Hours where $\sum s_i^{\text{act}} > 10^{-6}$ and $\sum d_j^{\text{act}} > 10^{-6}$.
3. **Active Market Clearing Hours ($H_{\text{cleared}}$):** Hours with $Q_{\text{traded}} > 10^{-6}\text{ kWh}$.
4. **Liquidity Execution Ratios:**
   - **Hourly Ratio:** For hour $k$, if $\min(S_{\text{avail}, k}, D_{\text{avail}, k}) > 10^{-6}$:
     $$\rho_{\text{exec}, k} = \frac{Q_{\text{traded}, k}}{\min(S_{\text{avail}, k}, D_{\text{avail}, k})}$$
     If available capacity is zero, $\rho_{\text{exec}, k}$ is undefined (excluded from hourly average).
   - **Average Hourly Liquidity Ratio:**
     $$\bar{\rho}_{\text{exec}} = \frac{1}{H_{\text{trade}}} \sum_{k \in \mathcal{H}_{\text{trade}}} \rho_{\text{exec}, k}$$
   - **Aggregate Portfolio Liquidity Ratio (Volume-Weighted):**
     $$\rho_{\text{exec}}^{\text{agg}} = \frac{\sum_{k=1}^H Q_{\text{traded}, k}}{\sum_{k=1}^H \min(S_{\text{avail}, k}, D_{\text{avail}, k})}$$
5. **Unmatched Seller Surplus ($S_{\text{unmatched}}$):** Total solar exported to central grid (kWh).
6. **Unmet Buyer Deficit ($D_{\text{unmatched}}$):** Total deficit imported from central grid (kWh).
7. **Volume-Weighted Average Clearing Price ($\bar{p}_{\text{tx}}$):** $\bar{p}_{\text{tx}} = \frac{\sum q_{\text{tx}} p_{\text{tx}}}{Q_{\text{traded}}}$ (AUD/kWh).

### 9.2 Economic and Welfare Metrics
8. **Individual Realized Net Cost ($C_i^{\text{net}}$):** Formula in Section 4.2.
9. **Individual Economic Savings ($\Delta C_i$):** $C_i^{\text{grid-only}} - C_i^{\text{net}}$ (AUD).
10. **Total Community Grid Expenditure ($C_{\text{grid}}^{\text{comm}}$):** Net cash paid to utility.
11. **Aggregate Community Economic Welfare Gain ($\Delta W$):** $\$0.22 \times Q_{\text{traded}}$ (AUD).
12. **Gross Seller Revenue ($\text{Rev}_S$) and Buyer Expenditure ($\text{Exp}_B$):** Internal cash flow totals.
13. **Individual Rationality Rates:**
    - **Per-Household Rate:** $\rho_{\text{IR}, i} = \frac{1}{H} \sum_{k=1}^H \mathbb{I}(\Delta U_{i, k} \ge -10^{-6})$.
    - **Portfolio Aggregation Rate:** $\rho_{\text{IR}}^{\text{port}} = \frac{1}{|N| \cdot H} \sum_{k=1}^H \sum_{i \in N} \mathbb{I}(\Delta U_{i, k} \ge -10^{-6})$.
14. **Budget Balance Residual ($\text{Res}_{\text{BB}}$):** $|\text{Exp}_B - \text{Rev}_S| < 10^{-6}\text{ AUD}$.
15. **Pareto Improvement Proportion ($\rho_{\text{Pareto}}$):** Fraction of tradeable hours where:
    $$\forall i \in N, \; \Delta U_{i, k} \ge -10^{-6}\text{ AUD} \quad \text{AND} \quad \exists j \in N, \; \Delta U_{j, k} > +10^{-6}\text{ AUD}$$
16. **Nash Equilibrium Distribution:** Profile counts, strictness proportions, and uniqueness frequencies.

---

## 10. Summary of Final Mathematical Decisions and Unresolved Assumptions

### 10.1 Final Mathematical Decisions (Approved for Implementation)

| Mathematical Domain | Final Specification Decision |
| :--- | :--- |
| **Market Architecture** | **Model B (Double Auction with Bilateral Midpoint Pricing)**. Sellers sorted by ask ascending; buyers by bid descending. $p_{\text{tx}} = (b_{\text{ask}} + b_{\text{bid}})/2$. |
| **Information Model** | **Two-track architecture:** (1) Ex-post deterministic benchmark for baseline comparison; (2) Ex-ante causal bidding with physical clamping for stochastic deployment. |
| **Action Space (Phase 8B)** | **Price-Only Discretization:** $b \in \{0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30\}$ ($|\mathcal{P}| = 7$). Quantities fixed to physical flows ($q = \text{flow}^{\text{act}}$). $|A| = 7^3 = 343$ profiles; 18 deviations. Inactive households receive $A_i = \{\emptyset\}$. |
| **Tie-Breaking Rule** | **Strict Pro-Rata Rationing:** Proportional volume allocation with bilinear bilateral decomposition and tolerance-based validation. |
| **Financial Settlement**| **Transaction-Level Accounting:** Payoffs computed directly from bilateral ledger entries: $\Delta U_i = \sum q_{ij}(p_{ij} - p_{\text{exp}})$. |
| **Equilibrium Solver** | **Exhaustive Enumeration:** Detect all pure equilibria; classify strict vs weak; identify Pareto frontier; output `NO_PURE_NASH_EQUILIBRIUM` if empty; apply midpoint-proximity heuristic tie-breaker only when single profile is required. |

### 10.2 Remaining Unresolved Modeling Assumptions

1. **Phase 8E Ex-Ante Quantity Policy Function:** The exact functional specification of $\bar{q}_i = f(\hat{D}, \hat{S}, \Omega)$ (e.g., mean point forecast vs scenario percentiles) will be calibrated and validated during Phase 8E.
2. **Mixed-Strategy Equilibria Handling:** If an hour possesses zero pure Nash equilibria on the discrete grid, the algorithm records `NO_PURE_NASH_EQUILIBRIUM` and reverts to standalone grid settlement. Mixed-strategy LP solving is deferred.
3. **Strategic Capacity Withholding:** Joint price-quantity bidding ($|A_i| = 15, |A| = 3,375$) is deferred to Phase 8C/F.

---

## 11. Staged Phase 8 Implementation Roadmap

- **Phase 8A — Mathematical Formulation & Design Specification:** COMPLETE (This Document). Zero source code changes.
- **Phase 8B — Deterministic Strategic Market Prototype:** Implement `src/game/strategic_market.py` with price-only double auction clearing, pro-rata tie-breaking, and frozen Phase 7 battery dispatch ($|A| = 343$).
- **Phase 8C — Nash Equilibrium Solver & Verification:** Implement exhaustive solver, best-response validation, and unit tests against hand-calculated matrices.
- **Phase 8D — Full Historical 1,752-Hour Benchmark Evaluation:** Execute full simulation across all held-out test hours; generate `reports/phase8_benchmark_metrics.csv`.
- **Phase 8E — Stochastic Expected-Payoff Market Extension:** Extend to Monte Carlo scenario evaluation using two-sided contingent bids ($|A_i| = 49, |A| = 117,649$).
- **Phase 8F — Optional Market-Aware Battery Dispatch:** Bilevel MPC feedback (deferred until 8B-8E are validated).

---
*End of Final Corrected Design Specification — Ready for Phase 8B Implementation.*
