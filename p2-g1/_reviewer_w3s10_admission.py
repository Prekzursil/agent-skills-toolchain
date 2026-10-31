import hashlib
import importlib.util
import json
import os
import subprocess
import sys

REPO = r'C:/Users/Prekzursil/p2-g1'
CANON = r'C:/Users/Prekzursil/source/ast-integrate'
UNITS = ["IMP-0084", "IMP-0090", "IMP-0093", "IMP-0097", "IMP-0098", "IMP-0103",
         "IMP-0134", "IMP-0147", "IMP-0154", "IMP-0165", "IMP-0168", "IMP-0189"]

# 1. Byte-identity of the physical receipt schema between p2-g1 and the NTFS mirror
a = open(os.path.join(REPO, 'platform', 'schema', 'receipt.schema.json'), 'rb').read()
b = open(os.path.join(CANON, 'platform', 'schema', 'receipt.schema.json'), 'rb').read()
print('physical receipt.schema.json byte-identical p2-g1 vs NTFS mirror:',
      hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest())

# 2. Shim identity too
c = open(os.path.join(REPO, 'command-center', 'schema', 'receipt.schema.json'), 'rb').read()
d = open(os.path.join(CANON, 'command-center', 'schema', 'receipt.schema.json'), 'rb').read()
print('declared shim receipt.schema.json byte-identical:', hashlib.sha256(c).hexdigest() == hashlib.sha256(d).hexdigest())

# 3. Program admission gate (receipt_validate.py) per unit
print()
print('=== admission gate (command-center/receipt_validate.py) ===')
py = sys.executable
for uid in UNITS:
    rp = os.path.join(REPO, 'command-center', 'receipts', uid + '.json')
    try:
        p = subprocess.run([py, '-I', '-B', os.path.join(REPO, 'command-center', 'receipt_validate.py'), rp],
                           cwd=REPO, capture_output=True, text=True, timeout=120)
        tail = ((p.stdout or '') + (p.stderr or '')).strip().replace('\n', ' | ')[-260:]
        print('%s rc=%d | %s' % (uid, p.returncode, tail))
    except subprocess.TimeoutExpired:
        print('%s rc=TIMEOUT' % uid)
