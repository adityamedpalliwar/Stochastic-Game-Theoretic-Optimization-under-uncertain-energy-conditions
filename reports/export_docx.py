"""
export_docx.py
──────────────
Convert ieee_paper_revised.html → ieee_paper_revised.docx
IEEE two-column academic paper format with FULL-WIDTH images that do not shrink.

Features:
 • Single-column header (Title, Subtitle, Authors, Abstract, Keywords)
 • Two-column body for text, headings, lists, equations, references
 • Continuous section breaks for Figures and Tables so they span across BOTH columns
 • Images rendered at full printable width (6.85 in / 17.4 cm), matching HTML layout
 • No hash collisions on images (sequential indexing)
 • True Word subscripts and superscripts for math
 • Clean table formatting with full-width layout
"""

import argparse
import base64
import io
import os
import re
import sys
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor
from PIL import Image as PILImage

# ─── Paths ──────────────────────────────────────────────────────────────────
BASE    = Path(__file__).resolve().parent
HTML_IN = BASE / "ieee_paper_revised.html"

# ─── Dimensions (A4 Page, IEEE Margins) ─────────────────────────────────────
PAGE_W_CM  = 21.0    # 8.27 in
PAGE_H_CM  = 29.7    # 11.69 in
MARGIN_LR  = 1.65    # 0.65 in margins left and right
MARGIN_TB  = 1.90    # 0.75 in margins top and bottom
COL_GAP_PT = 18      # 18 pt = 0.25 in column gap

# Full printable width for figures and tables spanning both columns:
# 21.0 cm - 2 * 1.65 cm = 17.7 cm = 6.97 in. Use 6.85 in for safe rendering without overflow.
FULL_WIDTH_IN = 6.85

# ─── Colours ────────────────────────────────────────────────────────────────
C_BLACK = RGBColor(0x00, 0x00, 0x00)
C_NAVY  = RGBColor(0x1e, 0x3a, 0x8a)
C_SLATE = RGBColor(0x37, 0x41, 0x51)
C_GREY  = RGBColor(0x6b, 0x72, 0x80)
C_BLUE  = RGBColor(0x02, 0x84, 0xc7)

# ═══════════════════════════════════════════════════════════════════════════
# Layout & Section Management
# ═══════════════════════════════════════════════════════════════════════════

def set_section_page_setup(section):
    """Set A4 page dimensions and IEEE margins on a section."""
    section.page_width   = Cm(PAGE_W_CM)
    section.page_height  = Cm(PAGE_H_CM)
    section.left_margin  = Cm(MARGIN_LR)
    section.right_margin = Cm(MARGIN_LR)
    section.top_margin   = Cm(MARGIN_TB)
    section.bottom_margin= Cm(MARGIN_TB)


def set_section_columns(section, num_cols: int, space_pt: int = COL_GAP_PT):
    """Set the number of columns on a section in OpenXML."""
    sectPr = section._sectPr
    for old_cols in sectPr.findall(qn("w:cols")):
        sectPr.remove(old_cols)
    cols_el = OxmlElement("w:cols")
    cols_el.set(qn("w:num"), str(num_cols))
    cols_el.set(qn("w:equalWidth"), "1")
    if num_cols > 1:
        cols_el.set(qn("w:space"), str(int(space_pt * 20)))  # in twips
    sectPr.append(cols_el)


class SectionManager:
    """
    Manages continuous section switching between 2-column text and 1-column
    full-width figures/tables so images never get squashed into a narrow column.
    """
    def __init__(self, doc: Document):
        self.doc = doc
        self.current_cols = 1
        # Set up the first section
        sec0 = doc.sections[0]
        set_section_page_setup(sec0)
        set_section_columns(sec0, 1)

    def switch_to_columns(self, num_cols: int):
        """Switch column mode if necessary using a continuous section break."""
        if self.current_cols == num_cols:
            return

        # Add continuous section
        new_sec = self.doc.add_section(WD_SECTION.CONTINUOUS)
        set_section_page_setup(new_sec)
        set_section_columns(new_sec, num_cols)

        # Zero out spacing on the section-break paragraph to avoid empty blank lines
        last_p = self.doc.paragraphs[-1]
        pPr = last_p._p.get_or_add_pPr()
        sp = OxmlElement("w:spacing")
        sp.set(qn("w:before"), "0")
        sp.set(qn("w:after"), "0")
        sp.set(qn("w:line"), "0")
        pPr.append(sp)

        self.current_cols = num_cols


