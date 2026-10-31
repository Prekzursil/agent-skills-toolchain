import json, os, sys
ROOT = os.path.expanduser('~/p2-g1')
os.chdir(ROOT)
def jl(p):
    with open(p, encoding='utf-8') as f: return json.load(f)
sys.path.insert(0, os.path.join(ROOT,'platform','lib'))
import schema_resolver

cat = jl('command-center/WORK-UNIT-CATALOG.json')
byid = {u['id']: u for u in cat['work_units'] if 'id' in u}

MINE = ['ADV-0127','ADV-0128','ARC-0001','ARC-0012','ARC-0013','ARC-0015','ARC-0019','ARC-0020','ARC-0021','ARC-0047','ARC-0048','ARC-0054']

def shim_class(osch):
    try:
        s = jl(osch)
        return s.get('x-artifact-class')
    except Exception:
        return None

# map: class -> list of (uid, violations) for a broad sample
import collections
cls_hits = collections.defaultdict(list)
sample = []
for u in cat['work_units']:
    uid = u.get('id')
    op, osch = u.get('output_path'), u.get('output_schema')
    if not op or not osch or not os.path.exists(op):
        continue
    c = shim_class(osch)
    if c in ('decision-record','architecture-review','test-plan','migration-plan','fault-injection-run'):
        sample.append((uid, c, op, osch))

print('units sharing my classes:', len(sample))
# measure a diverse slice: my 12 + up to 40 others per class
mine_set = set(MINE)
others = [s for s in sample if s[0] not in mine_set]
print('others in same classes:', len(others))
import random
random.seed(7)
others_sample = random.sample(others, min(40, len(others)))
for uid, c, op, osch in others_sample:
    try:
        art = jl(op)
        errs = schema_resolver.validate_artifact(art, osch)
        cls_hits[c].append((uid, len(errs)))
    except Exception as ex:
        cls_hits[c].append((uid, 'ERR:'+str(ex)[:60]))
for c, hits in cls_hits.items():
    zero = [h for h in hits if h[1] == 0]
    nz = [h for h in hits if h[1] != 0]
    print(f'class {c}: measured={len(hits)} zero_violations={len(zero)} nonzero={len(nz)}')
    for uid, n in nz[:6]:
        print('   nonzero:', uid, n)
    for uid, n in zero[:4]:
        print('   zero    :', uid, n)
