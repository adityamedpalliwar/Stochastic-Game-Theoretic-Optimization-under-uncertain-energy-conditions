import docx
import re
from pathlib import Path

# 1. Verify DOCX
doc = docx.Document('reports/Project_Report_Final.docx')
print('=== DOCX Verification ===')
print('Paragraphs:', len(doc.paragraphs))
print('Tables:', len(doc.tables))
images = [rel.target_ref for rel in doc.part.rels.values() if 'image' in rel.target_ref]
print('Images embedded:', len(images))
bad_p = [p.text for p in doc.paragraphs if '\\\\' in p.text or '\\max' in p.text or '\\frac' in p.text]
print('Bad raw LaTeX paragraphs:', len(bad_p))

# 2. Verify HTML
html = Path('reports/ieee_paper_revised.html').read_text(encoding='utf-8')
print('\n=== HTML Verification ===')
print('Size (bytes):', len(html))
print('Has \\x0c (formfeed):', '\x0c' in html)
print('Has \\x0d (carriage return):', '\x0d' in html)
print('Has spade symbol ♠:', '♠' in html)
print('Has raw \\frac:', r'\frac' in html)
eq_cards = re.findall(r'<div class="equation-card">[\s\S]*?</div>\s*</div>', html)
print('Equation cards found:', len(eq_cards))
print('Base64 images embedded:', len(re.findall(r'data:image/png;base64,', html)))

# 3. Verify Markdown
md = Path('reports/ieee_paper_revised.md').read_text(encoding='utf-8')
print('\n=== Markdown Verification ===')
print('Size (bytes):', len(md))
print('Math blocks ($$...$$):', len(re.findall(r'\$\$[\s\S]*?\$\$', md)))

