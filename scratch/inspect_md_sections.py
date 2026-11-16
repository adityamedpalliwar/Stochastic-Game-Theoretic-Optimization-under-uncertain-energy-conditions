with open('build_master_integrated_report.py', 'r', encoding='utf-8') as f:
    text = f.read()

pos_md = text.find('md_content = f"""')
md_sub = text[pos_md:]

# Let's see Section IV in md_sub
p4 = md_sub.find("## IV.")
p5 = md_sub.find("## V.")
print("=== MD SECTION IV ===")
print(md_sub[p4:p5])

# Let's see Section VI in md_sub
p6 = md_sub.find("## VI.")
p7 = md_sub.find("## VII.")
print("=== MD SECTION VI ===")
print(md_sub[p6:p7])

# Let's see Section IX in md_sub
p9 = md_sub.find("## IX.")
p10 = md_sub.find("## X.")
print("=== MD SECTION IX ===")
print(md_sub[p9:p10])

