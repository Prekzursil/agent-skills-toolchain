import hashlib, json
from pathlib import Path
REPO = Path.home() / 'p2-g1'
d = json.loads((REPO/'command-center/audit/AUD-0095-freeze-inventory.json').read_text(encoding='utf-8'))
inv = d.get('inventory') or []
print('inventory rows:', len(inv))
mismatched = []; absent = []; required_absent = []; checked = 0
for r in inv:
    if not isinstance(r, dict) or not r.get('path'): continue
    p = REPO / str(r['path'])
    if not p.is_file():
        absent.append((str(r['path']), bool(r.get('required_by_spec'))))
        if r.get('required_by_spec'): required_absent.append(str(r['path']))
        continue
    checked += 1
    live = hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    if live != str(r.get('sha256') or ''):
        mismatched.append(str(r['path']))
print('checked(present):', checked)
print('absent:', len(absent))
for a in absent[:35]: print('  absent:', a)
print('required_absent:', required_absent)
print('mismatched:', len(mismatched))
for m in mismatched[:35]: print('  drift:', m)
