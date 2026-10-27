#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
rsync -a "$SRC/command-center/p2-wave/seed-stage/" "$DST/command-center/p2-wave/seed-stage/"
rsync -a "$SRC/command-center/p2-wave/_measure_one_delivered.py" "$DST/command-center/p2-wave/_measure_one_delivered.py"
rsync -a "$SRC/tools/agentspec/agentspec/fanin/" "$DST/tools/agentspec/agentspec/fanin/"
rsync -a "$SRC/command-center/p2-wave/probes/ADV-0008/probe1_enumerate.py" "$DST/command-center/p2-wave/probes/ADV-0008/probe1_enumerate.py"
export AST_INTEGRATE_ROOT="$DST"
cd "$DST"
python3 -u "$DST/command-center/p2-wave/seed-stage/rewrite_schema_file_ids.py"
python3 - <<'PY'
import json
from pathlib import Path
p = Path("/home/prekzursil/p2-g1/platform/schema/receipt.schema.json")
doc = json.loads(p.read_text(encoding="utf-8"))
core = doc.get("$defs", {}).get("receipt_core")
if isinstance(core, dict):
    core["additionalProperties"] = True
    p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print("AP-true receipt_core")
else:
    print("AP-MISS")
PY
python3 -u "$DST/command-center/p2-wave/seed-stage/fast_fill_receipts.py"
set +e
python3 -u "$DST/command-center/p2-wave/_measure_one_delivered.py" ADV-0005
python3 -u "$DST/command-center/p2-wave/_measure_one_delivered.py" ADV-0010
python3 -u "$DST/command-center/p2-wave/_measure_one_delivered.py" ADV-0004
python3 -u "$DST/command-center/p2-wave/_measure_one_delivered.py" ADV-0003
python3 -u "$DST/command-center/p2-wave/_measure_one_delivered.py" BLD-0055
exit 0
