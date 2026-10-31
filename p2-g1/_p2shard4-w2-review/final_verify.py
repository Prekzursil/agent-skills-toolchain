#!/usr/bin/env python3
"""Final post-sweep verification: sha stability + canonical schema counts for the 12."""
import hashlib, json, sys
from pathlib import Path
REPO = Path(r"C:\Users\Prekzursil\p2-g1")
IDS = ["AUD-0043","AUD-0044","AUD-0047","AUD-0053","AUD-0055","AUD-0057","AUD-0064","AUD-0066","AUD-0069","AUD-0071","AUD-0072","AUD-0075"]
sys.path.insert(0, str(REPO / "platform" / "lib"))
import importlib.util
spec = importlib.util.spec_from_file_location("sr", REPO / "platform" / "lib" / "schema_resolver.py")
sr = importlib.util.module_from_spec(spec); sys.modules["sr"] = sr; spec.loader.exec_module(sr)
cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u.get("id"): u for u in cat.get("work_units") or [] if isinstance(u, dict)}
def sha_lf(p): return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
rows = []
for uid in IDS:
    u = byid[uid]
    out = REPO / str(u["output_path"]).replace("\\", "/")
    man = json.loads((REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
    prow = next((a for a in man["artifacts"] if a.get("unit_id") == uid and a.get("role") == "primary"), None)
    sha_ok = prow is not None and sha_lf(out) == prow.get("sha256")
    doc = json.loads(out.read_text(encoding="utf-8"))
    n_err = len(sr.validate_artifact(doc, u["output_schema"]))
    rows.append({"id": uid, "primary_sha_match": sha_ok, "schema_errors": n_err,
                 "artifact_state": doc.get("state")})
(REPO / "_p2shard4-w2-review" / "final_verify.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
for r in rows:
    print(r["id"], "sha_ok=" + str(r["primary_sha_match"]), "schema_errors=" + str(r["schema_errors"]), "state=" + str(r["artifact_state"]))
print("DONE:final-verify")
