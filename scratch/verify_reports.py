import docx
from pathlib import Path

# Verify Word Document
doc_path = Path("reports/Project_Report_Final.docx")
doc = docx.Document(doc_path)

words = sum(len(p.text.split()) for p in doc.paragraphs)
for t in doc.tables:
    for row in t.rows:
        words += sum(len(cell.text.split()) for cell in row.cells)

print("=== DOCX AUDIT ===")
print(f"Paragraphs: {len(doc.paragraphs)}")
print(f"Tables: {len(doc.tables)}")
print(f"Total Words (incl tables): {words}")

# Check for any accidental raw LaTeX slashes in docx paragraphs
latex_paras = [p.text for p in doc.paragraphs if "\\frac" in p.text or "\\cdot" in p.text]
print(f"Paragraphs with raw LaTeX backslashes: {len(latex_paras)}")

# Print table titles found in DOCX
for i, t in enumerate(doc.tables):
    print(f"Table {i+1}: {len(t.rows)} rows x {len(t.columns)} cols")

# Verify HTML Document
html_path = Path("reports/ieee_paper_revised.html")
html_text = html_path.read_text(encoding="utf-8")
print("\n=== HTML AUDIT ===")
print(f"HTML Size: {len(html_text) / (1024*1024):.2f} MB")
print(f"Has Table V: {'TABLE V:' in html_text}")
print(f"Has Section IV-B: {'Technical Justification for Battery Sizing' in html_text}")
print(f"Has Section VI-B: {'Technical Justification for the 0.15' in html_text}")
print(f"Has Section IX-E: {'Hourly Player Profit Dynamics' in html_text}")
print(f"Corrupted LaTeX tags count: {html_text.count('♠rac') + html_text.count('ight')}")

# Verify Markdown Document
md_path = Path("reports/ieee_paper_revised.md")
md_text = md_path.read_text(encoding="utf-8")
print("\n=== MD AUDIT ===")
print(f"MD Size: {len(md_text) / 1024:.2f} KB")
print(f"Has Table V: {'TABLE V:' in md_text}")
print(f"Has Section IV-B: {'Technical Justification for Battery Sizing' in md_text}")
print(f"Has Section VI-B: {'Technical Justification for the 0.15' in md_text}")
print(f"Has Section IX-E: {'Hourly Player Profit Dynamics' in md_text}")

