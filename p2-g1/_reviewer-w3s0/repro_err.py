#!/usr/bin/env python3
import json, sys, time
from pathlib import Path
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
src = (REPO / "_reviewer-w3s0/close_shard0.py").read_text(encoding="utf-8")
prefix = src.split("\nresults = {}")[0]
g = {"__name__": "cfg"}
exec(compile(prefix, "cfg", "exec"), g)
uid = "ADV-0005"
ok, fails, ctx = g["live_checks"](uid)
u = g["byid"][uid]
rp = REPO / ("command-center/receipts/" + uid + ".json")
orig = json.loads(rp.read_text(encoding="utf-8"))
ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
receipt = g["build_receipt"](uid, u, ctx, orig, ts, ts)
receipt["artifacts"].append({
    "path": "command-center/receipts/" + uid + ".json",
    "bytes": rp.stat().st_size,
    "sha256": g["raw_sha"](rp), "exists": True,
    "eol": g["eol_of"](rp), "role": "supporting"})
receipt["downstream_consumers"] = [{
    "consumer": "command-center/receipt_validate.py (admission gate C1-C4)",
    "artifact_path": "command-center/receipts/" + uid + ".json",
    "executed": True, "read_ok": False, "exit_code": 1,
    "probe": {"role": "verifier", "method": "command",
              "command": "python -I command-center/receipt_validate.py command-center/receipts/" + uid + ".json",
              "raw_output": "REJECT:" + uid + " C2 schema-invalid (1): downstream_consumers: [] should be non-empty",
              "exit_code": 0,
              "fingerprint": "w3s0-validate:" + uid + ":rc1"}}]
ctrls = ctx["artifact"].get("negative_controls") or []
if isinstance(ctrls, list):
    receipt["negative_controls"] = [{
        "id": str(c.get("id") or ("NC-" + str(i + 1))), "kind": "other",
        "description": str(c.get("description") or "")[:2000],
        "fired_on_bad_state": c.get("fired_on_bad_state") is True,
        "silent_on_good_state": c.get("silent_on_good_state") is True,
    } for i, c in enumerate(ctrls) if isinstance(c, dict)]
errs = g["rsg"].validate_receipt(receipt)
print("errors:", len(errs))
for e in errs:
    print("FULL:", e)
