import json
from pathlib import Path
BS = chr(92)
REPO = Path(r'C:\Users\Prekzursil' + BS + 'p2-g1')
mine = ['IMP-0423','IMP-0430','IMP-0435','IMP-0437','IMP-0439','IMP-0442','IMP-0448','IMP-0450','IMP-0460','IMP-0466','IMP-0467','IMP-0468']
norm = lambda s: str(s).replace(BS, '/')
for uid in mine:
    p = REPO/'command-center'/'receipts'/(uid+'.json')
    doc = json.loads(p.read_text(encoding='utf-8'))
    print('='*12, uid)
    print(' top keys:', sorted(doc.keys()))
    rev = doc.get('reviewer') or {}
    print(' reviewer:', json.dumps(rev)[:600])
