import json
from pathlib import Path

REPO = Path(r'C:/Users/Prekzursil/p2-g1')
MINE = ["AUD-0044", "AUD-0047", "AUD-0053", "AUD-0055", "AUD-0057",
        "AUD-0064", "AUD-0066", "AUD-0069", "AUD-0071", "AUD-0072",
        "AUD-0075", "AUD-0080"]
cat = json.loads((REPO / 'command-center/WORK-UNIT-CATALOG.json').read_text(encoding='utf-8'))
byid = {e['id']: e for e in cat['work_units']}
out = {}
for uid in MINE:
    e = byid[uid]
    rp = REPO / f'command-center/receipts/{uid}.json'
    rec = json.loads(rp.read_text(encoding='utf-8'))
    rev = rec.get('reviewer') or {}
    out[uid] = {
        'output_path': e.get('output_path'),
        'output_schema': e.get('output_schema'),
        'probes': e.get('probes'),
        'deps': e.get('dependencies'),
        'receipt_state': rec.get('state'),
        'reviewer_verdict': rev.get('verdict'),
        'independent': rev.get('independent'),
        'reviewer_id': rev.get('reviewer_id'),
        'receipt_keys': sorted(rec.keys()),
        'failure': rec.get('failure'),
    }
print(json.dumps(out, indent=1))
