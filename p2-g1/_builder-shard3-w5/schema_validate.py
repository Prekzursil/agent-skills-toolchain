import json
from jsonschema import Draft202012Validator
ids = ['AUD-0044','AUD-0047','AUD-0053','AUD-0055','AUD-0057','AUD-0064','AUD-0066','AUD-0069','AUD-0071','AUD-0072','AUD-0075','AUD-0080']
data = json.load(open('command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
units = {u['id']: u for u in data.get('work_units', []) if isinstance(u, dict)}
for i in ids:
    u = units[i]
    schema_path = u['output_schema']
    try:
        schema = json.load(open(schema_path, encoding='utf-8'))
        doc = json.load(open(u['output_path'], encoding='utf-8'))
        Draft202012Validator.check_schema(schema)
        v = Draft202012Validator(schema)
        errs = sorted(v.iter_errors(doc), key=lambda e: list(e.path))
        if errs:
            print(i, 'SCHEMA-ERRORS', len(errs))
            for e in errs[:3]:
                print('   ', list(e.path)[:6], str(e.message)[:200])
        else:
            print(i, 'SCHEMA-OK')
    except Exception as e:
        print(i, 'VALIDATION-FAILED', type(e).__name__, str(e)[:150])
