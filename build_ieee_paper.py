"""Script to build the revised IEEE paper into Markdown, DOCX, and PDF formats."""

import os
import sys
import win32com.client

MARKDOWN_PATH = os.path.abspath("reports/ieee_paper_revised.md")
HTML_PATH = os.path.abspath("reports/ieee_paper_revised.html")
DOCX_PATH = os.path.abspath("reports/ieee_paper_revised.docx")
PDF_PATH = os.path.abspath("reports/ieee_paper_revised.pdf")

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Stochastic Game-Theoretic Optimization for Peer-to-Peer Energy Trading in Residential Microgrids Under Forecast Uncertainty</title>
<style>
    @page {
        size: letter;
        margin: 0.75in 0.75in 0.75in 0.75in;
    }
    body {
        font-family: "Times New Roman", Times, serif;
        font-size: 10pt;
        line-height: 1.25;
        color: #000000;
        text-align: justify;
    }
    h1.title {
        font-size: 20pt;
        font-weight: bold;
        text-align: center;
        margin-bottom: 12pt;
        line-height: 1.2;
    }
    .authors {
        text-align: center;
        font-size: 10pt;
        margin-bottom: 18pt;
    }
    .abstract-box {
        margin: 0 0.2in 14pt 0.2in;
        font-size: 9pt;
        line-height: 1.2;
    }
    .abstract-box b {
        font-weight: bold;
    }
    h2.section-heading {
        font-size: 10pt;
        font-weight: bold;
        text-align: center;
        text-transform: uppercase;
        margin-top: 14pt;
        margin-bottom: 6pt;
    }
    h3.subsection-heading {
        font-size: 10pt;
        font-weight: bold;
        font-style: italic;
        margin-top: 10pt;
        margin-bottom: 4pt;
    }
    p {
        margin-top: 0;
        margin-bottom: 6pt;
        text-indent: 14pt;
    }
    p.no-indent {
        text-indent: 0;
    }
    ul, ol {
        margin-top: 2pt;
        margin-bottom: 6pt;
        padding-left: 28pt;
    }
    li {
        margin-bottom: 3pt;
    }
    .equation-table {
        width: 100%;
        margin: 6pt 0;
        border-collapse: collapse;
    }
    .equation-table td {
        padding: 2pt;
        vertical-align: middle;
    }
    .eq-content {
        text-align: center;
        font-family: "Cambria Math", "Times New Roman", serif;
        font-style: italic;
    }
    .eq-num {
        width: 10%;
        text-align: right;
        font-family: "Times New Roman", serif;
        font-style: normal;
    }
    table.data-table {
        width: 95%;
        margin: 10pt auto;
        border-collapse: collapse;
        font-size: 8.5pt;
        line-height: 1.15;
    }
    table.data-table th, table.data-table td {
        border-top: 0.75pt solid #000;
        border-bottom: 0.75pt solid #000;
        padding: 4pt 6pt;
        text-align: center;
    }
    table.data-table th {
        font-weight: bold;
        background-color: #f8f8f8;
        border-bottom: 1.5pt solid #000;
        border-top: 1.5pt solid #000;
    }
    table.data-table td.left-align {
        text-align: left;
    }
    .table-caption {
        text-align: center;
        font-size: 8.5pt;
        font-weight: bold;
        text-transform: uppercase;
        margin-bottom: 4pt;
    }
    .reference-item {
        font-size: 8.5pt;
        margin-bottom: 4pt;
        text-indent: -18pt;
        margin-left: 18pt;
    }
    .boxed {
        border: 1pt solid #000;
        padding: 2pt 6pt;
        display: inline-block;
    }
</style>
</head>
<body>

<h1 class="title">Stochastic Game-Theoretic Optimization for Peer-to-Peer Energy Trading in Residential Microgrids Under Forecast Uncertainty</h1>

<div class="authors">
    <b>Aditya and Collaborators</b><br>
    Department of Electrical Engineering, SVNIT Surat, Gujarat, India
</div>

<div class="abstract-box">
    <p class="no-indent"><b><i>Abstract</i>—This paper presents a stochastic game-theoretic framework for peer-to-peer (P2P) energy management in a small residential microgrid. The system combines household demand and photovoltaic generation forecasting, residual-based Monte Carlo scenario generation, stochastic model predictive control (MPC) for battery dispatch, and a strategic double-auction model in which households select asking or bidding prices. The framework is evaluated using three households derived from the Ausgrid Solar Home Electricity dataset. On the held-out period from 19 April to 30 June 2013, the evaluation covers 1,752 hourly timestamps and 5,256 household-hour observations. Each stochastic market evaluation uses 1,000 scenarios. Demand and solar mean absolute errors are 0.4660 kWh and 0.0814 kWh, respectively; the corresponding 90% prediction-interval coverages are 81.91% and 89.42%. Across the full horizon, the deterministic ex-post market clears 121.6114 kWh, while the stochastic expected-payoff market clears 87.6472 kWh. A timestamp-level audit distinguishes overlapping and non-overlapping trading hours and quantifies the physical Jensen gap separately from role-conditioned order restrictions. The results demonstrate an end-to-end computational framework and identify the limits of interpreting ex-post and ex-ante market outcomes as directly equivalent. The study is a simulation-based prototype, not a field deployment.</b></p>
    <p class="no-indent" style="margin-top: 4pt;"><b><i>Keywords</i>—Peer-to-peer energy trading, residential microgrid, game theory, Nash equilibrium, stochastic optimization, Monte Carlo simulation, solar forecasting, model predictive control.</b></p>
