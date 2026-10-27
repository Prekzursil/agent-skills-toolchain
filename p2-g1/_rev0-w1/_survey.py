import sys, os, json
sys.path.insert(0, r'C:/Users/Prekzursil/p2-g1/_rev0-w1')
from _util import load_json

REPO = r'C:/Users/Prekzursil/p2-g1'
UNITS = ["ADV-0006","ADV-0019","ADV-0027","ADV-0028","ADV-0029","ADV-0033",
         "ADV-0037","ADV-0038","ADV-0060","ADV-0096","ADV-0124","ADV-0127"]
cat = load_json(os.path.join(REPO, 'command-center/WORK-UNIT-CATALOG.json'))
by_id = {u['id']: u for u in cat['work_units']}
for uid in UNITS:
    u = by_id.get(uid)
    print('='*70)
    print(uid, '| in_catalog:', u is not None)
    if not u: continue
    op = u.get('output_path')
    print('output_path:', op)
    ap = os.path.join(REPO, op)
    print('artifact exists:', os.path.isfile(ap), '| size:', os.path.getsize(ap) if os.path.isfile(ap) else None)
    schema = u.get('output_schema')
    print('output_schema:', (json.dumps(schema)[:200] if schema else None))
    print('probes field type:', type(u.get('probes')).__name__, '| named_probes:', type(u.get('named_probes')).__name__)
    # probes dir
    pd = os.path.join(REPO, 'command-center/p2-wave/probes', uid)
    if os.path.isdir(pd):
        print('probes dir:', sorted(os.listdir(pd)))
    else:
        print('probes dir: MISSING')
    # receipt
    rp = os.path.join(REPO, 'command-center/receipts', uid + '.json')
    if os.path.isfile(rp):
        r = load_json(rp)
        rv = r.get('reviewer') or {}
        print('receipt state:', r.get('state'), '| reviewer:', {k: rv.get(k) for k in ('verdict','independent')})
    else:
        print('receipt: MISSING')
