"""
Builder script to generate reports/ieee_paper_revised.html and reports/ieee_paper_revised.md
with 100% clean typography, unclipped upright brackets, balanced word-spacing,
print-safe deep navy blue headings, and self-contained embedded images.
"""

import base64
from pathlib import Path

# Load images as base64
img_paths = {
    'fig1': Path('results/figures/simulate_five_house/05_demand_solar_profiles.png'),
    'fig2': Path('results/figures/simulate_five_house_monte_carlo/01_daily_cost_comparison_across_modes.png'),
    'fig3': Path('results/figures/simulate_five_house_monte_carlo/02_total_profit_and_cost_difference.png'),
    'fig4': Path('results/figures/simulate_five_house_monte_carlo/06_total_profit_difference_decomposition.png'),
    'fig5': Path('results/figures/simulate_five_house_monte_carlo/07_savings_portion_by_factor.png'),
    'fig6': Path('results/figures/simulate_five_house_monte_carlo/04_hourly_average_community_profit.png'),
    'fig7': Path('results/figures/simulate_five_house_monte_carlo/03_p2p_profit_distribution_1000_scenarios.png'),
}

b64_imgs = {}
for key, p in img_paths.items():
    if p.exists():
        data = base64.b64encode(p.read_bytes()).decode('ascii')
        b64_imgs[key] = f"data:image/png;base64,{data}"
    else:
        raise FileNotFoundError(f"Missing required figure: {p}")

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Stochastic Game-Theoretic Optimization for Peer-to-Peer Energy Trading with Distributed Battery Storage under Uncertainty</title>
<style>
    * {{
        box-sizing: border-box;
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
        color-adjust: exact !important;
    }}
    @page {{
        size: A4;
        margin: 0.65in 0.6in 0.65in 0.6in;
    }}
    body {{
        font-family: "Times New Roman", Times, serif;
        font-size: 9.5pt;
        line-height: 1.25;
        color: #000000;
        margin: 0;
        padding: 0;
        -webkit-font-smoothing: antialiased;
    }}
    .paper-header {{
        width: 100%;
        text-align: center;
        margin-bottom: 12pt;
    }}
    h1.paper-title {{
        font-size: 18.5pt;
        font-weight: bold;
        text-align: center;
        margin: 0 0 10pt 0;
        line-height: 1.2;
        color: #002b5b; /* Deep Academic Navy */
        -webkit-text-fill-color: #002b5b;
        letter-spacing: -0.2px;
    }}
    .authors-container {{
        display: flex;
        justify-content: space-between;
        text-align: center;
        margin-bottom: 12pt;
        font-size: 9pt;
        line-height: 1.2;
    }}
    .author-block {{
        flex: 1;
        padding: 0 6pt;
    }}
    .author-name {{
        font-size: 10pt;
        font-weight: bold;
        color: #003366; /* Classic Academic Navy */
        -webkit-text-fill-color: #003366;
    }}
    .author-dept {{
        font-style: italic;
    }}
    .author-org {{
        font-weight: 500;
    }}
    .abstract-box {{
        margin: 0 0.15in 10pt 0.15in;
        font-size: 8.5pt;
        text-align: justify;
        text-justify: auto;
        hyphens: auto;
        -webkit-hyphens: auto;
        line-height: 1.25;
        border-left: 2.5pt solid #003366;
        padding: 4pt 8pt;
        background: #f4f8fc;
    }}
    .abstract-box b {{
        font-weight: bold;
        color: #002b5b;
        -webkit-text-fill-color: #002b5b;
    }}
    .keywords-box {{
        margin: 2pt 0.15in 14pt 0.15in;
        font-size: 8.5pt;
        text-align: justify;
        text-justify: auto;
        line-height: 1.25;
    }}
    .keywords-box b {{
        color: #003366;
        -webkit-text-fill-color: #003366;
    }}

    /* Two-column layout with perfect hyphenation and natural word spacing */
    .two-column {{
        column-count: 2;
        column-gap: 0.22in;
        text-align: justify;
        text-justify: auto;
        hyphens: auto;
        -webkit-hyphens: auto;
        -ms-hyphens: auto;
        word-break: normal;
    }}

    h2.section-heading {{
        font-size: 9.5pt;
        font-weight: bold;
        text-align: center;
        text-transform: uppercase;
        margin-top: 11pt;
        margin-bottom: 5pt;
        break-after: avoid;
        page-break-after: avoid;
        color: #003366; /* Classic Academic Navy Blue */
        -webkit-text-fill-color: #003366;
        border-bottom: 0.5pt solid #c9daf8;
        padding-bottom: 1.5pt;
        letter-spacing: 0.3px;
    }}
    h3.subsection-heading {{
        font-size: 9.5pt;
        font-weight: bold;
        font-style: italic;
        margin-top: 8pt;
        margin-bottom: 3pt;
        break-after: avoid;
        page-break-after: avoid;
        color: #004c8c; /* Slate Navy Blue */
        -webkit-text-fill-color: #004c8c;
    }}
    p {{
        margin-top: 0;
        margin-bottom: 4.5pt;
        text-indent: 11pt;
        line-height: 1.25;
        text-align: justify;
        text-justify: auto;
        hyphens: auto;
        -webkit-hyphens: auto;
    }}
    p.no-indent {{
        text-indent: 0;
    }}

    /* Equation row formatting: upright brackets, upright functions, clean single-line fit */
    .eq-row {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: 4pt 0;
        page-break-inside: avoid;
        break-inside: avoid;
        width: 100%;
    }}
    .eq-math {{
        flex: 1;
        text-align: center;
        font-family: "Cambria Math", "Times New Roman", serif;
        font-style: normal; /* Normal font ensures all brackets, numbers, commas, and operators remain upright */
        font-size: 8.4pt;
        color: #0f172a;
        white-space: nowrap;
        letter-spacing: normal;
    }}
    .eq-math i {{
        font-style: italic;
    }}
    .eq-math sub, .eq-math sup {{
        font-size: 72%;
        line-height: 0;
        position: relative;
        vertical-align: baseline;
    }}
    .eq-math sup {{
        top: -0.45em;
    }}
    .eq-math sub {{
        bottom: -0.22em;
    }}
    .eq-tag {{
        flex-shrink: 0;
        font-family: "Times New Roman", serif;
        font-style: normal;
        font-size: 8.5pt;
        font-weight: bold;
        color: #003366;
        -webkit-text-fill-color: #003366;
        padding-left: 4pt;
        white-space: nowrap;
    }}

    /* Tables */
    table.data-table {{
        width: 100%;
        margin: 6pt 0;
        border-collapse: collapse;
        font-size: 7.2pt;
        line-height: 1.15;
        text-align: center;
        border-top: 1.2pt solid #003366;
        border-bottom: 1.2pt solid #003366;
        page-break-inside: avoid;
        break-inside: avoid;
    }}
    table.data-table th {{
        border-top: 0.8pt solid #003366;
        border-bottom: 0.8pt solid #003366;
        padding: 3pt 1.5pt;
        font-weight: bold;
        background-color: #eef4fa;
        color: #002b5b;
        -webkit-text-fill-color: #002b5b;
    }}
    table.data-table td {{
        padding: 2.2pt 1.5pt;
        border-bottom: 0.5pt solid #e2e8f0;
    }}
    .table-caption {{
        font-size: 7.5pt;
        font-weight: bold;
        text-align: center;
        text-transform: uppercase;
        margin-bottom: 2pt;
        margin-top: 8pt;
        color: #003366;
        -webkit-text-fill-color: #003366;
        page-break-after: avoid;
        break-after: avoid;
    }}

    /* Figures */
    .figure-container {{
        width: 100%;
        margin: 7pt 0;
        text-align: center;
        page-break-inside: avoid;
        break-inside: avoid;
    }}
    .figure-container img {{
        width: 100%;
        max-width: 100%;
        height: auto;
        max-height: 195px;
        object-fit: contain;
        display: block;
        margin: 0 auto;
        border: 0.5pt solid #bcd2e8;
        border-radius: 2pt;
    }}
    .figure-caption {{
        font-size: 7.5pt;
        text-align: justify;
        margin-top: 3pt;
        line-height: 1.18;
        hyphens: auto;
        -webkit-hyphens: auto;
    }}
    .figure-caption b {{
        color: #003366;
        -webkit-text-fill-color: #003366;
    }}

    /* References Table Layout: Eliminates bracket clipping */
    table.ref-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 7.5pt;
        line-height: 1.18;
        margin-top: 4pt;
    }}
    table.ref-table td.ref-num {{
        width: 20pt;
        min-width: 20pt;
        vertical-align: top;
        font-weight: bold;
        color: #003366;
        -webkit-text-fill-color: #003366;
        white-space: nowrap;
        padding-top: 1pt;
    }}
    table.ref-table td.ref-body {{
        vertical-align: top;
        padding-bottom: 3.5pt;
        text-align: justify;
        hyphens: auto;
        -webkit-hyphens: auto;
    }}

    /* Print-Specific Engine Overrides: Guarantees rich colors in saved PDF */
    @media print {{
        * {{
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
            color-adjust: exact !important;
        }}
        body {{
            color: #000000 !important;
        }}
        h1.paper-title {{
            color: #002b5b !important;
            -webkit-text-fill-color: #002b5b !important;
        }}
        .author-name {{
            color: #003366 !important;
            -webkit-text-fill-color: #003366 !important;
        }}
        h2.section-heading {{
            color: #003366 !important;
            -webkit-text-fill-color: #003366 !important;
            border-bottom: 0.75pt solid #003366 !important;
            page-break-after: avoid;
            break-after: avoid;
        }}
        h3.subsection-heading {{
            color: #004c8c !important;
            -webkit-text-fill-color: #004c8c !important;
            page-break-after: avoid;
            break-after: avoid;
        }}
        .abstract-box {{
            border-left: 2.5pt solid #003366 !important;
            background-color: #f1f6fa !important;
        }}
        .abstract-box b, .keywords-box b {{
            color: #002b5b !important;
            -webkit-text-fill-color: #002b5b !important;
        }}
        .eq-tag {{
            color: #003366 !important;
            -webkit-text-fill-color: #003366 !important;
        }}
        table.data-table {{
            border-top: 1.2pt solid #003366 !important;
            border-bottom: 1.2pt solid #003366 !important;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        table.data-table th {{
            background-color: #e8f0f8 !important;
            color: #002b5b !important;
            -webkit-text-fill-color: #002b5b !important;
            border-top: 1pt solid #003366 !important;
            border-bottom: 1pt solid #003366 !important;
        }}
        .table-caption, .figure-caption b, table.ref-table td.ref-num {{
            color: #003366 !important;
            -webkit-text-fill-color: #003366 !important;
        }}
    }}
