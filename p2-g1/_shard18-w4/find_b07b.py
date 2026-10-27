import json
from pathlib import Path
REPO = Path("C:/Users/Prekzursil/p2-g1")
cat = json.load(open(REPO/'command-center'/'WORK-UNIT-CATALOG.json', encoding='utf-8'))
ids = set()
for u in cat['work_units']:
    if isinstance(u, dict) and isinstance(u.get('id'), str):
        ids.add(u['id'])
print('B-prefixed ids:', sorted(i for i in ids if i.startswith('B')))
for u in cat.get('items', []):
    if isinstance(u, dict) and str(u.get('id','')).startswith('B0'):
        print('ITEM:', json.dumps(u, ensure_ascii=False)[:400])