</div>

<h2 class="section-heading">I. Introduction</h2>
<p>The increasing deployment of rooftop photovoltaic (PV) systems changes households from passive electricity consumers into prosumers that can both consume and export energy. At a given time, one household may have surplus solar generation while another experiences a demand deficit. Local peer-to-peer energy trading can create an opportunity to use part of this surplus within a community rather than relying entirely on grid export and grid import. However, household demand and solar generation are uncertain, and each participant may strategically choose the price at which it is willing to sell or buy energy.</p>
<p>This project studies the interaction between physical energy management and strategic market behaviour. Its central question is: how can a small community coordinate battery dispatch and P2P energy exchange when future demand and solar generation are uncertain and households choose their own trading prices? The proposed pipeline combines forecasting, scenario generation, stochastic battery control and non-cooperative game-theoretic market analysis.</p>
<p>The principal contributions are:</p>
<ol>
    <li>An integrated three-household simulation pipeline using real residential solar-home measurements.</li>
    <li>Uncertainty representation through 1,000 synchronized Monte Carlo scenarios.</li>
    <li>A strategic price-only double-auction game with deterministic and expected stochastic payoff analysis.</li>
    <li>Full-horizon evaluation of physical, financial and equilibrium properties.</li>
    <li>A quantitative decomposition that separates physical matching uncertainty, ex-ante role restrictions and observed market participation differences.</li>
</ol>
<p>All reported results are simulation results on historical data; no live electricity network or market deployment is claimed.</p>

<h2 class="section-heading">II. Related Work</h2>
<p>Peer-to-peer energy trading has been studied as a market arrangement that enables distributed energy resource owners to exchange electricity locally. Reviews identify market platforms, pricing, optimization, game theory and simulation as major research themes [1]. Game-theoretic formulations are particularly relevant when prosumers make strategic decisions and their outcomes depend on the actions of other participants. A clustered-microgrid study has, for example, applied game-theoretic optimization to P2P trading and participant payoff analysis [2].</p>
<p>Forecast uncertainty is also important in microgrid operation. Stochastic MPC methods represent uncertain load and renewable generation through scenarios and optimize decisions over a receding horizon [3]. Long short-term memory (LSTM) networks provide a recurrent neural architecture for learning temporal dependencies in sequences [4]. The present work combines these strands but focuses on the interaction between uncertain physical matching and strategic price selection in a small multi-household market.</p>

<h2 class="section-heading">III. System Model and Problem Formulation</h2>
<h3 class="subsection-heading">A. Residential Microgrid</h3>
<p>The simulated community contains three households, denoted H001, H002 and H003. Each household has a demand time series and a rooftop PV generation time series.</p>
<p>The selected household configurations used in the prototype are:</p>
<ul>
    <li>H001: 3.78 kWp PV capacity</li>
    <li>H002: 1.00 kWp PV capacity</li>
    <li>H003: 1.00 kWp PV capacity</li>
</ul>
<p class="no-indent">These are the configured participants in the experiment, not a claim that the three households represent the full Ausgrid population.</p>

<p>Each household is equipped with an identical residential battery energy storage system (BESS). The physical operational parameters implemented and enforced by the battery dispatch module (<code>src/energy/battery.py</code>) are:</p>
<ul>
    <li>Rated battery storage capacity: 5.0 kWh per household</li>
    <li>Maximum charging power limit (<i>P</i><sub>ch</sub><sup>max</sup>): 2.5 kW</li>
    <li>Maximum discharging power limit (<i>P</i><sub>dis</sub><sup>max</sup>): 2.5 kW</li>
    <li>Charging efficiency (&eta;<sub>ch</sub>): 95% (0.95)</li>
    <li>Discharging efficiency (&eta;<sub>dis</sub>): 95% (0.95), yielding an effective round-trip efficiency of &eta;<sub>rt</sub> = &eta;<sub>ch</sub> &times; &eta;<sub>dis</sub> &approx; 90.25%</li>
    <li>Operational state-of-charge (SoC) operating bounds: SoC<sub>min</sub> = 10% (0.10) and SoC<sub>max</sub> = 90% (0.90)</li>
    <li>Initial state-of-charge (SoC<sub>0</sub>): 50% (0.50, corresponding to 2.5 kWh stored energy)</li>
</ul>

<p>Let <i>D<sub>i</sub></i>(<i>t</i>) and <i>S<sub>i</sub></i>(<i>t</i>) denote the demand and solar generation of household <i>i</i> at time <i>t</i>. Let <i>C<sub>i</sub></i>(<i>t</i>) denote battery charging energy and <i>B<sub>i</sub></i>(<i>t</i>) denote battery discharging energy.</p>
<p>The post-battery net position of household <i>i</i> at time <i>t</i> is defined as:</p>
<table class="equation-table">
    <tr>
        <td class="eq-content"><i>n<sub>i</sub></i>(<i>t</i>) = [<i>D<sub>i</sub></i>(<i>t</i>) + <i>C<sub>i</sub></i>(<i>t</i>)] &minus; [<i>S<sub>i</sub></i>(<i>t</i>) + <i>B<sub>i</sub></i>(<i>t</i>)]</td>
        <td class="eq-num">(1)</td>
    </tr>
