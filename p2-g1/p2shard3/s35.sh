#!/bin/bash
cd /home/prekzursil/p2-g1
python3 - <<'PYEOF'
import json
from pathlib import Path
s = json.loads(Path('platform/schema/artifact-class-profiles.schema.json').read_text())
defs = s.get('$defs') or {}
d = defs.get('scale-model') or {}
print(json.dumps(d, indent=1)[:9000])
PYEOF
