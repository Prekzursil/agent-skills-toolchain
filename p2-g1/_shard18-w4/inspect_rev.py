import json
from pathlib import Path
REPO = Path("C:/Users/Prekzursil/p2-g1")
UNITS = ['TST-0092','TST-0094','TST-0100','TST-0109','TST-0113','TST-0116','TST-0124','TST-0129','TST-0130','TST-0136','TST-0137','TST-0138']
for uid in UNITS:
    p = REPO / 'command-center' / 'receipts' / (uid + '.json')
    doc = json.load(open(p, encoding='utf-8'))
    r = doc.get('reviewer') or {}
    print('='*15, uid)
    print(json.dumps(r, indent=1, ensure_ascii=False)[:900])
