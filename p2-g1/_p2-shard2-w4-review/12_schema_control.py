import json, os, sys
ROOT = os.path.expanduser('~/p2-g1')
os.chdir(ROOT)
def jl(p):
    with open(p, encoding='utf-8') as f: return json.load(f)
sys.path.insert(0, os.path.join(ROOT,'platform','lib'))
import schema_resolver

# Control sample: prior-closed units NOT in my shard
CONTROL = ['ADV-0005','ADV-0006','ADV-0010','ADV-0014','IMP-0095','ARC-0066','AUD-0020']
cat = jl('command-center/WORK-UNIT-CATALOG.json')
byid = {u['id']: u for u in cat['work_units'] if 'id' in u}
for uid in CONTROL:
    e = byid.get(uid)
    if not e:
        print(uid, 'not in catalog'); continue
    op, osch = e.get('output_path'), e.get('output_schema')
    if not op or not os.path.exists(op):
        print(uid, 'artifact missing'); continue
    try:
        art = jl(op)
    except Exception as ex:
        print(uid, 'unparseable', str(ex)[:80]); continue
    try:
        errs = schema_resolver.validate_artifact(art, osch)
        print(uid, 'schema_violations:', len(errs), '| sample:', (errs[0][:100] if errs else ''))
    except Exception as ex:
        print(uid, 'resolver error', str(ex)[:120])

print()
print('==== full violation list for ARC-0021 (only 3) ====')
art = jl(byid['ARC-0021']['output_path'])
for e in schema_resolver.validate_artifact(art, byid['ARC-0021']['output_schema']):
    print(' -', str(e)[:300])
print()
print('==== full violation list for ARC-0001 (first 8) ====')
art = jl(byid['ARC-0001']['output_path'])
for e in schema_resolver.validate_artifact(art, byid['ARC-0001']['output_schema'])[:8]:
    print(' -', str(e)[:200])
