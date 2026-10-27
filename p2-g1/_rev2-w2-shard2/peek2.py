import json, os
base = r'C:\Users\Prekzursil\p2-g1'
u = 'ADV-0124'
m = json.load(open(os.path.join(base, 'command-center', 'p2-wave', 'probes', u, 'UNIT-ARTIFACT-MANIFEST.json'), encoding='utf-8'))
print('PER-UNIT MANIFEST:')
print(json.dumps(m, indent=1)[:2500])
print()
d = json.load(open(os.path.join(base, 'command-center', 'receipts', u + '.json'), encoding='utf-8'))
print('REVIEWER:', json.dumps(d.get('reviewer'), indent=1))
print('FAILURE:', json.dumps(d.get('failure'), indent=1))
print('PRODUCED_BY:', json.dumps(d.get('produced_by'), indent=1))
print('MANIFEST_REG:', json.dumps(d.get('manifest_registration'), indent=1)[:600])
print('TIMESTAMPS:', json.dumps(d.get('timestamps'), indent=1))
print('N_EVIDENCE:', len(d.get('evidence', [])))
