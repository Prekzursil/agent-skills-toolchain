import json
import hashlib
import os
import sys

REPO = r'C:/Users/Prekzursil/p2-g1'
UNITS = ["IMP-0084", "IMP-0090", "IMP-0093", "IMP-0097", "IMP-0098", "IMP-0103",
         "IMP-0134", "IMP-0147", "IMP-0154", "IMP-0165", "IMP-0168", "IMP-0189"]

sys.path.insert(0, os.path.join(REPO, 'platform', 'lib'))
os.environ.setdefault('AST_INTEGRATE_ROOT', REPO)

import json as _json
with open(os.path.join(REPO, 'command-center', 'WORK-UNIT-CATALOG.json'), encoding='utf-8') as f:
    cat = _json.load(f)
byid = {u['id']: u for u in cat['work_units']}

def norm_sha(path):
    b = open(path, 'rb').read()
    n = b.replace(b'\r\n', b'\n')
    return hashlib.sha256(n).hexdigest()

print('=== A. SHA256 vs manifest ===')
for uid in UNITS:
    art = os.path.join(REPO, byid[uid]['output_path'].replace('/', os.sep))
    live = norm_sha(art)
    raw = hashlib.sha256(open(art, 'rb').read()).hexdigest()
    mp = os.path.join(REPO, 'command-center', 'p2-wave', 'probes', uid, 'UNIT-ARTIFACT-MANIFEST.json')
    m = json.load(open(mp, encoding='utf-8'))
    rows = m if isinstance(m, list) else m.get('artifacts') or m.get('rows') or m.get('manifest') or []
    hit = None
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        pth = str(row.get('path') or row.get('output_path') or '')
        if pth.replace(chr(92), '/').endswith(byid[uid]['output_path'].split('/')[-1]) or pth.endswith(byid[uid]['output_path']):
            hit = row
            break
    if hit is None and isinstance(rows, list):
        hit = next((r for r in rows if isinstance(r, dict) and r.get('sha256') in (live, raw)), None)
    ok = bool(hit) and hit.get('sha256') in (live, raw)
    print('%s manifest_row=%s sha_match=%s (norm=%s raw=%s row=%s)' % (
        uid, 'yes' if hit else 'NO', ok, live[:12], raw[:12], (hit or {}).get('sha256', '-')[:12]))

print()
print('=== B. output_schema validation (repo resolver) ===')
from schema_resolver import validate_artifact
from receipt_schema_gate import parse_schema_ref
for uid in UNITS:
    art = os.path.join(REPO, byid[uid]['output_path'].replace('/', os.sep))
    inst = json.load(open(art, encoding='utf-8'))
    decl = byid[uid].get('output_schema')
    errs = validate_artifact(inst, decl)
    print('%s resolver_errors=%d' % (uid, len(errs)), errs[:4])
