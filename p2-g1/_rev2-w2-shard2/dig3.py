import json
REPO = r'C:/Users/Prekzursil/p2-g1'
for uid in ['ADV-0124','ADV-0128','ARC-0012','ARC-0015','ARC-0021','ARC-0048']:
    d = json.load(open(REPO + '/command-center/receipts/' + uid + '.json', encoding='utf-8'))
    print(uid, {k: (len(v) if isinstance(v, (list, dict)) else v)
                for k, v in d.items()
                if k in ('state','sentinel','min_bytes_threshold','artifacts','evidence',
                         'tests','negative_controls','downstream_consumers',
                         'residual_unknowns','manifest_registration','extensions',
                         'failure','timestamps','retry','spec_anchor','schema_version')})
# ADV-0128 artifact spot read
d = json.load(open(REPO + '/command-center/adversarial/ADV-0128-offline-and-partition-degrade-loudly.json', encoding='utf-8'))
print()
print('ADV-0128 keys:', sorted(d.keys()))
for k in ('state','status','overall_verdict','headline_answer','answer'):
    if k in d: print(' ', k, '=', json.dumps(d[k])[:350])
tg = d.get('targets') or []
print(' targets:', [(t.get('id'), t.get('verdict')) for t in tg])
print(' negative_controls:', json.dumps(d.get('negative_controls'))[:400])
print(' named_probes:', [(p.get('id'), p.get('exit_code'), (p.get('command') or '')[-60:]) for p in d.get('named_probes', [])])
