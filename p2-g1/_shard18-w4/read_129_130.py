import json
from pathlib import Path
REPO = Path("C:/Users/Prekzursil/p2-g1")
for uid in ['TST-0129','TST-0130']:
    p = REPO / 'command-center' / 'receipts' / (uid + '.json')
    doc = json.load(open(p, encoding='utf-8'))
    print('='*25, uid, 'top-level keys:', sorted(doc.keys()))
    for k in ['state','title','question_or_target','verdict','claim','honesty','scope','limitations','residual','notes','gates','blockers','delivered_claims']:
        if k in doc:
            v = doc[k]
            print('--',k,':', json.dumps(v, ensure_ascii=False)[:700])
