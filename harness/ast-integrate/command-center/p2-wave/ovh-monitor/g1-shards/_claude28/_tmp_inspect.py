import json

import jsonschema

REPO = r'C:\Users\Prekzursil\source\ast-integrate'
schema = json.load(open(REPO + r'\command-center\schema\ecosystem-teardown.schema.json', encoding='utf-8'))
doc = json.load(open(REPO + r'\command-center\research\teardown\RES-0178-teardown-skill-and-mcp-distribution-hubs.json', encoding='utf-8'))

v = jsonschema.Draft202012Validator(schema)
errs = list(v.iter_errors(doc))
print('n errors:', len(errs))
for e in errs[:10]:
    print('json_path:', e.json_path)
    print('schema_path:', list(e.absolute_schema_path))
    # find the if-condition comment near this rule
    print('message:', e.message[:150])
    ctx = e.context or []
    for c in ctx[:3]:
        print('   ctx:', c.json_path, c.message[:120])
    print()
