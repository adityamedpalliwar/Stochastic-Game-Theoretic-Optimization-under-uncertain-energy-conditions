import docx
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = docx.Document()

def add_math_equation(doc, runs_spec, eq_num):
    """
    runs_spec: list of tuples (text, is_subscript, is_superscript, is_italic, is_bold)
    eq_num: int or str (e.g. '1')
    """
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.left_indent = Inches(0.4)
    p.paragraph_format.right_indent = Inches(0.2)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    
    # Add math runs
    for item in runs_spec:
        text = item[0]
        sub = item[1] if len(item) > 1 else False
        sup = item[2] if len(item) > 2 else False
        italic = item[3] if len(item) > 3 else False
        bold = item[4] if len(item) > 4 else False
        
        r = p.add_run(text)
        r.font.name = 'Cambria Math'
        r.font.size = Pt(8.5 if (sub or sup) else 10.5)
        r.font.subscript = sub
        r.font.superscript = sup
        r.font.italic = italic
        r.font.bold = bold
        r.font.color.rgb = RGBColor(15, 23, 42)
        
    # Add tab / spacing and equation number flush right
    # In Word, we can add spacing before the equation number
    r_sp = p.add_run(" " * 12)
    r_num = p.add_run(f"({eq_num})")
    r_num.bold = True
    r_num.font.name = 'Times New Roman'
    r_num.font.size = Pt(10)
    r_num.font.color.rgb = RGBColor(71, 85, 105)
    return p

# Test Eq 1
add_math_equation(doc, [
    ("S", False, False, True),
    ("i,t", True, False, True),
    ("raw", False, True, False),
    (" = max(0, ", False, False, False),
    ("G", False, False, True),
    ("i,t", True, False, True),
    (" − ", False, False, False),
    ("D", False, False, True),
    ("i,t", True, False, True),
    ("),       ", False, False, False),
    ("D", False, False, True),
    ("i,t", True, False, True),
    ("raw", False, True, False),
    (" = max(0, ", False, False, False),
    ("D", False, False, True),
    ("i,t", True, False, True),
    (" − ", False, False, False),
    ("G", False, False, True),
    ("i,t", True, False, True),
    (")", False, False, False)
], "1")

doc.save("scratch/test_math_formatted.docx")
print("Saved scratch/test_math_formatted.docx")

