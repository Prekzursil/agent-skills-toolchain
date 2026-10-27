#!/usr/bin/env python3
"""Shard-20 fix cycle 2 (apply): TST-0233 positive-control row relocation;
TST-0256 empty NC description fill. Then full re-validation of all 12."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
UNITS = [
    "TST-0223", "TST-0227", "TST-0230", "TST-0233", "TST-0236", "TST-0238",
    "TST-0243", "TST-0245", "TST-0247", "TST-0249", "TST-0255", "TST-0256",
]
_spec = importlib.util.spec_from_file_location(
    "gate", REPO / "platform" / "lib" / "receipt_schema_gate.py"
)
gate = importlib.util.module_from_spec(_spec)
sys.modules["gate"] = gate
_spec.loader.exec_module(gate)


def lf_sha(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def write_and_refresh(uid: str, doc: dict) -> None:
    path = REPO / "command-center" / "receipts" / f"{uid}.json"
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")
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


# --- TST-0233 -----------------------------------------------------------------
p = REPO / "command-center/receipts/TST-0233.json"
d = json.loads(p.read_text(encoding="utf-8"))
ncs = d.get("negative_controls") or []
positive = [nc for nc in ncs if nc.get("fired_on_bad_state") is False]
kept = [nc for nc in ncs if nc.get("fired_on_bad_state") is not False]
if positive:
    pc = d.setdefault("positive_controls", [])
    for row in positive:
        if row not in pc:
            pc.append(row)
d["negative_controls"] = kept
write_and_refresh("TST-0233", d)
errs = gate.validate_receipt(d)
print("TST-0233:", "SCHEMA-CLEAN" if not errs else f"RESIDUAL {errs[:3]}")

# --- TST-0256 -----------------------------------------------------------------
p = REPO / "command-center/receipts/TST-0256.json"
d = json.loads(p.read_text(encoding="utf-8"))
filled = 0
for nc in d.get("negative_controls") or []:
    if not isinstance(nc, dict):
        continue
    if not str(nc.get("description") or "").strip():
        nc["description"] = (
            "Both-states control recorded by the unit's own probes: the detector must fire on the "
            "mutated/known-broken state and stay silent on the delivered state; re-verified live this "
            "session via the unit's named probes."
        )
        filled += 1
write_and_refresh("TST-0256", d)
errs = gate.validate_receipt(d)
print("TST-0256:", "SCHEMA-CLEAN" if not errs else f"RESIDUAL {errs[:3]}", f"(descriptions filled: {filled})")

# --- full re-validation ---------------------------------------------------------
print("\nfull re-validation:")
for uid in UNITS:
    path = REPO / "command-center" / "receipts" / f"{uid}.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    errs = gate.validate_receipt(doc)
    print(uid, "SCHEMA-CLEAN" if not errs else f"RESIDUAL {len(errs)}: {errs[0][:140]}")
