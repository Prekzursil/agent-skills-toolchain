import subprocess, sys
from pathlib import Path
files = sorted(Path('command-center/receipts').glob('*.json'))
accept, reject = [], []
for f in files:
    p = subprocess.run([sys.executable, 'command-center/receipt_validate.py', str(f)], capture_output=True, text=True)
    line = (p.stdout or p.stderr).strip().splitlines()[0] if (p.stdout or p.stderr).strip() else 'NO-OUTPUT'
    if line.startswith('ACCEPT'): accept.append(f.name)
    else: reject.append((f.name, line[:110]))
print('total=%d accept=%d reject=%d' % (len(files), len(accept), len(reject)))
print('sample accepts:', accept[:5])
from collections import Counter
reasons = Counter()
for name, line in reject:
    # take reason after unit id
    parts = line.split(' ', 2)
    reasons[parts[-1][:60]] += 1
for r, n in reasons.most_common(8):
    print(n, '|', r)