</style>
</head>
<body>

<div class="paper-header">
    <h1 class="paper-title">Stochastic Game-Theoretic Optimization for Peer-to-Peer Energy Trading with Distributed Battery Storage under Uncertainty</h1>
    
    <div class="authors-container">
        <div class="author-block">
            <div class="author-name">Aditya</div>
            <div class="author-dept">Department of Mathematics</div>
            <div class="author-org">Sardar Vallabhbhai National Institute of Technology (SVNIT)</div>
            <div>Surat, Gujarat, India</div>
            <div>u24mc003@amhd.svnit.ac.in</div>
        </div>
        <div class="author-block">
            <div class="author-name">Heet</div>
            <div class="author-dept">Department of Mathematics</div>
            <div class="author-org">Sardar Vallabhbhai National Institute of Technology (SVNIT)</div>
            <div>Surat, Gujarat, India</div>
            <div>u24mc019@amhd.svnit.ac.in</div>
        </div>
        <div class="author-block">
            <div class="author-name">Dimpal</div>
            <div class="author-dept">Department of Mathematics</div>
            <div class="author-org">Sardar Vallabhbhai National Institute of Technology (SVNIT)</div>
            <div>Surat, Gujarat, India</div>
            <div>u24mc020@amhd.svnit.ac.in</div>
        </div>
    </div>
</div>

<div class="abstract-box">
    <b><i>Abstract</i>&mdash;Rapid proliferation of residential rooftop photovoltaics and battery energy storage systems necessitates decentralized market mechanisms to overcome retail feed-in tariff distortions. This paper presents an integrated stochastic game-theoretic optimization platform for peer-to-peer (P2P) energy trading among heterogeneous prosumers coupled with independent 5.0 kWh physical battery energy storage systems. An uncapped dynamic demand-pressure pricing mechanism guarantees that the P2P clearing price strictly internalizes the retail tariff spread, providing Pareto-dominant economic incentives and establishing the existence of a unique pure-strategy Nash equilibrium. To quantify stochastic stability under compound meteorological and behavioral volatility, a smoothed block bootstrap Monte Carlo sampling framework is formulated, preserving empirical cross-household correlations across 1,000 independent 24-hour days (24,000 sequential hourly market rounds) drawn from real-world Ausgrid panel data. Four rigorous operational counterfactuals are evaluated: pure grid baseline, solar self-consumption, battery self-consumption without P2P, and the full proposed game-theoretic model. Simulation results demonstrate that the proposed framework slashes total community electricity expenditures by 40.07%, saving an average of $10.56 AUD/day across the microgrid (reducing daily community energy expenditure from $26.36/day under pure grid reliance down to $15.80/day under coordinated trading). Factor decomposition confirms that while solar self-consumption ($5.52 AUD/day, 52.3%) and battery storage ($4.50 AUD/day, 42.6%) furnish substantial baseline arbitrage, P2P software coordination delivers an additional $0.54 AUD/day (5.1% of community savings, and up to 19.1% for high-demand consumers) with zero marginal hardware expenditure. Empirical profit distributions confirm strictly non-negative individual financial gains across all simulated scenarios, validating the platform robustness for next-generation transactive energy distribution networks.</b>
</div>

<div class="keywords-box">
    <b><i>Keywords</i>&mdash;Peer-to-peer energy trading, game theory, battery energy storage systems, Nash equilibrium, dynamic pricing, Monte Carlo simulation, prosumer microgrid, uncertainty quantification.</b>
</div>

<div class="two-column">

<h2 class="section-heading">I. Introduction</h2>
<p>Distributed renewable energy resources, specifically residential rooftop photovoltaics (PV) and battery energy storage systems (BESS), are fundamentally restructuring modern low-voltage distribution grids&nbsp;[1]. Traditionally passive domestic electricity consumers are rapidly transforming into active prosumers capable of localized generation and load modulation&nbsp;[2], [3].</p>

<p>A primary barrier to efficient residential energy utilization is the substantial structural spread between retail import tariffs and feed-in export tariffs imposed by utility retailers&nbsp;[4]. In typical residential pricing schemes&mdash;such as those across the Australian National Electricity Market (NEM)&mdash;homeowners import electricity from the grid at approximately $0.30/kWh while receiving a feed-in credit of only $0.08/kWh for exported solar. This 22&cent;/kWh spread creates an economic distortion: prosumers with abundant midday solar generation receive negligible financial compensation, while adjacent non-solar neighbors are forced to import energy from centralized generation at full retail price.</p>

<p>Peer-to-peer (P2P) local energy trading has emerged as an attractive market framework to internalize this spread&nbsp;[5], [6]. By enabling direct, localized electricity transactions between prosumers and consumers within a distribution feeder, P2P markets allow prosumers to sell surplus energy at prices above the utility export credit (<i>P</i><sub>export</sub> = $0.08/kWh) while offering consumers energy below the grid import rate (<i>P</i><sub>import</sub> = $0.30/kWh). However, real-world residential microgrids operate under stochastic weather variations, unpredictable consumer occupancy patterns, and physical battery degradation constraints, making static or centralized optimization brittle&nbsp;[7], [8].</p>

<p>To address these challenges, this paper presents an integrated stochastic game-theoretic optimization platform for residential microgrids. The principal contributions of this work are as follows: (1) an <i>N</i>-player normal-form energy trading game coupling heterogeneous residential prosumers with independent 5.0 kWh physical battery energy storage systems; (2) an uncapped dynamic demand-pressure pricing mechanism guaranteeing Pareto-dominant coordination; (3) a smoothed block bootstrap Monte Carlo sampling framework evaluating 1,000 independent 24-hour days (24,000 sequential hourly market rounds) over real-world Ausgrid panel data; and (4) a rigorous four-mode counterfactual evaluation isolating the exact financial dividends of solar (52.3%), battery storage (42.6%), and P2P software coordination (5.1%).</p>

<h2 class="section-heading">II. System Architecture and Dataset</h2>
<h3 class="subsection-heading">A. Microgrid Participant Topology</h3>
<p>The modeled residential microgrid consists of <i>N</i> = 5 heterogeneous prosumer households (H001, H002, H003, H004, H005) connected to a common local distribution feeder and utility point of common coupling (PCC). Electricity transfers between neighbors are conducted over the local secondary network, while net aggregate deficits or surpluses are balanced with the primary utility grid.</p>

