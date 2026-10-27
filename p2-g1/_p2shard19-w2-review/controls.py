import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
import receipt_schema_gate as rsg  # noqa: E402

# pick known-closed receipts with reviewer PASS as controls
closed = []
for p in sorted((REPO / "command-center" / "receipts").glob("*.json")):
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    if d.get("state") == "SUCCESS" and isinstance(d.get("reviewer"), dict) \
            and d["reviewer"].get("verdict") == "PASS" and d["reviewer"].get("independent") is True:
        closed.append((p.stem, d))

print("closed-with-valid-PASS controls:", len(closed))
# admission status under the CURRENT gate for 5 controls
for uid, d in closed[:5]:
    errs = rsg.validate_receipt(d)
    print("CONTROL", uid, "admission_errors=", len(errs), [str(e)[:120] for e in errs[:3]])

v = json.loads((REPO / "_p2shard19-w2-review" / "verify_out.json").read_text(encoding="utf-8"))
print()
print("shard19 RES-0151 admission errors:")
for e in v["RES-0151"]["admission_errors"][:8]:
    print("   -", str(e)[:280])