</table>

<p>The sign of <i>n<sub>i</sub></i>(<i>t</i>) governs the physical market role of household <i>i</i>:</p>
<ul>
    <li><i>n<sub>i</sub></i>(<i>t</i>) &lt; 0 represents a household net surplus (available seller energy <i>s<sub>i</sub></i>(<i>t</i>) = max(0, &minus;<i>n<sub>i</sub></i>(<i>t</i>))).</li>
    <li><i>n<sub>i</sub></i>(<i>t</i>) &gt; 0 represents a household net deficit (unserved buyer load <i>d<sub>i</sub></i>(<i>t</i>) = max(0, <i>n<sub>i</sub></i>(<i>t</i>))).</li>
</ul>

<p>Across the residential microgrid of <i>N</i> households (<i>N</i> = 3), the aggregate available community surplus <i>S</i>(<i>t</i>) and aggregate energy deficit <i>D</i>(<i>t</i>) at time <i>t</i> are formally defined as:</p>
<table class="equation-table">
    <tr>
        <td class="eq-content"><i>S</i>(<i>t</i>) = &sum;<sub><i>i</i>=1</sub><sup><i>N</i></sup> max(0, &minus;<i>n<sub>i</sub></i>(<i>t</i>))</td>
        <td class="eq-num">(2)</td>
    </tr>
    <tr>
        <td class="eq-content"><i>D</i>(<i>t</i>) = &sum;<sub><i>i</i>=1</sub><sup><i>N</i></sup> max(0, <i>n<sub>i</sub></i>(<i>t</i>))</td>
        <td class="eq-num">(3)</td>
    </tr>
</table>

<p>A feasible bilateral peer-to-peer traded quantity <i>Q</i><sub>P2P</sub>(<i>t</i>) between aggregate surplus <i>S</i>(<i>t</i>) and aggregate deficit <i>D</i>(<i>t</i>) is strictly bounded by:</p>
<table class="equation-table">
    <tr>
        <td class="eq-content"><i>Q</i><sub>P2P</sub>(<i>t</i>) &le; min(<i>S</i>(<i>t</i>), <i>D</i>(<i>t</i>))</td>
        <td class="eq-num">(4)</td>
    </tr>
</table>

<h3 class="subsection-heading">B. Grid Tariffs and Community Welfare</h3>
<p>The prototype uses:</p>
<ul>
    <li>Grid import tariff: AUD 0.30/kWh</li>
    <li>Grid export credit: AUD 0.08/kWh</li>
</ul>
<p class="no-indent">The difference, AUD 0.22/kWh, is the maximum community value created when one kWh that would otherwise be exported by a seller and imported by a buyer is instead matched locally, before considering any additional network or platform costs:</p>
<table class="equation-table">
    <tr>
        <td class="eq-content"><i>W</i>(<i>t</i>) = (0.30 &minus; 0.08) <i>Q</i><sub>P2P</sub>(<i>t</i>) = <b>0.22 <i>Q</i><sub>P2P</sub>(<i>t</i>)</b></td>
        <td class="eq-num">(5)</td>
    </tr>
</table>
<p>Household utility is defined as the negative of net energy expenditure. Net expenditure includes grid purchases, grid export revenue, P2P purchase payments and P2P sale revenue.</p>
<p>An accounting invariant checks that the sum of household incremental benefits equals community welfare for the implemented settlement accounting: &sum;<sub><i>i</i>=1</sub><sup><i>N</i></sup> <i>U<sub>i</sub></i>(<i>t</i>) = <i>W</i>(<i>t</i>).</p>

