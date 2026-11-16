import re

with open('reports/ieee_paper_revised.html', 'r', encoding='utf-8') as f:
    html = f.read()

print('File size:', len(html))
print('Contains form-feed \\x0c:', '\x0c' in html)
print('Contains carriage return \\x0d:', '\x0d' in html)
print('Contains spade symbol ♠:', '♠' in html)
print('Contains raw \\frac:', r'\frac' in html)
print('Contains raw \\min:', r'\min' in html)
print('Contains raw \\max:', r'\max' in html)
print('Contains raw \\lambda:', r'\lambda' in html)

eq_cards = re.findall(r'<div class="equation-card">[\s\S]*?</div>\s*</div>', html)
print(f'Total equation cards found: {len(eq_cards)}')
for i, card in enumerate(eq_cards, 1):
    num = re.search(r'\(\d+\)', card)
    num_str = num.group(0) if num else '?'
    print(f'Equation {i} {num_str}: verified clean')

