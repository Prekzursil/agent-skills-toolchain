#!/bin/bash
find /home/prekzursil/p2-g1 -name "*receipt_core*" -o -name "*receipt-core*" 2>/dev/null | head
echo ---DEFS---
grep -rln "def.*receipt" /home/prekzursil/p2-g1/platform/lib/*.py /home/prekzursil/p2-g1/tools/*.py 2>/dev/null | head
echo ---RECEIPTCORE-GREP---
grep -rn "receipt_core" /home/prekzursil/p2-g1/command-center/p2-wave/_build_AUD0020.py | head -5
echo ---STATES---
python3 - <<'PYEOF'
import json, glob, collections
c = collections.Counter()
vals = collections.Counter()
for p in glob.glob('/home/prekzursil/p2-g1/command-center/p2-wave/probes/*/SUBAGENT-RETURN.json'):
    try:
        d = json.load(open(p))
        c[str(d.get('status') or d.get('state'))] += 1
    except Exception as e:
        c['UNPARSEABLE'] += 1
print('SUBAGENT-RETURN status counts:', dict(c))
PYEOF
