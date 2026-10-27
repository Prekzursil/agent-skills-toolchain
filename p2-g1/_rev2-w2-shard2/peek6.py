import json
c = json.load(open(r'C:/Users/Prekzursil/p2-g1/command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
byid = {u['id']: u for u in c['work_units']}
for i in ['ADV-0124','ADV-0127','ADV-0128','ARC-0001','ARC-0012','ARC-0013','ARC-0015','ARC-0019','ARC-0020','ARC-0021','ARC-0047','ARC-0048']:
    u = byid[i]
    print('===', i)
    print(' SENTINEL:', u.get('completion_sentinel'))
