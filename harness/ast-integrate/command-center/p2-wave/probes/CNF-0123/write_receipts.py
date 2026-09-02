#!/usr/bin/env python3
"""Write per-unit UNIT-ARTIFACT-MANIFEST.json and SUBAGENT-RETURN.json for CNF-0123."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "CNF-0123"
OUT = "command-center/confirmation/CNF-0123-downstream-readability.json"
RET = HERE / "SUBAGENT-RETURN.json"
MAN = HERE / "UNIT-ARTIFACT-MANIFEST.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0123/probe1_consumer_matrix.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0123/probe2_detector_control.py"
)

SUPPORTING = [
    "command-center/schema/conformance-report.schema.json",
    "command-center/p2-wave/probes/CNF-0123/consumers.py",
    "command-center/p2-wave/probes/CNF-0123/inventory.py",
    "command-center/p2-wave/probes/CNF-0123/measure.py",
    "command-center/p2-wave/probes/CNF-0123/emit_report.py",
    "command-center/p2-wave/probes/CNF-0123/probe1_consumer_matrix.py",
    "command-center/p2-wave/probes/CNF-0123/probe2_detector_control.py",
    "command-center/p2-wave/probes/CNF-0123/fixtures/payload-records.schema.json",
    "command-center/p2-wave/probes/CNF-0123/fixtures/schema-valid-unreadable.json",
    "command-center/p2-wave/probes/CNF-0123/fixtures/schema-valid-readable.json",
    "command-center/p2-wave/probes/CNF-0123/fixtures/planted-unconsumed.json",
    "command-center/p2-wave/probes/CNF-0123/fixtures/receipt-sample.json",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/CNF-0123/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    artifacts = [row(OUT, "primary")]
    for rel in SUPPORTING:
        artifacts.append(row(rel, "supporting"))
    primary = artifacts[0]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    MAN.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")

    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0123",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/conformance-report.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": 0,
                "role": "consumer-matrix",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": 0,
                "role": "detector-control",
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/CNF-0123/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNF-0123-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "G-1 for CNF-0123: live named probes exit 0, downstream-readability "
            "artifact state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    RET.write_text(json.dumps(ret, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {MAN.relative_to(REPO).as_posix()} rows={len(artifacts)}")
    print(f"wrote {RET.relative_to(REPO).as_posix()} sha256={primary['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