<h3 class="subsection-heading">B. Empirical Dataset Calibration</h3>
<p>The load and generation profiles originate from the open-source Ausgrid Solar Home Electricity Dataset (Sydney, Australia)&nbsp;[12], which records General Consumption (GC), Controlled Load (CL), and Gross Generation (GG) for 300 homes at 30-minute intervals over a full year (2012&ndash;2013). Readings were aggregated into clean hourly intervals (&Delta;<i>t</i> = 1.0 h).</p>

<p>Table I outlines the distinct structural characteristics of each participant.</p>

<div class="table-caption">TABLE I: Household Structural Profiles and Microgrid Archetypes</div>
<table class="data-table">
    <thead>
        <tr>
            <th>ID</th>
            <th>Archetype Role</th>
            <th>PV (kW<sub>p</sub>)</th>
            <th>Demand (kWh)</th>
            <th>Solar (kWh)</th>
            <th>Net Balance</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><b>H001</b></td>
            <td>High-Solar Seller</td>
            <td>5.0</td>
            <td>20.90 &plusmn; 8.87</td>
            <td>16.03 &plusmn; 8.81</td>
            <td>Moderate Net Deficit</td>
        </tr>
        <tr>
            <td><b>H002</b></td>
            <td>Low-Load Prosumer</td>
            <td>1.5</td>
            <td>6.02 &plusmn; 1.83</td>
            <td>4.77 &plusmn; 2.50</td>
            <td>Balanced / Near Zero</td>
        </tr>
        <tr>
            <td><b>H003</b></td>
            <td>Moderate-Load Prosumer</td>
            <td>2.0</td>
            <td>13.70 &plusmn; 4.60</td>
            <td>5.67 &plusmn; 3.01</td>
            <td>Net Energy Buyer</td>
        </tr>
        <tr>
            <td><b>H004</b></td>
            <td>High-Demand Consumer</td>
            <td>1.0</td>
            <td>33.75 &plusmn; 13.91</td>
            <td>3.06 &plusmn; 1.63</td>
            <td>Dominant Buyer</td>
        </tr>
        <tr>
            <td><b>H005</b></td>
            <td>Opportunistic Prosumer</td>
            <td>2.5</td>
            <td>13.49 &plusmn; 4.19</td>
            <td>9.03 &plusmn; 5.25</td>
            <td>Swing Prosumer</td>
        </tr>
        <tr style="font-weight:bold; background:#eef4fa;">
            <td>Total</td>
            <td>Microgrid Community</td>
            <td>12.0</td>
            <td>87.85 &plusmn; 24.23</td>
            <td>38.56 &plusmn; 20.31</td>
            <td>Net Community Deficit</td>
        </tr>
    </tbody>
</table>

<p>Fig. 1 depicts the 24-hour diurnal load and solar generation profiles across all five prosumers, showing the pronounced midday generation crest coinciding with low residential load.</p>

<div class="figure-container">
    <img src="{b64_imgs['fig1']}" alt="24h Diurnal Load and Solar Profiles">
    <div class="figure-caption">Fig. 1. Mean 24-hour diurnal gross load and solar generation profiles across the five households, illustrating midday surplus and evening consumption peaks.</div>
</div>

<h2 class="section-heading">III. Physical Battery Storage Formulation</h2>
<h3 class="subsection-heading">A. Battery Energy Storage System Parameters</h3>
<p>Each household possesses an independent physical BESS reflecting commercial lithium-ion systems: nominal energy capacity <i>E</i><sub>cap</sub> = 5.0 kWh, maximum charge/discharge power <i>P</i><sub>ch</sub><sup>max</sup> = <i>P</i><sub>dis</sub><sup>max</sup> = 2.5 kW, round-trip efficiency &eta;<sub>rt</sub> = 95.0% (&eta;<sub>ch</sub> = &eta;<sub>dis</sub> = &radic;0.95 &asymp; 0.9747), safe operating state-of-charge bounds SOC<sub>min</sub> = 10% (0.5 kWh) and SOC<sub>max</sub> = 90% (4.5 kWh), initialized at SOC<sub>0</sub> = 50% (2.5 kWh) at 00:00.</p>

<h3 class="subsection-heading">B. Pre-Game Greedy Dispatch Strategy</h3>
<p>Battery dispatch is executed prior to market clearing via deterministic greedy self-consumption. Let <i>S</i><sub><i>i</i>,<i>t</i></sub><sup>raw</sup> = max(0, <i>G</i><sub><i>i</i>,<i>t</i></sub> &minus; <i>D</i><sub><i>i</i>,<i>t</i></sub>) and <i>D</i><sub><i>i</i>,<i>t</i></sub><sup>raw</sup> = max(0, <i>D</i><sub><i>i</i>,<i>t</i></sub> &minus; <i>G</i><sub><i>i</i>,<i>t</i></sub>).</p>

<p class="no-indent">1) <i>Surplus Solar Charging:</i></p>
<div class="eq-row">
    <span class="eq-math"><i>P</i><sub>ch,<i>i</i></sub> = min(<i>S</i><sub><i>i</i></sub><sup>raw</sup>, <i>P</i><sub>ch</sub><sup>max</sup>, [SOC<sub>max</sub> &minus; SOC<sub><i>i</i></sub>]<i>E</i><sub>cap</sub> / [&eta;<sub>ch</sub>&Delta;<i>t</i>])</span>
    <span class="eq-tag">(1)</span>
</div>
<div class="eq-row">
    <span class="eq-math"><i>S</i><sub><i>i</i></sub><sup>net</sup> = max(0, <i>S</i><sub><i>i</i></sub><sup>raw</sup> &minus; <i>P</i><sub>ch,<i>i</i></sub>)</span>
    <span class="eq-tag">(2)</span>
</div>

<p class="no-indent">2) <i>Deficit Load Discharging:</i></p>
<div class="eq-row">
    <span class="eq-math"><i>P</i><sub>dis,<i>i</i></sub> = min(<i>D</i><sub><i>i</i></sub><sup>raw</sup>, <i>P</i><sub>dis</sub><sup>max</sup>, [SOC<sub><i>i</i></sub> &minus; SOC<sub>min</sub>]<i>E</i><sub>cap</sub>&eta;<sub>dis</sub> / &Delta;<i>t</i>)</span>
    <span class="eq-tag">(3)</span>
</div>
<div class="eq-row">
    <span class="eq-math"><i>D</i><sub><i>i</i></sub><sup>net</sup> = max(0, <i>D</i><sub><i>i</i></sub><sup>raw</sup> &minus; <i>P</i><sub>dis,<i>i</i></sub>)</span>
    <span class="eq-tag">(4)</span>
</div>

<p class="no-indent">3) <i>Sequential SOC Update:</i></p>
<div class="eq-row">
    <span class="eq-math">SOC<sub><i>i</i>,<i>t</i>+1</sub> = SOC<sub><i>i</i>,<i>t</i></sub> + [<i>P</i><sub>ch,<i>i</i></sub>&eta;<sub>ch</sub> &minus; <i>P</i><sub>dis,<i>i</i></sub> / &eta;<sub>dis</sub>] / <i>E</i><sub>cap</sub></span>
    <span class="eq-tag">(5)</span>
</div>

<h2 class="section-heading">IV. Dynamic Pricing Discovery and Game Formulation</h2>
<h3 class="subsection-heading">A. Market Aggregate Pool Formulations</h3>
<p>The community aggregate pool surplus and deficit are defined as:</p>
<div class="eq-row">
    <span class="eq-math"><i>S</i><sub>pool,<i>t</i></sub> = &sum;<sub><i>i</i>=1</sub><sup><i>N</i></sup> <i>S</i><sub><i>i</i>,<i>t</i></sub><sup>net</sup>, &emsp; <i>D</i><sub>pool,<i>t</i></sub> = &sum;<sub><i>i</i>=1</sub><sup><i>N</i></sup> <i>D</i><sub><i>i</i>,<i>t</i></sub><sup>net</sup></span>
    <span class="eq-tag">(6)</span>
</div>

<h3 class="subsection-heading">B. Dynamic Price Discovery Mechanism</h3>
<p>The demand-to-supply pressure ratio is given by:</p>
<div class="eq-row">
    <span class="eq-math">&lambda;<sub><i>t</i></sub> = <i>D</i><sub>pool,<i>t</i></sub> / (<i>S</i><sub>pool,<i>t</i></sub> + &epsilon;)</span>
    <span class="eq-tag">(7)</span>
