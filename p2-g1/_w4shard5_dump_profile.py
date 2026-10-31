import json

base = json.load(open('C:/Users/Prekzursil/source/ast-integrate/platform/schema/artifact-class-profiles.schema.json', encoding='utf-8'))
defs = base.get('$defs', {})
print('artifact-class-profiles $defs:', sorted(defs.keys()))
d = defs.get('blindspot-register')
print('blindspot-register keys:', list(d.keys()) if d else None)
if d:
    brs = d.get('allOf', [])
    for i, b in enumerate(brs):
        print(' allOf[%d] keys:' % i, list(b.keys()))
        if '$ref' in b:
            print('   ref:', b['$ref'])
        req = b.get('required')
        if req:
            print('   required:', req)
        props = b.get('properties', {})
        for k in ('state', 'sentinel', 'manifest_registration', 'tests', 'defects', 'downstream_consumers', 'report'):
            if k in props:
                p = props[k]
                print('   prop %s:' % k, json.dumps(p)[:260])
