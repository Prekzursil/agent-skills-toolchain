#!/usr/bin/env bash
set -u
python3 - <<'EOF'
import json
from pathlib import Path

p = Path.home() / "p2-g1/command-center/p2-wave/ovh-monitor/g1-shards/classes.json"
d = json.loads(p.read_text())
for k, v in d.items():
    if isinstance(v, list):
        print(k, len(v))
        if len(v) <= 12:
            print("  ", v)
EOF
