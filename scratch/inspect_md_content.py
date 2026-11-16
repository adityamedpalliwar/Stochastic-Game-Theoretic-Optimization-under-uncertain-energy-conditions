with open('build_master_integrated_report.py', 'r', encoding='utf-8') as f:
    text = f.read()

pos_md = text.find('md_content = f"""')
print('md_content pos:', pos_md)
if pos_md != -1:
    md_sub = text[pos_md:]
    for h in ["## IV.", "## VI.", "## IX."]:
        p = md_sub.find(h)
        print(f"Header {h} pos: {p}")
        if p != -1:
            print(md_sub[p:p+300])
            print("="*40)

