with open('build_master_integrated_report.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
print(f'Total lines: {len(lines)}')

for i, l in enumerate(lines):
    if 'add_h1("IV. PHYSICAL BATTERY' in l:
        print(f'DOCX Section IV: line {i+1}')
    elif 'add_h1("VI. MONTE CARLO' in l:
        print(f'DOCX Section VI: line {i+1}')
    elif 'add_h1("IX. COMMUNITY SIMULATION' in l:
        print(f'DOCX Section IX: line {i+1}')
    elif 'section-heading">IV. PHYSICAL' in l:
        print(f'HTML Section IV: line {i+1}')
    elif 'section-heading">VI. MONTE' in l:
        print(f'HTML Section VI: line {i+1}')
    elif 'section-heading">IX. COMMUNITY' in l:
        print(f'HTML Section IX: line {i+1}')
    elif '## IV. PHYSICAL BATTERY' in l:
        print(f'MD Section IV: line {i+1}')
    elif '## VI. MONTE CARLO' in l:
        print(f'MD Section VI: line {i+1}')
    elif '## IX. COMMUNITY SIMULATION' in l:
        print(f'MD Section IX: line {i+1}')
    elif 'add_h1("X. CONCLUSION' in l:
        print(f'DOCX Section X: line {i+1}')
    elif 'section-heading">X. CONCLUSION' in l:
        print(f'HTML Section X: line {i+1}')
    elif '## X. CONCLUSION' in l:
        print(f'MD Section X: line {i+1}')

