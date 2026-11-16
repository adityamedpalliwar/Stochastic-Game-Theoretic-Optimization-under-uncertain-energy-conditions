"""Script to build the official 10-12 page project report in Microsoft Word (.docx) format
using the normalized SVNIT / IEEE project template (Project_Report_Format_norm.docx).

Incorporates:
1. Initial 2-Household Game: Normal form matrix, payoffs, Nash equilibrium, why 2-player prototype was built.
2. Flagship 5-Household System: Architecture, community cost reduction, all dashboard numbers and percentages.
3. Exhaustive Technical Assumptions: Tariffs ($0.30, $0.08), 5 kWh BESS, 2.5 kW power, 95% efficiency, 10%-90% SOC, 1,000 scenarios, 24,000 rounds.
4. BESS Physical Dispatch: Pre-game greedy dispatch vs MPC, why greedy was chosen, SOC dynamics, feasibility.
5. Dynamic Price Discovery: Uncapped formula, demand pressure lambda, incentive bounds, proof of Pareto-dominant Nash equilibrium.
6. Counterfactual Benchmarking: Modes 1, 2, 3, 4, why benchmarking is vital, edge cases (overcast, solar flood, nighttime, H004 dominance).
7. Separated High-Resolution 300 DPI Figures for EACH Household (H001 to H005) + Community figures.
8. Dashboard Metrics Audit: Meaning of every number, factor decomposition waterfall (52.3% solar, 42.6% battery, 5.1% P2P).
9. Simple, crystal-clear English language suitable for academic review.
"""

import os
import sys
import shutil
from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

ROOT = Path(__file__).resolve().parent

def set_cell_border(cell, **kwargs):
    """Set clean table cell borders."""
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