# ═══════════════════════════════════════════════════════════════════════════
# Styling & Run Helpers
# ═══════════════════════════════════════════════════════════════════════════

def set_spacing(para, before=0, after=4, lines=1.3):
    pf = para.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after  = Pt(after)
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.line_spacing = lines


def add_run(para, text, bold=False, italic=False, size=10, color=None,
            font="Times New Roman", subscript=False, superscript=False):
    if not text:
        return None
    r = para.add_run(text)
    r.font.name = font
    r.font.bold = bold
    r.font.italic = italic
    r.font.size = Pt(size)
    if subscript:
        r.font.subscript = True
    if superscript:
        r.font.superscript = True
    if color:
        r.font.color.rgb = color
    return r


def text_content(node) -> str:
    return node.get_text(separator=" ", strip=True) if node else ""


def render_inline(para, node, bold=False, italic=False, size=10,
                  color=None, mono=False, sub=False, sup=False):
    """Recursively add runs with formatting including true sub/sup."""
    if isinstance(node, NavigableString):
        t = str(node)
        if t:
            add_run(para, t, bold=bold, italic=italic, size=size,
                    color=color, font="Courier New" if mono else "Times New Roman",
                    subscript=sub, superscript=sup)
        return
    if not isinstance(node, Tag):
        return

    tag = node.name
    b   = bold   or tag in ("strong", "b")
    i   = italic or tag in ("em", "i", "var")
    m   = mono   or tag in ("code", "tt", "kbd")
    is_sub = sub or tag == "sub"
    is_sup = sup or tag == "sup"
    c   = C_BLUE if tag == "a" else color
    s   = max(7, size - 2) if (tag in ("sup", "sub") and not is_sub and not is_sup) else size

    # Handle HTML math entities cleanly
    for child in node.children:
        render_inline(para, child, b, i, s, c, m, is_sub, is_sup)


def p_bottom_border(para, color="000000", sz="4"):
    pPr = para._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    b = OxmlElement("w:bottom")
    b.set(qn("w:val"), "single")
    b.set(qn("w:sz"), sz)
    b.set(qn("w:space"), "2")
    b.set(qn("w:color"), color)
    bdr.append(b)
    pPr.append(bdr)


def p_left_border(para, color="1e3a8a", sz="12", space="8", fill=None):
    pPr = para._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), sz)
    left.set(qn("w:space"), space)
    left.set(qn("w:color"), color)
    bdr.append(left)
    pPr.append(bdr)
    if fill:
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), fill.lstrip("#"))
        pPr.append(shd)


def set_cell_shading(cell, fill_hex: str):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex.lstrip("#"))
    tcPr.append(shd)