<h3 class="subsection-heading">C. Strategic Price Action Space and Merit-Order Double Auction</h3>
<p>The price-only auction uses the discrete action set:</p>
<p class="no-indent" style="text-align: center;"><b><i>P</i> = {0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30} AUD/kWh</b></p>
<p>A seller selects an asking price from <i>P</i> and a buyer selects a bidding price from <i>P</i>. The auction executes bilateral matching using a merit-order double-auction mechanism:</p>
<ol>
    <li><b>Order Book Construction and Sorting:</b> Seller ask orders are sorted in ascending merit order of asking price (lowest ask price first; ties broken deterministically by household ID). Buyer bid orders are sorted in descending merit order of bidding price (highest bid price first; ties broken deterministically by household ID).</li>
    <li><b>Crossing and Eligibility Condition:</b> An eligible matching round occurs if and only if the highest available buyer bid is at least the lowest available seller ask (<i>b</i><sub>max</sub> &ge; <i>a</i><sub>min</sub>). If <i>b</i><sub>max</sub> &lt; <i>a</i><sub>min</sub>, the order books do not cross and auction matching terminates.</li>
    <li><b>Midpoint Transaction Pricing:</b> For each matched transaction between seller <i>i</i> and buyer <i>j</i>, the cleared unit price is set to the exact midpoint of their submitted prices: <i>p<sub>ij</sub></i> = (<i>a</i><sub>min</sub> + <i>b</i><sub>max</sub>) / 2.</li>
    <li><b>Tie Handling and Pro-Rata Rationing:</b> When multiple sellers submit the same minimum ask price (<i>S</i><sub>tied</sub>) or multiple buyers submit the same maximum bid price (<i>B</i><sub>tied</sub>), the cleared volume at that price step is <i>Q</i><sub>trade</sub> = min(&sum;<sub><i>i</i>&isin;<i>S</i><sub>tied</sub></sub> <i>s<sub>i</sub></i><sup>rem</sup>, &sum;<sub><i>j</i>&isin;<i>B</i><sub>tied</sub></sub> <i>d<sub>j</sub></i><sup>rem</sup>). Volume is allocated among tied participants strictly pro-rata according to their remaining available quantities:
    <br><i>q<sub>i</sub></i><sup>alloc</sup> = <i>Q</i><sub>trade</sub> &times; [<i>s<sub>i</sub></i><sup>rem</sup> / &sum;<sub><i>k</i>&isin;<i>S</i><sub>tied</sub></sub> <i>s<sub>k</sub></i><sup>rem</sup>], &forall; <i>i</i> &isin; <i>S</i><sub>tied</sub>
    <br><i>q<sub>j</sub></i><sup>alloc</sup> = <i>Q</i><sub>trade</sub> &times; [<i>d<sub>j</sub></i><sup>rem</sup> / &sum;<sub><i>k</i>&isin;<i>B</i><sub>tied</sub></sub> <i>d<sub>k</sub></i><sup>rem</sup>], &forall; <i>j</i> &isin; <i>B</i><sub>tied</sub>
    <br>Bilateral trades between tied sellers and buyers are decomposed proportionally as <i>q<sub>ij</sub></i> = (<i>q<sub>i</sub></i><sup>alloc</sup> &times; <i>q<sub>j</sub></i><sup>alloc</sup>) / <i>Q</i><sub>trade</sub>.</li>
    <li><b>Iterative Clearing:</b> Available quantities are decremented by allocated volumes (<i>s<sub>i</sub></i><sup>rem</sup> &larr; <i>s<sub>i</sub></i><sup>rem</sup> &minus; <i>q<sub>i</sub></i><sup>alloc</sup>, <i>d<sub>j</sub></i><sup>rem</sup> &larr; <i>d<sub>j</sub></i><sup>rem</sup> &minus; <i>q<sub>j</sub></i><sup>alloc</sup>), and the algorithm iterates until no eligible matching pairs remain.</li>
</ol>
<p>This discrete action space makes exhaustive unilateral-deviation analysis tractable for the three-player game. The model studies strategic price selection; it does not model strategic quantity offers as independent actions.</p>

<h2 class="section-heading">IV. Proposed Methodology</h2>
<h3 class="subsection-heading">A. Data Processing and Forecasting</h3>
<p>The source is the Ausgrid Solar Home Electricity dataset, which records residential electricity consumption and rooftop solar generation [5]. The project uses the 2012–2013 data and constructs hourly series from the half-hourly source records. General consumption (GC), controlled load (CL) and gross generation (GG) are used in the data preparation pipeline. A three-household hourly dataset is prepared for forecasting and market simulation.</p>
<p>An LSTM model forecasts demand and solar generation from a sequence of recent observations and temporal features. The feature set used by the implemented model includes demand, solar generation, hour-of-day sine and cosine terms, and day-of-week sine and cosine terms. The model predicts the next demand and solar values. Forecast errors are evaluated on a held-out chronological test period; the test period is not used as the training target for the reported evaluation.</p>

