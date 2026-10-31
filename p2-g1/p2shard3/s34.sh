#!/bin/bash
cd /home/prekzursil/p2-g1
python3 - <<'PYEOF'
import json
from pathlib import Path
s = json.loads(Path('command-center/schema/scale-model.schema.json').read_text())
print('SCHEMA SIZE:', Path('command-center/schema/scale-model.schema.json').stat().st_size)
print(json.dumps(s, indent=1)[:6000])
PYEOF
echo "===old artifact report==="
python3 -c "
import json
d = json.load(open('command-center/receipts/BLD-0057.json'))
print(json.dumps(d.get('report'), indent=1)[:1200])
print('top keys:', sorted(d.keys()))
"
