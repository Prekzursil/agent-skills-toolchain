#!/usr/bin/env python3
import importlib.util, json, subprocess, sys, time
from pathlib import Path
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
G = ["ADV-0005","ADV-0010","ADV-0014","ADV-0019","ADV-0022","ADV-0023","ADV-0028","ADV-0029"]
spec = importlib.util.spec_from_file_location("rsg", REPO / "platform/lib/receipt_schema_gate.py")
rsg = importlib.util.module_from_spec(spec); sys.modules["rsg"] = rsg; spec.loader.exec_module(rsg)
for uid in G:
    rp = REPO / ("command-center/receipts/" + uid + ".json")
    r = json.loads(rp.read_text(encoding="utf-8"))
    ext = r.get("extensions") or {}
    outer = ext.get("builder_receipt_original")
    if not isinstance(outer, dict):
        print(uid, "no nesting - skip"); continue
    inner = outer.get("extensions", {}).get("builder_receipt_original") if isinstance(outer.get("extensions"), dict) else None
    if isinstance(inner, dict) and inner.get("state") in ("BLOCKED", "SUCCESS"):
        ext["builder_receipt_original"] = inner
        ext["unwrap_note"] = ("builder_receipt_original unwrapped one level after an "
                              "idempotent re-run nested a prior reviewer closure; the "
                              "true builder document is restored verbatim.")
    else:
        # outer IS the true original (run-1 receipt nested nothing) - already correct
        print(uid, "outer is true original - keep")
        continue
    rp.write_text(json.dumps(r, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    # re-verify
    v = subprocess.run([sys.executable, "-I", str(REPO / "command-center/receipt_validate.py"),
                        str(rp)], capture_output=True, text=True, cwd=str(REPO))
    res = rsg.evaluate_gate_a(json.loads(rp.read_text(encoding="utf-8")), repo_root=str(REPO), verify_filesystem=True)
    print(uid, "| validator rc:", v.returncode, "| gate complete:", res.complete, "|", res.marker())
