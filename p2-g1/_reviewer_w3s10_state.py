import json
import os

REPO = r'C:/Users/Prekzursil/p2-g1'
UNITS = ["IMP-0084", "IMP-0090", "IMP-0093", "IMP-0097", "IMP-0098", "IMP-0103",
         "IMP-0134", "IMP-0147", "IMP-0154", "IMP-0165", "IMP-0168", "IMP-0189"]

with open(os.path.join(REPO, 'command-center', 'WORK-UNIT-CATALOG.json'), encoding='utf-8') as f:
    cat = json.load(f)
byid = {}
for u in cat['work_units']:
    byid[u['id']] = u

for uid in UNITS:
    cu = byid.get(uid)
    print('=' * 20, uid)
    if not cu:
        print('  MISSING FROM CATALOG')
        continue
    print('  output_path :', cu.get('output_path'))
    print('  output_schema:', cu.get('output_schema'))
    print('  probes      :', json.dumps(cu.get('probes'))[:220])
    print('  deps        :', cu.get('dependencies'))
    print('  owner_gate  :', cu.get('owner_approval_required'))
    # artifact
    op = os.path.join(REPO, cu.get('output_path', '').replace('/', os.sep))
    if os.path.exists(op):
        sz = os.path.getsize(op)
        print('  artifact    : EXISTS size=%d' % sz)
    else:
        print('  artifact    : MISSING at', op)
    # manifest
    mp = os.path.join(REPO, 'command-center', 'p2-wave', 'probes', uid, 'UNIT-ARTIFACT-MANIFEST.json')
    if os.path.exists(mp):
        print('  manifest    : EXISTS size=%d' % os.path.getsize(mp))
    else:
        print('  manifest    : MISSING at', mp)
    # receipt
    rp = os.path.join(REPO, 'command-center', 'receipts', uid + '.json')
    try:
        r = json.load(open(rp, encoding='utf-8'))
        rev = r.get('reviewer') or {}
        fail = r.get('failure') or {}
        print('  receipt     : state=%s verdict=%s indep=%s reviewer=%s fail=%s' % (
            r.get('state'), rev.get('verdict'), rev.get('independent'),
            rev.get('reviewer_id'), fail.get('classification')))
    except FileNotFoundError:
        print('  receipt     : MISSING')
    except Exception as e:
        print('  receipt     : UNPARSEABLE', e)
