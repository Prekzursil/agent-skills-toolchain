import json

base = json.load(open('C:/Users/Prekzursil/source/ast-integrate/platform/schema/artifact-class-profiles.schema.json', encoding='utf-8'))
d = base['$defs']['test-quality-census']
ref = d['allOf'][0]['$ref']
print('base ref:', ref)
path, frag = ref.split('#')
p = path[len('file:///'):]
doc = json.load(open(p, encoding='utf-8'))
node = doc
for part in [x for x in frag.split('/') if x]:
    node = node[part.replace('~1', '/').replace('~0', '~')]
print('resolved keys:', list(node.keys()))
brs = node.get('allOf', [])
print('branches:', len(brs))
for i, b in enumerate(brs):
    print('branch', i, 'keys:', list(b.keys()))
    if 'if' in b:
        print('  IF:', json.dumps(b['if'])[:300])
    props = b.get('properties', {})
    if 'report' in props:
        rep = props['report']
        print('  report.required:', rep.get('required'))
        print('  report has if:', 'if' in rep, '| has allOf:', 'allOf' in rep)
        inner = rep.get('allOf')
        if inner:
            for j, ib in enumerate(inner):
                print('   report.branch', j, 'keys:', list(ib.keys()))
                if 'if' in ib:
                    print('     IF:', json.dumps(ib['if'])[:300])
                rp = ib.get('then', {}).get('properties', {}).get('report', {})
                if rp:
                    print('     THEN report.required:', rp.get('required'))
