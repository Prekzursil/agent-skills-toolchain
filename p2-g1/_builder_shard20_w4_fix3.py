#!/usr/bin/env python3
"""Shard-20 fix cycle 3: wrap TST-0256 string residual_unknowns into schema objects."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
_spec = importlib.util.spec_from_file_location(
    "gate", REPO / "platform" / "lib" / "receipt_schema_gate.py"
)
gate = importlib.util.module_from_spec(_spec)
sys.modules["gate"] = gate
_spec.loader.exec_module(gate)

p = REPO / "command-center/receipts/TST-0256.json"
d = json.loads(p.read_text(encoding="utf-8"))
SETTLE = {
    "command-center/RUNBOOK.md is absent": (
        "Capture a real prior-release RUNBOOK.md layout section, place it at "
        "command-center/RUNBOOK.md, and re-run probe1_convert_and_diff.py to confirm the guide still converts it."
    ),
    "No git repository at the estate root": (
        "Run the documented migration command inside a real git worktree of a prior release tag "
        "and re-run probe2_idempotence_and_noop.py for the idempotence half."
    ),
}
wrapped = []
for item in d.get("residual_unknowns") or []:
    if isinstance(item, str):
        claim = item
        settle = next((v for k, v in SETTLE.items() if claim.startswith(k)),
                      "Re-run the unit's two named probes against a captured prior-release layout fixture.")
        wrapped.append({"claim": claim[:2000], "verdict": "PARTIAL", "settling_experiment": settle})
    else:
        wrapped.append(item)
d["residual_unknowns"] = wrapped
path = REPO / "command-center" / "receipts" / "TST-0256.json"
path.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
errs = gate.validate_receipt(d)
print("TST-0256:", "SCHEMA-CLEAN" if not errs else f"RESIDUAL {errs[:3]}")

# refresh manifest sha
raw = path.read_bytes().replace(b"\r\n", b"\n")
sha = hashlib.sha256(raw).hexdigest()
size = len(raw)
man_path = REPO / "command-center/p2-wave/probes/TST-0256/UNIT-ARTIFACT-MANIFEST.json"
mandoc = json.loads(man_path.read_text(encoding="utf-8"))
rel = "command-center/receipts/TST-0256.json"
for a in mandoc.get("artifacts") or []:
    if isinstance(a, dict) and a.get("unit_id") == "TST-0256" and \
            str(a.get("path", "")).replace("\\", "/") == rel:
        a["sha256"] = sha
        a["bytes"] = size
        a["present"] = True
man_path.write_text(json.dumps(mandoc, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")
print("manifest refreshed", sha[:16])