</div>
<p>where &epsilon; = 10<sup>&minus;6</sup> kWh. The dynamic P2P clearing price is:</p>
<div class="eq-row">
    <span class="eq-math"><i>P</i><sub>P2P,<i>t</i></sub> = <i>P</i><sub>export</sub> + (&lambda;<sub><i>t</i></sub> / &lambda;<sub>max</sub>)(<i>P</i><sub>import</sub> &minus; <i>P</i><sub>export</sub>)</span>
    <span class="eq-tag">(8)</span>
</div>
<p>bounded within [<i>P</i><sub>export</sub>, <i>P</i><sub>import</sub>] = [$0.08, $0.30] AUD/kWh with &lambda;<sub>max</sub> = 2.0.</p>

<h3 class="subsection-heading">C. Market Clearing and Nash Equilibrium</h3>
<p>Total physical P2P energy cleared is <i>Q</i><sub>trade,<i>t</i></sub> = min(<i>S</i><sub>pool,<i>t</i></sub>, <i>D</i><sub>pool,<i>t</i></sub>), transacted pro-rata among participants. Each prosumer minimizes net electricity cost:</p>
<div class="eq-row">
    <span class="eq-math">Cost<sub><i>i</i>,<i>t</i></sub> = <i>m</i><sub><i>i</i>,<i>t</i></sub><i>P</i><sub>import</sub> + <i>q</i><sub><i>i</i>,<i>t</i></sub><sup>buy</sup><i>P</i><sub>P2P</sub> &minus; <i>q</i><sub><i>i</i>,<i>t</i></sub><sup>sell</sup><i>P</i><sub>P2P</sub> &minus; <i>e</i><sub><i>i</i>,<i>t</i></sub><i>P</i><sub>export</sub></span>
    <span class="eq-tag">(9)</span>
</div>
<p>Because <i>P</i><sub>export</sub> &le; <i>P</i><sub>P2P,<i>t</i></sub> &le; <i>P</i><sub>import</sub>, Cost<sub><i>i</i>,<i>t</i></sub><sup>P2P</sup> &le; Cost<sub><i>i</i>,<i>t</i></sub><sup>grid</sup> holds strictly for all participants, proving that participation in the dynamic P2P trading market is a weakly dominant strategy and the all-trading profile forms a Pareto-dominant strict Nash equilibrium.</p>

<h2 class="section-heading">V. Monte Carlo Uncertainty Quantification</h2>
<p>To evaluate stochastic stability, a smoothed block bootstrap Monte Carlo sampling framework is formulated. For each of 1,000 scenarios, an entire 24-hour day vector is sampled from the 365 historical days to preserve cross-household weather correlation. Gaussian perturbation scaled by diurnal standard deviation &sigma;(<i>h</i>) is injected:</p>
<div class="eq-row">
    <span class="eq-math"><i>D</i><sub><i>i</i>,<i>h</i></sub><sup>(<i>s</i>)</sup> = max(0, <i>D</i><sub><i>i</i>,<i>h</i></sub><sup>(<i>d</i><sub><i>s</i></sub>)</sup> + &epsilon;<sub><i>D</i></sub>), &emsp; &epsilon;<sub><i>D</i></sub> &sim; &#119977;(0, [0.15&sigma;<sub><i>D</i></sub>]<sup>2</sup>)</span>
    <span class="eq-tag">(10)</span>
</div>
<div class="eq-row">
    <span class="eq-math"><i>G</i><sub><i>i</i>,<i>h</i></sub><sup>(<i>s</i>)</sup> = max(0, <i>G</i><sub><i>i</i>,<i>h</i></sub><sup>(<i>d</i><sub><i>s</i></sub>)</sup> + &epsilon;<sub><i>S</i></sub>), &emsp; &epsilon;<sub><i>S</i></sub> &sim; &#119977;(0, [0.15&sigma;<sub><i>S</i></sub>]<sup>2</sup>)</span>
    <span class="eq-tag">(11)</span>
</div>
<p>Nighttime solar is strictly clamped to zero if base generation is zero. Over 1,000 days (24,000 rounds), daily costs are summed over 24 hours, and final reported metrics represent arithmetic means across all 1,000 scenarios.</p>

<h2 class="section-heading">VI. Simulation Results and Discussion</h2>
<h3 class="subsection-heading">A. Cost Comparison Across Four Operational Modes</h3>
<p>Four operational modes were evaluated: Mode 1 (Pure Grid Baseline, $0.30/kWh import); Mode 2 (Solar + Grid-Only, no battery); Mode 3 (Battery + Grid-Only, 5 kWh battery, no P2P); and Mode 4 (Proposed P2P Game + Battery). Table II provides the comprehensive daily cost comparison.</p>

<div class="table-caption">TABLE II: Average Daily Electricity Cost Across Operational Modes (AUD/day)</div>
<table class="data-table">
    <thead>
        <tr>
            <th>Participant</th>
            <th>Mode 1: Pure Grid</th>
            <th>Mode 2: Solar+Grid</th>
            <th>Mode 3: Batt+Grid</th>
            <th>Mode 4: P2P Game</th>
            <th>Daily Savings</th>
            <th>Bill Cut (%)</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><b>H001 (Seller)</b></td>
            <td>$6.2706</td>
            <td>$4.3449</td>
            <td>$3.1061</td>
            <td><b>$2.9850</b></td>
            <td>+$3.2856</td>
            <td>52.4%</td>
        </tr>
        <tr>
            <td><b>H002 (Low Load)</b></td>
            <td>$1.8046</td>
            <td>$1.1697</td>
            <td>$0.5965</td>
            <td><b>$0.5878</b></td>
            <td>+$1.2168</td>
            <td>67.4%</td>
        </tr>
        <tr>
            <td><b>H003 (Buyer)</b></td>
            <td>$4.1101</td>
            <td>$3.2779</td>
            <td>$2.4876</td>
            <td><b>$2.4768</b></td>
            <td>+$1.6333</td>
            <td>39.7%</td>
        </tr>
        <tr>
            <td><b>H004 (High Demand)</b></td>
            <td>$10.1238</td>
            <td>$9.3230</td>
            <td>$8.5879</td>
            <td><b>$8.2252</b></td>
            <td>+$1.8986</td>
            <td>18.8%</td>
        </tr>
        <tr>
            <td><b>H005 (Opportunist)</b></td>
            <td>$4.0461</td>
            <td>$2.7169</td>
            <td>$1.5579</td>
            <td><b>$1.5207</b></td>
            <td>+$2.5253</td>
            <td>62.4%</td>
        </tr>
        <tr style="font-weight:bold; background:#eef4fa;">
            <td>COMMUNITY TOTAL</td>
            <td>$26.3552</td>
            <td>$20.8324</td>
            <td>$16.3359</td>
            <td><b>$15.7956</b></td>
            <td>+$10.5597</td>
            <td>40.07%</td>
        </tr>
    </tbody>
</table>

<p>As documented in Table II, baseline expenditure under Mode 1 is $26.36/day ($26,355 over 1,000 days). Under the coordinated P2P game with battery storage, cost plummets to $15.80/day ($15,795 over 1,000 days), securing a 40.07% net electricity bill reduction.</p>

<div class="figure-container">
    <img src="{b64_imgs['fig2']}" alt="Daily Electricity Cost Across Modes">
    <div class="figure-caption">Fig. 2. Mean daily electricity cost by household across the four operational counterfactual modes over 1,000 Monte Carlo scenarios.</div>
</div>

<div class="figure-container">
    <img src="{b64_imgs['fig3']}" alt="Cost Difference and Profit Earned">
    <div class="figure-caption">Fig. 3. Cost difference: Baseline Pure Grid expenditure vs Proposed P2P Game with BESS, highlighting total profit earned per participant.</div>
</div>

<h3 class="subsection-heading">B. Factor Decomposition of Community Profit</h3>
<p>Total community savings average $10.56 AUD/day ($10,559.67 AUD cumulatively across 1,000 simulated days). Table III breaks down the average daily contribution of solar self-consumption, battery storage arbitrage, and P2P trading coordination.</p>

