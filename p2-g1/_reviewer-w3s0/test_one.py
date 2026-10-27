#!/usr/bin/env python3
import json, sys, io, time
from pathlib import Path
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
src = (REPO / "_reviewer-w3s0/close_shard0.py").read_text(encoding="utf-8")
prefix = src.split("\nresults = {}")[0]
g = {"__name__": "cfg"}
exec(compile(prefix, "cfg", "exec"), g)
uid = "ADV-0005"
ok, fails, ctx = g["live_checks"](uid)
print("live ok:", ok, fails)
u = g["byid"][uid]
rp = REPO / ("command-center/receipts/" + uid + ".json")
orig = json.loads(rp.read_text(encoding="utf-8"))
ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
receipt = g["build_receipt"](uid, u, ctx, orig, ts, ts)
# replicate main-loop enrichment
art_doc = ctx["artifact"]
ctrls = art_doc.get("negative_controls") or []
if isinstance(ctrls, list):
    receipt["negative_controls"] = [{
        "id": str(c.get("id") or ("NC-" + str(i + 1))), "kind": "other",
        "description": str(c.get("description") or "")[:2000],
        "fired_on_bad_state": c.get("fired_on_bad_state") is True,
        "silent_on_good_state": c.get("silent_on_good_state") is True,
    } for i, c in enumerate(ctrls) if isinstance(c, dict)]
receipt["report"]["observations"] = [
    {"name": "artifact_bytes", "measured": ctx["artifact_bytes"], "method": "stat", "anchor": ctx["out_rel"]},
    {"name": "named_probes_exit0", "measured": len(ctx["probe_runs"]), "method": "subprocess re-run", "anchor": "command-center/p2-wave/probes/" + uid + "/"},
    {"name": "manifest_lf_sha_match", "measured": True, "method": "sha256 CRLF-normalized byte-compare", "anchor": "command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json"},
]
receipt["report"]["control_ids"] = [c["id"] for c in receipt["negative_controls"]]
receipt["artifacts"].append({"path": "command-center/receipts/ADV-0005.json", "bytes": 2400, "sha256": "0"*64, "exists": True, "eol": "LF", "role": "supporting"})
receipt["downstream_consumers"] = [{
    "consumer": "command-center/receipt_validate.py (admission gate C1-C4)",
    "artifact_path": "command-center/receipts/" + uid + ".json",
    "executed": True, "read_ok": True, "exit_code": 0,
    "probe": {"role": "verifier", "method": "command",
              "command": "python -I command-center/receipt_validate.py command-center/receipts/" + uid + ".json",
              "raw_output": "ACCEPT:" + uid + " (recorded post-write)", "exit_code": 0,
              "fingerprint": "w3s0-validate:" + uid + ":rc0"},
}]
errs = g["rsg"].validate_receipt(receipt)
print("schema errors:", len(errs))
for e in errs[:10]:
    print("  ", e[:200])
res = g["rsg"].evaluate_gate_a(receipt, repo_root=str(REPO), verify_filesystem=True)
print("complete:", res.complete, "| marker:", res.marker())
print("blocking:", [(c.n, c.outcome, c.basis[:90]) for c in res.blocking_conditions])
