import json, sys
p = r'C:\Users\Prekzursil\p2-g1\command-center\WORK-UNIT-CATALOG.json'
with open(p, encoding='utf-8') as f:
    cat = json.load(f)
units = {u['id']: u for u in cat['work_units']}
items = {i['id']: i for i in cat.get('items', [])}
for uid in sys.argv[1:]:
    e = units.get(uid)
    print('='*20, uid, '='*20)
    if e:
        print(json.dumps(e, indent=1, ensure_ascii=False))
    else:
        print('MISSING FROM work_units; items hit:', json.dumps(items.get(uid), ensure_ascii=False))