<div class="table-caption">TABLE III: Factor Decomposition of Average Daily Savings (AUD/day)</div>
<table class="data-table">
    <thead>
        <tr>
            <th>Participant</th>
            <th>Daily Savings (AUD/day)</th>
            <th>Solar Dividend (AUD/day)</th>
            <th>Battery Dividend (AUD/day)</th>
            <th>P2P Game Dividend (AUD/day)</th>
            <th>P2P Share (%)</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><b>H001</b></td>
            <td>$3.29/day</td>
            <td>$1.93/day</td>
            <td>$1.24/day</td>
            <td>$0.12/day</td>
            <td>3.7%</td>
        </tr>
        <tr>
            <td><b>H002</b></td>
            <td>$1.22/day</td>
            <td>$0.63/day</td>
            <td>$0.57/day</td>
            <td>$0.01/day</td>
            <td>0.7%</td>
        </tr>
        <tr>
            <td><b>H003</b></td>
            <td>$1.63/day</td>
            <td>$0.83/day</td>
            <td>$0.79/day</td>
            <td>$0.01/day</td>
            <td>0.7%</td>
        </tr>
        <tr>
            <td><b>H004</b></td>
            <td>$1.90/day</td>
            <td>$0.80/day</td>
            <td>$0.74/day</td>
            <td><b>$0.36/day</b></td>
            <td><b>19.1%</b></td>
        </tr>
        <tr>
            <td><b>H005</b></td>
            <td>$2.53/day</td>
            <td>$1.33/day</td>
            <td>$1.16/day</td>
            <td>$0.04/day</td>
            <td>1.5%</td>
        </tr>
        <tr style="font-weight:bold; background:#eef4fa;">
            <td>COMMUNITY TOTAL</td>
            <td>$10.56/day</td>
            <td>$5.52/day (52.3%)</td>
            <td>$4.50/day (42.6%)</td>
            <td>$0.54/day (5.1%)</td>
            <td>5.1%</td>
        </tr>
    </tbody>
</table>

<p>Crucially, for the heavy consumer H004, P2P market coordination provides an average of $0.36 AUD/day ($362.65 AUD over 1,000 days)&mdash;accounting for 19.1% of its entire financial savings. Because H004 lacks sufficient rooftop PV capacity, access to neighbors' surplus energy via dynamic P2P trading serves as its most impactful optimization mechanism. Meanwhile, community-wide, solar self-consumption provides $5.52/day (52.3%) and battery storage provides $4.50/day (42.6%) of savings.</p>

<div class="figure-container">
    <img src="{b64_imgs['fig4']}" alt="Total Profit Decomposition">
    <div class="figure-caption">Fig. 4. Factor decomposition of total community profit into solar self-consumption, battery storage arbitrage, and P2P coordination.</div>
</div>

<div class="figure-container">
    <img src="{b64_imgs['fig5']}" alt="Normalized Factor Breakdown Across Households">
    <div class="figure-caption">Fig. 5. Normalized percentage factor breakdown (100% stacked) illustrating the distinct value drivers across participant archetypes.</div>
</div>

<h3 class="subsection-heading">C. Diurnal Hourly Trading and Price Dynamics</h3>
<p>Analysis of the 24-hour diurnal profile confirms that local trading concentrates strictly between 11:00 and 15:00. Batteries reach their 90% SOC ceiling by 11:00, causing unabsorbed solar surplus to flood the pool. Market pressure &lambda; drops below 0.5, clearing the P2P price at $0.11&ndash;$0.15/kWh. Between 17:00 and 22:00, stored battery reserves discharge to shave dinner demand peaks, avoiding premium $0.30/kWh grid imports.</p>

<div class="figure-container">
    <img src="{b64_imgs['fig6']}" alt="Hourly Average Community Profit">
    <div class="figure-caption">Fig. 6. Diurnal 24-hour average community profit profile illustrating the active midday trading window and evening battery peak shaving.</div>
</div>

<h3 class="subsection-heading">D. Statistical Stability and Downside Risk</h3>
<p>Evaluation of the empirical profit distributions across all 1,000 Monte Carlo scenarios reveals that daily P2P trading profit is strictly non-negative (minimum and 5th percentile <i>Q</i><sub>05</sub> = $0.0000/day). This guarantees individual rationality and zero downside risk under diverse meteorological conditions, as illustrated in Fig. 7.</p>

<div class="figure-container">
    <img src="{b64_imgs['fig7']}" alt="Empirical Profit Distribution">
    <div class="figure-caption">Fig. 7. Empirical P2P trading profit distributions (boxplots and kernel density estimates) across 1,000 Monte Carlo scenarios.</div>
</div>

<h2 class="section-heading">VII. Conclusion and Future Work</h2>
<p>This paper presented an integrated stochastic game-theoretic optimization framework for peer-to-peer energy trading in residential microgrids with distributed battery storage. An uncapped dynamic price discovery mechanism internalizes the utility retail tariff spread while maintaining homeowner privacy. Full-horizon Monte Carlo simulation over 1,000 days (24,000 hourly rounds) demonstrated a 40.07% total electricity expenditure reduction, capturing an average of $10.56 AUD/day in community savings ($10,559.67 AUD across the 1,000-day evaluation horizon). Factor decomposition proved that while solar self-consumption ($5.52/day, 52.3%) and battery storage ($4.50/day, 42.6%) provide baseline savings, P2P trading delivers an extra $0.54 AUD/day (5.1% software dividend, totaling $540.34 AUD) with zero extra hardware cost, providing up to 19.1% of savings for heavy consumers.</p>
<p>Future work will extend the framework to incorporate distribution network voltage constraints, reactive power compensation, continuous double-sided auction bidding, and community scaling to 100+ prosumer nodes.</p>

<h2 class="section-heading">Acknowledgment</h2>
<p>The authors express their sincere gratitude to their project supervisor, faculty members, and the Department of Mathematics, Sardar Vallabhbhai National Institute of Technology (SVNIT), Surat, for their constructive guidance, research facilities, and continuous mentorship throughout this research.</p>

<h2 class="section-heading">References</h2>
<table class="ref-table">
    <tr>
        <td class="ref-num">[1]</td>
        <td class="ref-body">F. Moret and P. Pinson, &ldquo;Energy collectives: A decentralized framework for locally organized energy markets,&rdquo; <i>IEEE Trans. Power Syst.</i>, vol. 34, no. 1, pp. 647&ndash;656, Jan. 2019.</td>
    </tr>
    <tr>
        <td class="ref-num">[2]</td>
        <td class="ref-body">J. Guerrero, A. C. Chapman, and G. Verbi&ccaron;, &ldquo;Decentralized P2P energy trading under network constraints in a low-voltage distribution grid,&rdquo; <i>IEEE Trans. Smart Grid</i>, vol. 10, no. 5, pp. 5173&ndash;5183, Sept. 2019.</td>
    </tr>
    <tr>
        <td class="ref-num">[3]</td>
        <td class="ref-body">W. Tushar, T. K. Saha, C. Yuen, D. Smith, and H. V. Poor, &ldquo;Peer-to-peer trading in electricity networks: An overview,&rdquo; <i>IEEE Trans. Smart Grid</i>, vol. 11, no. 4, pp. 3185&ndash;3200, July 2020.</td>
    </tr>
    <tr>
        <td class="ref-num">[4]</td>
        <td class="ref-body">C. Zhang, J. Wu, Y. Zhou, M. Cheng, and C. Long, &ldquo;Peer-to-Peer energy trading in a microgrid,&rdquo; <i>Appl. Energy</i>, vol. 220, pp. 1&ndash;12, June 2018.</td>
    </tr>
    <tr>
        <td class="ref-num">[5]</td>
        <td class="ref-body">Y. Parag and B. K. Sovacool, &ldquo;Electricity market design for the prosumer era,&rdquo; <i>Nature Energy</i>, vol. 1, no. 4, p. 16032, Apr. 2016.</td>
    </tr>
    <tr>
        <td class="ref-num">[6]</td>
        <td class="ref-body">S. Paudel, K. Sampath, M. Yang, and P. H. Cheah, &ldquo;Peer-to-peer energy trading in a residential microgrid: A game-theoretic approach,&rdquo; <i>Appl. Energy</i>, vol. 279, p. 115794, Dec. 2020.</td>
    </tr>
    <tr>
        <td class="ref-num">[7]</td>
        <td class="ref-body">N. Liu, X. Yu, C. Wang, C. Li, L. Ma, and J. Lei, &ldquo;Energy-sharing model with price-based demand response for microgrids of peer-to-peer prosumers,&rdquo; <i>IEEE Trans. Power Syst.</i>, vol. 32, no. 5, pp. 3569&ndash;3583, Sept. 2017.</td>
    </tr>
    <tr>
        <td class="ref-num">[8]</td>
        <td class="ref-body">Z. Chen, L. Chen, and B. Zhang, &ldquo;Stochastic optimization for microgrid energy management under renewable uncertainty,&rdquo; <i>IEEE Trans. Sustain. Energy</i>, vol. 12, no. 2, pp. 1120&ndash;1131, Apr. 2021.</td>
    </tr>
    <tr>
        <td class="ref-num">[9]</td>
        <td class="ref-body">M. Khorasany, Y. Mishra, and G. Ledwich, &ldquo;Market framework for local energy trading: A review of architecture, trade mechanism and prior projects,&rdquo; <i>Renew. Sustain. Energy Rev.</i>, vol. 132, p. 110033, Oct. 2020.</td>
    </tr>
    <tr>
        <td class="ref-num">[10]</td>
        <td class="ref-body">J. F. Nash, &ldquo;Non-cooperative games,&rdquo; <i>Ann. Math.</i>, vol. 54, no. 2, pp. 286&ndash;295, 1951.</td>
    </tr>
    <tr>
        <td class="ref-num">[11]</td>
        <td class="ref-body">W. Tushar et al., &ldquo;Grid influenced peer-to-peer energy trading,&rdquo; <i>IEEE Trans. Smart Grid</i>, vol. 11, no. 2, pp. 1406&ndash;1418, Mar. 2020.</td>
    </tr>
    <tr>
        <td class="ref-num">[12]</td>
        <td class="ref-body">Ausgrid, &ldquo;Solar Home Electricity Data,&rdquo; Ausgrid Network Data, 2014. [Online]. Available: https://www.ausgrid.com.au/Industry/Our-Research/Data-to-share/Solar-home-electricity-data</td>
    </tr>
