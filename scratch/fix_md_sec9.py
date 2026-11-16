with open("build_master_integrated_report.py", "r", encoding="utf-8") as f:
    text = f.read()

pos_md = text.find('md_content = f"""')
pre_md = text[:pos_md]
md_sub = text[pos_md:]

target_md_ix = """![Empirical Stability Boxplots]({FIG_DIR_MC / '03_p2p_profit_distribution_1000_scenarios.png'})  
*Fig. 13. Empirical P2P trading profit distributions (boxplots and kernel density estimates) across 1,000 Monte Carlo scenarios.*

---"""

replacement_md_ix = """![Empirical Stability Boxplots]({FIG_DIR_MC / '03_p2p_profit_distribution_1000_scenarios.png'})  
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
- **Phase 1: Nighttime Baseload and Battery Depletion (Hours 00:00 – 07:00):** Solar generation is strictly zero. Each household discharges its battery (up to the 2.5 kW / 10% SOC limit) to cover baseload consumption (refrigeration, standby loads). By 02:00, batteries reach their 10% SOC floor. Because all households face net deficits and zero solar is available, the P2P pool is completely inactive ($Q_{{\\text{{trade}}}} = 0$). All remaining deficits are imported from the utility grid at $0.30/kWh.
- **Phase 2: Morning Solar Ramp & Behind-the-Meter Storage (Hours 08:00 – 10:00):** Solar production ramps upward. In accordance with greedy dispatch, each prosumer directs 100% of solar generation into its local battery first ($P_{{\\text{{ch}}}} \\le 2.5\\text{{ kW}}$). Because local batteries absorb the solar surplus, net export to the community pool remains zero ($S_i^{{\\text{{net}}}} = 0$). The P2P pool remains quiet while domestic batteries replenish.
- **Phase 3: Midday Battery Saturation & Active P2P Market Clearing (Hours 11:00 – 15:00):** Solar prosumer H001 generates 8.73 kWh of cumulative PV energy. By Hour 14, H001's battery reaches the 90% SOC ceiling (4.5 kWh). Because the battery cannot accept further charge, surplus solar spills over into the community pool as physical net surplus ($S_{{\\text{{pool}}}} = 1.81\\text{{ kWh}}$). High-demand prosumer H004 and neighbors H002 and H003 have unmet deficits. Demand pressure $\\lambda_t$ is calculated dynamically ($\\lambda_t \\approx 0.67$), establishing the market-clearing P2P price at $0.1534/kWh. H001 sells 0.098 kWh to H002, 0.150 kWh to H003, and 0.728 kWh to H004. At Hour 15, H001 clears 0.348 kWh with H003 at $0.2251/kWh. Both buyers and seller gain substantial economic margins.
- **Phase 4: Evening Peak Shaving (Hours 18:00 – 22:00):** Solar generation collapses to zero while domestic cooking, lighting, and entertainment loads surge. Households discharge their remaining stored midday solar energy, completely shaving the evening grid import peak and saving $0.30/kWh grid retail charges.

#### 2) Mathematical Coupling Proof: How Individual Player Profits Strictly Equal Community Profit:
A foundational mathematical property of our dynamic pricing mechanism is that community profit is not an abstract statistical aggregate—it is the exact mathematical sum of individual participant savings. Consider any hourly P2P transaction of volume $q$ traded at clearing price $P_{{\\text{{P2P}}}}$, where $P_{{\\text{{export}}}} \\le P_{{\\text{{P2P}}}} \\le P_{{\\text{{import}}}}$:
- **Seller Financial Gain:** By selling locally at $P_{{\\text{{P2P}}}}$ instead of exporting to the utility grid at $P_{{\\text{{export}}}} = \\$0.08/\\text{{kWh}}$, the seller earns an extra profit of: $\\Pi_{{\\text{{seller}}}} = q \\cdot (P_{{\\text{{P2P}}}} - P_{{\\text{{export}}}})$.
- **Buyer Financial Gain:** By purchasing locally at $P_{{\\text{{P2P}}}}$ instead of importing from the utility grid at $P_{{\\text{{import}}}} = \\$0.30/\\text{{kWh}}$, the buyer reduces its electricity bill by: $\\Pi_{{\\text{{buyer}}}} = q \\cdot (P_{{\\text{{import}}}} - P_{{\\text{{P2P}}}})$.
- **Total Community Welfare Identity:** Summing the gains of seller and buyer yields the community welfare gain:
  $$\\Pi_{{\\text{{community}}}} = \\Pi_{{\\text{{seller}}}} + \\Pi_{{\\text{{buyer}}}} = q \\cdot (P_{{\\text{{P2P}}}} - P_{{\\text{{export}}}}) + q \\cdot (P_{{\\text{{import}}}} - P_{{\\text{{P2P}}}}) = q \\cdot (P_{{\\text{{import}}}} - P_{{\\text{{export}}}}) = q \\cdot (\\$0.30 - \\$0.08) = q \\cdot \\$0.22/\\text{{kWh}}$$

This identity provides profound insight: Every kilowatt-hour traded peer-to-peer captures the exact 22¢/kWh tariff spread that the utility retailer previously extracted from the neighborhood. The dynamic price $P_{{\\text{{P2P}}}}$ functions purely as an internal value-sharing rule that fairly distributes this 22¢/kWh margin between buyer and seller based on real-time market pressure. Consequently, whenever any household gains profit, the entire community gains profit by the identical amount. In the single-day trace, H001 earns +$0.1221, H004 saves +$0.1068, H003 saves +$0.0481, and H002 saves +$0.0144, summing precisely to the community total of $0.2914 AUD/day.

---"""

if target_md_ix in md_sub:
    md_sub = md_sub.replace(target_md_ix, replacement_md_ix, 1)
    with open("build_master_integrated_report.py", "w", encoding="utf-8") as f:
        f.write(pre_md + md_sub)
    print("Successfully replaced Section IX in MD!")
else:
    print("Target string not found in md_sub!")
