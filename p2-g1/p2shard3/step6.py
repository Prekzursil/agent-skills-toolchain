from wslrun import read_unc
script = '''#!/bin/bash
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
'''
open('s6.sh', 'w', newline='\n').write(script)
import subprocess
r = subprocess.run(['wsl.exe', '-d', 'Ubuntu', 'bash', '-c',
    'cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s6.sh /tmp/s6.sh && bash /tmp/s6.sh > /tmp/s6.out 2>&1'],
    capture_output=True, timeout=600)
print('rc', r.returncode, (r.stderr or b'')[-200:])
print(read_unc('/tmp/s6.out'))
