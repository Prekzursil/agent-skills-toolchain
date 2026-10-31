import json
ids = ['AUD-0044','AUD-0047','AUD-0053','AUD-0055','AUD-0057','AUD-0064','AUD-0066','AUD-0069','AUD-0071','AUD-0072','AUD-0075','AUD-0080']
data = json.load(open('command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
units = {u['id']: u for u in data.get('work_units', []) if isinstance(u, dict)}
for i in ids:
    u = units[i]
    print(i, 'owner_approval_required=', u.get('owner_approval_required'), '| title=', str(u.get('title'))[:100])
    if u.get('owner_approval_required'):
        print('   FULL-GATE-FIELD:', json.dumps(u.get('owner_approval_required'))[:300])
