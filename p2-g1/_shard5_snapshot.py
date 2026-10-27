import hashlib, json, sys
from pathlib import Path
REPO = Path('.')
def nsha(p):
    return hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
ids = ['CNF-0173','CNF-0177','CNF-0178','CNF-0180','CNF-0188','CNL-0076','IMP-0003','IMP-0013','IMP-0014','IMP-0018','IMP-0020','IMP-0022']
snap = {}
for uid in ids:
    snap[uid] = nsha(REPO/f'command-center/receipts/{uid}.json')
Path('_shard5_presnap.json').write_text(json.dumps(snap, indent=1))
print('snapshot written:', len(snap), 'receipts')
