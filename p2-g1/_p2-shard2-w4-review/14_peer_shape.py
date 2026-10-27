import json, os, sys, datetime
ROOT = os.path.expanduser('~/p2-g1')
os.chdir(ROOT)
def jl(p):
    with open(p, encoding='utf-8') as f: return json.load(f)
sys.path.insert(0, os.path.join(ROOT,'platform','lib'))
import schema_resolver

cat = jl('command-center/WORK-UNIT-CATALOG.json')
byid = {u['id']: u for u in cat['work_units'] if 'id' in u}
MINE = ['ADV-0127','ADV-0128','ARC-0001','ARC-0012','ARC-0013','ARC-0015','ARC-0019','ARC-0020','ARC-0021','ARC-0047','ARC-0048','ARC-0054']

# 1. conforming peer shape
for peer in ('ARC-0066','ARC-0006','ADV-0121'):
    e = byid[peer]
    art = jl(e['output_path'])
    s = jl(e['output_schema'])
    print(peer, '| class:', s.get('x-artifact-class'), '| top keys:', sorted(art.keys())[:18] if isinstance(art,dict) else type(art).__name__)
    rp = f'command-center/receipts/{peer}.json'
    if os.path.exists(rp):
        rec = jl(rp)
        rev = rec.get('reviewer') or {}
        print('   receipt state:', rec.get('state'), '| reviewer verdict:', rev.get('verdict'), '| reviewed_at:', rev.get('reviewed_at'))

print()
# 2. my units receipt closure times
for uid in MINE:
    rec = jl(f'command-center/receipts/{uid}.json')
    rev = rec.get('reviewer') or {}
    print(uid, '| state:', rec.get('state'), '| verdict:', rev.get('verdict'), '| independent:', rev.get('independent'), '| reviewed_at:', rev.get('reviewed_at'))

print()
# 3. substrate file mtimes vs closure times
for f in ('platform/schema/artifact-class-profiles.schema.json','platform/schema/receipt.schema.json','platform/schema/ARTIFACT-CLASS-REGISTRY.json'):
    st = os.stat(f)
    print(f, 'mtime:', datetime.datetime.fromtimestamp(st.st_mtime).isoformat(timespec='seconds'), 'size:', st.st_size)

print()
# 4. per-unit violation counts + top 3 samples (compact, for the report)
viol = {}
for uid in MINE:
    e = byid[uid]
    art = jl(e['output_path'])
    errs = schema_resolver.validate_artifact(art, e['output_schema'])
    viol[uid] = {'count': len(errs), 'sample': [str(x)[:140] for x in errs[:3]]}
json.dump(viol, open('_p2-shard2-w4-review/violations.json','w',encoding='utf-8'), indent=1)
for uid, v in viol.items():
    print(uid, 'violations:', v['count'])
