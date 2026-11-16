import re

with open('build_expanded_html_and_md.py', 'r', encoding='utf-8') as f:
    text = f.read()

matches = re.findall(r'<div class="equation">.*?</div>', text, re.DOTALL)
print(f'Found equation blocks: {len(matches)}')
for i, m in enumerate(matches, 1):
    print(f'=== Eq {i} ===')
    print(m)

with open('reports/ieee_paper_revised.html', 'r', encoding='utf-8') as f:
    c = f.read()

m = re.findall(r'<div class="equation">.*?</div>', c, re.DOTALL)
print('In ieee_paper_revised.html:')
for i, eq in enumerate(m, 1):
    print(f'Eq {i}: {repr(eq[20:70])}')
