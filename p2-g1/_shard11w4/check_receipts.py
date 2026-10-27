import json, os
base = os.path.join(r'C:\Users\Prekzursil\p2-g1', 'command-center', 'receipts')
ids = ['IMP-0261','IMP-0264','IMP-0269','IMP-0270','IMP-0271','IMP-0272','IMP-0273','IMP-0274','IMP-0275','IMP-0279','IMP-0303','IMP-0304']
for uid in ids:
    p = os.path.join(base, uid + '.json')
    try:
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
    except FileNotFoundError:
        print(uid, '| NO RECEIPT')
        continue
    except Exception as e:
        print(uid, '| ERR', type(e).__name__, str(e)[:80])
        continue
    st = d.get('state')
    rv = d.get('reviewer')
    fcore = d.get('receipt_core') or {}
    fc = d.get('failure', {}).get('classification') if isinstance(d.get('failure'), dict) else None
    rvs = (rv.get('verdict'), rv.get('independent')) if isinstance(rv, dict) else None
    print(uid, '| state=', st, '| core.state=', fcore.get('state') if isinstance(fcore, dict) else None,
          '| reviewer=', rvs, '| failure.class=', fc)
    print('    keys:', sorted(d.keys()))