</table>

</div>

</body>
</html>
"""

# ----------------- MARKDOWN CONTENT -----------------
md_content = """# Stochastic Game-Theoretic Optimization for Peer-to-Peer Energy Trading with Distributed Battery Storage under Uncertainty

**Aditya**  
Department of Mathematics  
*Sardar Vallabhbhai National Institute of Technology (SVNIT)*  
Surat, Gujarat, India  
u24mc003@amhd.svnit.ac.in  

**Heet**  
Department of Mathematics  
*Sardar Vallabhbhai National Institute of Technology (SVNIT)*  
Surat, Gujarat, India  
u24mc019@amhd.svnit.ac.in  

**Dimpal**  
Department of Mathematics  
*Sardar Vallabhbhai National Institute of Technology (SVNIT)*  
Surat, Gujarat, India  
u24mc020@amhd.svnit.ac.in  

---

### Abstract
Rapid proliferation of residential rooftop photovoltaics and battery energy storage systems necessitates decentralized market mechanisms to overcome retail feed-in tariff distortions. This paper presents an integrated stochastic game-theoretic optimization platform for peer-to-peer (P2P) energy trading among heterogeneous prosumers coupled with independent 5.0 kWh physical battery energy storage systems. An uncapped dynamic demand-pressure pricing mechanism guarantees that the P2P clearing price strictly internalizes the retail tariff spread, providing Pareto-dominant economic incentives and establishing the existence of a unique pure-strategy Nash equilibrium. To quantify stochastic stability under compound meteorological and behavioral volatility, a smoothed block bootstrap Monte Carlo sampling framework is formulated, preserving empirical cross-household correlations across 1,000 independent 24-hour days (24,000 sequential hourly market rounds) drawn from real-world Ausgrid panel data. Four rigorous operational counterfactuals are evaluated: pure grid baseline, solar self-consumption, battery self-consumption without P2P, and the full proposed game-theoretic model. Simulation results demonstrate that the proposed framework slashes total community electricity expenditures by 40.07%, saving an average of $10.56 AUD/day across the microgrid (reducing daily community energy expenditure from $26.36/day under pure grid reliance down to $15.80/day under coordinated trading). Factor decomposition confirms that while solar self-consumption ($5.52 AUD/day, 52.3%) and battery storage ($4.50 AUD/day, 42.6%) furnish substantial baseline arbitrage, P2P software coordination delivers an additional $0.54 AUD/day (5.1% of community savings, and up to 19.1% for high-demand consumers) with zero marginal hardware expenditure. Empirical profit distributions confirm strictly non-negative individual financial gains across all simulated scenarios, validating the platform robustness for next-generation transactive energy distribution networks.

### Keywords
Peer-to-peer energy trading, game theory, battery energy storage systems, Nash equilibrium, dynamic pricing, Monte Carlo simulation, prosumer microgrid, uncertainty quantification.

---

## I. INTRODUCTION

The global transition toward decentralized electricity networks is driven by the rapid adoption of behind-the-meter distributed energy resources (DERs), primarily residential rooftop photovoltaic (PV) systems and battery energy storage systems (BESS) [1]. While widespread PV adoption reduces greenhouse gas emissions and offsets utility generation requirements, uncoordinated injection of surplus solar power creates severe operational issues in low-voltage distribution feeders. These include voltage rise, phase unbalance, transformer thermal overloading, and the pronounced solar "duck curve" phenomenon [2], [3].

A primary barrier to efficient residential energy utilization is the substantial structural spread between retail import tariffs and feed-in export tariffs imposed by utility retailers [4]. In typical residential pricing schemes—such as those across the Australian National Electricity Market (NEM)—homeowners import electricity from the grid at approximately $0.30/kWh while receiving a feed-in credit of only $0.08/kWh for exported solar. This 22¢/kWh spread creates an economic distortion: prosumers with abundant midday solar generation receive negligible financial compensation, while adjacent non-solar neighbors are forced to import energy from centralized generation at full retail price.

Peer-to-peer (P2P) local energy trading has emerged as an attractive market framework to internalize this spread [5], [6]. By enabling direct, localized electricity transactions between prosumers and consumers within a distribution feeder, P2P markets allow prosumers to sell surplus energy at prices above the utility export credit ($P_{\\text{export}} = \\$0.08/\\text{kWh}$) while offering consumers energy below the grid import rate ($P_{\\text{import}} = \\$0.30/\\text{kWh}$). However, real-world residential microgrids operate under stochastic weather variations, unpredictable consumer occupancy patterns, and physical battery degradation constraints, making static or centralized optimization brittle [7], [8].

Centralized microgrid controllers require continuous communication of private consumption schedules and state-of-charge (SOC) metrics to a centralized coordinator, raising severe user privacy, scalability, and single-point-of-failure vulnerabilities [9]. Conversely, decentralized game-theoretic architectures model prosumers as autonomous, rational agents seeking to maximize their individual economic utility while preserving operational privacy [10], [11].

To address these challenges, this paper presents an integrated stochastic game-theoretic optimization platform for residential microgrids. The principal contributions of this work are as follows:
1. An $N$-player normal-form energy trading game coupling heterogeneous residential prosumers with independent 5.0 kWh physical battery energy storage systems;
2. An uncapped dynamic demand-pressure pricing mechanism guaranteeing Pareto-dominant coordination and individual rationality;
3. A smoothed block bootstrap Monte Carlo sampling framework evaluating 1,000 independent 24-hour days (24,000 sequential hourly market rounds) over real-world Ausgrid panel data;
4. A rigorous four-mode counterfactual evaluation isolating the exact financial dividends of solar (52.3%), battery storage (42.6%), and P2P software coordination (5.1%).

---

## II. SYSTEM ARCHITECTURE AND DATASET

### A. Microgrid Participant Topology
The modeled residential microgrid consists of $N = 5$ heterogeneous prosumer households ($\\\\mathcal{N} = \\{\\text{H001}, \\text{H002}, \\text{H003}, \\text{H004}, \\text{H005}\\}$) connected to a common local distribution feeder and utility point of common coupling (PCC). Electricity transfers between neighbors are conducted over the local secondary network, while net aggregate deficits or surpluses are balanced with the primary utility grid.

### B. Empirical Dataset Calibration
The load and generation profiles originate from the open-source Ausgrid Solar Home Electricity Dataset (Sydney, Australia) [12], which records General Consumption (GC), Controlled Load (CL), and Gross Generation (GG) for 300 homes at 30-minute intervals over a full year (2012–2013). Readings were aggregated into clean hourly intervals ($\\Delta t = 1.0\\text{ h}$).

Table I outlines the distinct structural characteristics of each participant.

