#!/bin/bash
cd /home/prekzursil/p2-g1
python3 - <<'PYEOF'
import json
from pathlib import Path
s = json.loads(Path('platform/schema/receipt.schema.json').read_text())
d = s.get('$defs') or {}
for k in ['terminal_state', 'sentinel', 'unit_id', 'timestamps', 'retry', 'evidence_item', 'test_result', 'negative_control', 'reviewer', 'manifest_registration', 'downstream_consumer', 'artifact', 'residual_unknown']:
    v = d.get(k)
    print('==== %s ====' % k)
    print(json.dumps(v, indent=1)[:1600])
PYEOF
echo "===old artifact spec_anchor/min_bytes==="
python3 -c "
import json
d = json.load(open('command-center/receipts/BLD-0057.json'))
print('spec_anchor:', json.dumps(d.get('spec_anchor'))[:300])
print('min_bytes_threshold:', d.get('min_bytes_threshold'))
print('state:', d.get('state'))
print('schema_version:', d.get('schema_version'))
"
