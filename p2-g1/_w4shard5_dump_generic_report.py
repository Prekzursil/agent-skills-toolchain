import json

receipt_schema = json.load(open('C:/Users/Prekzursil/source/ast-integrate/platform/schema/receipt.schema.json', encoding='utf-8'))
defs = receipt_schema.get('$defs', {})
gr = defs.get('generic_report')
print('generic_report keys:', list(gr.keys()) if gr else None)
print(json.dumps(gr, indent=1)[:5500])
