import hashlib
import json
from pathlib import Path

REPO = Path('C:/Users/Prekzursil/p2-g1')


def sha_n(p):
    raw = (REPO / p).read_bytes().replace(b'\r\n', b'\n')
    return hashlib.sha256(raw).hexdigest()


for uid in ['IMP-0095', 'IMP-0146', 'IMP-0074', 'IMP-0076', 'IMP-0082']:
    m = json.loads((REPO / f'command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json')
                   .read_text(encoding='utf-8'))
    live = sha_n(f'command-center/receipts/{uid}.json')
    rows = m.get('artifacts', [])
    hit = any(
        r.get('path', '').replace(chr(92), '/') == f'command-center/receipts/{uid}.json'
        and r.get('sha256') == live and r.get('present') is True
        for r in rows
    )
    print(uid, 'rows=%d' % len(rows), 'primary_row_match=', hit)
    for r in rows[:2]:
        print('   row:', r.get('path'), '|', r.get('role'), '|', str(r.get('sha256'))[:16],
              '| live:', live[:16])
