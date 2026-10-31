#!/bin/bash
cd /home/prekzursil/p2-g1
python3 - <<'PYEOF'
import json
from pathlib import Path
s = json.loads(Path('platform/schema/receipt.schema.json').read_text())
g = (s.get('$defs') or {}).get('receipt_core') or {}
print(json.dumps(g, indent=1)[:12000])
PYEOF
