"""
Script to build the official project report in Microsoft Word (.docx) format
using the IEEE Conference template (Project Report Format.docx) provided by supervisor,
fully aligned with the 5-household flagship Monte Carlo stochastic game architecture,
all 7 verified figures, and complete academic tables.
"""

import sys
import os
import shutil
import zipfile
from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

ROOT = Path(__file__).resolve().parent

def set_cell_border(cell, **kwargs):
    """
    Set cell borders for IEEE style table formatting (booktabs).
    kwargs can contain: top, bottom, left, right, insideH, insideV
    e.g. bottom={'val': 'single', 'sz': '4', 'color': 'auto'}
    """
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = tcPr.first_child_found_in('w:tcBorders')
    if tcBorders is None:
        tcBorders = OxmlElement('w:tcBorders')
        tcPr.append(tcBorders)
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        edge_data = kwargs.get(edge)
        if edge_data:
            tag = f'w:{edge}'
            element = tcBorders.find(qn(tag))
            if element is None:
                element = OxmlElement(tag)
                tcBorders.append(element)
            for key, val in edge_data.items():
                element.set(qn(f'w:{key}'), str(val))

def set_cell_shading(cell, color_hex):
    """Set background color of a cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    tcPr.append(shd)

def create_normalized_template():
    """Ensure Project_Report_Format_norm.docx exists with standard openxml namespaces."""
    raw_path = ROOT / "reports" / "Project_Report_Format.docx"
    norm_path = ROOT / "reports" / "Project_Report_Format_norm.docx"

    replacements = [
        (b'http://purl.oclc.org/ooxml/officeDocument/relationships/', b'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'),
        (b'http://purl.oclc.org/ooxml/wordprocessingml/', b'http://schemas.openxmlformats.org/wordprocessingml/2006/'),
        (b'http://purl.oclc.org/ooxml/drawingml/', b'http://schemas.openxmlformats.org/drawingml/2006/'),
    ]

    with zipfile.ZipFile(raw_path, 'r') as zin, zipfile.ZipFile(norm_path, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            for old, new in replacements:
                data = data.replace(old, new)
            zout.writestr(item, data)

    return norm_path

def build_word_report():
    print("Preparing normalized IEEE template...")
    norm_path = create_normalized_template()
    doc = docx.Document(str(norm_path))

    body = doc._body._element

    # 1. Update Title in paragraph 0
    p_title = doc.paragraphs[0]
    p_title.text = "Stochastic Game-Theoretic Optimization for Peer-to-Peer Energy Trading with Distributed Battery Storage under Uncertainty"
    p_title.style = 'paper title'
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Paragraph 1 subtitle note: make it blank or project subtitle
    p_sub = doc.paragraphs[1]
    p_sub.text = ""

    # Paragraph 2 & 3: empty spacing with section break
    doc.paragraphs[2].text = ""

    # Paragraphs 4, 5, 6: 3-Author block in 3 columns
    authors_info = [
        ("Aditya", "u24mc003@amhd.svnit.ac.in"),
        ("Heet", "u24mc019@amhd.svnit.ac.in"),
        ("Dimpal", "u24mc020@amhd.svnit.ac.in"),
    ]
    for i, (name, email) in enumerate(authors_info):
        p = doc.paragraphs[4 + i]
        p.text = (
            f"{name}\n"
            f"Department of Mathematics\n"
            f"Sardar Vallabhbhai National Institute of Technology (SVNIT)\n"
            f"Surat, Gujarat, India\n"
            f"{email}"
        )
        p.style = 'Author'
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if i < 2:
            r = p.add_run()
            br = OxmlElement('w:br')
            br.set(qn('w:type'), 'column')
            r._r.append(br)

    # Clear paragraph 7
    doc.paragraphs[7].text = ""

    # Paragraph 8 and 9 contain the transitions to Section 3 (2 columns)
    doc.paragraphs[8].text = ""
    doc.paragraphs[9].text = ""

    # Remove all default template placeholder paragraphs from index 10 onwards (except p89 and trailing)
    # We will remove placeholder elements and insert our clean article text!
    # Let's inspect paragraphs 10 through 90
    print(f"Total initial paragraphs: {len(doc.paragraphs)}")

    # We can delete all child elements from body between p[10] and p[89]
    elements_to_remove = []
    p10_elem = doc.paragraphs[10]._p
    p89_elem = doc.paragraphs[89]._p

    collect = False
    for child in list(body):
        if child == p10_elem:
            collect = True
        if child == p89_elem:
            collect = False
            break
        if collect:
            elements_to_remove.append(child)

    for el in elements_to_remove:
        body.remove(el)

    print(f"Removed {len(elements_to_remove)} placeholder elements.")

    # Now we insert our content before p89_elem so it sits inside the 2-column Section 3!
    # Helper insertion function:
    def insert_p_before_89(text="", style='Body Text', align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=4, bold_prefix=None):
        p = doc.add_paragraph()
        p89_elem.addprevious(p._p)
        try:
            p.style = style
        except Exception:
            p.style = 'Normal'
        p.alignment = align
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = 1.05

        if bold_prefix:
            r_pre = p.add_run(bold_prefix)
            r_pre.bold = True
            r_pre.font.name = 'Times New Roman'
        if text:
            r = p.add_run(text)
            r.font.name = 'Times New Roman'
        return p

    def insert_heading_1(title):
        p = insert_p_before_89(title, style='Heading 1', align=WD_ALIGN_PARAGRAPH.LEFT, space_after=6)
        p.runs[0].bold = True
        return p

    def insert_heading_2(title):
        p = insert_p_before_89(title, style='Heading 2', align=WD_ALIGN_PARAGRAPH.LEFT, space_after=4)
        p.runs[0].bold = True
        p.runs[0].italic = True
        return p

    def insert_equation(eq_str, eq_num):
        p = insert_p_before_89("", style='Body Text', align=WD_ALIGN_PARAGRAPH.LEFT, space_after=4)
        r = p.add_run(f"    {eq_str}")
        r.italic = True
        r.font.name = 'Times New Roman'
        # Add equation number flush right
        r_num = p.add_run(f"   ({eq_num})")
        r_num.bold = True
        return p

    def insert_figure(img_path_str, caption_title):
        # Insert image
        p_img = insert_p_before_89("", style='Body Text', align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
        run_img = p_img.add_run()
        run_img.add_picture(img_path_str, width=Inches(3.35))
        # Insert caption
        p_cap = insert_p_before_89(caption_title, style='figure caption', align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)
        p_cap.runs[0].font.size = Pt(8.0)
        p_cap.runs[0].italic = True
        return p_cap

    def insert_table(table_data, col_widths, caption_title):
        # Table caption
        p_cap = insert_p_before_89(caption_title, style='table head', align=WD_ALIGN_PARAGRAPH.CENTER, space_after=3)
        p_cap.runs[0].font.size = Pt(8.0)
        p_cap.runs[0].bold = True

        table = doc.add_table(rows=0, cols=len(col_widths))
        p89_elem.addprevious(table._tbl)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        # Build rows
        for row_idx, row_values in enumerate(table_data):
            row = table.add_row()
            is_header = (row_idx == 0)
            is_footer = (row_idx == len(table_data) - 1)

            for col_idx, val in enumerate(row_values):
                cell = row.cells[col_idx]
                cell.width = col_widths[col_idx]
                cell.text = str(val)
                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(2)

                if is_header:
                    try:
                        p.style = 'table col head'
                    except Exception:
                        pass
                    for r in p.runs:
                        r.bold = True
                        r.font.size = Pt(7.5)
                        r.font.name = 'Times New Roman'
                    set_cell_border(cell, top={'val': 'single', 'sz': '8', 'color': 'black'},
                                          bottom={'val': 'single', 'sz': '6', 'color': 'black'})
                    set_cell_shading(cell, "F2F2F2")
                elif is_footer:
                    try:
                        p.style = 'table copy'
                    except Exception:
                        pass
                    for r in p.runs:
                        r.bold = True
                        r.font.size = Pt(7.5)
                        r.font.name = 'Times New Roman'
                    set_cell_border(cell, top={'val': 'single', 'sz': '4', 'color': 'black'},
                                          bottom={'val': 'single', 'sz': '8', 'color': 'black'})
                else:
                    try:
                        p.style = 'table copy'
                    except Exception:
                        pass
                    for r in p.runs:
                        r.font.size = Pt(7.5)
                        r.font.name = 'Times New Roman'
                    set_cell_border(cell, bottom={'val': 'none', 'sz': '0', 'color': 'white'})

        # spacing after table
        insert_p_before_89("", space_after=6)
        return table

    # -------------------------------------------------------------------------
    # DOCUMENT BODY CONTENT
    # -------------------------------------------------------------------------

    # ABSTRACT
    p_abs = insert_p_before_89(
        "Rapid proliferation of residential rooftop photovoltaics (PV) and distributed battery energy storage systems (BESS) "
        "necessitates decentralized market mechanisms to overcome retail feed-in tariff distortions. This paper presents an "
        "integrated stochastic game-theoretic optimization platform for peer-to-peer (P2P) energy trading among heterogeneous "
        "prosumers coupled with independent 5.0 kWh physical battery storage. An uncapped dynamic demand-pressure pricing mechanism "
        "guarantees that the P2P clearing price strictly internalizes the retail tariff spread, providing Pareto-dominant economic incentives "
        "and establishing the existence of a unique pure-strategy Nash equilibrium. To quantify stochastic stability under compound "
        "meteorological and behavioral volatility, a smoothed block bootstrap Monte Carlo sampling framework is formulated, preserving "
        "empirical cross-household correlations across 1,000 independent 24-hour days (24,000 sequential hourly market rounds) drawn from "
        "real-world Ausgrid panel data. Four operational counterfactuals are evaluated: pure grid baseline, solar self-consumption, "
        "battery self-consumption without P2P, and the full proposed game-theoretic model. Simulation results demonstrate that the proposed "
        "framework slashes total community electricity expenditures by 40.07%, saving an average of $10.56 AUD/day across the microgrid "
        "(reducing daily community energy expenditure from $26.36/day under pure grid reliance down to $15.80/day under coordinated trading). "
        "Factor decomposition confirms that while solar self-consumption ($5.52 AUD/day, 52.3%) and battery storage ($4.50 AUD/day, 42.6%) "
        "furnish substantial baseline arbitrage, P2P software coordination delivers an additional $0.54 AUD/day (5.1% of community savings, "
        "and up to 19.1% for high-demand consumers) with zero marginal hardware expenditure. "
        "Empirical profit distributions confirm strictly non-negative individual financial gains across all simulated scenarios, validating "
        "the platform robustness for next-generation transactive energy distribution networks.",
        style='Abstract',
        bold_prefix="Abstract—"
    )

    # KEYWORDS
    insert_p_before_89(
        "Peer-to-peer energy trading, game theory, battery energy storage systems, Nash equilibrium, dynamic pricing, "
        "Monte Carlo simulation, prosumer microgrid, uncertainty quantification.",
        style='Keywords',
        bold_prefix="Keywords—"
    )

    # I. INTRODUCTION
    insert_heading_1("I. INTRODUCTION")
    insert_p_before_89(
        "The global transition toward decentralized electricity networks is driven by the rapid adoption of behind-the-meter "
        "distributed energy resources (DERs), primarily residential rooftop photovoltaic (PV) systems and battery energy storage "
        "systems (BESS) [1]. While widespread PV adoption reduces greenhouse gas emissions and offsets centralized utility generation "
        "requirements, uncoordinated injection of surplus solar power creates severe operational challenges in low-voltage distribution feeders. "
        "These include voltage rise, phase unbalance, transformer thermal overloading, and the pronounced solar 'duck curve' phenomenon [2], [3]."
    )
    insert_p_before_89(
        "A primary structural barrier to efficient residential energy utilization is the substantial spread between retail import tariffs "
        "and feed-in export credits imposed by utility retailers [4]. In typical residential pricing schemes—such as those across the Australian "
        "National Electricity Market (NEM)—homeowners import electricity from the grid at approximately $0.30/kWh while receiving a feed-in credit "
        "of only $0.08/kWh for exported solar. This 22¢/kWh spread creates an economic distortion: prosumers with abundant midday solar generation "
        "receive negligible compensation, while adjacent neighbors without solar are forced to import energy at full retail price."
    )
    insert_p_before_89(
        "Peer-to-peer (P2P) local energy trading has emerged as an attractive market framework to internalize this spread [5], [6]. By enabling "
        "direct, localized electricity transactions within a distribution feeder, P2P markets allow prosumers to sell surplus energy at prices above "
        "the utility export credit (P_export = $0.08/kWh) while offering consumers energy below the grid import rate (P_import = $0.30/kWh). "
        "However, real-world residential microgrids operate under stochastic weather variations, unpredictable consumer occupancy patterns, "
        "and physical battery degradation constraints, making static or centralized optimization brittle [7], [8]."
    )
    insert_p_before_89(
        "Centralized microgrid controllers require continuous communication of private consumption schedules and state-of-charge (SOC) metrics, "
        "raising severe user privacy and single-point-of-failure vulnerabilities [9]. Conversely, decentralized game-theoretic architectures "
        "model prosumers as autonomous, rational agents seeking to maximize individual economic utility while preserving operational privacy [10], [11]."
    )
    insert_p_before_89(
        "To address these challenges, this paper presents an integrated stochastic game-theoretic optimization platform for residential microgrids. "
        "The principal contributions of this work are as follows:"
    )
    insert_p_before_89("1) An N-player normal-form energy trading game coupling heterogeneous residential prosumers with independent 5.0 kWh physical battery storage;", style='bullet list')
    insert_p_before_89("2) An uncapped dynamic demand-pressure pricing mechanism guaranteeing Pareto-dominant coordination and individual rationality;", style='bullet list')
    insert_p_before_89("3) A smoothed block bootstrap Monte Carlo sampling framework evaluating 1,000 independent 24-hour days (24,000 sequential hourly market rounds) over real-world Ausgrid panel data;", style='bullet list')
    insert_p_before_89("4) A rigorous four-mode counterfactual evaluation isolating the exact financial dividends of solar (52.3%), battery storage (42.6%), and P2P software coordination (5.1%).", style='bullet list')

    # II. SYSTEM ARCHITECTURE AND DATASET
    insert_heading_1("II. SYSTEM ARCHITECTURE AND DATASET")
    insert_heading_2("A. Microgrid Participant Topology")
    insert_p_before_89(
        "The modeled residential microgrid consists of N = 5 heterogeneous prosumer households (N = {H001, H002, H003, H004, H005}) "
        "connected to a common local distribution feeder and utility point of common coupling (PCC). Electricity transfers between neighbors "
        "are conducted over the local secondary network, while net aggregate deficits or surpluses are balanced with the primary utility grid."
    )

    insert_heading_2("B. Empirical Dataset Calibration")
    insert_p_before_89(
        "The load and generation profiles originate from the open-source Ausgrid Solar Home Electricity Dataset (Sydney, Australia) [12], "
        "which records General Consumption (GC), Controlled Load (CL), and Gross Generation (GG) for 300 homes at 30-minute intervals over a full year. "
        "Readings were aggregated into clean hourly intervals (Δt = 1.0 h). Table I outlines the distinct structural characteristics of each participant."
    )

    # TABLE I
    t1_data = [
        ["Participant", "Role Archetype", "PV (kWp)", "Avg Demand (kWh/d)", "Avg Solar (kWh/d)", "Net Position"],
        ["H001", "High-Solar Seller", "5.0", "20.90 ± 8.87", "16.03 ± 8.81", "Net Midday Seller"],
        ["H002", "Low-Load Prosumer", "1.5", "6.02 ± 1.83", "4.77 ± 2.50", "Balanced Prosumer"],
        ["H003", "Moderate-Load Prosumer", "2.0", "13.70 ± 4.60", "5.67 ± 3.01", "Regular Net Buyer"],
        ["H004", "High-Demand Consumer", "1.0", "33.75 ± 13.91", "3.06 ± 1.63", "Dominant Net Buyer"],
        ["H005", "Opportunistic Prosumer", "2.5", "13.49 ± 4.19", "9.03 ± 5.25", "Swing Trader"],
        ["Community Total", "5-House Microgrid", "12.0", "87.85 ± 24.23", "38.56 ± 20.31", "Net Energy Buyer"],
    ]
    t1_widths = [Inches(0.65), Inches(0.75), Inches(0.35), Inches(0.55), Inches(0.55), Inches(0.55)]
    insert_table(t1_data, t1_widths, "TABLE I: Household Structural Profiles and Microgrid Archetypes")

    # FIG 1: Demand and Solar Profiles
    insert_figure(
        str(ROOT / "results" / "figures" / "simulate_five_house" / "05_demand_solar_profiles.png"),
        "Fig. 1. Mean 24-hour diurnal gross load and rooftop solar generation profiles for the five microgrid participants."
    )

    # III. PHYSICAL BATTERY STORAGE FORMULATION
    insert_heading_1("III. PHYSICAL BATTERY STORAGE FORMULATION")
    insert_heading_2("A. Battery Energy Storage System Parameters")
    insert_p_before_89(
        "Each household possesses an independent physical BESS reflecting commercial lithium-ion systems: nominal energy capacity "
        "E_cap = 5.0 kWh, maximum charge/discharge power P_ch^max = P_dis^max = 2.5 kW, round-trip efficiency η_rt = 95.0% "
        "(η_ch = η_dis = sqrt(0.95) ≈ 0.9747), safe operating state-of-charge bounds SOC_min = 10% (0.5 kWh) and SOC_max = 90% (4.5 kWh), "
        "initialized at SOC_0 = 50% (2.5 kWh) at 00:00."
    )

    insert_heading_2("B. Pre-Game Greedy Dispatch Strategy")
    insert_p_before_89(
        "Battery dispatch is executed prior to market clearing via deterministic greedy self-consumption. "
        "Let S_i,t^raw = max(0, G_i,t - D_i,t) and D_i,t^raw = max(0, D_i,t - G_i,t)."
    )
    insert_equation("P_ch,i = min(S_i^raw, P_ch^max, [SOC_max - SOC_i] E_cap / (η_ch Δt))", 1)
    insert_equation("S_i^net = max(0, S_i^raw - P_ch,i)", 2)
    insert_equation("P_dis,i = min(D_i^raw, P_dis^max, [SOC_i - SOC_min] E_cap η_dis / Δt)", 3)
    insert_equation("D_i^net = max(0, D_i^raw - P_dis,i)", 4)
    insert_equation("SOC_i,t+1 = SOC_i,t + (P_ch,i η_ch - P_dis,i / η_dis) / E_cap", 5)

    # IV. DYNAMIC PRICING DISCOVERY AND GAME FORMULATION
    insert_heading_1("IV. DYNAMIC PRICING DISCOVERY AND GAME FORMULATION")
    insert_heading_2("A. Market Aggregate Pool Formulations")
    insert_p_before_89(
        "The community aggregate pool surplus and deficit are defined as:"
    )
    insert_equation("S_pool,t = Σ_{i=1}^N S_i,t^net,    D_pool,t = Σ_{i=1}^N D_i,t^net", 6)

    insert_heading_2("B. Dynamic Price Discovery Mechanism")
    insert_p_before_89(
        "The demand-to-supply market pressure ratio is given by:"
    )
    insert_equation("λ_t = D_pool,t / (S_pool,t + ε)", 7)
    insert_p_before_89(
        "where ε = 10^-6 kWh prevents singularity. The dynamic P2P clearing price is formulated as:"
    )
    insert_equation("P_P2P,t = P_export + (λ_t / λ_max) (P_import - P_export)", 8)
    insert_p_before_89(
        "bounded strictly within [P_export, P_import] = [$0.08, $0.30] AUD/kWh with sensitivity λ_max = 2.0."
    )

    insert_heading_2("C. Market Clearing and Nash Equilibrium")
    insert_p_before_89(
        "Total physical P2P energy cleared is Q_trade,t = min(S_pool,t, D_pool,t), allocated pro-rata among trading agents. "
        "Each prosumer minimizes net electricity cost:"
    )
    insert_equation("Cost_i,t^P2P = m_i,t P_import + q_i,t^buy P_P2P - q_i,t^sell P_P2P - e_i,t P_export", 9)
    insert_p_before_89(
        "Because P_export ≤ P_P2P,t ≤ P_import, Cost_i,t^P2P ≤ Cost_i,t^grid holds strictly for all participants. "
        "Participation in the dynamic P2P trading market is therefore a weakly dominant strategy, proving that the all-trading profile "
        "forms a Pareto-dominant strict Nash equilibrium."
    )

    # V. MONTE CARLO UNCERTAINTY QUANTIFICATION
    insert_heading_1("V. MONTE CARLO UNCERTAINTY QUANTIFICATION")
    insert_p_before_89(
        "To evaluate stochastic stability, a smoothed block bootstrap Monte Carlo sampling framework is formulated. "
        "For each of 1,000 scenarios, an entire 24-hour day vector is sampled from historical days to preserve cross-household correlation. "
        "Gaussian perturbation scaled by diurnal standard deviation σ(h) is injected:"
    )
    insert_equation("D_i,h^(s) = max(0, D_i,h^(ds) + ε_D),   ε_D ~ N(0, [0.15 σ_D,i(h)]^2)", 10)
    insert_equation("G_i,h^(s) = max(0, G_i,h^(ds) + ε_S),   ε_S ~ N(0, [0.15 σ_S,i(h)]^2)", 11)
    insert_p_before_89(
        "Nighttime solar is strictly clamped to zero if base generation is zero. Over 1,000 days (24,000 sequential rounds), "
        "daily costs are aggregated over 24 hours, and final reported metrics represent arithmetic means across all 1,000 scenarios."
    )

    # VI. SIMULATION RESULTS AND DISCUSSION
    insert_heading_1("VI. SIMULATION RESULTS AND DISCUSSION")
    insert_heading_2("A. Cost Comparison Across Four Operational Modes")
    insert_p_before_89(
        "Four operational counterfactuals were evaluated across 1,000 Monte Carlo scenarios: "
        "Mode 1 (Pure Grid Baseline, $0.30/kWh); Mode 2 (Solar + Grid-Only, no battery); "
        "Mode 3 (Battery + Grid-Only, 5 kWh battery, no P2P); and Mode 4 (Proposed P2P Game + Battery). "
        "Table II documents the authoritative daily cost metrics."
    )

    # TABLE II
    t2_data = [
        ["Participant", "Mode 1: Pure Grid", "Mode 2: Solar+Grid", "Mode 3: Batt+Grid", "Mode 4: P2P Game", "Daily Savings", "Bill Cut (%)"],
        ["H001 (Seller)", "$6.2706", "$4.3449", "$3.1061", "$2.9850", "+$3.2856", "52.4%"],
        ["H002 (Low Load)", "$1.8046", "$1.1697", "$0.5965", "$0.5878", "+$1.2168", "67.4%"],
        ["H003 (Buyer)", "$4.1101", "$3.2779", "$2.4876", "$2.4768", "+$1.6333", "39.7%"],
        ["H004 (High Demand)", "$10.1238", "$9.3230", "$8.5879", "$8.2252", "+$1.8986", "18.8%"],
        ["H005 (Opportunist)", "$4.0461", "$2.7169", "$1.5579", "$1.5207", "+$2.5253", "62.4%"],
        ["COMMUNITY TOTAL", "$26.3552", "$20.8324", "$16.3359", "$15.7956", "+$10.5597", "40.07%"],
    ]
    t2_widths = [Inches(0.65), Inches(0.48), Inches(0.48), Inches(0.48), Inches(0.48), Inches(0.48), Inches(0.35)]
    insert_table(t2_data, t2_widths, "TABLE II: Average Daily Electricity Cost Across Operational Modes (AUD/day)")

    insert_p_before_89(
        "As documented in Table II, baseline expenditure under Mode 1 is $26.36/day ($26,355 over 1,000 days). "
        "Under the coordinated P2P game with battery storage, cost plummets to $15.80/day ($15,795 over 1,000 days), "
        "securing a 40.07% net electricity bill reduction."
    )

    # FIG 2: Cost Comparison Across Modes
    insert_figure(
        str(ROOT / "results" / "figures" / "simulate_five_house_monte_carlo" / "01_daily_cost_comparison_across_modes.png"),
        "Fig. 2. Mean daily electricity cost by household across the four operational counterfactual modes over 1,000 Monte Carlo scenarios."
    )

    # FIG 3: Cost Difference & Total Profit (Single Panel!)
    insert_figure(
        str(ROOT / "results" / "figures" / "simulate_five_house_monte_carlo" / "02_total_profit_and_cost_difference.png"),
        "Fig. 3. Cost difference: Baseline Pure Grid expenditure vs Proposed P2P Game with BESS, highlighting total profit earned per participant."
    )

    insert_heading_2("B. Factor Decomposition of Community Profit")
    insert_p_before_89(
        "Total community savings average $10.56 AUD/day ($10,559.67 AUD cumulatively across 1,000 simulated days). "
        "Table III breaks down the average daily contribution of solar self-consumption, battery storage arbitrage, and P2P trading coordination."
    )

    # TABLE III
    t3_data = [
        ["Participant", "Daily Savings", "Solar Div.", "Battery Div.", "P2P Div.", "P2P Share"],
        ["H001", "$3.29/day", "$1.93/day", "$1.24/day", "$0.12/day", "3.7%"],
        ["H002", "$1.22/day", "$0.63/day", "$0.57/day", "$0.01/day", "0.7%"],
        ["H003", "$1.63/day", "$0.83/day", "$0.79/day", "$0.01/day", "0.7%"],
        ["H004", "$1.90/day", "$0.80/day", "$0.74/day", "$0.36/day", "19.1%"],
        ["H005", "$2.53/day", "$1.33/day", "$1.16/day", "$0.04/day", "1.5%"],
        ["COMMUNITY TOTAL", "$10.56/day", "$5.52 (52.3%)", "$4.50 (42.6%)", "$0.54 (5.1%)", "5.1%"],
    ]
    t3_widths = [Inches(0.65), Inches(0.55), Inches(0.55), Inches(0.55), Inches(0.55), Inches(0.45)]
    insert_table(t3_data, t3_widths, "TABLE III: Factor Decomposition of Average Daily Savings (AUD/day)")

    insert_p_before_89(
        "Crucially, for the heavy consumer H004, P2P market coordination provides an average of $0.36 AUD/day ($362.65 AUD over 1,000 days)—"
        "accounting for 19.1% of its entire financial savings. Because H004 lacks sufficient rooftop PV capacity, access to neighbors' surplus energy "
        "via dynamic P2P trading serves as its most impactful optimization mechanism. Meanwhile, community-wide, solar self-consumption provides "
        "$5.52/day (52.3%) and battery storage provides $4.50/day (42.6%) of savings."
    )

    # FIG 4: Factor Decomposition
    insert_figure(
        str(ROOT / "results" / "figures" / "simulate_five_house_monte_carlo" / "06_total_profit_difference_decomposition.png"),
        "Fig. 4. Factor decomposition of total community profit into solar self-consumption, battery storage arbitrage, and P2P coordination."
    )

    # FIG 5: Savings Portion by Factor
    insert_figure(
        str(ROOT / "results" / "figures" / "simulate_five_house_monte_carlo" / "07_savings_portion_by_factor.png"),
        "Fig. 5. Normalized percentage factor breakdown (100% stacked) illustrating the distinct value drivers across participant archetypes."
    )

    insert_heading_2("C. Diurnal Hourly Trading and Price Dynamics")
    insert_p_before_89(
        "Analysis of the 24-hour diurnal profile confirms that local trading concentrates strictly between 11:00 and 15:00. "
        "Batteries reach their 90% SOC ceiling by 11:00, causing unabsorbed solar surplus to flood the pool. Market pressure λ drops below 0.5, "
        "clearing the P2P price at $0.11–$0.15/kWh. Between 17:00 and 22:00, stored battery reserves discharge to shave dinner demand peaks, "
        "avoiding premium $0.30/kWh grid imports."
    )

    # FIG 6: Hourly Average Community Profit
    insert_figure(
        str(ROOT / "results" / "figures" / "simulate_five_house_monte_carlo" / "04_hourly_average_community_profit.png"),
        "Fig. 6. Diurnal 24-hour average community profit profile illustrating the active midday trading window and evening battery peak shaving."
    )

    insert_heading_2("D. Statistical Stability and Downside Risk")
    insert_p_before_89(
        "Evaluation of the empirical profit distributions across all 1,000 Monte Carlo scenarios reveals that daily P2P trading profit is strictly "
        "non-negative (minimum and 5th percentile Q_05 = $0.0000/day). This guarantees individual rationality and zero downside risk under "
        "diverse meteorological conditions, as illustrated in Fig. 7."
    )

    # FIG 7: Profit Distribution Across 1,000 Scenarios
    insert_figure(
        str(ROOT / "results" / "figures" / "simulate_five_house_monte_carlo" / "03_p2p_profit_distribution_1000_scenarios.png"),
        "Fig. 7. Empirical P2P trading profit distributions (boxplots and kernel density estimates) across 1,000 Monte Carlo scenarios."
    )

    # VII. CONCLUSION AND FUTURE WORK
    insert_heading_1("VII. CONCLUSION AND FUTURE WORK")
    insert_p_before_89(
        "This paper presented an integrated stochastic game-theoretic optimization framework for peer-to-peer energy trading in residential "
        "microgrids with distributed battery storage. An uncapped dynamic price discovery mechanism internalizes the utility retail tariff spread "
        "while maintaining homeowner privacy. Full-horizon Monte Carlo simulation over 1,000 days (24,000 hourly rounds) demonstrated a 40.07% "
        "total electricity expenditure reduction, capturing an average of $10.56 AUD/day in community savings ($10,559.67 AUD across the 1,000-day evaluation horizon). "
        "Factor decomposition proved that while solar self-consumption ($5.52/day, 52.3%) and battery storage ($4.50/day, 42.6%) provide baseline savings, "
        "P2P trading delivers an extra $0.54 AUD/day (5.1% software dividend, totaling $540.34 AUD) with zero extra hardware cost, providing up to 19.1% of savings "
        "for heavy consumers. Empirical distributions confirm zero downside risk for all participants."
    )
    insert_p_before_89(
        "Future work will extend the framework to incorporate distribution network voltage constraints, reactive power compensation, "
        "continuous double-sided auction bidding, and community scaling to 100+ prosumer nodes."
    )

    # ACKNOWLEDGMENT
    insert_heading_1("ACKNOWLEDGMENT")
    insert_p_before_89(
        "The authors express their sincere gratitude to their project supervisor, faculty members, and the Department of Mathematics, "
        "Sardar Vallabhbhai National Institute of Technology (SVNIT), Surat, for their constructive guidance, research facilities, "
        "continuous mentorship, and valuable academic feedback throughout the development and execution of this research project."
    )

    # REFERENCES
    insert_heading_1("REFERENCES")
    refs = [
        "[1] F. Moret and P. Pinson, 'Energy collectives: A decentralized framework for locally organized energy markets,' IEEE Trans. Power Syst., vol. 34, no. 1, pp. 647–656, Jan. 2019.",
        "[2] J. Guerrero, A. C. Chapman, and G. Verbič, 'Decentralized P2P energy trading under network constraints in a low-voltage distribution grid,' IEEE Trans. Smart Grid, vol. 10, no. 5, pp. 5173–5183, Sept. 2019.",
        "[3] W. Tushar, T. K. Saha, C. Yuen, D. Smith, and H. V. Poor, 'Peer-to-peer trading in electricity networks: An overview,' IEEE Trans. Smart Grid, vol. 11, no. 4, pp. 3185–3200, July 2020.",
        "[4] C. Zhang, J. Wu, Y. Zhou, M. Cheng, and C. Long, 'Peer-to-Peer energy trading in a microgrid,' Appl. Energy, vol. 220, pp. 1–12, June 2018.",
        "[5] Y. Parag and B. K. Sovacool, 'Electricity market design for the prosumer era,' Nature Energy, vol. 1, no. 4, p. 16032, Apr. 2016.",
        "[6] S. Paudel, K. Sampath, M. Yang, and P. H. Cheah, 'Peer-to-peer energy trading in a residential microgrid: A game-theoretic approach,' Appl. Energy, vol. 279, p. 115794, Dec. 2020.",
        "[7] N. Liu, X. Yu, C. Wang, C. Li, L. Ma, and J. Lei, 'Energy-sharing model with price-based demand response for microgrids of peer-to-peer prosumers,' IEEE Trans. Power Syst., vol. 32, no. 5, pp. 3569–3583, Sept. 2017.",
        "[8] Z. Chen, L. Chen, and B. Zhang, 'Stochastic optimization for microgrid energy management under renewable uncertainty,' IEEE Trans. Sustain. Energy, vol. 12, no. 2, pp. 1120–1131, Apr. 2021.",
        "[9] M. Khorasany, Y. Mishra, and G. Ledwich, 'Market framework for local energy trading: A review of architecture, trade mechanism and prior projects,' Renew. Sustain. Energy Rev., vol. 132, p. 110033, Oct. 2020.",
        "[10] J. F. Nash, 'Non-cooperative games,' Ann. Math., vol. 54, no. 2, pp. 286–295, 1951.",
        "[11] W. Tushar et al., 'Grid influenced peer-to-peer energy trading,' IEEE Trans. Smart Grid, vol. 11, no. 2, pp. 1406–1418, Mar. 2020.",
        "[12] Ausgrid, 'Solar Home Electricity Data,' Ausgrid Network Data, 2014. [Online]. Available: https://www.ausgrid.com.au/Industry/Our-Research/Data-to-share/Solar-home-electricity-data"
    ]
    for r in refs:
        p_ref = insert_p_before_89(r, style='references', space_after=3)
        p_ref.runs[0].font.size = Pt(8.0)

    # Clean p89 text: it was holding guidance note, make it blank
    doc.paragraphs[89].text = ""

    # Save output documents
    out_final = ROOT / "reports" / "Project_Report_Final.docx"
    out_revised = ROOT / "reports" / "ieee_paper_revised.docx"
    doc.save(str(out_final))
    shutil.copy(out_final, out_revised)
    print(f"Successfully saved final Word report to:\n  - {out_final}\n  - {out_revised}")

if __name__ == "__main__":
    build_word_report()
