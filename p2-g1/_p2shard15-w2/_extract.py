import json
from pathlib import Path
BS = chr(92)
REPO = Path(r'C:\Users\Prekzursil' + BS + 'p2-g1')
mine = ['IMP-0430','IMP-0435','IMP-0437','IMP-0439','IMP-0442','IMP-0448','IMP-0450','IMP-0460','IMP-0466','IMP-0467','IMP-0468']
for uid in mine:
    doc = json.loads((REPO/'command-center'/'receipts'/(uid+'.json')).read_text(encoding='utf-8'))
    print('#'*20, uid)
    for key in ('implementation','named_probes','tests','artifact_paths','artifacts'):
        v = doc.get(key)
        if v is None: continue
        s = json.dumps(v, indent=1)
        print(f'--{key}--')
        print(s[:2600])