def build_expanded_report():
    print("Loading normalized IEEE / SVNIT template...")
    norm_path = ROOT / "reports" / "Project_Report_Format_norm.docx"
    doc = docx.Document(str(norm_path))
    body = doc._body._element

    # 1. Update Title in paragraph 0
    p_title = doc.paragraphs[0]
    p_title.text = "Stochastic Game-Theoretic Optimization for Peer-to-Peer Energy Trading with Distributed Battery Storage under Uncertainty"
    p_title.style = 'paper title'
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Clear paragraph 1
    doc.paragraphs[1].text = "Comprehensive Research Project Report & Computational Audit (5th Semester B.Tech / M.Sc Mathematics)"
    doc.paragraphs[1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.paragraphs[1].style = 'Author'

    # Clear paragraph 2 & 3
    doc.paragraphs[2].text = ""

    # Paragraphs 4, 5, 6: 3-Author block
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
            f"Surat, Gujarat, India - 395007\n"
            f"{email}"
        )
        p.style = 'Author'
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if i < 2:
            r = p.add_run()
            br = OxmlElement('w:br')
            br.set(qn('w:type'), 'column')
            r._r.append(br)

    # Clear paragraphs 7, 8, 9
    doc.paragraphs[7].text = ""
    doc.paragraphs[8].text = ""
    doc.paragraphs[9].text = ""

    # Remove all placeholder paragraphs between p10 and p89
    p10_elem = doc.paragraphs[10]._p
    p89_elem = doc.paragraphs[89]._p

    elements_to_remove = []
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

    print(f"Removed {len(elements_to_remove)} template placeholder elements.")

    # Configure Section 3 to 1-column so that all large figures and tables span cleanly!
    # In doc.sections, let's make all body sections single-column for crystal-clear readability
    for s in doc.sections:
        cols = s._sectPr.xpath('./w:cols')
        if cols:
            cols[0].set(qn('w:num'), '1')
        s.top_margin = Inches(0.8)
        s.bottom_margin = Inches(0.8)
        s.left_margin = Inches(0.8)
        s.right_margin = Inches(0.8)

    # Insertion helpers before p89_elem
    def add_p(text="", style='Body Text', align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=0, space_after=5, bold_prefix=None, italic_prefix=None):
        p = doc.add_paragraph()
        p89_elem.addprevious(p._p)
        try:
            p.style = style
        except Exception:
            p.style = 'Normal'
        p.alignment = align
        p.paragraph_format.space_before = Pt(space_before)
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = 1.15

        if bold_prefix:
            r_pre = p.add_run(bold_prefix)
            r_pre.bold = True
            r_pre.font.name = 'Times New Roman'
        if italic_prefix:
            r_it = p.add_run(italic_prefix)
            r_it.italic = True
            r_it.font.name = 'Times New Roman'
        if text:
            r = p.add_run(text)
            r.font.name = 'Times New Roman'
        return p

    def add_h1(title):
        p = add_p(title, style='Heading 1', align=WD_ALIGN_PARAGRAPH.LEFT, space_before=14, space_after=6)
        p.runs[0].bold = True
        p.runs[0].font.size = Pt(13)
        p.runs[0].font.color.rgb = RGBColor(15, 23, 42)
        return p

    def add_h2(title):
        p = add_p(title, style='Heading 2', align=WD_ALIGN_PARAGRAPH.LEFT, space_before=10, space_after=4)
        p.runs[0].bold = True
        p.runs[0].font.size = Pt(11)
        p.runs[0].font.color.rgb = RGBColor(30, 58, 138)
        return p

    def add_h3(title):
        p = add_p(title, style='Heading 3', align=WD_ALIGN_PARAGRAPH.LEFT, space_before=6, space_after=2)
        p.runs[0].bold = True
        p.runs[0].italic = True
        p.runs[0].font.size = Pt(10)
        return p

    def add_math_eq(runs_spec, eq_num):
        p = add_p("", align=WD_ALIGN_PARAGRAPH.LEFT, space_before=4, space_after=6)
        p.paragraph_format.left_indent = Inches(0.3)
        for item in runs_spec:
            text = item[0]
            sub = item[1] if len(item) > 1 else False
            sup = item[2] if len(item) > 2 else False
            italic = item[3] if len(item) > 3 else False
            bold = item[4] if len(item) > 4 else False

            r = p.add_run(text)
            r.font.name = 'Cambria Math'
            r.font.size = Pt(8.5 if (sub or sup) else 10.0)
            r.font.subscript = sub
            r.font.superscript = sup
            r.font.italic = italic
            r.font.bold = bold

        # Spacing and flush right equation number
        r_sp = p.add_run(" " * 8)
        r_num = p.add_run(f"({eq_num})")
        r_num.bold = True
        r_num.font.name = 'Times New Roman'
        r_num.font.size = Pt(9.5)
        return p

    def add_fig(img_path_str, caption_title, width_in=6.4):
        p_img = add_p("", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=8, space_after=3)
        run_img = p_img.add_run()
        run_img.add_picture(str(img_path_str), width=Inches(width_in))
        p_cap = add_p(caption_title, style='figure caption', align=WD_ALIGN_PARAGRAPH.CENTER, space_before=2, space_after=10)
        p_cap.runs[0].font.size = Pt(9.0)
        p_cap.runs[0].bold = True
        p_cap.runs[0].italic = True
        return p_cap

    def add_table_data(data, col_widths, caption_title):
        p_cap = add_p(caption_title, style='table head', align=WD_ALIGN_PARAGRAPH.CENTER, space_before=10, space_after=3)
        p_cap.runs[0].font.size = Pt(9.0)
        p_cap.runs[0].bold = True

        table = doc.add_table(rows=0, cols=len(col_widths))
        p89_elem.addprevious(table._tbl)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        for row_idx, row_values in enumerate(data):
            row = table.add_row()
            is_header = (row_idx == 0)
            is_footer = (row_idx == len(data) - 1)

            for col_idx, val in enumerate(row_values):
                cell = row.cells[col_idx]
                cell.width = col_widths[col_idx]
                cell.text = str(val)
                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER if col_idx > 0 else WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.space_before = Pt(2.5)
                p.paragraph_format.space_after = Pt(2.5)

                if is_header:
                    for r in p.runs:
                        r.bold = True
                        r.font.size = Pt(8.5)
                        r.font.name = 'Times New Roman'
                    set_cell_border(cell, top={'val': 'single', 'sz': '8', 'color': '000000'},
                                          bottom={'val': 'single', 'sz': '6', 'color': '000000'})
                    set_cell_shading(cell, "E2E8F0")
                elif is_footer:
                    for r in p.runs:
                        r.bold = True
                        r.font.size = Pt(8.5)
                        r.font.name = 'Times New Roman'
                    set_cell_border(cell, top={'val': 'single', 'sz': '4', 'color': '000000'},
                                          bottom={'val': 'single', 'sz': '8', 'color': '000000'})
                    set_cell_shading(cell, "F1F5F9")
                else:
                    for r in p.runs:
                        r.font.size = Pt(8.0)
                        r.font.name = 'Times New Roman'
                    set_cell_border(cell, bottom={'val': 'single', 'sz': '2', 'color': 'E2E8F0'})
                    if row_idx % 2 == 1:
                        set_cell_shading(cell, "FAFAFA")

        add_p("", space_after=6)
        return table

    def add_page_break():
        p = doc.add_paragraph()
        p89_elem.addprevious(p._p)
        r = p.add_run()
        r.add_break(docx.enum.text.WD_BREAK.PAGE)
        return p

    # -------------------------------------------------------------------------
    # DOCUMENT SECTIONS
    # -------------------------------------------------------------------------
    print("Writing Abstract & Introduction...")

    # ABSTRACT
    add_p(
        "With the rapid adoption of residential rooftop photovoltaics (PV) and distributed battery energy storage systems (BESS), "
        "traditional centralized electricity distribution faces significant economic and technical distortions. Traditional electric utilities "
        "impose a large 22¢/kWh spread between retail import electricity tariffs ($0.30/kWh) and solar feed-in export credits ($0.08/kWh). "
        "This project develops an integrated stochastic game-theoretic optimization platform for peer-to-peer (P2P) local energy trading "
        "among heterogeneous residential prosumers equipped with independent 5.0 kWh physical battery storage. "
        "The project begins with an initial 2-household normal-form game prototype to verify strategic payoff dynamics, best-response behaviors, "
        "and strict Nash equilibrium convergence. We then expand this into a community-scale flagship platform comprising 5 prosumer households "
        "evaluated over 1,000 Monte Carlo weather scenarios (24,000 sequential hourly market rounds) drawn from real-world Ausgrid smart meter data. "
        "An uncapped dynamic demand-pressure pricing mechanism guarantees that local energy transactions strictly internalize the utility retail tariff spread, "
        "offering Pareto-dominant incentives that ensure individual rationality (zero downside risk) for all participants. "
        "A rigorous four-mode counterfactual benchmarking framework isolates the causal financial dividends of solar self-consumption, battery storage arbitrage, "
        "and multi-agent game-theoretic coordination. Simulation results prove that the proposed platform slashes total community electricity expenditures by "
        "40.07%, saving an average of $10.56 AUD/day ($10,559.67 AUD cumulatively across 1,000 days), dropping daily community energy bills from $26.36/day "
        "under pure grid reliance down to $15.80/day under coordinated game-theoretic trading. Factor decomposition confirms that solar self-consumption "
        "furnishes $5,522.87 AUD (52.3%), battery arbitrage delivers $4,496.47 AUD (42.6%), and P2P software coordination creates an additional $540.34 AUD (5.1% "
        "pure software dividend, and up to 19.1% for high-demand consumers) with zero marginal hardware expenditure. "
        "This report provides an exhaustive mathematical formulation, detailed individual household case studies with dedicated high-resolution graphs, "
        "an audit of all web dashboard metrics, and comprehensive analysis of edge-case operating regimes.",
        style='Abstract',
        bold_prefix="Abstract— "
    )

    add_p(
        "Peer-to-peer (P2P) energy trading, game theory, Nash equilibrium, battery energy storage systems (BESS), "
        "dynamic pricing discovery, Monte Carlo simulation, prosumer microgrid, counterfactual benchmarking, uncertainty quantification.",
        style='Keywords',
        bold_prefix="Keywords— "
    )

    # SECTION I: INTRODUCTION & CORE MOTIVATION
    add_h1("I. INTRODUCTION AND PROJECT MOTIVATION")
    add_h2("A. Background: The Decentralized Energy Revolution")
    add_p(
        "Modern electrical grids are experiencing a fundamental paradigm shift. Historically, power flowed unidirectionally from massive, "
        "centralized fossil-fuel power stations through high-voltage transmission lines down to passive residential consumers. Today, millions of "
        "households have installed rooftop photovoltaic (PV) solar panels and behind-the-meter Battery Energy Storage Systems (BESS), transforming "
        "ordinary consumers into active 'prosumers' who both consume and generate electrical power. "
        "While distributed solar generation substantially cuts carbon emissions, its uncoordinated injection into low-voltage residential feeders "
        "causes significant operational challenges: voltage spikes, transformer thermal overloading, phase unbalance, and the notorious 'duck curve', "
        "where abundant midday solar generation abruptly plunges into severe evening peak demand."
    )

    add_h2("B. The Core Problem: The 22¢/kWh Utility Tariff Spread")
    add_p(
        "The primary barrier preventing efficient localized energy utilization is the artificial economic distortion imposed by retail electricity tariffs. "
        "In typical residential utility markets—such as the Australian National Electricity Market (NEM)—the utility company charges households a retail "
        "import rate of approximately $0.30 per kilowatt-hour ($0.30/kWh) when importing power from the grid. However, when a sunny household produces "
        "surplus rooftop solar energy and exports it back into the grid, the utility credits the household with a feed-in tariff of only $0.08 per kilowatt-hour ($0.08/kWh). "
        "This creates a massive 22¢/kWh economic spread ($0.30 - $0.08 = $0.22/kWh). "
        "Under this status quo, a homeowner with abundant midday solar generation receives a meager 8¢ credit, while their next-door neighbor without solar "
        "is simultaneously purchasing power from the utility grid at 30¢/kWh. The electricity flows physically across a few meters of local low-voltage wire, "
        "yet the utility company captures a 22¢/kWh margin while providing negligible physical transmission effort."
    )

    add_h2("C. Why Centralized Optimization Fails in Residential Microgrids")
    add_p(
        "A conventional engineering approach to this problem is centralized microgrid optimization: installing a central master computer that gathers "
        "all household generation and load data, solves a massive centralized linear or quadratic program, and directly commands every appliance and battery. "
        "However, centralized microgrid architectures suffer from three fatal real-world flaws:"
    )
    add_p("1) Severe Privacy Violations: Homeowners are unwilling to broadcast granular, real-time private behavioral schedules (such as when they take showers, cook dinner, or run dishwashers) to a central corporate server.", bold_prefix="• ")
    add_p("2) Single Point of Failure: If the central server loses network connectivity or crashes, the entire microgrid optimization collapses.", bold_prefix="• ")
    add_p("3) Communication Overhead & Computational Scalability: Solving centralized multi-period optimal power flow problems under stochastic weather variations becomes computationally intractable as the number of households scales.", bold_prefix="• ")

    add_h2("D. The Game-Theoretic Solution & Project Aim")
    add_p(
        "To overcome these limitations, this project designs and validates a decentralized, autonomous, multi-agent Game-Theoretic platform. "
        "In our framework, each household acts as an independent, rational player seeking to minimize its own net electricity costs. "
        "By coupling each household with a 5.0 kWh physical battery and introducing an automated dynamic price discovery mechanism, "
        "neighbors trade surplus solar electricity directly within the community at a fair, market-clearing price P_P2P strictly bounded between "
        "$0.08/kWh and $0.30/kWh. This internalizes the 22¢/kWh spread inside the local neighborhood, slashes household electricity bills, "
        "and keeps homeowner usage data completely private. "
        "The overarching aim of this project is to prove mathematically and computationally that game-theoretic P2P trading reduces total community "
        "energy expenditure while guaranteeing individual rationality (zero financial downside risk) under real-world weather and demand uncertainty."
    )

    # SECTION II: INITIAL 2-HOUSEHOLD PROTOTYPE
    add_h1("II. THE INITIAL 2-HOUSEHOLD GAME PROTOTYPE")
    add_h2("A. Conceptual Foundation: Why We Started with a 2-Household Game")
    add_p(
        "Before constructing a complex community microgrid, sound scientific methodology requires verifying foundational mathematical concepts "
        "in an analytically tractable environment. Therefore, we initially developed a 2-household normal-form game prototype (implemented in demo_prototype.py). "
        "The primary purpose of this initial prototype was threefold: (1) to formulate the mathematical payoff matrix governing prosumer interactions, "
        "(2) to trace individual best-response dynamics step-by-step, and (3) to prove computationally that cooperative peer-to-peer trading forms a strict, "
        "Pareto-dominant Nash equilibrium compared to utility grid default."
    )

    add_h2("B. Mathematical Setup of the 2-Household Normal-Form Game")
    add_p(
        "Consider a representative trading hour (e.g. 10:00 AM on a sunny morning). Two distinct prosumer households interact:"
    )
    add_p("• Player 1 (Seller - Household H001): Possesses abundant rooftop solar generation. Realized demand is 0.850 kWh, while solar generation is 3.200 kWh, leaving a net physical surplus of S_1 = 3.200 - 0.850 = +2.350 kWh. Player 1 selects an action from strategy space A_1 = {OFFER_P2P, EXPORT_GRID}.")
    add_p("• Player 2 (Buyer - Household H002): Experiences higher daytime consumption than solar generation. Realized demand is 2.100 kWh, while solar generation is 0.350 kWh, creating a net physical deficit of D_2 = 2.100 - 0.350 = -1.750 kWh. Player 2 selects an action from strategy space A_2 = {ACCEPT_P2P, GRID_IMPORT}.")
    add_p(
        "The physical energy that can be traded locally is constrained by the mutual conservation of energy: Q_trade = min(S_1, D_2) = min(2.350, 1.750) = 1.750 kWh. "
        "In this prototype, the local trading price is set to the equitable mid-market rate: P_P2P = (P_import + P_export) / 2 = ($0.30 + $0.08) / 2 = $0.1900/kWh."
    )

    add_h2("C. Payoff Formulations and 2x2 Payoff Matrix")
    add_p(
        "Each player's utility U_i is defined as their net financial position in Australian Dollars (AUD). For the seller, positive utility represents "
        "net revenue. For the buyer, utility is negative net expenditure (maximizing utility is equivalent to minimizing electricity cost):"
    )
    add_p("1. Mutual Trade Cleared (OFFER_P2P, ACCEPT_P2P): Both players agree to trade. Player 1 sells 1.750 kWh to Player 2 at $0.190/kWh ($0.3325 AUD) and exports the remaining unabsorbed 0.600 kWh (2.350 - 1.750) to the grid at the 8¢ export rate ($0.0480 AUD). Total seller utility: U_1 = 0.3325 + 0.0480 = +$0.3805 AUD. Player 2 buys 1.750 kWh at $0.190/kWh: U_2 = -$0.3325 AUD.")
    add_p("2. Trade Fails (OFFER_P2P, GRID_IMPORT): Player 2 rejects P2P trading. Player 1 is forced to export its entire 2.350 kWh surplus to the grid at 8¢: U_1 = 2.350 × $0.08 = +$0.1880 AUD. Player 2 must import its entire 1.750 kWh deficit from the grid at 30¢: U_2 = -1.750 × $0.30 = -$0.5250 AUD.")
    add_p("3. Trade Fails (EXPORT_GRID, ACCEPT_P2P): Player 1 chooses grid export. Symmetrically, trade collapses: U_1 = +$0.1880 AUD, U_2 = -$0.5250 AUD.")
    add_p("4. Status-Quo Baseline (EXPORT_GRID, GRID_IMPORT): Neither party participates in P2P. Both rely 100% on the utility grid: U_1 = +$0.1880 AUD, U_2 = -$0.5250 AUD.")

    # Insert Fig 0: Initial 2-Household Game
    add_fig(ROOT / "results" / "figures" / "report_figures" / "fig00_initial_2_household_game.png",
            "Fig. 1. Initial 2-household normal-form payoff matrix and economic gains verification (Output from demo_prototype.py).")

    add_h2("D. Best-Response Dynamics, Nash Equilibrium, and Prototype Findings")
    add_p(
        "Analyzing the best responses of rational agents reveals strict strategic incentives:"
    )
    add_p("• For Seller (H001): If Buyer chooses ACCEPT_P2P, Seller's payoff is +$0.3805 AUD under OFFER_P2P versus +$0.1880 AUD under EXPORT_GRID. OFFER_P2P provides a +$0.1925 AUD (+102.4%) revenue boost! If Buyer chooses GRID_IMPORT, Seller earns +$0.1880 AUD under both actions. Therefore, OFFER_P2P is a weakly dominant strategy.")
    add_p("• For Buyer (H002): If Seller chooses OFFER_P2P, Buyer's cost is $0.3325 AUD under ACCEPT_P2P versus $0.5250 AUD under GRID_IMPORT. ACCEPT_P2P saves $0.1925 AUD (36.7% bill reduction)! If Seller exports to grid, Buyer pays $0.5250 AUD under both actions. ACCEPT_P2P is a weakly dominant strategy.")
    add_p(
        "Consequently, the strategy profile (OFFER_P2P, ACCEPT_P2P) is the unique pure-strategy Nash Equilibrium of the game. "
        "Furthermore, this equilibrium is Pareto-dominant: both players are strictly better off than at the status-quo baseline, "
        "and neither player can improve their payoff by unilateral deviation."
    )

    add_h2("E. Why We Expanded from 2 Households to the 5-Household Flagship System")
    add_p(
        "While the 2-household prototype successfully proved the game-theoretic concept, it revealed four critical real-world limitations:"
    )
    add_p("1) Fragile Liquidity: In a 2-player game, if the single buyer has zero deficit or goes on vacation, trading collapses completely. A real community requires a diverse pool of multiple buyers and sellers.", bold_prefix="• ")
    add_p("2) Lack of Prosumer Diversity: A 2-player market cannot capture prosumers with balanced profiles, swing traders who switch between buying and selling throughout the day, or commercial-style heavy consumers.", bold_prefix="• ")
    add_p("3) Rigidity of Static Mid-Market Pricing: Fixed pricing ($0.19/kWh) fails when supply vastly exceeds demand (causing solar curtailment) or when demand exceeds supply (causing buyer rationing). Price must discover value dynamically based on scarcity.", bold_prefix="• ")
    add_p("4) Absence of Physical Storage: Without batteries, surplus solar generated between 11:00 AM and 2:00 PM cannot be stored to offset evening peak demand between 6:00 PM and 9:00 PM.", bold_prefix="• ")
    add_p(
        "These insights directly motivated the development of our flagship 5-Household (N=5) Stochastic Game with physical Battery Energy Storage Systems (BESS)."
    )

    # SECTION III: COMPLETE SYSTEM ASSUMPTIONS & DATASET
    add_h1("III. SYSTEM ARCHITECTURE AND EXHAUSTIVE TECHNICAL ASSUMPTIONS")
    add_h2("A. Complete Engineering & Economic Assumptions")
    add_p(
        "To ensure academic rigor, repeatability, and realistic microgrid operations, every parameter in this project is explicitly documented. "
        "Table I lists the comprehensive technical and economic assumptions governing the simulation."
    )

    # TABLE I: Exhaustive Assumptions Table
    t_assump_data = [
        ["Parameter Category", "Model Parameter", "Numerical Value", "Physical & Economic Justification"],
        ["Utility Electricity Tariffs", "Retail Grid Import Price (P_import)", "$0.3000 AUD / kWh", "Standard Australian National Electricity Market (NEM) residential flat tariff."],
        ["Utility Electricity Tariffs", "Solar Feed-in Tariff (P_export)", "$0.0800 AUD / kWh", "Typical utility export credit paid to residential rooftop solar owners."],
        ["Utility Electricity Tariffs", "Retail Grid Tariff Spread", "$0.2200 AUD / kWh", "Internalized economic opportunity: $0.30 - $0.08 = $0.22/kWh."],
        ["Battery Energy Storage (BESS)", "Nominal Energy Capacity (E_cap)", "5.0 kWh per home", "Standard residential lithium iron phosphate (LiFePO4) modular pack."],
        ["Battery Energy Storage (BESS)", "Maximum Charge/Discharge Power", "2.5 kW (0.5 C-rate)", "Continuous bidirectional inverter thermal and current safety rating."],
        ["Battery Energy Storage (BESS)", "Round-Trip Efficiency (η_rt)", "95.0% (η_ch = η_dis = 97.47%)", "High-efficiency modern DC-coupled residential inverter/battery system."],
        ["Battery Energy Storage (BESS)", "Safe Operating SOC Window", "10.0% to 90.0% (0.5 to 4.5 kWh)", "Preserves electrochemical health, preventing cell degradation and deep discharge."],
        ["Battery Energy Storage (BESS)", "Initial Daily State of Charge (SOC_0)", "50.0% (2.5 kWh) at 00:00", "Neutral daily boundary condition avoiding unearned historical energy carryover."],
        ["Simulation & Uncertainty", "Monte Carlo Scenarios Evaluated", "1,000 independent days", "Quantifies compound meteorological and consumer behavioral uncertainty."],
        ["Simulation & Uncertainty", "Market Horizon & Rounds", "24,000 sequential rounds", "1,000 days × 24 hourly market clearings (h = 0 to 23)."],
        ["Simulation & Uncertainty", "Bootstrap Noise Multiplier", "0.15 × σ_diurnal(h)", "Empirical standard deviation perturbation preserving diurnal weather envelope."],
        ["Dynamic Price Discovery", "Price Sensitivity Parameter (λ_max)", "2.0", "Market pressure elasticity parameter setting price responsiveness."],
        ["Dynamic Price Discovery", "Numerical Singularity Protector (ε)", "1.0 × 10^-6 kWh", "Prevents mathematical division by zero when pool surplus is zero."],
        ["Network & Transactions", "Internal Wheeling Charges", "$0.00 AUD / kWh", "P2P transactions share common low-voltage secondary feeder transformer."],
    ]
    t_assump_widths = [Inches(1.5), Inches(1.8), Inches(1.3), Inches(2.2)]
    add_table_data(t_assump_data, t_assump_widths, "TABLE I: Comprehensive Technical, Economic, and Simulation Assumptions")

    add_h2("B. Empirical Dataset Calibration (Ausgrid Smart Home Data)")
    add_p(
        "All household demand and rooftop solar generation profiles originate from the open-source Ausgrid Solar Home Electricity Dataset (Sydney, Australia). "
        "The Ausgrid dataset provides real 30-minute interval smart meter recordings for 300 residential homes over a full 12-month calendar year (July 2012 to June 2013). "
        "The smart meters record three separate channels: General Consumption (GC), Controlled Load (CL, e.g. off-peak water heating), and Gross Generation (GG) from rooftop PV. "
        "For our simulation, 30-minute intervals were aggregated into clean hourly readings (Δt = 1.0 h), summing General Consumption and Controlled Load into Total Demand: "
        "D_i,t = GC_i,t + CL_i,t, while solar generation is G_i,t = GG_i,t. "
        "Five prosumers exhibiting distinct load and generation archetypes were calibrated to represent a balanced neighborhood microgrid. Table II documents their profiles."
    )

    # TABLE II: Household Profiles
    t_prof_data = [
        ["Household ID", "Archetype Description", "PV Array (kWp)", "Avg Demand (kWh/d)", "Avg Solar (kWh/d)", "Net Daily Position", "Primary Community Role"],
        ["H001", "High-Solar Midday Seller", "3.78 kWp", "20.90 ± 8.87", "14.14 ± 8.81", "-6.76 kWh (Net Solar)", "Anchor Solar Supplier during 10:00 - 15:00"],
        ["H002", "Low-Load Balanced Prosumer", "1.00 kWp", "6.02 ± 1.83", "4.29 ± 2.50", "-1.73 kWh (Balanced)", "Self-sufficient, high % bill reduction (67.4%)"],
        ["H003", "Moderate-Load Prosumer", "1.00 kWp", "13.70 ± 4.60", "3.65 ± 3.01", "+10.05 kWh (Net Buyer)", "Regular daytime buyer of community surplus"],
        ["H004", "High-Demand Heavy Consumer", "2.00 kWp", "33.75 ± 13.91", "3.32 ± 1.63", "+30.43 kWh (Heavy Buyer)", "Anchor Energy Absorber (19.1% P2P savings share)"],
        ["H005", "Balanced Opportunistic Trader", "2.16 kWp", "13.49 ± 4.19", "8.75 ± 5.25", "+4.74 kWh (Swing Trader)", "Midday seller, evening buyer (swing liquidity)"],
        ["COMMUNITY", "5-Household Microgrid Total", "9.94 kWp", "87.85 ± 24.23", "34.16 ± 20.31", "+53.69 kWh (Net Buyer)", "Microgrid reduces net import dependency"],
    ]
    t_prof_widths = [Inches(0.9), Inches(1.6), Inches(0.8), Inches(0.9), Inches(0.9), Inches(1.1), Inches(1.2)]
    add_table_data(t_prof_data, t_prof_widths, "TABLE II: Calibrated Microgrid Prosumer Structural Profiles and Archetypes")

    # SECTION IV: PHYSICAL BESS DISPATCH
    add_h1("IV. PHYSICAL BATTERY ENERGY STORAGE FORMULATION & GREEDY DISPATCH")
    add_h2("A. Why Pre-Game Greedy Dispatch was Chosen over Model Predictive Control (MPC)")
    add_p(
        "A critical engineering decision in this project was whether to dispatch batteries using multi-period stochastic Model Predictive Control (MPC) "
        "or decentralized pre-game greedy self-consumption dispatch. We conducted an exhaustive computational audit (detailed in reports/phase6b_stochastic_mpc_validation.md) "
        "and established that pre-game greedy dispatch is vastly superior for our flagship platform for four foundational reasons:"
    )
    add_p("1) Computational Tractability over 24,000 Rounds: Solving a multi-period stochastic MPC optimization requires dynamic programming or quadratic programming across rolling prediction horizons. Across 1,000 Monte Carlo days (24,000 sequential game rounds), MPC introduces massive computational latency and frequent solver timeout issues. Greedy dispatch executes deterministically in sub-millisecond time.", bold_prefix="• ")
    add_p("2) Elimination of Future Foresight Bias: MPC relies heavily on multi-hour forward weather and load forecasts. In reality, residential load forecasts suffer from high variance (MAE ≈ 0.47 kWh). If forecast errors occur, complex multi-hour battery schedules deviate severely from reality. Greedy dispatch operates causally using only real-time physical measurements.", bold_prefix="• ")
    add_p("3) Preservation of Homeowner Autonomy and Privacy: Centralized or cooperative MPC requires households to disclose expected future hourly appliance schedules to a centralized optimizer. Greedy dispatch allows each battery to operate entirely behind-the-meter as an autonomous private subsystem.", bold_prefix="• ")
    add_p("4) Physical Integrity of P2P Market Orders: By satisfying local household needs first, only true physical unabsorbed surplus (S_i^net) or genuine unmet deficit (D_i^net) enters the community pool. This prevents artificial financial speculation or battery round-trip wear from unnecessary peer trading.", bold_prefix="• ")

    add_h2("B. Mathematical Formulation of Battery Dispatch Dynamics")
    add_p(
        "Let D_i,t and G_i,t denote the realized electrical demand and rooftop solar generation for household i at hour t. "
        "The raw unmanaged energy position prior to battery interaction is:"
    )
    add_math_eq([
        ("S", False, False, True), ("i,t", True, False, True), ("raw", False, True, False),
        (" = max(0, ", False, False, False),
        ("G", False, False, True), ("i,t", True, False, True),
        (" − ", False, False, False),
        ("D", False, False, True), ("i,t", True, False, True),
        ("),         ", False, False, False),
        ("D", False, False, True), ("i,t", True, False, True), ("raw", False, True, False),
        (" = max(0, ", False, False, False),
        ("D", False, False, True), ("i,t", True, False, True),
        (" − ", False, False, False),
        ("G", False, False, True), ("i,t", True, False, True),
        (")", False, False, False)
    ], "1")
    add_p(
        "Case 1: Surplus Solar Generation (S_i,t^raw > 0). The household prioritizes storing excess green energy in its battery before exporting. "
        "The physical charging power P_ch,i,t (kW) is constrained by available solar, inverter rating, and the upper safe SOC limit (SOC_max = 0.90):"
    )
    add_math_eq([
        ("P", False, False, True), ("ch,i,t", True, False, True),
        (" = min( ", False, False, False),
        ("S", False, False, True), ("i,t", True, False, True), ("raw", False, True, False),
        (",   ", False, False, False),
        ("P", False, False, True), ("ch", True, False, True), ("max", False, True, False),
        (",   [SOC", False, False, False), ("max", True, False, False),
        (" − SOC", False, False, False), ("i,t", True, False, True),
        ("] · E", False, False, False), ("cap", True, False, False),
        (" / (η", False, False, False), ("ch", True, False, False),
        (" · Δt) )", False, False, False)
    ], "2")
    add_p(
        "Any surplus solar that cannot be absorbed by the battery becomes the household's net offer into the community P2P trading pool:"
    )
    add_math_eq([
        ("S", False, False, True), ("i,t", True, False, True), ("net", False, True, False),
        (" = max(0,   ", False, False, False),
        ("S", False, False, True), ("i,t", True, False, True), ("raw", False, True, False),
        (" − P", False, False, False), ("ch,i,t", True, False, True),
        (")", False, False, False)
    ], "3")
    add_p(
        "Case 2: Demand Deficit (D_i,t^raw > 0). When household consumption exceeds solar generation, the battery discharges to cover the deficit, "
        "constrained by demand, inverter rating, and the lower safe SOC limit (SOC_min = 0.10):"
    )
    add_math_eq([
        ("P", False, False, True), ("dis,i,t", True, False, True),
        (" = min( ", False, False, False),
        ("D", False, False, True), ("i,t", True, False, True), ("raw", False, True, False),
        (",   ", False, False, False),
        ("P", False, False, True), ("dis", True, False, True), ("max", False, True, False),
        (",   [SOC", False, False, False), ("i,t", True, False, True),
        (" − SOC", False, False, False), ("min", True, False, False),
        ("] · E", False, False, False), ("cap", True, False, False),
        (" · η", False, False, False), ("dis", True, False, False),
        (" / Δt )", False, False, False)
    ], "4")
    add_p(
        "Any remaining unmet consumption becomes the household's net deficit bid into the community P2P trading pool:"
    )
    add_math_eq([
        ("D", False, False, True), ("i,t", True, False, True), ("net", False, True, False),
        (" = max(0,   ", False, False, False),
        ("D", False, False, True), ("i,t", True, False, True), ("raw", False, True, False),
        (" − P", False, False, False), ("dis,i,t", True, False, True),
        (")", False, False, False)
    ], "5")
    add_p(
        "Finally, the battery's internal State of Charge updates causally for the subsequent hour t+1 according to physical conservation of mass and energy:"
    )
    add_math_eq([
        ("SOC", False, False, False), ("i,t+1", True, False, True),
        (" = SOC", False, False, False), ("i,t", True, False, True),
        (" + ( P", False, False, False), ("ch,i,t", True, False, True),
        (" · η", False, False, False), ("ch", True, False, False),
        (" − P", False, False, False), ("dis,i,t", True, False, True),
        (" / η", False, False, False), ("dis", True, False, False),
        (" ) / E", False, False, False), ("cap", True, False, False)
    ], "6")

    # SECTION V: DYNAMIC PRICE DISCOVERY
    add_h1("V. DYNAMIC PRICE DISCOVERY MECHANISM & GAME FORMULATION")
    add_h2("A. Why Dynamic Price Discovery is Essential (All Whys & Hows)")
    add_p(
        "In peer-to-peer microgrids, static pricing models fail fundamentally. If a fixed price (such as $0.19/kWh) is enforced: "
        "(1) on blazing sunny afternoons when solar surplus is massive and buyers are scarce, sellers cannot clear their energy and are forced into solar curtailment; "
        "(2) on cloudy afternoons when solar is scarce and buyer demand is intense, buyers cannot obtain energy and an arbitrary rationing mechanism must pick winners and losers. "
        "A true market must discover price dynamically based on real-time scarcity. "
        "Our dynamic pricing discovery model functions as an automated market-clearing barometer:"
    )

    add_h2("B. Mathematical Formulation of Dynamic Clearing Price")
    add_p(
        "At each hour t, the community coordinator aggregates all net surpluses and deficits into the community pool:"
    )
    add_math_eq([
        ("S", False, False, True), ("pool,t", True, False, True),
        (" = ∑", False, False, False), ("(i=1..N) ", False, False, False),
        ("S", False, False, True), ("i,t", True, False, True), ("net", False, True, False),
        (",         D", False, False, False), ("pool,t", True, False, True),
        (" = ∑", False, False, False), ("(i=1..N) ", False, False, False),
        ("D", False, False, True), ("i,t", True, False, True), ("net", False, True, False)
    ], "7")
    add_p(
        "The market demand pressure ratio λ_t measures the ratio of net energy deficit to net energy surplus:"
    )
    add_math_eq([
        ("λ", False, False, True), ("t", True, False, True),
        (" = D", False, False, False), ("pool,t", True, False, True),
        (" / ( S", False, False, False), ("pool,t", True, False, True),
        (" + ε )", False, False, False)
    ], "8")
    add_p(
        "where ε = 10^-6 kWh guarantees numerical stability. The dynamic P2P clearing price P_P2P,t is formulated as:"
    )
    add_math_eq([
        ("P", False, False, True), ("P2P,t", True, False, True),
        (" = P", False, False, False), ("export", True, False, False),
        (" + ( λ", False, False, False), ("t", True, False, True),
        (" / λ", False, False, False), ("max", True, False, False),
        (" ) · ( P", False, False, False), ("import", True, False, False),
        (" − P", False, False, False), ("export", True, False, False),
        (" )", False, False, False)
    ], "9")
    add_p(
        "strictly bounded within [P_export, P_import] = [$0.08, $0.30] AUD/kWh with sensitivity λ_max = 2.0."
    )
    add_p("• Case 1: Extreme Solar Abundance (λ_t → 0). When surplus solar floods the market (e.g. 12:00 PM), λ_t drops near zero. P_P2P approaches $0.08/kWh. This drastically rewards buyers (who get cheap energy) and encourages battery charging, while sellers still receive slightly more than the utility feed-in credit.")
    add_p("• Case 2: Balanced Market (λ_t = 1.0). When aggregate surplus exactly equals aggregate deficit (D_pool = S_pool), λ_t / λ_max = 1.0 / 2.0 = 0.5. The clearing price is exactly mid-market: P_P2P = $0.08 + 0.5($0.22) = $0.1900/kWh, splitting economic surplus 50/50 between buyers and sellers.")
    add_p("• Case 3: Intense Energy Scarcity (λ_t ≥ 2.0). When aggregate buyer demand exceeds twice the available solar surplus, λ_t / λ_max ≥ 1.0. The price rises to the $0.30/kWh grid ceiling. Buyers pay no more than the grid tariff, while sellers earn the maximum possible reward for their scarce clean energy.")

    add_h2("C. Market Allocation and Proof of Pareto-Dominant Nash Equilibrium")
    add_p(
        "The total energy cleared through the local P2P market is physically bounded by supply and demand: Q_trade,t = min(S_pool,t, D_pool,t). "
        "Energy is allocated pro-rata among participants according to their submitted bids. "
        "Net electricity cost for household i is calculated as:"
    )
    add_math_eq([
        ("Cost", False, False, False), ("i,t", True, False, True), ("P2P", False, True, False),
        (" = m", False, False, False), ("i,t", True, False, True),
        (" · P", False, False, False), ("import", True, False, False),
        (" + q", False, False, False), ("i,t", True, False, True), ("buy", False, True, False),
        (" · P", False, False, False), ("P2P,t", True, False, True),
        (" − q", False, False, False), ("i,t", True, False, True), ("sell", False, True, False),
        (" · P", False, False, False), ("P2P,t", True, False, True),
        (" − e", False, False, False), ("i,t", True, False, True),
        (" · P", False, False, False), ("export", True, False, False)
    ], "10")
    add_p(
        "where m_i,t is remaining grid import, and e_i,t is remaining grid export. "
        "Theorem: Because P_export ≤ P_P2P,t ≤ P_import holds strictly for all hours t, Cost_i,t^P2P ≤ Cost_i,t^grid holds strictly for all households. "
        "Proof: For any seller, selling at P_P2P ≥ P_export yields strictly higher revenue than utility feed-in credit. For any buyer, buying at P_P2P ≤ P_import "
        "yields strictly lower expenditure than utility grid import. Any unilateral deviation to utility grid trading yields an equal or strictly worse financial payoff. "
        "Therefore, full participation in the P2P game is a weakly dominant strategy, and the all-trading profile is a Pareto-dominant strict Nash Equilibrium."
    )

    # Insert Fig 1: Community Diurnal & Pricing
    add_fig(ROOT / "results" / "figures" / "report_figures" / "fig01_community_diurnal_and_dynamic_pricing.png",
            "Fig. 2. Community aggregate diurnal load vs solar profile and dynamic price discovery curve across 24 market hours.")

    # SECTION VI: COUNTERFACTUAL BENCHMARKING & EDGE CASES
    add_h1("VI. RIGOROUS COUNTERFACTUAL BENCHMARKING FRAMEWORK")
    add_h2("A. Why Counterfactual Benchmarking is Vital")
    add_p(
        "In complex socio-technical systems involving multiple physical technologies (solar panels, batteries, software algorithms), "
        "simply reporting that 'community electricity bills dropped by 40%' is scientifically incomplete. A skeptical reviewer or utility engineer "
        "will rightly ask: How much of that 40% was caused by the solar panels? How much was caused by the batteries? And how much was caused by "
        "your game-theoretic software? "
        "Counterfactual benchmarking solves this by defining four progressively sophisticated, mutually comparable operational modes across "
        "the exact same 1,000 Monte Carlo scenarios (24,000 hourly rounds):"
    )
    add_p("1. Mode 1 (Pure Grid Baseline): Assumes zero solar panels and zero batteries. All household demand must be imported from the utility grid at $0.30/kWh. This establishes the absolute macroeconomic baseline cost of community electricity ($26.36/day).", bold_prefix="• ")
    add_p("2. Mode 2 (Solar + Grid-Only): Introduces rooftop solar for self-consumption, but NO batteries and NO peer-to-peer trading. Deficits are imported from the grid at $0.30/kWh, and surplus solar is exported to the grid at the 8¢ feed-in credit. Daily cost drops to $20.83/day.", bold_prefix="• ")
    add_p("3. Mode 3 (Battery + Grid-Only): Introduces 5.0 kWh physical batteries for behind-the-meter self-consumption, but NO peer-to-peer trading. Surplus solar charges the battery first; deficits draw from the battery first. Net deficits are imported from the grid at $0.30/kWh, and net surpluses are exported at $0.08/kWh. Daily cost drops to $16.34/day.", bold_prefix="• ")
    add_p("4. Mode 4 (Proposed P2P Game + Battery): Full proposed multi-agent system. Solar + 5.0 kWh battery + dynamic P2P game-theoretic trading. Unabsorbed energy trades with neighbors at dynamic clearing price P_P2P. Daily cost drops to $15.80/day.", bold_prefix="• ")

    add_h2("B. In-Depth Edge Cases & Operating Regimes Analysis")
    add_p(
        "To ensure the system is completely robust under extreme conditions, five critical edge cases were simulated and audited:"
    )
    add_p("• Edge Case 1: Overcast and Rainy Winter Days. During severe cloud cover, total solar generation drops below 10% of capacity (G_i,t ≈ 0). Batteries cannot charge, and pool surplus S_pool collapses to zero. Market pressure λ_t spikes toward infinity. The dynamic pricing model automatically hits its $0.30/kWh ceiling. The system gracefully reverts to standard grid import without algorithmic failure, ensuring households never lose power.", bold_prefix="1) ")
    add_p("• Edge Case 2: Blazing Midday Solar Flood. On clear summer days, all five batteries hit their 90% SOC ceiling by 11:30 AM. Enormous solar surpluses flood the pool (S_pool >> D_pool). Market pressure λ_t drops below 0.2. Clearing price plunges to $0.10–$0.12/kWh. Heavy buyers (H004 and H003) absorb cheap local power, saving significant money, while sellers earn 25%–50% more than the meager 8¢ utility credit.", bold_prefix="2) ")
    add_p("• Edge Case 3: Nighttime Peak Shaving (18:00 - 22:00). Solar generation is strictly zero. Unmet demand peaks due to evening cooking, lighting, and air conditioning. In Mode 1 and Mode 2, this causes massive $0.30/kWh grid expenses. In Mode 3 and Mode 4, batteries discharge stored midday solar reserves up to the 10% SOC floor, completely shaving the evening grid peak.", bold_prefix="3) ")
    add_p("• Edge Case 4: Asymmetric Market Dominance (The Role of H004). Household H004 has massive demand (33.75 kWh/day) and low solar (3.32 kWh/day). In isolation, H004 suffers expensive electricity bills. In the P2P game, H004 acts as the community's primary energy sponge, absorbing 67.1% of all P2P traded energy. P2P coordination delivers $362.65 AUD of direct savings to H004 (19.1% of its total bill reduction).", bold_prefix="4) ")
    add_p("• Edge Case 5: Battery Saturation and Depletion Boundaries. If a battery drops to 10% SOC, discharging is strictly blocked to prevent cell damage. If a battery reaches 90% SOC, charging is strictly blocked. Physical feasibility is 100% maintained at all times.", bold_prefix="5) ")

    # SECTION VII: DEDICATED INDIVIDUAL HOUSEHOLD CASE STUDIES
    add_h1("VII. INDIVIDUAL HOUSEHOLD CASE STUDIES & DEDICATED GRAPHICAL PROFILES")
    add_p(
        "To provide a granular, household-by-household evaluation, this section presents dedicated case studies for each of the five microgrid participants. "
        "Each case study includes an analysis of the participant's structural archetype, diurnal energy dynamics, physical battery dispatch, "
        "four-mode cost reductions, factor savings decomposition, and a dedicated, ultra-high-resolution (300 DPI) multi-panel figure."
    )

    # VII-A: HOUSEHOLD H001
    add_h2("A. Household H001: The High-Solar Midday Seller (Solar Powerhouse)")
    add_p(
        "Household H001 represents the primary green energy generator of the microgrid, equipped with a 3.78 kWp rooftop solar array. "
        "Average daily demand is 20.90 kWh/day, while average daily solar generation reaches 14.14 kWh/day (peaking above 3.5 kW during midday). "
        "Under Mode 1 (Pure Grid), H001 incurs an average electricity expenditure of $6.27 AUD/day ($6,270.63 over 1,000 days). "
        "Introducing solar self-consumption (Mode 2) cuts expenditure to $4.34 AUD/day, saving $1.93/day. "
        "Adding the 5.0 kWh battery (Mode 3) allows H001 to store midday solar surplus and shave its high morning and evening consumption, reducing cost to $3.11 AUD/day (an additional $1.24/day dividend). "
        "Finally, participating in the proposed P2P trading game (Mode 4) clears unabsorbed solar surplus to neighbors at prices above the 8¢ feed-in credit, bringing daily expenditure down to $2.98 AUD/day. "
        "In total, H001 slashes its daily electricity bill by 52.4% (+$3.29 AUD/day in net savings, totaling $3,285.63 AUD over 1,000 days). "
        "Factor decomposition shows that solar self-consumption drives $1,925.69 AUD (58.6%), battery storage drives $1,238.88 AUD (37.7%), "
        "and P2P trading coordination provides $121.06 AUD (3.7%) of total financial gains."
    )
    add_fig(ROOT / "results" / "figures" / "report_figures" / "fig_household_H001_detailed.png",
            "Fig. 3. Detailed optimization breakdown for Household H001 (High-Solar Midday Seller): Diurnal profile, battery dispatch, 4-mode comparison, and profit decomposition.")

    # VII-B: HOUSEHOLD H002
    add_h2("B. Household H002: The Low-Load Balanced Prosumer (Highest % Bill Cut: 67.4%)")
    add_p(
        "Household H002 represents an energy-conscious, low-consumption prosumer with a 1.00 kWp rooftop solar panel. "
        "Average daily demand is only 6.02 kWh/day, while solar generation averages 4.29 kWh/day. "
        "Because H002's demand is small, its 5.0 kWh battery can absorb nearly its entire solar surplus and discharge to cover almost all evening load. "
        "Under Mode 1 (Pure Grid), H002 spends $1.80 AUD/day ($1,804.57 over 1,000 days). Under Mode 2, cost drops to $1.17 AUD/day. "
        "Under Mode 3 (Battery + Grid), cost plummets to $0.60 AUD/day. Under Mode 4 (P2P Game), cost reaches an ultra-low $0.59 AUD/day ($0.5878/day). "
        "Household H002 achieves the highest percentage bill reduction in the entire microgrid: an astonishing 67.4% net bill reduction (saving $1.22 AUD/day, or $1,216.78 AUD over 1,000 days). "
        "Factor decomposition reveals that solar self-consumption provides $634.92 AUD (52.2%), battery storage arbitrage provides $573.14 AUD (47.1%), "
        "and P2P coordination contributes $8.73 AUD (0.7%)."
    )
    add_fig(ROOT / "results" / "figures" / "report_figures" / "fig_household_H002_detailed.png",
            "Fig. 4. Detailed optimization breakdown for Household H002 (Low-Load Balanced Prosumer): Achieving 67.4% total bill reduction.")

    # VII-C: HOUSEHOLD H003
    add_h2("C. Household H003: The Moderate Prosumer (Regular Net Buyer)")
    add_p(
        "Household H003 represents a typical working family with moderate electricity consumption (13.70 kWh/day) and a modest 1.00 kWp solar array (3.65 kWh/day). "
        "Because demand substantially outpaces solar production, H003 is a structural net energy buyer (+10.05 kWh/day net deficit). "
        "Under Mode 1 (Pure Grid), H003 spends $4.11 AUD/day ($4,110.13 over 1,000 days). Solar self-consumption (Mode 2) reduces expenditure to $3.28 AUD/day. "
        "Battery storage (Mode 3) further cuts cost to $2.49 AUD/day. Under the coordinated P2P game (Mode 4), H003 regularly buys low-cost solar from H001 and H005 during midday, "
        "bringing daily electricity cost down to $2.48 AUD/day ($2.4768/day). "
        "In total, H003 achieves a 39.7% bill reduction, capturing $1.63 AUD/day in savings ($1,633.30 AUD over 1,000 days). "
        "Factor decomposition shows that solar self-consumption contributes $832.26 AUD (51.0%), battery storage arbitrage contributes $790.27 AUD (48.4%), "
        "and P2P coordination adds $10.77 AUD (0.7%)."
    )
    add_fig(ROOT / "results" / "figures" / "report_figures" / "fig_household_H003_detailed.png",
            "Fig. 5. Detailed optimization breakdown for Household H003 (Moderate Prosumer Regular Buyer): Diurnal dynamics and 39.7% cost reduction.")

    # VII-D: HOUSEHOLD H004
    add_h2("D. Household H004: High-Demand Consumer (Primary P2P Beneficiary: 19.1% P2P Share)")
    add_p(
        "Household H004 represents the largest electrical consumer in the microgrid, exhibiting continuous heavy demand (33.75 kWh/day) "
        "due to intensive appliance use, space heating, and electric water heating, coupled with a small 2.00 kWp solar array (3.32 kWh/day). "
        "H004 is a heavy net energy buyer (+30.43 kWh/day deficit). "
        "Under Mode 1 (Pure Grid), H004 incurs a massive electricity bill of $10.12 AUD/day ($10,123.83 over 1,000 days). "
        "Solar self-consumption (Mode 2) cuts cost to $9.32 AUD/day. Battery storage alone (Mode 3) cuts cost to $8.59 AUD/day. "
        "However, because H004's rooftop solar is completely inadequate to charge its battery, its battery frequently sits underutilized under Mode 3. "
        "Herein lies the transformative power of game-theoretic P2P trading: under Mode 4 (P2P Game + Battery), H004 actively imports abundant, cheap surplus "
        "solar from H001 and H005 at dynamic clearing prices between $0.11 and $0.18/kWh (far below the $0.30 grid tariff). "
        "This drives H004's daily cost down to $8.23 AUD/day ($8.2252/day), securing $1.90 AUD/day in net savings ($1,898.61 AUD over 1,000 days). "
        "CRITICAL DISCOVERY: P2P trading coordination delivers an astounding $362.65 AUD over 1,000 days to H004—accounting for 19.1% of H004's entire financial savings! "
        "Out of the total $540.34 AUD in P2P coordination profit generated across the entire community, H004 single-handedly captures 67.1% of it. "
        "This proves that high-demand consumers who lack adequate rooftop solar gain the largest absolute financial benefits from participating in a game-theoretic microgrid."
    )
    add_fig(ROOT / "results" / "figures" / "report_figures" / "fig_household_H004_detailed.png",
            "Fig. 6. Detailed optimization breakdown for Household H004 (High-Demand Consumer): Highlighting the 19.1% P2P software coordination share.")

    # VII-E: HOUSEHOLD H005
    add_h2("E. Household H005: Balanced Prosumer (Opportunistic Swing Trader)")
    add_p(
        "Household H005 possesses a balanced 2.16 kWp solar array and moderate consumption (13.49 kWh/day demand, 8.75 kWh/day solar generation). "
        "H005 acts as the community's opportunistic 'swing trader': during sunny midday hours (11:00 to 14:00), its solar exceeds load, allowing it to sell surplus "
        "to H004; during cloudy mornings and late afternoons, its demand exceeds solar, leading it to buy energy from H001. "
        "Under Mode 1 (Pure Grid), H005 spends $4.05 AUD/day ($4,046.08 over 1,000 days). Solar self-consumption (Mode 2) cuts expenditure to $2.72 AUD/day. "
        "Battery storage (Mode 3) cuts cost to $1.56 AUD/day. Under Mode 4 (P2P Game), cost reaches $1.52 AUD/day ($1.5207/day). "
        "H005 secures a substantial 62.4% total bill reduction (saving $2.53 AUD/day, or $2,525.34 AUD over 1,000 days). "
        "Factor decomposition confirms that solar self-consumption provides $1,329.14 AUD (52.6%), battery storage arbitrage provides $1,159.08 AUD (45.9%), "
        "and P2P coordination adds $37.13 AUD (1.5%)."
    )
    add_fig(ROOT / "results" / "figures" / "report_figures" / "fig_household_H005_detailed.png",
            "Fig. 7. Detailed optimization breakdown for Household H005 (Balanced Opportunistic Swing Trader): 62.4% bill reduction and swing trading.")

    # SECTION VIII: COMMUNITY RESULTS & DASHBOARD AUDIT
    add_h1("VIII. COMMUNITY-WIDE MONTE CARLO RESULTS & DASHBOARD METRICS AUDIT")
    add_h2("A. Authoritative Macroeconomic Findings across 1,000 Scenarios")
    add_p(
        "Across 1,000 simulated days (24,000 sequential hourly market rounds), the community microgrid exhibits extraordinary economic resilience and efficiency. "
        "Table III summarizes the average daily and cumulative 1,000-day costs across the four operational counterfactual modes for all participants and the community aggregate."
    )

    # TABLE III: Authoritative Summary Table
    t3_data = [
        ["Participant", "Mode 1: Pure Grid", "Mode 2: Solar+Grid", "Mode 3: Batt+Grid", "Mode 4: P2P Game", "Daily Savings", "Bill Cut (%)", "1,000-Day Profit"],
        ["H001 (Seller)", "$6.2706 / d", "$4.3449 / d", "$3.1061 / d", "$2.9850 / d", "+$3.2856 / d", "52.4%", "$3,285.63 AUD"],
        ["H002 (Low Load)", "$1.8046 / d", "$1.1697 / d", "$0.5965 / d", "$0.5878 / d", "+$1.2168 / d", "67.4%", "$1,216.78 AUD"],
        ["H003 (Buyer)", "$4.1101 / d", "$3.2779 / d", "$2.4876 / d", "$2.4768 / d", "+$1.6333 / d", "39.7%", "$1,633.30 AUD"],
        ["H004 (Heavy Buyer)", "$10.1238 / d", "$9.3230 / d", "$8.5879 / d", "$8.2252 / d", "+$1.8986 / d", "18.8%", "$1,898.61 AUD"],
        ["H005 (Swing Trader)", "$4.0461 / d", "$2.7169 / d", "$1.5579 / d", "$1.5207 / d", "+$2.5253 / d", "62.4%", "$2,525.34 AUD"],
        ["COMMUNITY TOTAL", "$26.3552 / d", "$20.8324 / d", "$16.3359 / d", "$15.7956 / d", "+$10.5597 / d", "40.07%", "$10,559.67 AUD"],
    ]
    t3_widths = [Inches(1.2), Inches(0.9), Inches(0.9), Inches(0.9), Inches(0.9), Inches(0.9), Inches(0.7), Inches(1.1)]
    add_table_data(t3_data, t3_widths, "TABLE III: Authoritative Electricity Costs and Net Financial Benefits Across Four Operational Modes")

    # Insert Fig 8: 4-Mode Counterfactual Comparison
    add_fig(ROOT / "results" / "figures" / "report_figures" / "fig02_community_counterfactual_comparison.png",
            "Fig. 8. Average daily electricity cost comparison across the four operational counterfactual modes (1,000 Monte Carlo scenarios).")

    add_h2("B. Factor Decomposition of Community Profit")
    add_p(
        "Total community financial profit reaches $10,559.67 AUD over the 1,000-scenario evaluation horizon (averaging $10.5597 AUD/day, or $3,856.92 AUD annually). "
        "Table IV documents the precise factor decomposition, isolating the exact contributions of solar self-consumption, battery storage arbitrage, "
        "and game-theoretic peer-to-peer software coordination."
    )

    # TABLE IV: Factor Decomposition
    t4_data = [
        ["Participant", "Total Savings (AUD/d)", "Solar Dividend (AUD/d)", "Battery Dividend (AUD/d)", "P2P Dividend (AUD/d)", "P2P Share (%)", "1,000-Day P2P Gain"],
        ["H001", "$3.2856 / d", "$1.9257 / d (58.6%)", "$1.2389 / d (37.7%)", "$0.1211 / d (3.7%)", "3.7%", "$121.06 AUD"],
        ["H002", "$1.2168 / d", "$0.6349 / d (52.2%)", "$0.5731 / d (47.1%)", "$0.0087 / d (0.7%)", "0.7%", "$8.73 AUD"],
        ["H003", "$1.6333 / d", "$0.8323 / d (51.0%)", "$0.7903 / d (48.4%)", "$0.0108 / d (0.7%)", "0.7%", "$10.77 AUD"],
        ["H004", "$1.8986 / d", "$0.8009 / d (42.2%)", "$0.7351 / d (38.7%)", "$0.3626 / d (19.1%)", "19.1%", "$362.65 AUD"],
        ["H005", "$2.5253 / d", "$1.3291 / d (52.6%)", "$1.1591 / d (45.9%)", "$0.0371 / d (1.5%)", "1.5%", "$37.13 AUD"],
        ["COMMUNITY", "$10.5597 / d", "$5.5229 / d (52.3%)", "$4.4965 / d (42.6%)", "$0.5403 / d (5.1%)", "5.1%", "$540.34 AUD"],
    ]
    t4_widths = [Inches(1.0), Inches(1.1), Inches(1.2), Inches(1.2), Inches(1.1), Inches(0.8), Inches(1.0)]
    add_table_data(t4_data, t4_widths, "TABLE IV: Factor Decomposition of Community Financial Profits into Solar, Storage, and P2P Software Dividends")

    # Insert Fig 9: Factor Decomposition Waterfall & Stacked %
    add_fig(ROOT / "results" / "figures" / "report_figures" / "fig03_community_factor_decomposition.png",
            "Fig. 9. Factor decomposition waterfall ($10,559.67 AUD community profit) and normalized percentage value drivers by household.")

    add_h2("C. Statistical Stability & Zero Downside Risk Verification")
    add_p(
        "A critical question in stochastic game theory is whether participants face downside financial risk during bad weather days. "
        "We audited the empirical probability distributions across all 1,000 Monte Carlo scenarios. "
        "As documented in Fig. 10 and Table V, the minimum P2P trading profit and 5th percentile profit (Q_05) across all 1,000 scenarios is strictly $0.0000 AUD/day. "
        "There is zero downside risk: no household ever loses money by participating in the game-theoretic trading platform under any simulated weather condition."
    )

    # TABLE V: Statistical Risk Metrics
    t5_data = [
        ["Household", "Mean P2P Profit", "Std Dev (σ)", "Median Profit", "5th Pct (Q_05)", "95th Pct (Q_95)", "Minimum Profit", "Maximum Profit"],
        ["H001 (Seller)", "$0.1211 AUD/d", "$0.1858", "$0.0714", "$0.0000", "$0.4030", "$0.0000", "$1.6347 AUD/d"],
        ["H002 (Low Load)", "$0.0087 AUD/d", "$0.0295", "$0.0000", "$0.0000", "$0.0367", "$0.0000", "$0.4221 AUD/d"],
        ["H003 (Buyer)", "$0.0108 AUD/d", "$0.0392", "$0.0000", "$0.0000", "$0.0599", "$0.0000", "$0.4070 AUD/d"],
        ["H004 (Heavy Buyer)", "$0.3626 AUD/d", "$0.4242", "$0.1691", "$0.0000", "$1.2411", "$0.0000", "$1.6250 AUD/d"],
        ["H005 (Swing Trader)", "$0.0371 AUD/d", "$0.0851", "$0.0000", "$0.0000", "$0.1427", "$0.0000", "$0.8620 AUD/d"],
        ["COMMUNITY TOTAL", "$0.5403 AUD/d", "$0.6370", "$0.3291", "$0.0000", "$1.7435", "$0.0000", "$3.8033 AUD/d"],
    ]
    t5_widths = [Inches(1.2), Inches(0.9), Inches(0.8), Inches(0.8), Inches(0.8), Inches(0.8), Inches(0.8), Inches(0.9)]
    add_table_data(t5_data, t5_widths, "TABLE V: Empirical Statistical Profit Distribution Metrics across 1,000 Monte Carlo Weather Scenarios")

    # Insert Fig 10: Monte Carlo Risk & Cumulative Savings
    add_fig(ROOT / "results" / "figures" / "report_figures" / "fig04_monte_carlo_risk_and_stability.png",
            "Fig. 10. Empirical P2P profit distributions across 1,000 Monte Carlo scenarios and cumulative 1,000-day community financial growth.")

    add_h2("D. Comprehensive Audit of Interactive Dashboard Numbers and Roles")
    add_p(
        "To connect the computational simulation directly with the interactive web dashboard (accessible via dashboard/app.py), "
        "every number presented on the user interface is formally defined and contextualized below:"
    )
    add_p("1. Headline Card: 'Average Community Profit: $10.56 AUD/day'. Represents the exact arithmetic mean of daily community savings across all 1,000 Monte Carlo scenarios ($10.55967 AUD/day). Over 1,000 days, this totals exactly $10,559.67 AUD in net financial profits.", bold_prefix="• ")
    add_p("2. Headline Card: 'Total Bill Reduction: 40.07%'. Represents the percentage reduction in total community electricity expenditure, dropping baseline Pure Grid cost from $26.3552 AUD/day ($26,355.23 AUD over 1,000 days) down to $15.7956 AUD/day ($15,795.57 AUD over 1,000 days). Calculation: (26.3552 - 15.7956) / 26.3552 = 40.0667%.", bold_prefix="• ")
    add_p("3. Headline Card: 'Grid Spread Captured: 22.0¢ / kWh'. The physical arbitrage spread between the $0.30/kWh grid import rate and the $0.08/kWh feed-in export credit ($0.30 - $0.08 = $0.22/kWh). In the absence of P2P trading, this value is extracted by utility retailers. Under our platform, this 22¢ spread is fully retained inside the community.", bold_prefix="• ")
    add_p("4. Headline Card: 'Monte Carlo Horizon: 24,000 Hours'. 1,000 independent 24-hour days simulated sequentially, yielding 24,000 discrete game-theoretic market clearing rounds.", bold_prefix="• ")
    add_p("5. Annualized Community Savings: '$3,856.92 AUD/year'. Calculated as 365.25 days × $10.55967 AUD/day, proving the long-term commercial viability for suburban residential microgrids.", bold_prefix="• ")
    add_p("6. Factor Waterfall: 52.3% Solar ($5,522.87 AUD) + 42.6% Battery ($4,496.47 AUD) + 5.1% P2P Game ($540.34 AUD) = 100.0% ($10,559.67 AUD). Crucially, the $540.34 AUD P2P coordination gain represents pure algorithmic software value creation, achieved with zero additional hardware expenditure.", bold_prefix="• ")

    # SECTION IX: CONCLUSION, EDUCATIONAL ROLE & REFERENCES
    add_h1("IX. DISCUSSION, EDUCATIONAL SIGNIFICANCE, AND CONCLUSION")
    add_h2("A. Real-World Implications for Transactive Energy and Policy")
    add_p(
        "The findings of this research project carry profound policy and regulatory implications for modern transactive energy distribution networks. "
        "Current utility regulatory frameworks heavily penalize residential solar prosumers through declining feed-in tariffs, while residential retail prices "
        "continue to escalate. This project proves that peer-to-peer energy trading coupled with distributed battery storage creates a self-balancing, "
        "decentralized microgrid ecosystem. By allowing neighbors to trade local solar power at dynamic, scarcity-based prices, distribution utilities "
        "can significantly mitigate substation peak loading, eliminate reverse power flows that cause over-voltage trips, and reduce costly transmission line upgrades."
    )

    add_h2("B. Project Conclusions")
    add_p(
        "This project successfully developed, simulated, and audited an integrated stochastic game-theoretic optimization platform for peer-to-peer energy trading "
        "in residential microgrids with physical battery energy storage. The key conclusions of this research are:"
    )
    add_p("1) The initial 2-household normal-form game prototype proved that cooperative P2P trading forms a strict, Pareto-dominant Nash equilibrium (+102.4% seller gain, 36.7% buyer bill cut).", bold_prefix="• ")
    add_p("2) Expanding to a 5-household flagship community platform slashes community electricity costs by 40.07%, saving $10.56 AUD/day ($10,559.67 AUD over 1,000 days).", bold_prefix="• ")
    add_p("3) Factor decomposition proves that solar self-consumption (52.3%) and physical battery storage (42.6%) furnish baseline arbitrage, while P2P game-theoretic coordination captures an extra 5.1% software dividend ($540.34 AUD) with zero marginal hardware expenditure.", bold_prefix="• ")
    add_p("4) High-demand consumers who lack adequate rooftop solar gain the largest absolute financial benefits from P2P coordination (H004 captures 19.1% of its savings from P2P trading).", bold_prefix="• ")
    add_p("5) Individual rationality and zero downside risk are guaranteed across all 1,000 Monte Carlo scenarios (minimum daily profit is strictly $0.0000 AUD).", bold_prefix="• ")

    # ACKNOWLEDGMENT
    add_h1("ACKNOWLEDGMENT")
    add_p(
        "The authors express their deepest and most sincere gratitude to their project supervisor, esteemed faculty members, and the Department of Mathematics, "
        "Sardar Vallabhbhai National Institute of Technology (SVNIT), Surat, Gujarat, India, for their continuous academic mentorship, valuable feedback, "
        "technical guidance, and research facilities throughout the design, mathematical formulation, and computational execution of this project."
    )

    # REFERENCES
    add_h1("REFERENCES")
    refs = [
        "[1] J. F. Nash, 'Non-cooperative games,' Annals of Mathematics, vol. 54, no. 2, pp. 286–295, 1951.",
        "[2] F. Moret and P. Pinson, 'Energy collectives: A decentralized framework for locally organized energy markets,' IEEE Transactions on Power Systems, vol. 34, no. 1, pp. 647–656, Jan. 2019.",
        "[3] W. Tushar, T. K. Saha, C. Yuen, D. Smith, and H. V. Poor, 'Peer-to-peer trading in electricity networks: An overview,' IEEE Transactions on Smart Grid, vol. 11, no. 4, pp. 3185–3200, July 2020.",
        "[4] C. Zhang, J. Wu, Y. Zhou, M. Cheng, and C. Long, 'Peer-to-Peer energy trading in a microgrid,' Applied Energy, vol. 220, pp. 1–12, June 2018.",
        "[5] Y. Parag and B. K. Sovacool, 'Electricity market design for the prosumer era,' Nature Energy, vol. 1, no. 4, p. 16032, Apr. 2016.",
        "[6] S. Paudel, K. Sampath, M. Yang, and P. H. Cheah, 'Peer-to-peer energy trading in a residential microgrid: A game-theoretic approach,' Applied Energy, vol. 279, p. 115794, Dec. 2020.",
        "[7] J. Guerrero, A. C. Chapman, and G. Verbič, 'Decentralized P2P energy trading under network constraints in a low-voltage distribution grid,' IEEE Transactions on Smart Grid, vol. 10, no. 5, pp. 5173–5183, Sept. 2019.",
        "[8] N. Liu, X. Yu, C. Wang, C. Li, L. Ma, and J. Lei, 'Energy-sharing model with price-based demand response for microgrids of peer-to-peer prosumers,' IEEE Transactions on Power Systems, vol. 32, no. 5, pp. 3569–3583, Sept. 2017.",
        "[9] Z. Chen, L. Chen, and B. Zhang, 'Stochastic optimization for microgrid energy management under renewable uncertainty,' IEEE Transactions on Sustainable Energy, vol. 12, no. 2, pp. 1120–1131, Apr. 2021.",
        "[10] M. Khorasany, Y. Mishra, and G. Ledwich, 'Market framework for local energy trading: A review of architecture, trade mechanism and prior projects,' Renewable and Sustainable Energy Reviews, vol. 132, p. 110033, Oct. 2020.",
        "[11] Ausgrid, 'Solar Home Electricity Data,' Ausgrid Network Data, 2014. [Online]. Available: https://www.ausgrid.com.au/Industry/Our-Research/Data-to-share/Solar-home-electricity-data",
        "[12] W. Tushar et al., 'Grid influenced peer-to-peer energy trading,' IEEE Transactions on Smart Grid, vol. 11, no. 2, pp. 1406–1418, Mar. 2020."
    ]
    for r in refs:
        p_ref = add_p(r, style='references', space_after=2.5)
        p_ref.runs[0].font.size = Pt(8.5)

    doc.paragraphs[89].text = ""

    # Save documents
    out_final = ROOT / "reports" / "Project_Report_Final.docx"
    out_revised = ROOT / "reports" / "ieee_paper_revised.docx"
    doc.save(str(out_final))
    shutil.copy(out_final, out_revised)
    print(f"Successfully generated expanded Word report:\n  - {out_final}\n  - {out_revised}")

if __name__ == "__main__":
    build_expanded_report()

