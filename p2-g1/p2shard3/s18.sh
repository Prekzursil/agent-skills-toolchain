#!/bin/bash
cd /home/prekzursil/p2-g1
echo "===artifact states for my 15==="
python3 - <<'PYEOF'
import json
from pathlib import Path
REPO = Path('/home/prekzursil/p2-g1')
cat = json.loads((REPO/'command-center/WORK-UNIT-CATALOG.json').read_text())
units = {u['id']: u for u in cat['work_units']}
mine = ['ADV-0005','AUD-0031','AUD-0043','AUD-0044','AUD-0055','AUD-0095','BLD-0010','BLD-0013','BLD-0014','BLD-0031','BLD-0032','BLD-0037','BLD-0044','BLD-0048','BLD-0057']
for uid in mine:
    p = REPO / units[uid]['output_path']
    d = json.loads(p.read_text())
    rev = d.get('reviewer') or {}
    fail = d.get('failure') or {}
    print(uid, 'state=%s' % d.get('state'), '| reviewer.verdict=%s independent=%s' % (rev.get('verdict'), rev.get('independent')), '| failure.classification=%s' % (fail.get('classification')))
PYEOF
echo "===BLD-0057 schema manifest_registration==="
python3 - <<'PYEOF'
import json
from pathlib import Path
s = json.loads(Path('/home/prekzursil/p2-g1/command-center/schema/scale-model.schema.json').read_text())
import sys
def find(node, key, path=''):
    if isinstance(node, dict):
        if key in str(path):
            pass
        for k, v in node.items():
            p = path + '/' + str(k)
            if 'manifest' in str(k).lower():
                print('SCHEMA KEY', p, json.dumps(v)[:300])
            find(v, key, p)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            find(v, key, path + '/%d' % i)
find(s, 'manifest_registration')
PYEOF
