"""Scan estate receipts for ones the admission gate ACCEPTS, to use as structural template."""
import json, subprocess, sys
from pathlib import Path
REPO = Path.home() / "p2-g1"
gate = REPO / "command-center/receipt_validate.py"
accepted = []
rejected = 0
for p in sorted((REPO / "command-center/receipts").glob("*.json")):
    r = subprocess.run([sys.executable, str(gate), str(p)], capture_output=True, text=True,
                       cwd=str(REPO), env={"PYTHONDONTWRITEBYTECODE": "1", "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT","")})
    out = (r.stdout + r.stderr)
    if out.startswith("ACCEPT"):
        accepted.append(p.name)
    else:
        rejected += 1
print("accepted:", len(accepted), "rejected:", rejected)
print("sample accepted:", accepted[:20])
