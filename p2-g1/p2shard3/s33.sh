#!/bin/bash
cd /home/prekzursil/p2-g1
python3 - <<'PYEOF'
import json
from pathlib import Path
s = json.loads(Path('command-center/schema/scale-model.schema.json').read_text())
props = s.get('properties') or {}
print('top required:', s.get('required'))
print('=== report schema ===')
print(json.dumps(props.get('report'), indent=1)[:1500])
print('=== manifest_registration schema ===')
print(json.dumps(props.get('manifest_registration'), indent=1)[:1200])
print('=== registered (top) ===')
print(json.dumps(props.get('registered'), indent=1)[:400])
PYEOF
echo "===estate manifest check==="
ls -la command-center/UNIT-ARTIFACT-MANIFEST.json 2>/dev/null && python3 -c "
import json
d = json.load(open('command-center/UNIT-ARTIFACT-MANIFEST.json'))
rows = d.get('artifacts') or d.get('units') or []
ids = [r.get('unit_id') or r.get('id') for r in rows if isinstance(r, dict)]
print('estate manifest rows:', len(ids), 'BLD-0057 in it:', 'BLD-0057' in ids)
"
python3 tools/command-center/unit_manifest.py --check 2>&1 | tail -5
