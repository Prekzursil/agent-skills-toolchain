import json, os, sys
ROOT = os.path.expanduser('~/p2-g1')
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, 'platform', 'lib'))
import schema_resolver

def jl(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)

cat = jl('command-center/WORK-UNIT-CATALOG.json')
byid = {u['id']: u for u in cat['work_units'] if isinstance(u, dict) and 'id' in u}

# Controls: prior-closed units NOT in shard 17, drawn from the same control set the
# shard-2 review used plus same-class test-receipt units that should conform.
CONTROLS = ['ADV-0005','ADV-0006','ADV-0010','ADV-0014','IMP-0095','ARC-0066','AUD-0020',
            'ARC-0022','ARC-0036','ARC-0050','ARC-0057','ARC-0028','ARC-0049','ADV-0121','ADV-0122']
print('CONTROL SAMPLE (instrument both-states proof):')
for uid in CONTROLS:
    e = byid.get(uid)
    if not e:
        print(uid, 'not-in-catalog')
        continue
    op, osch = e.get('output_path'), e.get('output_schema')
    if not op or not os.path.isfile(op.replace('/', os.sep)):
        print(uid, 'artifact-missing')
        continue
    try:
        art = jl(op)
    except Exception as ex:
        print(uid, 'unparseable', str(ex)[:80])
        continue
    try:
        errs = schema_resolver.validate_artifact(art, osch)
        print(uid, 'violations:', len(errs), '|', (errs[0][:90] if errs else 'CLEAN'))
    except Exception as ex:
        print(uid, 'resolver-error', str(ex)[:120])

# Same-class conforming-peer hunt: recent SUCCESS test-receipt + fault-injection
# units outside shard 17 — do ANY validate clean on my instrument?
print()
print('SAME-CLASS PEERS (receipts updated after 2026-10-24T08:49, not in my shard):')
import datetime
peers = []
for u in cat['work_units']:
    if not isinstance(u, dict):
        continue
    uid = u.get('id')
    if not uid or uid.startswith('TST-00'):
        continue
    osch = u.get('output_schema') or ''
    if any(k in osch for k in ('test-receipt', 'benchmark-receipt', 'fault-injection-receipt')):
        p = os.path.join(ROOT, (u.get('output_path') or '').replace('/', os.sep))
        if p and os.path.isfile(p):
            peers.append(uid)
checked = 0
clean = 0
for uid in sorted(set(peers)):
    e = byid[uid]
    try:
        art = jl(e['output_path'])
        errs = schema_resolver.validate_artifact(art, e['output_schema'])
        checked += 1
        if not errs:
            clean += 1
            print(uid, 'CLEAN')
    except Exception:
        pass
print('same-class peers checked:', checked, '| clean:', clean)
