#!/usr/bin/env python3
"""Shard-20 fix cycle 2: the two residual schema errors (TST-0233, TST-0256)."""
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


def lf_sha(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def refresh_manifest(uid: str, path: Path) -> None:
    sha, size = lf_sha(path)
    man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    mandoc = json.loads(man_path.read_text(encoding="utf-8"))
    rel = f"command-center/receipts/{uid}.json"
    for a in mandoc.get("artifacts") or []:
        if isinstance(a, dict) and a.get("unit_id") == uid and \
                str(a.get("path", "")).replace("\\", "/") == rel:
            a["sha256"] = sha
            a["bytes"] = size
            a["present"] = True
    man_path.write_text(json.dumps(mandoc, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")


# --- TST-0233: dump the full negative_controls error --------------------------
p233 = REPO / "command-center/receipts/TST-0233.json"
d = json.loads(p233.read_text(encoding="utf-8"))
errs = gate.validate_receipt(d)
print("TST-0233 residual errors:")
for e in errs:
    print("   ", e[:400])
print("negative_controls now:", json.dumps(d.get("negative_controls"), indent=1)[:1200])
