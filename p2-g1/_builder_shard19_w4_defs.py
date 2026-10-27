import json
s = json.load(open('platform/schema/receipt.schema.json', encoding='utf-8'))
d = s['$defs']
for name in ['artifact','evidence_item','test_result','negative_control','reviewer','manifest_registration','downstream_consumer','residual_unknown','timestamps','retry','terminal_state','disposition','sentinel','unit_id','vendor_id']:
    x = d.get(name)
    if x is None:
        print('=== %s: ABSENT' % name); continue
    print('=== %s' % name)
    print(json.dumps(x, ensure_ascii=False)[:1800])
    print()
