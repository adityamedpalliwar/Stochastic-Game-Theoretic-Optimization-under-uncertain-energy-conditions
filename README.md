# Stochastic Game-Theoretic Optimization under Uncertain Energy Conditions

A microgrid peer-to-peer (P2P) energy trading prototype that integrates:
1. **LSTM Next-Hour Forecasting** for household demand and rooftop solar generation.
2. **Monte Carlo Uncertainty Quantification** (1,000 empirical scenarios via residual resampling) enforcing physical constraints ($E \ge 0$).
3. **2-Household Normal-Form Energy Trading Game** under physical and financial conservation laws.
4. **Best-Response Analysis & Pure-Strategy Nash Equilibrium** solver.
5. **Stochastic vs. Deterministic Expected Payoff Optimization** demonstrating coordination gains and microgrid community welfare maximization.

---

## Quick Start: Terminal Demonstration for Teacher Presentation

To run the interactive terminal demonstration with colored outputs and all 5 stages:

```bash
# Run complete demonstration
python main.py

# Run in step-by-step interactive mode (pause between stages to explain to teacher)
python main.py --step-by-step

# Run with customized parameters
python main.py --hour "2013-06-08 10:00:00" --scenarios 1000 --seed 42
```

---

## Demonstration Structure

The terminal output is organized into 5 clear stages tailored for academic presentation:

1. **Stage 1: Monte Carlo Uncertainty Quantification**
   - Historical validation residual distributions ($e_t = y_t - \hat{y}_t$).
   - 1,000 physical realizations preserving demand-solar correlation.
   - Point forecast vs. scenario mean, std deviation, and 90% prediction intervals.
   - *Why this matters*: Explains why point forecasts fail under rapid weather variations and why uncertainty modeling is essential.

2. **Stage 2: Game Setup & Normal-Form Payoff Matrix**
   - Player 1 (H001, Seller) with available surplus ($+1.245\text{ kWh}$).
   - Player 2 (H002, Buyer) with required deficit ($-1.463\text{ kWh}$).
   - Retail grid tariffs: Import at $\$0.30/\text{kWh}$, Feed-in export credit at $\$0.08/\text{kWh}$.
   - Incentive-compatible mid-market P2P price: $\$0.19/\text{kWh}$ (splits the $22¢/\text{kWh}$ grid spread).
   - $2 \times 2$ payoff matrix in terms of net utility ($U_i = -\text{Net Expenditure}$).

3. **Stage 3: Best-Response Dynamics & Strategic Dominance**
   - Detailed best-response mappings: $BR_i(a_{-i}) = \arg\max_{a_i} U_i(a_i, a_{-i})$.
   - Explains unilateral incentive to trade: H001 earns $+137.5\%$ more revenue; H002 reduces electricity cost by $31.2\%$.
   - Weak dominance of P2P participation.

4. **Stage 4: Nash Equilibrium Calculation & Community Savings**
   - Formal verification: $(\text{OFFER\_P2P}, \text{ACCEPT\_P2P})$ is the unique Pareto-dominant strict Nash equilibrium.
   - Financial breakdown: Baseline uncoordinated cost ($\$0.3393$) vs. Coordinated game cost ($\$0.0654$).
   - Community savings: $\$0.2739$ ($80.7\%$ total microgrid cost reduction).

5. **Stage 5: Stochastic Optimization & Teacher Presentation Takeaways**
   - Expected Payoff Matrix $E[U_i(a)]$ across 1,000 Monte Carlo scenarios.
   - Proof of stochastic stability under forecast uncertainty.
   - 4 Core Academic Takeaways:
     1. Solves the retail spread distortion.
     2. Mitigates the solar "duck curve" and transformer reverse power flow.
     3. Eliminates point-forecast vulnerability.
     4. Fully decentralized and privacy-preserving design.

---

## Running Tests

All 35 unit tests can be executed via:

```bash
python -m pytest
```
