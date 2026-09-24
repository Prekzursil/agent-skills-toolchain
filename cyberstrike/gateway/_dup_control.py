"""Negative control (rule 3b): inject a duplicate alias into a TEMP ssot copy,
run gen_routes against it, expect the lint to FAIL non-zero. Never touches the
real SSOT or the real generated artifact."""

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_routes

real_ssot = gen_routes.SSOT
tmp = Path(tempfile.mkdtemp(prefix="gw-dup-control-"))
ssot_copy = tmp / "mcp-ssot.json"
shutil.copy(real_ssot, ssot_copy)
d = json.loads(ssot_copy.read_text(encoding="utf-8"))
d["fronts"]["osint"]["aliases"] = d["fronts"]["osint"].get("aliases", ["osint"]) + [
    "cve"
]
ssot_copy.write_text(json.dumps(d), encoding="utf-8")

gen_routes.SSOT = ssot_copy
gen_routes.OUT = tmp / "gateway-routes.json"
routes = gen_routes.build_routes(json.loads(ssot_copy.read_text(encoding="utf-8")))
dups = gen_routes.lint_duplicate_aliases(routes)
if dups:
    print("CONTROL-FIRED (expected):", dups[0])
    sys.exit(1)
print("CONTROL-DID-NOT-FIRE (detector broken)")
sys.exit(2)
