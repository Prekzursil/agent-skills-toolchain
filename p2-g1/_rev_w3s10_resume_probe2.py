import json, hashlib, os
from pathlib import Path
R = Path(r'C:\Users\Prekzursil\p2-g1')

def lfsha(p):
    raw = Path(p).read_bytes().replace(b'\r\n', b'\n')
    return hashlib.sha256(raw).hexdigest(), len(raw)

# w3s4-closed AUD units and w3-shard1-closed ADV units: receipt sha vs manifest primary row
for uid in ['AUD-0044','AUD-0047','ADV-0038']:
    rp = R/('command-center/receipts/%s.json' % uid)
    live, nb = lfsha(rp)
    mp = R/('command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json' % uid)
    m = json.load(open(mp, encoding='utf-8'))
    rows = [a for a in m['artifacts'] if str(a.get('path','')).endswith('receipts/%s.json' % uid)]
    d = json.load(open(rp, encoding='utf-8'))
    rev = d.get('reviewer') or {}
    print(uid, '| reviewer:', rev.get('reviewer_id'))
    print('   live:', live[:16], nb, 'bytes | manifest rows for receipt:', len(rows))
    for r in rows:
        print('   row  :', str(r.get('sha256'))[:16], r.get('bytes'), 'MATCH' if r.get('sha256')==live else 'MISMATCH')
    # does receipt record manifest_registration?
    mr = d.get('manifest_registration')
    print('   receipt.manifest_registration:', json.dumps(mr)[:200])
