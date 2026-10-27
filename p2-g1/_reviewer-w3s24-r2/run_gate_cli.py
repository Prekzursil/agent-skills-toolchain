"""Third-signal check: run the program's own receipt_schema_gate CLI (layer-2
12-condition completion predicate + layer-1 schema) over my 8 receipts."""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
uids = ["TST-0206", "TST-0215", "TST-0219", "TST-0221",
        "TST-0223", "TST-0227", "TST-0230", "TST-0233"]
out = {}
for uid in uids:
    proc = subprocess.run(
        [sys.executable, "-B", str(REPO / "platform/lib/receipt_schema_gate.py"),
         str(REPO / f"command-center/receipts/{uid}.json"), "--no-fs"],
        cwd=str(REPO), capture_output=True, text=True, timeout=300,
    )
    out[uid] = {"rc": proc.returncode, "stdout_tail": (proc.stdout or "")[-700:],
                "stderr_tail": (proc.stderr or "")[-300:]}
Path(r"C:/Users/Prekzursil/p2-g1/_reviewer-w3s24-r2/gate_cli_results.json").write_text(
    json.dumps(out, indent=1), encoding="utf-8")
for uid, r in out.items():
    print(uid, "| rc:", r["rc"])
    print("   ", r["stdout_tail"].replace(chr(10), " | ")[:450])
