#!/usr/bin/env python3
"""Write the probe-local UNIT-ARTIFACT-MANIFEST.json for AUD-0095 (condition 11).

Per-unit manifest contract (owner decision Option B postscript): registers the
catalog output_path plus this probe's named scripts, hashed off disk over
CRLF-normalised bytes (the inventory.digest_bytes algorithm).
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

OUT_REL = "command-center/audit/AUD-0095-freeze-inventory.json"
MANIFEST_REL = "command-center/p2-wave/probes/AUD-0095/UNIT-ARTIFACT-MANIFEST.json"
SCHEMA_REL = "command-center/schema/audit-inventory.schema.json"
UNIT = "AUD-0095"

FILES = [
    (OUT_REL, "primary"),
    (SCHEMA_REL, "supporting"),
    ("command-center/p2-wave/probes/AUD-0095/contract.py", "supporting"),
    ("command-center/p2-wave/probes/AUD-0095/inventory.py", "supporting"),
    ("command-center/p2-wave/probes/AUD-0095/detector.py", "supporting"),
    ("command-center/p2-wave/probes/AUD-0095/emit_artifact.py", "supporting"),
    ("command-center/p2-wave/probes/AUD-0095/probe1_freeze_anchors.py", "supporting"),
    ("command-center/p2-wave/probes/AUD-0095/probe2_change_detection.py", "supporting"),
    ("command-center/p2-wave/probes/AUD-0095/write_receipts.py", "supporting"),
]


def row(rel: str, role: str) -> dict:
    p = REPO / rel
    if not p.is_file():
        return {"path": rel, "present": False, "role": role, "unit_id": UNIT}
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "present": True,
        "role": role,
        "unit_id": UNIT,
    }


def main() -> int:
    artifacts = [row(rel, role) for rel, role in FILES]
    missing = [a["path"] for a in artifacts if not a.get("present")]
    if missing:
        print(f"FAILED:{UNIT}-manifest missing: {missing}")
        return 1
    doc = {
        "schema_version": 2,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit manifest (command-center/p2-wave/probes/AUD-0095)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "registered_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "artifacts": artifacts,
    }
    (REPO / MANIFEST_REL).write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"SUCCESS:{UNIT}-manifest {MANIFEST_REL} rows={len(artifacts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
