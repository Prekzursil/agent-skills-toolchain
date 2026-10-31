import json
c = json.load(open(r'C:/Users/Prekzursil/p2-g1/command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
byid = {u['id']: u for u in c['work_units']}
for i in ['ADV-0124','ADV-0127','ADV-0128','ARC-0012','ARC-0015','ARC-0021','ARC-0048']:
    u = byid[i]
    print('===', i)
    print(' reviewer_requirement:', u.get('reviewer_requirement'))
    print(' owner_approval_required:', u.get('owner_approval_required'))
    print(' output_schema:', u.get('output_schema'))
    print(' tests_required:', json.dumps(u.get('tests_required'))[:400])
