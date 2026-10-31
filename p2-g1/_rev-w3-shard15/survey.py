import json, os
BASE = r'C:\Users\Prekzursil\p2-g1'
IDS = ['IMP-0478','REL-0001','REL-0006','REL-0014','REL-0017','REL-0020','REL-0021','REL-0022','RES-0004','RES-0009','RES-0011','RES-0020']
for i in IDS:
    sub = 'research' if i.startswith('RES-') else 'receipts'
    p = os.path.join(BASE, 'command-center', sub, i + '.json')
    try:
        d = json.load(open(p, encoding='utf-8'))
    except Exception as e:
        print(i, '| LOAD-FAIL |', repr(e)[:120]); continue
    state = d.get('state')
    rev = d.get('reviewer') or {}
    verdict = rev.get('verdict') if isinstance(rev, dict) else None
    indep = rev.get('independent') if isinstance(rev, dict) else None
    fail = d.get('failure')
    fcl = (fail or {}).get('classification') if isinstance(fail, dict) else None
    print(i, '| state=', state, '| verdict=', verdict, '| independent=', indep, '| failure=', fcl)
