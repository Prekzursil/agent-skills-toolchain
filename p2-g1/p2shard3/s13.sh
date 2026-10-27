#!/bin/bash
cd /home/prekzursil/p2-g1
echo "===local repo identity==="
git remote -v 2>/dev/null | head -4
git log --oneline -3 2>/dev/null
ls .github/workflows/ 2>/dev/null | head
ls .github/AUTOMATION.md 2>/dev/null
echo "===gh auth==="
command -v gh && gh auth status 2>&1 | head -5
env | grep -iE "GH_|GITHUB" | sed 's/=.*/=<set>/' | head
echo "===AUD-0095 changed files==="
python3 - <<'PYEOF'
import json, hashlib
from pathlib import Path
REPO = Path('/home/prekzursil/p2-g1')
doc = json.loads((REPO/'command-center/audit/AUD-0095-freeze-inventory.json').read_text())
for r in doc.get('inventory', []):
    p = REPO / r['path']
    if r.get('present'):
        raw = p.read_bytes().replace(b"\r\n", b"\n") if p.is_file() else b''
        live = hashlib.sha256(raw).hexdigest()
        if live != r.get('sha256'):
            print('CHANGED:', r['path'])
    else:
        if p.is_file():
            print('NOW-PRESENT:', r['path'])
print('inventory rows:', len(doc.get('inventory', [])))
PYEOF
echo "===BLD-0037 artifact reviewer==="
python3 - <<'PYEOF'
import json
from pathlib import Path
doc = json.loads(Path('/home/prekzursil/p2-g1/command-center/receipts/BLD-0037.json').read_text())
rev = doc.get('reviewer') or {}
print('verdict:', rev.get('verdict'), 'independent:', rev.get('independent'))
print('queries n=', len(rev.get('queries') or []))
for q in (rev.get('queries') or [])[:6]:
    print('  Q:', json.dumps(q)[:200])
PYEOF
echo "===BLD-0057 manifest_registration==="
python3 - <<'PYEOF'
import json
from pathlib import Path
doc = json.loads(Path('/home/prekzursil/p2-g1/command-center/receipts/BLD-0057.json').read_text())
print(json.dumps(doc.get('manifest_registration'), indent=1))
PYEOF
ls tools/command-center/unit_manifest.py 2>/dev/null || find tools -name "unit_manifest*" | head -3
