"""Program-wide census toward '2007 full green' (v3)."""
import json, subprocess, sys
from pathlib import Path

R = Path(r'C:\Users\Prekzursil\p2-g1')
PY = sys.executable
catalog = json.load(open(R / 'command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
units = catalog['work_units']
print('catalog total:', len(units))

states = {}
green = []
nreceipt = 0
nparse_fail = 0
blocked = []
nobody = []
not_success = []
reviewer_str = 0
for u in units:
    uid = u['id']
    p = R / u['output_path']
    if not p.is_file() or p.stat().st_size == 0:
        nobody.append(uid)
        continue
    try:
        d = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        nparse_fail += 1
        continue
    nreceipt += 1
    st = str(d.get('state', '')).upper()
    states[st] = states.get(st, 0) + 1
    rev = d.get('reviewer')
    if isinstance(rev, str):
        reviewer_str += 1
        rev = {}
    rev = rev or {}
    is_green = (st == 'SUCCESS' and rev.get('verdict') == 'PASS'
                and rev.get('independent') is True)
    if is_green:
        green.append(uid)
    elif st in ('BLOCKED', 'FAILED', 'SEVERED', 'TIMEOUT'):
        blocked.append(uid)
    else:
        not_success.append(uid)

print('receipts parsed:', nreceipt, '| missing/empty:', len(nobody),
      '| parse-fail:', nparse_fail, '| reviewer-as-string:', reviewer_str)
print('state census:', json.dumps(states, sort_keys=True))
print('GREEN (SUCCESS+PASS+independent):', len(green))
print('BLOCKED/FAILED/etc:', len(blocked))
print('delivered-but-not-closed:', len(not_success))
print('sample missing (10):', nobody[:10])
print('sample blocked (10):', blocked[:10])
print('sample not-closed (10):', not_success[:10])

p = subprocess.run([PY, '-I', str(R / 'command-center/receipt_validate.py'),
                    str(R / 'command-center/receipts')],
                   cwd=str(R), capture_output=True, text=True, timeout=1800)
tail = ((p.stdout or '') + (p.stderr or ''))[-700:]
print()
print('admission gate over receipts dir rc=%d tail:' % p.returncode)
print(tail)