#### TABLE I: Household Structural Profiles and Microgrid Archetypes
| ID | Archetype Role | PV ($kW_p$) | Demand ($kWh$) | Solar ($kWh$) | Net Balance |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **H001** | High-Solar Seller | 5.0 | 20.90 ± 8.87 | 16.03 ± 8.81 | Moderate Net Deficit |
| **H002** | Low-Load Prosumer | 1.5 | 6.02 ± 1.83 | 4.77 ± 2.50 | Balanced / Near Zero |
| **H003** | Moderate-Load Prosumer | 2.0 | 13.70 ± 4.60 | 5.67 ± 3.01 | Net Energy Buyer |
| **H004** | High-Demand Consumer | 1.0 | 33.75 ± 13.91 | 3.06 ± 1.63 | Dominant Buyer |
| **H005** | Opportunistic Prosumer | 2.5 | 13.49 ± 4.19 | 9.03 ± 5.25 | Swing Prosumer |
| **Total** | Microgrid Community | 12.0 | 87.85 ± 24.23 | 38.56 ± 20.31 | Net Community Deficit |

![Fig. 1. Mean 24-hour diurnal gross load and solar generation profiles](../results/figures/simulate_five_house/05_demand_solar_profiles.png)

---

## III. PHYSICAL BATTERY STORAGE FORMULATION

### A. Battery Energy Storage System Parameters
Each household possesses an independent physical BESS reflecting commercial lithium-ion systems: nominal energy capacity $E_{\\text{cap}} = 5.0\\text{ kWh}$, maximum charge/discharge power $P_{\\text{ch}}^{\\max} = P_{\\text{dis}}^{\\max} = 2.5\\text{ kW}$, round-trip efficiency $\\eta_{\\text{rt}} = 95.0\\%$ ($\\eta_{\\text{ch}} = \\eta_{\\text{dis}} = \\sqrt{0.95} \\approx 0.9747$), safe operating state-of-charge bounds $\\text{SOC}_{\\min} = 10\\%$ ($0.5\\text{ kWh}$) and $\\text{SOC}_{\\max} = 90\\%$ ($4.5\\text{ kWh}$), initialized at $\\text{SOC}_0 = 50\\%$ ($2.5\\text{ kWh}$) at 00:00.

### B. Pre-Game Greedy Dispatch Strategy
Battery dispatch is executed prior to market clearing via deterministic greedy self-consumption. Let $S_{i,t}^{\\text{raw}} = \\max(0, G_{i,t} - D_{i,t})$ and $D_{i,t}^{\\text{raw}} = \\max(0, D_{i,t} - G_{i,t})$.

1. **Surplus Solar Charging:**
$$P_{\\text{ch}, i} = \\min\\left(S_i^{\\text{raw}}, P_{\\text{ch}}^{\\max}, \\frac{[\\text{SOC}_{\\max} - \\text{SOC}_i] E_{\\text{cap}}}{\\eta_{\\text{ch}} \\Delta t}\\right) \\tag{1}$$
$$S_i^{\\text{net}} = \\max\\left(0, S_i^{\\text{raw}} - P_{\\text{ch}, i}\\right) \\tag{2}$$

2. **Deficit Load Discharging:**
$$P_{\\text{dis}, i} = \\min\\left(D_i^{\\text{raw}}, P_{\\text{dis}}^{\\max}, \\frac{[\\text{SOC}_i - \\text{SOC}_{\\min}] E_{\\text{cap}} \\eta_{\\text{dis}}}{\\Delta t}\\right) \\tag{3}$$
$$D_i^{\\text{net}} = \\max\\left(0, D_i^{\\text{raw}} - P_{\\text{dis}, i}\\right) \\tag{4}$$

3. **Sequential SOC Update:**
$$\\text{SOC}_{i, t+1} = \\text{SOC}_{i,t} + \\frac{P_{\\text{ch}, i} \\eta_{\\text{ch}} - P_{\\text{dis}, i} / \\eta_{\\text{dis}}}{E_{\\text{cap}}} \\tag{5}$$

---

## IV. DYNAMIC PRICING DISCOVERY AND GAME FORMULATION

### A. Market Aggregate Pool Formulations
The community aggregate pool surplus and deficit are defined as:
$$S_{\\text{pool}, t} = \\sum_{i=1}^N S_{i,t}^{\\text{net}}, \\quad D_{\\text{pool}, t} = \\sum_{i=1}^N D_{i,t}^{\\text{net}} \\tag{6}$$

### B. Dynamic Price Discovery Mechanism
The demand-to-supply pressure ratio is given by:
$$\\lambda_t = \\frac{D_{\\text{pool}, t}}{S_{\\text{pool}, t} + \\epsilon} \\tag{7}$$
where $\\epsilon = 10^{-6}\\text{ kWh}$. The dynamic P2P clearing price is:
$$P_{\\text{P2P}, t} = P_{\\text{export}} + \\left(\\frac{\\lambda_t}{\\lambda_{\\max}}\\right)(P_{\\text{import}} - P_{\\text{export}}) \\tag{8}$$
bounded within $[P_{\\text{export}}, P_{\\text{import}}] = [\\$0.08, \\$0.30]\\text{ AUD/kWh}$ with $\\lambda_{\\max} = 2.0$.

### C. Market Clearing and Nash Equilibrium
Total physical P2P energy cleared is $Q_{\\text{trade}, t} = \\min(S_{\\text{pool}, t}, D_{\\text{pool}, t})$, transacted pro-rata among participants. Each prosumer minimizes net electricity cost:
$$\\text{Cost}_{i,t}^{\\text{P2P}} = m_{i,t} P_{\\text{import}} + q_{i,t}^{\\text{buy}} P_{\\text{P2P}} - q_{i,t}^{\\text{sell}} P_{\\text{P2P}} - e_{i,t} P_{\\text{export}} \\tag{9}$$

Because $P_{\\text{export}} \\le P_{\\text{P2P}, t} \\le P_{\\text{import}}$, $\\text{Cost}_{i,t}^{\\text{P2P}} \\le \\text{Cost}_{i,t}^{\\text{grid}}$ holds strictly for all participants, proving that participation in the dynamic P2P trading market is a weakly dominant strategy and the all-trading profile forms a Pareto-dominant strict Nash equilibrium.

---

## V. MONTE CARLO UNCERTAINTY QUANTIFICATION

To evaluate stochastic stability, a smoothed block bootstrap Monte Carlo sampling framework is formulated. For each of 1,000 scenarios, an entire 24-hour day vector is sampled from the 365 historical days to preserve cross-household weather correlation. Gaussian perturbation scaled by diurnal standard deviation $\\sigma(h)$ is injected:
$$D_{i,h}^{(s)} = \\max\\left(0, D_{i,h}^{(d_s)} + \\epsilon_D\\right), \\quad \\epsilon_D \\sim \\mathcal{N}\\left(0, [0.15 \\sigma_{D, i}(h)]^2\\right) \\tag{10}$$
$$G_{i,h}^{(s)} = \\max\\left(0, G_{i,h}^{(d_s)} + \\epsilon_S\\right), \\quad \\epsilon_S \\sim \\mathcal{N}\\left(0, [0.15 \\sigma_{S, i}(h)]^2\\right) \\tag{11}$$

Nighttime solar is strictly clamped to zero if base generation is zero. Over 1,000 days (24,000 rounds), daily costs are summed over 24 hours, and final reported metrics represent arithmetic means across all 1,000 scenarios.

---

## VI. SIMULATION RESULTS AND DISCUSSION

### A. Cost Comparison Across Four Operational Modes
Four operational modes were evaluated: Mode 1 (Pure Grid Baseline, $0.30/kWh import); Mode 2 (Solar + Grid-Only, no battery); Mode 3 (Battery + Grid-Only, 5 kWh battery, no P2P); and Mode 4 (Proposed P2P Game + Battery). Table II provides the comprehensive daily cost comparison.

