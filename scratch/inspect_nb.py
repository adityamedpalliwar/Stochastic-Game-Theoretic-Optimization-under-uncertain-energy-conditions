import json

with open('notebooks/05_five_house_game.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

for idx in [5, 6, 7, 8, 9, 10, 11, 12, 13, 23]:
    cell = nb['cells'][idx]
    print(f'=== CELL {idx} [{cell["cell_type"]}] ===')
    source = ''.join(cell['source'])
    print(source[:1500])
    if 'outputs' in cell:
        for out in cell['outputs']:
            if 'text' in out:
                print('--- OUTPUT ---')
                print(''.join(out['text'])[:1000])