def remove_cell_borders(cell):
    tcPr = cell._tc.get_or_add_tcPr()
    bdr = OxmlElement("w:tcBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        s = OxmlElement(f"w:{side}")
        s.set(qn("w:val"), "none")
        bdr.append(s)
    tcPr.append(bdr)


# ═══════════════════════════════════════════════════════════════════════════
# Element Renderers
# ═══════════════════════════════════════════════════════════════════════════

def render_title(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_spacing(p, 0, 6, 1.15)
    add_run(p, text, bold=True, size=18, color=C_BLACK)


def render_subtitle(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_spacing(p, 0, 14, 1.0)
    add_run(p, text, italic=True, size=10, color=C_SLATE)


def render_authors(doc, grid_node):
    divs = [d for d in grid_node.children if isinstance(d, Tag) and d.name == "div"]
    if not divs:
        return
    tbl = doc.add_table(rows=1, cols=len(divs))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.style = "Table Grid"

    for i, div in enumerate(divs):
        cell = tbl.rows[0].cells[i]
        remove_cell_borders(cell)
        name = div.find(class_="author-name")
        dept = div.find(class_="author-dept")
        mail = div.find(class_="author-email")

        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_spacing(p, 0, 2, 1.1)
        if name:
            add_run(p, text_content(name), bold=True, size=11, color=C_NAVY)

        if dept:
            p2 = cell.add_paragraph()
            p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
            set_spacing(p2, 0, 2, 1.0)
            add_run(p2, text_content(dept), size=9, color=C_GREY)

        if mail:
            p3 = cell.add_paragraph()
            p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
            set_spacing(p3, 0, 0, 1.0)
            add_run(p3, text_content(mail), size=8.5, color=C_BLUE, font="Courier New")

    sp = doc.add_paragraph()
    set_spacing(sp, 0, 4, 1.0)


def render_abstract(doc, node):
    kw_node = node.find(class_="keywords")

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.left_indent = Cm(0.3)
    set_spacing(p, 2, 3, 1.35)
    p_left_border(p, fill="F8FAFC")
    add_run(p, "Abstract\u2014", bold=True, italic=True, size=10, color=C_BLACK)

    for child in node.children:
        if isinstance(child, NavigableString):
            t = str(child).strip()
            if t:
                add_run(p, t + " ", size=9.5, color=C_BLACK)
        elif isinstance(child, Tag):
            cls = child.get("class", [])
            if "abstract-title" in cls or "keywords" in cls:
                continue
            render_inline(p, child, size=9.5)

    if kw_node:
        kp = doc.add_paragraph()
        kp.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        kp.paragraph_format.left_indent = Cm(0.3)
        set_spacing(kp, 2, 10, 1.2)
        p_left_border(kp, fill="F8FAFC")
        add_run(kp, "Keywords\u2014", bold=True, italic=True, size=9, color=C_BLACK)
        strong = kw_node.find("strong")
        txt = text_content(kw_node)
        if strong:
            txt = txt[len(text_content(strong)):].strip()
        add_run(kp, txt, size=9, color=C_SLATE)


def render_h2(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_spacing(p, 14, 4, 1.0)
    add_run(p, text.upper(), bold=True, size=10.5, color=C_BLACK)
    p_bottom_border(p, sz="4")


def render_h3(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_spacing(p, 10, 3, 1.0)
    add_run(p, text, bold=True, italic=True, size=10, color=C_NAVY)


def render_h4(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_spacing(p, 7, 2, 1.0)
    add_run(p, text, bold=True, size=10, color=C_SLATE)


def render_body_para(doc, node, size=10):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    set_spacing(p, 0, 5, 1.35)
    render_inline(p, node, size=size)


def render_bullet_list(doc, ul_node):
    for li in ul_node.find_all("li", recursive=False):
        p = doc.add_paragraph(style="List Bullet")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        set_spacing(p, 1, 3, 1.2)
        render_inline(p, li, size=10)
        for r in p.runs:
            r.font.name = "Times New Roman"
            r.font.size = Pt(10)


def render_equation(doc, node):
    """Render equation card with clean linear math formatting and right-aligned eq-num."""
    math_node = node.find(class_="math-formula")
    eq_n_node = node.find(class_="eq-num")
    eq_n_text = text_content(eq_n_node) if eq_n_node else ""

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_spacing(p, 6, 6, 1.1)

    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "FAFAFA")
    pPr.append(shd)

    # Cleanly format formula: replace &Biggl( with (, clean fractions
    if math_node:
        for child in math_node.children:
            if isinstance(child, Tag) and "frac" in child.get("class", []):
                num = child.find(class_="num")
                den = child.find(class_="den")
                add_run(p, "(", font="Cambria Math", size=10)
                render_inline(p, num, size=10)
                add_run(p, " / ", font="Cambria Math", size=10)
                render_inline(p, den, size=10)
                add_run(p, ")", font="Cambria Math", size=10)
            else:
                render_inline(p, child, size=10)
    else:
        add_run(p, text_content(node), italic=True, size=10, font="Cambria Math")

    if eq_n_text:
        add_run(p, f"    ({eq_n_text})", bold=True, size=10, color=C_GREY)


def render_figure(doc, node, fig_index: int, tmp_dir: Path):
    """
    Render Figure spanning the FULL PRINTABLE WIDTH across both columns.
    Ensures image is never squashed or scaled down into a column.
    """
    img_tag = node.find("img")
    cap_tag = node.find(class_="figure-caption")

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_spacing(p, 12, 4, 1.0)

    if img_tag:
        src = img_tag.get("src", "")
        if src.startswith("data:image"):
            b64 = re.sub(r"^data:image/[^;]+;base64,", "", src)
            try:
                img_bytes = base64.b64decode(b64)
                # Save raw pristine bytes to temp PNG
                tmp_f = tmp_dir / f"fig_{fig_index:03d}.png"
                tmp_f.write_bytes(img_bytes)

                # Check dimensions with Pillow
                with PILImage.open(tmp_f) as pil:
                    orig_w, orig_h = pil.size

                # Insert at full printable width (6.85 in = 17.4 cm), aspect ratio preserved!
                run = p.add_run()
                run.add_picture(str(tmp_f), width=Inches(FULL_WIDTH_IN))

            except Exception as ex:
                add_run(p, f"[Figure {fig_index} could not be embedded: {ex}]",
                        italic=True, size=9, color=C_GREY)

    if cap_tag:
        cp = doc.add_paragraph()
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_spacing(cp, 3, 12, 1.0)
        add_run(cp, text_content(cap_tag), bold=True, italic=True, size=9, color=C_SLATE)


def render_table(doc, caption_node, table_node):
    """Render academic table spanning full width across both columns."""
    if caption_node:
        cp = doc.add_paragraph()
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_spacing(cp, 12, 4, 1.0)
        add_run(cp, text_content(caption_node), bold=True, size=9.5, color=C_BLACK)

    headers  = [text_content(th) for th in table_node.find_all("th")]
    all_rows = []
    for tr in table_node.find_all("tr"):
        tds = tr.find_all("td")
        if tds:
            all_rows.append([text_content(td) for td in tds])

    if not headers and not all_rows:
        return

    n_cols = max(len(headers) if headers else 0, max((len(r) for r in all_rows), default=0))
    n_rows = (1 if headers else 0) + len(all_rows)
    if n_cols == 0 or n_rows == 0:
        return

    tbl = doc.add_table(rows=n_rows, cols=n_cols)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.style = "Table Grid"

    # Distribute columns evenly across FULL_WIDTH_IN
    col_w_in = FULL_WIDTH_IN / n_cols
    for row in tbl.rows:
        for ci, cell in enumerate(row.cells):
            cell.width = Inches(col_w_in)

    row_i = 0
    if headers:
        for ci, htext in enumerate(headers[:n_cols]):
            cell = tbl.rows[row_i].cells[ci]
            set_cell_shading(cell, "E5E7EB")
            pp = cell.paragraphs[0]
            pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            set_spacing(pp, 3, 3, 1.0)
            add_run(pp, htext, bold=True, size=8.5, color=C_BLACK)
        row_i += 1

    for di, vals in enumerate(all_rows):
        is_last = (di == len(all_rows) - 1)
        bg = "F9FAFB" if di % 2 == 1 else "FFFFFF"
        if is_last:
            bg = "F1F5F9"
        for ci, v in enumerate(vals[:n_cols]):
            cell = tbl.rows[row_i].cells[ci]
            set_cell_shading(cell, bg)
            pp = cell.paragraphs[0]
            pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            set_spacing(pp, 2.5, 2.5, 1.0)
            add_run(pp, v, bold=is_last, size=8.5, color=C_BLACK)
        row_i += 1

    sp = doc.add_paragraph()
    set_spacing(sp, 0, 10, 1.0)


def render_ref_item(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.left_indent       = Cm(0.6)
    p.paragraph_format.first_line_indent = Cm(-0.6)
    set_spacing(p, 0, 4, 1.2)
    add_run(p, text, size=8.5, color=C_BLACK)


# ═══════════════════════════════════════════════════════════════════════════
# Main Pipeline
# ═══════════════════════════════════════════════════════════════════════════

def convert(html_path: Path, out_path: Path):
    print(f"Reading HTML : {html_path}")
    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")

    doc = Document()

    # Configure Normal style
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(10)

    mgr = SectionManager(doc)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        # ── 1. Single-column Header ───────────────────────────────────────
        print("  Rendering single-column header…")
        mgr.switch_to_columns(1)

        title_tag = soup.find("h1", class_="paper-title")
        sub_tag   = soup.find(class_="subtitle")
        grid_tag  = soup.find(class_="authors-grid")
        abs_tag   = soup.find(class_="abstract-box")

        if title_tag: render_title(doc, text_content(title_tag))
        if sub_tag:   render_subtitle(doc, text_content(sub_tag))
        if grid_tag:  render_authors(doc, grid_tag)

        # Separator line before abstract
        hr1 = doc.add_paragraph()
        set_spacing(hr1, 0, 4, 1.0)
        p_bottom_border(hr1, color="CBD5E1", sz="4")

        if abs_tag:   render_abstract(doc, abs_tag)

        # Separator line before body
        hr2 = doc.add_paragraph()
        set_spacing(hr2, 4, 4, 1.0)
        p_bottom_border(hr2, color="000000", sz="8")

        # ── 2. Body Content ───────────────────────────────────────────────
        body_div = soup.find(class_="two-col-body")
        if body_div is None:
            print("  WARNING: .two-col-body not found, falling back to container")
            body_div = soup.find(class_="container")

        print("  Rendering body content (adaptive 2-col / full-width)…")
        fig_count = 0
        pending_cap = None

        for node in body_div.children:
            if isinstance(node, NavigableString):
                continue
            if not isinstance(node, Tag):
                continue

            cls = node.get("class", [])
            tag = node.name

            # ── Full-Width Figures ─────────────────────────────────────────
            if tag == "div" and "figure-container" in cls:
                fig_count += 1
                print(f"    → Figure {fig_count} (full-width: {FULL_WIDTH_IN} in)…")
                mgr.switch_to_columns(1)  # switch to full width
                render_figure(doc, node, fig_count, tmp_dir)

            # ── Full-Width Tables ──────────────────────────────────────────
            elif tag == "div" and "table-wrapper" in cls:
                mgr.switch_to_columns(1)  # switch to full width
                cap = node.find(class_="table-caption")
                tbl = node.find("table", class_="academic-table")
                if tbl:
                    render_table(doc, cap, tbl)

            elif tag == "div" and "table-caption" in cls:
                pending_cap = node

            elif tag == "table" and "academic-table" in cls:
                mgr.switch_to_columns(1)  # switch to full width
                render_table(doc, pending_cap, node)
                pending_cap = None

            # ── Regular Two-Column Content ─────────────────────────────────
            else:
                mgr.switch_to_columns(2)  # switch to two columns

                if tag == "h2" and "section-heading" in cls:
                    render_h2(doc, text_content(node))
                elif tag == "h3" and "sub-heading" in cls:
                    render_h3(doc, text_content(node))
                elif tag == "h4" and "subsub-heading" in cls:
                    render_h4(doc, text_content(node))
                elif tag == "p":
                    render_body_para(doc, node)
                elif tag == "ul" and "bullet-list" in cls:
                    render_bullet_list(doc, node)
                elif tag == "div" and "equation-card" in cls:
                    render_equation(doc, node)
                elif tag == "div" and "ref-list" in cls:
                    for ref in node.find_all(class_="ref-item"):
                        render_ref_item(doc, text_content(ref))
                elif tag == "div" and "ref-item" in cls:
                    render_ref_item(doc, text_content(node))

        # ── 3. Save Document ──────────────────────────────────────────────
        print(f"  Saving output to: {out_path}")
        doc.save(str(out_path))

    size_mb = out_path.stat().st_size / 1_048_576
    print(f"Done ✓ : {out_path} ({size_mb:.2f} MB, {fig_count} full-width figures embedded)")


def export_to_pdf_via_word(docx_path: Path, pdf_path: Path):
    """Optionally export DOCX to PDF using Word COM automation."""
    try:
        import win32com.client
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(str(docx_path.resolve()))
        doc.ExportAsFixedFormat(str(pdf_path.resolve()), 17) # 17 = wdExportFormatPDF
        doc.Close(False)
        word.Quit()
        pdf_mb = pdf_path.stat().st_size / 1_048_576
        print(f"PDF exported : {pdf_path} ({pdf_mb:.2f} MB)")
    except Exception as e:
        print(f"Note: Could not export to PDF via Word ({e}). Use export_pdf.py instead.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export IEEE paper to DOCX with full-width images")
    parser.add_argument("--html", default=str(HTML_IN), help="Input HTML path")
    parser.add_argument("--out",  default=str(BASE / "ieee_paper_revised.docx"), help="Output DOCX path")
    parser.add_argument("--pdf",  action="store_true", help="Also export to PDF via Word automation")
    args = parser.parse_args()

    out_docx = Path(args.out)
    convert(Path(args.html), out_docx)

    if args.pdf:
        out_pdf = out_docx.with_suffix(".pdf")
        export_to_pdf_via_word(out_docx, out_pdf)