<h3 class="subsection-heading">B. Residual-Based Monte Carlo Scenarios</h3>
<p>Forecasts provide point estimates but do not describe all possible future outcomes. The stochastic layer samples historical forecast residuals to construct 1,000 demand and solar scenarios for each timestamp. The implementation uses synchronized cross-household scenario sampling so that household residuals retain their common timestamp alignment. A deterministic timestamp-specific seed supports reproducible scenario construction within the pinned software and numerical environment.</p>
<p>The scenario generation equations are:</p>
<table class="equation-table">
    <tr>
        <td class="eq-content"><i>D<sub>i</sub></i><sup>(<i>s</i>)</sup>(<i>t</i>) = max(0, <i>D&#770;<sub>i</sub></i>(<i>t</i>) + &epsilon;<sub><i>D,i</i></sub><sup>(<i>s</i>)</sup>)</td>
        <td class="eq-num">(6a)</td>
    </tr>
    <tr>
        <td class="eq-content"><i>S<sub>i</sub></i><sup>(<i>s</i>)</sup>(<i>t</i>) = max(0, <i>S&#770;<sub>i</sub></i>(<i>t</i>) + &epsilon;<sub><i>S,i</i></sub><sup>(<i>s</i>)</sup>)</td>
        <td class="eq-num">(6b)</td>
    </tr>
</table>
<p class="no-indent">Here, <i>s</i> indexes the Monte Carlo scenario, hats denote point forecasts, &epsilon; denotes sampled residuals, and non-negativity is enforced for physical demand and generation.</p>
<p>Scenario generation represents uncertainty using an empirical residual distribution; it does not guarantee calibrated probability distributions, as reflected by the measured prediction-interval coverage.</p>

<h3 class="subsection-heading">C. Stochastic MPC Battery Dispatch</h3>
<p>The battery controller uses stochastic MPC to make an operational charging and discharging decision while accounting for uncertain net demand and PV generation. The first-stage battery decisions are frozen across the scenario set for the subsequent stochastic strategic game. This non-anticipativity condition ensures that the household does not choose a different already-committed battery action after learning which future scenario occurred. The market analysis therefore evaluates strategic trading conditional on the selected battery dispatch, rather than jointly re-optimizing battery actions for every price deviation.</p>

<h3 class="subsection-heading">D. Deterministic and Stochastic Strategic Games</h3>
<p>In the deterministic ex-post formulation (Phase 8C), the game is evaluated using the realized historical physical conditions at each timestamp. Each household selects an action from its role-appropriate price set, and the solver enumerates action profiles and unilateral deviations to identify pure Nash equilibria (PNE). A PNE is a profile in which no single player can improve its payoff by changing its own action while the other players' actions remain fixed.</p>
<p>The stochastic expected-payoff formulation (Phase 8E) evaluates each candidate action profile over all 1,000 scenarios. Expected payoff is the arithmetic mean of scenario payoffs, including scenarios with no trade. The implemented role-conditioned action rule determines each household's ex-ante role from its expected post-battery net position. Sellers choose an ask and buyers choose a bid; if a household's realized scenario role conflicts with its ex-ante role, it submits no order in that scenario. This is a restricted ex-ante policy class, not a fully contingent two-sided bidding policy.</p>
<p>The expected payoff is calculated as:</p>
<table class="equation-table">
    <tr>
        <td class="eq-content"><i>U&#772;<sub>i</sub></i>(<i>a</i>) = (1 / 1000) &sum;<sub><i>s</i>=1</sub><sup>1000</sup> <i>U<sub>i</sub></i>(<i>a</i>; <i>s</i>)</td>
        <td class="eq-num">(7)</td>
    </tr>
</table>
<p>The stochastic solver searches for PNE using expected payoffs and records strict and weak equilibria. Weak equilibria permit payoff-indifferent deviations; therefore, a large number of weak PNE in a zero-trade hour should not be interpreted as meaningful price discovery. Pareto-undominated equilibrium profiles are also identified to support equilibrium selection. The fairness-aware deterministic selection module is retained as a separate comparison stage.</p>

<h2 class="section-heading">V. Experimental Setup</h2>
<p>The full-horizon evaluation uses the held-out interval from 19 April 2013, 00:00 to 30 June 2013, 23:00. This interval contains 1,752 hourly timestamps. With three households, the evaluation contains 1,752 &times; 3 = 5,256 household-hour observations. The stochastic market uses 1,000 scenarios per timestamp. The deterministic and stochastic market outputs are compared on the same historical evaluation horizon, while recognizing that they represent different information structures: ex-post realized conditions versus ex-ante expected payoffs under uncertainty.</p>

<div class="table-caption">Table I. Experimental Configuration</div>
<table class="data-table">
    <tr>
        <th>Experimental Item</th>
        <th>Configured Value</th>
    </tr>
    <tr>
        <td class="left-align">Households</td>
        <td>H001, H002, H003</td>
    </tr>
    <tr>
        <td class="left-align">PV capacities</td>
        <td>3.78 kWp, 1.00 kWp, 1.00 kWp</td>
    </tr>
    <tr>
        <td class="left-align">Battery capacity & limits</td>
        <td>5.0 kWh capacity, 2.5 kW max charge/discharge, SoC &isin; [0.10, 0.90]</td>
    </tr>
    <tr>
        <td class="left-align">Held-out horizon</td>
        <td>2013-04-19 00:00 to 2013-06-30 23:00</td>
    </tr>
    <tr>
        <td class="left-align">Hourly timestamps</td>
        <td>1,752</td>
    </tr>
    <tr>
        <td class="left-align">Household-hour evaluations</td>
        <td>5,256</td>
    </tr>
    <tr>
        <td class="left-align">Monte Carlo scenarios</td>
        <td>1,000 per timestamp</td>
    </tr>
    <tr>
        <td class="left-align">Grid import / export</td>
        <td>AUD 0.30 / 0.08 per kWh</td>
    </tr>
    <tr>
        <td class="left-align">Price actions</td>
        <td>0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30 AUD/kWh</td>
    </tr>
    <tr>
        <td class="left-align">Auction settlement price</td>
        <td>Midpoint of compatible ask and bid with merit-order pro-rata clearing</td>
    </tr>
</table>

<h2 class="section-heading">VI. Results and Discussion</h2>
<h3 class="subsection-heading">A. Forecast Accuracy and Prediction Intervals</h3>
<p>Across the 5,256 household-hour observations, demand MAE is 0.4660 kWh and RMSE is 0.7834 kWh. Solar MAE is 0.0814 kWh and RMSE is 0.1600 kWh. The 90% prediction-interval coverage is 81.91% for demand and 89.42% for solar. Thus, the solar interval coverage is close to its nominal level, whereas the demand interval under-covers the nominal 90% target. These results indicate that the residual-based uncertainty model is more reliable for solar than for demand under this evaluation setup.</p>

<div class="table-caption">Table II. Forecast Performance</div>
<table class="data-table">
    <tr>
        <th>Forecast Target</th>
        <th>MAE (kWh)</th>
        <th>RMSE (kWh)</th>
        <th>90% PI Coverage</th>
        <th>Mean PI Width (kWh)</th>
    </tr>
    <tr>
        <td class="left-align">Demand</td>
        <td>0.4660</td>
        <td>0.7834</td>
        <td>81.91%</td>
        <td>1.2340</td>
    </tr>
    <tr>
        <td class="left-align">Solar</td>
        <td>0.0814</td>
        <td>0.1600</td>
        <td>89.42%</td>
        <td>0.3625</td>
    </tr>
</table>

<p>Forecast bias is reported using: Bias = mean(prediction &minus; actual). Under this convention, demand bias is &minus;0.133982 kWh and solar bias is +0.030114 kWh. This means that the model underpredicts demand on average and overpredicts solar generation on average. Earlier residual summaries used the opposite operand order, mean(actual &minus; prediction), which reverses the signs but not the underlying prediction errors.</p>

<h3 class="subsection-heading">B. Full-Horizon Market Outcomes</h3>
<p>Across the full 1,752-hour horizon, Phase 8C records 866 tradeable hours and 886 zero-trade hours. Phase 8E records 722 tradeable hours and 1,030 zero-trade hours. Total bilateral energy is 121.611449 kWh for Phase 8C and 87.647245 kWh for Phase 8E, a difference of &minus;33.964203 kWh (&minus;27.93%). Corresponding community welfare is AUD 26.754519 and AUD 19.282394, respectively. These are empirical differences between two formulations, not a controlled causal estimate of the effect of uncertainty alone.</p>

<div class="table-caption">Table III. Full-Horizon Market Comparison</div>
<table class="data-table">
    <tr>
        <th>Metric</th>
        <th>Phase 8C Deterministic Ex-Post</th>
        <th>Phase 8E Stochastic Expected</th>
    </tr>
    <tr>
        <td class="left-align">Tradeable hours</td>
        <td>866 (49.43%)</td>
        <td>722 (41.21%)</td>
    </tr>
    <tr>
        <td class="left-align">Zero-trade hours</td>
        <td>886 (50.57%)</td>
        <td>1,030 (58.79%)</td>
    </tr>
    <tr>
        <td class="left-align">Total bilateral energy</td>
        <td>121.611449 kWh</td>
        <td>87.647245 kWh</td>
    </tr>
    <tr>
        <td class="left-align">Total community welfare</td>
        <td>AUD 26.754519</td>
        <td>AUD 19.282394</td>
    </tr>
    <tr>
        <td class="left-align">H001 incremental payoff</td>
        <td>AUD 8.413031</td>
        <td>AUD 5.340941</td>
    </tr>
    <tr>
        <td class="left-align">H002 incremental payoff</td>
        <td>AUD 11.090010</td>
        <td>AUD 8.521557</td>
    </tr>
    <tr>
        <td class="left-align">H003 incremental payoff</td>
        <td>AUD 7.251477</td>
        <td>AUD 5.419896</td>
    </tr>
</table>

<p>The full-horizon participation difference is not a set of 144 identical hours. The timestamp-level contingency table contains: 473 hours in which both formulations trade, 393 deterministic-only trading hours, 249 stochastic-only trading hours, and 637 hours in which neither trades. The net difference in tradeable-hour counts is 866 &minus; 722 = 144. However, it arises from offsetting changes in both directions.</p>

<div class="table-caption">Table IV. Timestamp-Level Participation Comparison</div>
<table class="data-table">
    <tr>
        <th>Participation Regime</th>
        <th>Hours</th>
        <th>Share</th>
    </tr>
    <tr>
        <td class="left-align">Both formulations trade</td>
        <td>473</td>
        <td>26.99%</td>
    </tr>
    <tr>
        <td class="left-align">Phase 8C only</td>
        <td>393</td>
        <td>22.43%</td>
    </tr>
    <tr>
        <td class="left-align">Phase 8E only</td>
        <td>249</td>
        <td>14.21%</td>
    </tr>
    <tr>
        <td class="left-align">Neither trades</td>
        <td>637</td>
        <td>36.36%</td>
    </tr>
    <tr>
        <td class="left-align"><b>Total</b></td>
        <td><b>1,752</b></td>
        <td><b>100.00%</b></td>
    </tr>
</table>

<h3 class="subsection-heading">C. Household Benefit Distribution</h3>
<p>Under Phase 8C, H001, H002 and H003 receive 31.45%, 41.45% and 27.10% of total incremental household benefit, respectively. Under Phase 8E, the shares are 27.70%, 44.19% and 28.11%. The distribution changes between formulations, even though the sum of household incremental benefits remains consistent with aggregate community welfare under the implemented accounting identity. This is relevant because total welfare alone does not describe how the economic gains are distributed among participants.</p>

<h3 class="subsection-heading">D. Equilibrium Results</h3>
<p>Across the full horizon, the solver records 315,280 PNE for Phase 8C and 361,507 PNE for Phase 8E. Strict PNE increase from 1,224 to 1,825 (+49.10%), while weak PNE increase from 314,056 to 359,682. Pareto-undominated profiles number 312,810 and 356,107, respectively. The average number of PNE per tradeable hour is 13.48 for Phase 8C and 11.38 for Phase 8E. The increase in strict PNE is an observed empirical result; the analysis does not establish a causal mechanism such as larger unilateral deviation gaps from scenario averaging.</p>

<div class="table-caption">Table V. Equilibrium Comparison</div>
<table class="data-table">
    <tr>
        <th>Equilibrium Measure</th>
        <th>Phase 8C</th>
        <th>Phase 8E</th>
    </tr>
    <tr>
        <td class="left-align">Total PNE</td>
        <td>315,280</td>
        <td>361,507</td>
    </tr>
    <tr>
        <td class="left-align">Strict PNE</td>
        <td>1,224</td>
        <td>1,825</td>
    </tr>
    <tr>
        <td class="left-align">Weak PNE</td>
        <td>314,056</td>
        <td>359,682</td>
    </tr>
    <tr>
        <td class="left-align">Pareto-undominated profiles</td>
        <td>312,810</td>
        <td>356,107</td>
    </tr>
    <tr>
        <td class="left-align">Mean PNE per tradeable hour</td>
        <td>13.48</td>
        <td>11.38</td>
    </tr>
</table>

<p>Zero-trade hours require careful interpretation. In Phase 8E, a zero-trade hour can produce 343 weak PNE because all action profiles and unilateral deviations yield zero payoffs (7<sup>3</sup> = 343 combinations). These are indifference equilibria generated by payoff equivalence, not evidence that the market has discovered 343 economically meaningful prices.</p>

<h3 class="subsection-heading">E. Physical Matching and Jensen-Gap Audit</h3>
<p>Jensen's inequality for the concave matching function min(<i>S</i>, <i>D</i>) gives: <i>E</i>[min(<i>S</i>, <i>D</i>)] &le; min(<i>E</i>[<i>S</i>], <i>E</i>[<i>D</i>]).</p>
<p>A scenario-level audit was performed for the 473 timestamps where both Phase 8C and Phase 8E trade. The aggregate matching quantity at expected physical positions is 155.9049 kWh, while expected physical matching across the 1,000 scenarios is 90.0524 kWh. The resulting physical Jensen gap is 65.8524 kWh, or 42.24% of the mean-position matching quantity. The inequality holds at all 473 timestamps; the smallest measured positive gap is 0.000386 kWh.</p>

<div class="table-caption">Table VI. Matching Decomposition Over 473 Overlapping Hours</div>
<table class="data-table">
    <tr>
        <th>Matching Stage</th>
        <th>Aggregate Quantity</th>
    </tr>
    <tr>
        <td class="left-align">Matching at expected positions, min(<i>E</i>[<i>S</i>], <i>E</i>[<i>D</i>])</td>
        <td>155.9049 kWh</td>
    </tr>
    <tr>
        <td class="left-align">Expected physical matching, <i>E</i>[min(<i>S</i>, <i>D</i>)]</td>
        <td>90.0524 kWh</td>
    </tr>
    <tr>
        <td class="left-align">Physical Jensen gap</td>
        <td>65.8524 kWh (42.24%)</td>
    </tr>
    <tr>
        <td class="left-align">Expected physical matching after role clamping</td>
        <td>63.6854 kWh</td>
    </tr>
    <tr>
        <td class="left-align">Actual Phase 8E expected auction clearing</td>
        <td>63.6854 kWh</td>
    </tr>
    <tr>
        <td class="left-align">Phase 8C ex-post cleared volume</td>
        <td>78.3303 kWh</td>
    </tr>
</table>

<p>The role-conditioned order rule reduces expected physical matching from 90.0524 kWh to 63.6854 kWh, a reduction of 26.3671 kWh (29.28% of expected physical matching). On these 473 overlapping hours, the selected Phase 8E equilibria clear the role-clamped quantity (100.0% execution, 0.0000 kWh strategic withholding). This equality is specific to the audited sample and definition; it does not prove that strategic pricing can never reduce trading in other settings.</p>
<p>Phase 8C ex-post volume on the same 473 hours is 78.3303 kWh, whereas Phase 8E expected auction volume is 63.6854 kWh, a difference of &minus;14.6449 kWh (&minus;18.70%). However, expected physical matching (90.0524 kWh) is itself 14.97% higher than the Phase 8C ex-post volume. Therefore, the observed &minus;18.70% Phase 8C-to-Phase 8E difference must not be labelled as the Jensen effect. The Jensen gap compares mean-position matching with expected physical matching; role clamping is a separate restriction; and Phase 8C is an ex-post equilibrium on one realized historical trajectory.</p>

<p>The decomposition is:</p>
<table class="equation-table">
    <tr>
        <td class="eq-content"><i>Q</i><sub>stoch</sub> &minus; <i>Q</i><sub>det</sub> = (<i>Q</i><sub>stoch</sub> &minus; <i>Q</i><sub>physical expected</sub>) + (<i>Q</i><sub>physical expected</sub> &minus; <i>Q</i><sub>det</sub>)</td>
    </tr>
    <tr>
        <td class="eq-content">63.6854 &minus; 78.3303 = (63.6854 &minus; 90.0524) + (90.0524 &minus; 78.3303)</td>
    </tr>
    <tr>
        <td class="eq-content"><span class="boxed"><b>&minus;14.6449 = &minus;26.3671 + 11.7221 kWh</b></span></td>
    </tr>
</table>
<p>The full-horizon difference of &minus;27.93% additionally reflects extensive-margin participation changes across the 393 deterministic-only and 249 stochastic-only hours. It is not a single Jensen effect. This distinction prevents conflating physical uncertainty, ex-ante role restrictions and market participation changes.</p>

<h3 class="subsection-heading">F. Physical and Financial Consistency</h3>
<p>The Phase 9 validation reports zero physical constraint violations over the 1,752 timestamps. Financial accounting identities pass across the evaluated records, with maximum reported identity errors below 10<sup>&minus;15</sup> AUD. The welfare identity links community welfare to the tariff spread and locally traded quantity. These checks support internal consistency of the simulated energy and settlement accounting; they do not by themselves validate distribution-network voltage, line-loss or protection constraints, which are outside the three-household model's stated scope.</p>

<h2 class="section-heading">VII. Limitations</h2>
<p>The study is a three-household computational prototype and does not establish performance at feeder or city scale. The market uses a discrete price-only action space and a restricted role-conditioned policy class. Battery first-stage decisions are frozen across scenarios, so the strategic market does not jointly re-optimize storage for every scenario or price deviation. Residual-based Monte Carlo sampling depends on the representativeness of the residual pool; demand prediction intervals under-cover the nominal 90% level. The dataset does not provide a complete distribution-network model in this project configuration, so voltage, line thermal limits, network losses and local grid constraints are not evaluated. Finally, the tariff spread and household configuration are simulation assumptions and should not be interpreted as current retail tariffs or a validated commercial settlement design.</p>

<h2 class="section-heading">VIII. Conclusion and Future Work</h2>
<p>This paper presented an integrated stochastic game-theoretic framework for residential P2P energy management. The pipeline combines LSTM-based household forecasting, residual-based Monte Carlo scenarios, stochastic MPC battery dispatch and strategic ask/bid selection. Full-horizon evaluation over 1,752 hours demonstrated forecast performance, physical and financial consistency, and measurable differences between deterministic ex-post and stochastic expected-payoff market outcomes.</p>
<p>The quantitative matching audit is a key finding: Jensen's inequality holds for all 473 overlapping trading hours, with an aggregate physical gap of 65.8524 kWh between matching at expected positions and expected physical matching. A further 26.3671 kWh reduction is associated with the implemented ex-ante role-conditioned order restriction. The observed 18.70% difference between deterministic and stochastic cleared volume on the overlapping hours is not itself the Jensen gap. Across the full horizon, market participation changes in both directions, so the 27.93% aggregate volume difference should be interpreted as an empirical comparison of two different information and strategy formulations.</p>
<p>Future work includes improving demand interval calibration, testing conformal or adaptive uncertainty calibration, expanding the number of households, evaluating continuous or richer bidding policies, modelling strategic quantity offers, jointly optimizing storage and market decisions, and adding distribution-network constraints. A larger-scale validation with contemporary data and realistic tariff structures would be required before considering operational deployment.</p>

<h2 class="section-heading">Acknowledgment</h2>
<p>The authors acknowledge [Project Guide's Full Name], [Designation], Department of [Department], SVNIT Surat, for guidance and feedback.</p>

<h2 class="section-heading">References</h2>
<div class="reference-item">[1] E. A. Soto, L. B. Bosman, E. Wollega, and W. D. Leon-Salas, &ldquo;Peer-to-peer energy trading: A review of the literature,&rdquo; <i>Applied Energy</i>, vol. 283, Art. no. 116268, Feb. 2021, doi: 10.1016/j.apenergy.2020.116268.</div>
<div class="reference-item">[2] L. Ali, S. M. Muyeen, H. Bizhani, and A. Ghosh, &ldquo;A peer-to-peer energy trading for a clustered microgrid&mdash;Game theoretical approach,&rdquo; <i>International Journal of Electrical Power &amp; Energy Systems</i>, vol. 129, Art. no. 106797, 2021, doi: 10.1016/j.ijepes.2021.107307.</div>
<div class="reference-item">[3] Y. Zhang, F. Meng, R. Wang, W. Zhu, and X.-J. Zeng, &ldquo;A stochastic MPC based approach to integrated energy management in microgrids,&rdquo; <i>Sustainable Cities and Society</i>, vol. 41, pp. 349&ndash;362, Aug. 2018, doi: 10.1016/j.scs.2018.05.044.</div>
<div class="reference-item">[4] S. Hochreiter and J. Schmidhuber, &ldquo;Long short-term memory,&rdquo; <i>Neural Computation</i>, vol. 9, no. 8, pp. 1735&ndash;1780, 1997, doi: 10.1162/neco.1997.9.8.1735.</div>
<div class="reference-item">[5] Ausgrid, &ldquo;Solar Home Electricity Data,&rdquo; Ausgrid. [Online]. Available: https://www.ausgrid.com.au/Industry/Our-Research/Data-to-share/Solar-home-electricity-data. [Accessed: Nov. 1, 2026].</div>
<div class="reference-item">[6] J. F. Nash, &ldquo;Equilibrium points in n-person games,&rdquo; <i>Proceedings of the National Academy of Sciences</i>, vol. 36, no. 1, pp. 48&ndash;49, 1950, doi: 10.1073/pnas.36.1.48.</div>

</body>
</html>
"""

def save_html():
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(HTML_CONTENT)
    print(f"Saved HTML to: {HTML_PATH}")

def convert_to_docx_and_pdf():
    print("Launching Word COM Application...")
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    try:
        print(f"Opening HTML: {HTML_PATH}")
        doc = word.Documents.Open(HTML_PATH)
        
        # Save as DOCX (wdFormatXMLDocument = 16)
        print(f"Saving DOCX to: {DOCX_PATH}")
        doc.SaveAs2(DOCX_PATH, 16)
        
        # Export as PDF (wdExportFormatPDF = 17)
        print(f"Exporting PDF to: {PDF_PATH}")
        doc.ExportAsFixedFormat(PDF_PATH, 17)
        
        doc.Close()
        print("Conversion completed successfully!")
    finally:
        word.Quit()

if __name__ == "__main__":
    save_html()
    convert_to_docx_and_pdf()

