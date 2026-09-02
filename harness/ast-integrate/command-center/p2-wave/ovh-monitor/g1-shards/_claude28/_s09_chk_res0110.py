import json
import sys
from pathlib import Path

HERE = Path(r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\probes\RES-0110")
REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
sys.path.insert(0, str(HERE))
import schema_local as SL  # noqa: E402

print("GARBAGE docs:", [json.dumps(g)[:60] for g in SL.GARBAGE])
for g in SL.GARBAGE:
    errs = SL.iter_errors(g)
    print("garbage", json.dumps(g)[:40], "-> errors:", len(errs), errs[:1])
try:
    n = SL.assert_rejects_garbage()
    print("assert_rejects_garbage:", n)
except ValueError as exc:
    print("assert_rejects_garbage FAILED:", exc)

doc = json.loads((REPO / "command-center/research/RES-0110.json").read_text(encoding="utf-8"))
try:
    SL.assert_valid(doc)
    print("artifact schema-valid: OK")
except ValueError as exc:
    print("artifact schema errors:", str(exc)[:400])

body = SL.payload(doc)
rows = list((body.get("register") or {}).get("rows") or [])
print("register rows:", len(rows))