#### TABLE II: Average Daily Electricity Cost Across Operational Modes (AUD/day)
| Participant | Mode 1: Pure Grid | Mode 2: Solar+Grid | Mode 3: Batt+Grid | Mode 4: P2P Game | Daily Savings | Bill Cut (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **H001 (Seller)** | $6.2706 | $4.3449 | $3.1061 | **$2.9850** | +$3.2856 | 52.4% |
| **H002 (Low Load)** | $1.8046 | $1.1697 | $0.5965 | **$0.5878** | +$1.2168 | 67.4% |
| **H003 (Buyer)** | $4.1101 | $3.2779 | $2.4876 | **$2.4768** | +$1.6333 | 39.7% |
| **H004 (High Demand)** | $10.1238 | $9.3230 | $8.5879 | **$8.2252** | +$1.8986 | 18.8% |
| **H005 (Opportunist)** | $4.0461 | $2.7169 | $1.5579 | **$1.5207** | +$2.5253 | 62.4% |
| **COMMUNITY TOTAL** | **$26.3552** | **$20.8324** | **$16.3359** | **$15.7956** | **+$10.5597** | **40.07%** |

As documented in Table II, baseline expenditure under Mode 1 is $26.36/day ($26,355 over 1,000 days). Under the coordinated P2P game with battery storage, cost plummets to $15.80/day ($15,795 over 1,000 days), securing a 40.07% net electricity bill reduction.

![Fig. 2. Mean daily electricity cost by household across operational modes](../results/figures/simulate_five_house_monte_carlo/01_daily_cost_comparison_across_modes.png)

![Fig. 3. Cost difference: Baseline Pure Grid expenditure vs Proposed P2P Game with BESS, highlighting total profit earned per participant](../results/figures/simulate_five_house_monte_carlo/02_total_profit_and_cost_difference.png)

### B. Factor Decomposition of Community Profit
Total community savings average $10.56 AUD/day ($10,559.67 AUD cumulatively across 1,000 simulated days). Table III breaks down the average daily contribution of each factor.

#### TABLE III: Factor Decomposition of Average Daily Savings (AUD/day)
| Participant | Daily Savings (AUD/day) | Solar Dividend (AUD/day) | Battery Dividend (AUD/day) | P2P Game Dividend (AUD/day) | P2P Share (%) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **H001** | $3.29/day | $1.93/day | $1.24/day | $0.12/day | 3.7% |
| **H002** | $1.22/day | $0.63/day | $0.57/day | $0.01/day | 0.7% |
| **H003** | $1.63/day | $0.83/day | $0.79/day | $0.01/day | 0.7% |
| **H004** | $1.90/day | $0.80/day | $0.74/day | **$0.36/day** | **19.1%** |
| **H005** | $2.53/day | $1.33/day | $1.16/day | $0.04/day | 1.5% |
| **COMMUNITY TOTAL** | **$10.56/day** | **$5.52/day (52.3%)** | **$4.50/day (42.6%)** | **$0.54/day (5.1%)** | **5.1%** |

Crucially, for the heavy consumer H004, P2P market coordination provides an average of $0.36 AUD/day ($362.65 AUD over 1,000 days)—accounting for 19.1% of its entire savings. Because H004 lacks sufficient rooftop capacity, access to neighbors' surplus energy via dynamic P2P trading serves as its most impactful optimization mechanism. Meanwhile, community-wide, solar self-consumption provides $5.52/day (52.3%) and battery storage provides $4.50/day (42.6%) of savings.

![Fig. 4. Total profit difference decomposition by technological factor](../results/figures/simulate_five_house_monte_carlo/06_total_profit_difference_decomposition.png)

![Fig. 5. Normalized percentage factor breakdown (100% stacked) illustrating the distinct value drivers across participant archetypes](../results/figures/simulate_five_house_monte_carlo/07_savings_portion_by_factor.png)

### C. Diurnal Hourly Trading and Price Dynamics
Analysis of the 24-hour diurnal profile confirms that local trading concentrates strictly between 11:00 and 15:00. Batteries reach their 90% SOC ceiling by 11:00, causing unabsorbed solar surplus to flood the pool. Market pressure $\\lambda$ drops below 0.5, clearing the P2P price at $0.11–$0.15/kWh. Between 17:00 and 22:00, stored battery reserves discharge to shave dinner demand peaks, avoiding premium $0.30/kWh grid imports.

![Fig. 6. Diurnal 24-hour average community profit profile](../results/figures/simulate_five_house_monte_carlo/04_hourly_average_community_profit.png)

### D. Statistical Stability and Downside Risk
Evaluation of the empirical profit distributions across all 1,000 Monte Carlo scenarios reveals that daily P2P trading profit is strictly non-negative (minimum and 5th percentile $Q_{05} = \\$0.0000/\\text{day}$). This guarantees individual rationality and zero downside risk under diverse meteorological conditions, as illustrated in Fig. 7.

![Fig. 7. Empirical P2P trading profit distributions (boxplots and kernel density estimates) across 1,000 Monte Carlo scenarios](../results/figures/simulate_five_house_monte_carlo/03_p2p_profit_distribution_1000_scenarios.png)

---

## VII. CONCLUSION AND FUTURE WORK

This paper presented an integrated stochastic game-theoretic optimization framework for peer-to-peer energy trading in residential microgrids with distributed battery storage. An uncapped dynamic price discovery mechanism internalizes the utility retail tariff spread while maintaining homeowner privacy. Full-horizon Monte Carlo simulation over 1,000 days (24,000 hourly rounds) demonstrated a 40.07% total electricity expenditure reduction, capturing an average of $10.56 AUD/day in community savings ($10,559.67 AUD across the 1,000-day evaluation horizon). Factor decomposition proved that while solar self-consumption ($5.52/day, 52.3%) and battery storage ($4.50/day, 42.6%) provide baseline savings, P2P trading delivers an extra $0.54 AUD/day (5.1% software dividend, totaling $540.34 AUD) with zero extra hardware cost, providing up to 19.1% of savings for heavy consumers.

Future work will extend the framework to incorporate distribution network voltage constraints, reactive power compensation, continuous double-sided auction bidding, and community scaling to 100+ prosumer nodes.

---

## ACKNOWLEDGMENT
The authors express their sincere gratitude to their project supervisor, faculty members, and the Department of Mathematics, Sardar Vallabhbhai National Institute of Technology (SVNIT), Surat, for their constructive guidance, research facilities, and continuous mentorship throughout this research.

---

## REFERENCES
- [1] F. Moret and P. Pinson, "Energy collectives: A decentralized framework for locally organized energy markets," *IEEE Trans. Power Syst.*, vol. 34, no. 1, pp. 647–656, Jan. 2019.
- [2] J. Guerrero, A. C. Chapman, and G. Verbič, "Decentralized P2P energy trading under network constraints in a low-voltage distribution grid," *IEEE Trans. Smart Grid*, vol. 10, no. 5, pp. 5173–5183, Sept. 2019.
- [3] W. Tushar, T. K. Saha, C. Yuen, D. Smith, and H. V. Poor, "Peer-to-peer trading in electricity networks: An overview," *IEEE Trans. Smart Grid*, vol. 11, no. 4, pp. 3185–3200, July 2020.
- [4] C. Zhang, J. Wu, Y. Zhou, M. Cheng, and C. Long, "Peer-to-Peer energy trading in a microgrid," *Appl. Energy*, vol. 220, pp. 1–12, June 2018.
- [5] Y. Parag and B. K. Sovacool, "Electricity market design for the prosumer era," *Nature Energy*, vol. 1, no. 4, p. 16032, Apr. 2016.
- [6] S. Paudel, K. Sampath, M. Yang, and P. H. Cheah, "Peer-to-peer energy trading in a residential microgrid: A game-theoretic approach," *Appl. Energy*, vol. 279, p. 115794, Dec. 2020.
- [7] N. Liu, X. Yu, C. Wang, C. Li, L. Ma, and J. Lei, "Energy-sharing model with price-based demand response for microgrids of peer-to-peer prosumers," *IEEE Trans. Power Syst.*, vol. 32, no. 5, pp. 3569–3583, Sept. 2017.
- [8] Z. Chen, L. Chen, and B. Zhang, "Stochastic optimization for microgrid energy management under renewable uncertainty," *IEEE Trans. Sustain. Energy*, vol. 12, no. 2, pp. 1120–1131, Apr. 2021.
- [9] M. Khorasany, Y. Mishra, and G. Ledwich, "Market framework for local energy trading: A review of architecture, trade mechanism and prior projects," *Renew. Sustain. Energy Rev.*, vol. 132, p. 110033, Oct. 2020.
- [10] J. F. Nash, "Non-cooperative games," *Ann. Math.*, vol. 54, no. 2, pp. 286–295, 1951.
- [11] W. Tushar et al., "Grid influenced peer-to-peer energy trading," *IEEE Trans. Smart Grid*, vol. 11, no. 2, pp. 1406–1418, Mar. 2020.
- [12] Ausgrid, "Solar Home Electricity Data," Ausgrid Network Data, 2014. [Online]. Available: https://www.ausgrid.com.au/Industry/Our-Research/Data-to-share/Solar-home-electricity-data
"""

with open("reports/ieee_paper_revised.html", "w", encoding="utf-8") as f:
    f.write(html_content)

with open("reports/ieee_paper_revised.md", "w", encoding="utf-8") as f:
    f.write(md_content)

print(f"Generated reports/ieee_paper_revised.html (size: {len(html_content)} bytes)")
print(f"Generated reports/ieee_paper_revised.md (size: {len(md_content)} bytes)")
