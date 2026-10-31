import json, os
os.chdir(os.path.expanduser('~/p2-g1'))
cat = json.load(open('command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
byid = {u['id']: u for u in cat['work_units']}
e = byid['IMP-0002']
print(json.dumps(e, indent=1, ensure_ascii=False)[:3500])
