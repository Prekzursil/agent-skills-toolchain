import sys, json, collections
sys.path.insert(0, 'C:/Users/Prekzursil/p2-g1/platform/lib')
from schema_resolver import validate_artifact
REPO = 'C:/Users/Prekzursil/p2-g1/'
doc = json.load(open(REPO + 'command-center/audit/AUD-0095-freeze-inventory.json', encoding='utf-8'))
doc['timestamps'].pop('repaired_at', None)
stub = [{'consumer': 'probe-validation-stub', 'artifact_path': 'n/a', 'executed': True,
         'read_ok': True, 'exit_code': 0,
         'probe': {'role': 'verifier', 'method': 'other', 'command': 'validation-stub',
                   'raw_output': 'stub', 'fingerprint': 'stub', 'exit_code': 0}}]
for cand in ['SUCCESS', 'DELIVERED', 'COMPLETE', 'BUILT-AWAITING-INDEPENDENT-REVIEW',
             'BUILT', 'PENDING-REVIEW', 'SUBMITTED', 'OPEN']:
    errs = validate_artifact({**doc, 'state': cand}, 'command-center/schema/audit-inventory.schema.json')
    print(cand, '->', 'SCHEMA-OK' if not errs else errs[:2])
# estate vocabulary
cnt = collections.Counter()
import glob
for f in glob.glob(REPO + 'command-center/receipts/*.json')[:400]:
    try:
        d = json.load(open(f, encoding='utf-8'))
        if isinstance(d, dict) and d.get('state'):
            cnt[str(d.get('state'))] += 1
    except Exception:
        pass
print('estate state vocabulary (sample):', dict(cnt))
