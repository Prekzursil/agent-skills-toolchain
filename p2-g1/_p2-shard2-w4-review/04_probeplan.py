import json, os
os.chdir(os.path.expanduser('~/p2-g1'))
MINE = ['ADV-0127','ADV-0128','ARC-0001','ARC-0012','ARC-0013','ARC-0015','ARC-0019','ARC-0020','ARC-0021','ARC-0047','ARC-0048','ARC-0054']
def jl(p):
    with open(p, encoding='utf-8') as f: return json.load(f)
plan = {}
for uid in MINE:
    rp = f'command-center/receipts/{uid}.json'
    rec = jl(rp)
    man = jl(f'command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json')
    plan[uid] = {
        'receipt_named_probes': rec.get('named_probes'),
        'manifest': man,
        'receipt_state': rec.get('state'),
        'reviewer_checks': (rec.get('reviewer') or {}).get('checks'),
        'artifact_sha_in_receipt': (rec.get('artifacts') or [{}])[0].get('sha256'),
        'artifact_bytes_in_receipt': (rec.get('artifacts') or [{}])[0].get('bytes'),
    }
json.dump(plan, open('_p2-shard2-w4-review/probeplan.json','w',encoding='utf-8'), indent=1)
for uid in MINE:
    p = plan[uid]
    print('='*12, uid, '| receipt state:', p['receipt_state'])
    print(' named_probes:', json.dumps(p['receipt_named_probes'])[:600])
    m = p['manifest']
    if isinstance(m, dict):
        print(' manifest keys:', list(m.keys()))
        rows = m.get('artifacts') or m.get('rows') or m.get('entries')
        print(' manifest rows:', json.dumps(rows)[:500] if rows else json.dumps(m)[:500])
    print(' reviewer checks:', json.dumps(p['reviewer_checks']))
