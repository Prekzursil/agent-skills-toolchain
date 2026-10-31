import json, sys
from pathlib import Path
HERE = Path("command-center/p2-wave/probes/ADV-0038").resolve()
REPO = Path(".").resolve()
sys.path.insert(0, str(HERE))
import harness as H
doc = json.loads((REPO / H.ARTIFACT_REL).read_text(encoding="utf-8"))
art = (doc.get("production") or {}).get("tree_token_hits")
live_full = H.run_scenario()
live = live_full["production"].get("tree_token_hits")
print("artifact rows:", len(art or []), "live rows:", len(live or []))
artset = {json.dumps(r, sort_keys=True) for r in (art or [])}
liveset = {json.dumps(r, sort_keys=True) for r in (live or [])}
print("--- in live but not artifact:")
for r in sorted(liveset - artset): print(" ", r)
print("--- in artifact but not live:")
for r in sorted(artset - liveset): print(" ", r)
print("--- install_path hits live:", live_full["production"].get("install_path_token_hits"))
print("--- token_hits empty (failure gate):", live_full["production"].get("token_hits"))
print("--- other gates:", {k: v for k, v in live_full.get("controls", {}).items()})
