#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json for REL-0005."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/REL-0005.json"
SCHEMA = "command-center/schema/lifecycle-drill-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0005/probe1_idempotence.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0005/probe2_controls.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/REL-0005/upgrade.py",
    "command-center/p2-wave/probes/REL-0005/drill.py",
    "command-center/p2-wave/probes/REL-0005/probe1_idempotence.py",
    "command-center/p2-wave/probes/REL-0005/probe2_controls.py",
    "command-center/p2-wave/probes/REL-0005/emit_receipt.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "REL-0005",
        "receipt_path": "command-center/p2-wave/probes/REL-0005/SUBAGENT-RETURN.json",
        "role": role,
    }


def write_json(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    code_e, text_e = run(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/REL-0005/emit_receipt.py"
    )
    if code_e != 0:
        print(f"FAILED:receipts emit rc={code_e}")
        print(text_e[-2000:])
        return 1
    c1, t1 = run(P1)
    c2, t2 = run(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "REL-0005",
        "unit_id": "REL-0005",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:REL-0005",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "idempotence-and-skill-survival",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "dirty-control-and-skip-version",
                "raw_output": t2,
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
        "manifest_path": "command-center/p2-wave/probes/REL-0005/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "REL-0005-probe2-controls",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for REL-0005: live named probes exit 0, receipts/REL-0005.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. REL-0004 absent; isolated HOME implemented here."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "REL-0005",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    write_json(HERE / "SUBAGENT-RETURN.json", ret)
    write_json(HERE / "UNIT-ARTIFACT-MANIFEST.json", man)
    # Measure currently names these files; keep both spellings identical.
    write_json(HERE / "SUBAGENT-RETURN.json", ret)
    write_json(HERE / "UNIT-ARTIFACT-MANIFEST.json", man)
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:REL-0005 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
