import json, hashlib, glob, re, os
from pathlib import Path
R = Path(r'C:\Users\Prekzursil\p2-g1')

def lfsha(p):
    raw = Path(p).read_bytes().replace(b'\r\n', b'\n')
    return hashlib.sha256(raw).hexdigest(), len(raw)

# 1. ADV-0005 manifest rows
m = json.load(open(R/'command-center/p2-wave/probes/ADV-0005/UNIT-ARTIFACT-MANIFEST.json', encoding='utf-8'))
print('ADV-0005 manifest rows:')
for a in m['artifacts']:
    print('  ', a.get('path'), a.get('role'), str(a.get('sha256'))[:12], a.get('bytes'))
live, nb = lfsha(R/'command-center/receipts/ADV-0005.json')
print('ADV-0005 receipt live:', live[:12], nb)

# 2. wave3-closed receipts + sha-vs-manifest status
pat = re.compile(r'w3[-_ ]?shard|w3s\d+|wave-?3', re.I)
hits = []
for p in glob.glob(str(R/'command-center/receipts/*.json')):
    try:
        d = json.load(open(p, encoding='utf-8'))
    except Exception:
        continue
    rid = str((d.get('reviewer') or {}).get('reviewer_id', ''))
    if pat.search(rid):
        hits.append((p, rid))
print()
print('wave3-reviewer-closed receipts:', len(hits))
for p, rid in hits[:10]:
    print('  ', os.path.basename(p), '|', rid[:70])
