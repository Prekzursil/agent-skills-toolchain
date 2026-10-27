import json, os, glob
from collections import Counter

p = r'C:/Users/Prekzursil/p2-g1/command-center/receipts'
states = Counter()
pending = []
for f in sorted(glob.glob(p + '/*.json')):
    uid = os.path.basename(f)[:-5]
    try:
        d = json.load(open(f, encoding='utf-8'))
    except Exception as e:
        print('UNPARSEABLE:', uid, e)
        continue
    st = d.get('state')
    states[st] += 1
    rv = d.get('reviewer') or {}
    if st == 'BLOCKED' or (st != 'SUCCESS' and st != 'FAILED'):
        fc = (d.get('failure') or {}).get('classification')
        pending.append((uid, st, fc, rv.get('verdict'), rv.get('independent')))

print('STATE COUNTS:', dict(states))
print('NON-SUCCESS COUNT:', len(pending))
for row in pending:
    print(row)
