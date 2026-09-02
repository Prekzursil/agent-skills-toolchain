#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/BLD-0030.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0030/probe1_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0030/probe2_reviewer.py"
)
SUPPORTING = [
    "command-center/schema/tag-position-audit.schema.json",
    "command-center/p2-wave/probes/BLD-0030/audit.py",
    "command-center/p2-wave/probes/BLD-0030/probe1_controls.py",
    "command-center/p2-wave/probes/BLD-0030/probe2_reviewer.py",
    "command-center/p2-wave/probes/BLD-0030/emit_receipt.py",
    "command-center/p2-wave/probes/BLD-0030/fixtures/control-inline.md",
    "command-center/p2-wave/probes/BLD-0030/fixtures/control-buried-short.md",
    "command-center/p2-wave/probes/BLD-0030/fixtures/control-no-tags.md",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
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
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/BLD-0030/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": "BLD-0030",
    }


def main() -> int:
    out = REPO / OUT
    if not out.is_file() or out.stat().st_size <= 0:
        print("FAILED:receipts missing " + OUT)
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "artifacts": [
            {
                "bytes": primary["bytes"],
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": primary["sha256"],
            }
        ],
        "cloud_ok": False,
        "id": "BLD-0030",
        "manifest_path": (
            "command-center/p2-wave/probes/BLD-0030/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1[-4000:],
                "role": "catalog-controls",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2[-4000:],
                "role": "independent-buried-review",
            },
        ],
        "notes": (
            "G-1 for BLD-0030: live named probes exit 0, receipts/BLD-0030.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/tag-position-audit.schema.json",
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "BLD-0030-probe2-reviewer",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:BLD-0030",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": "BLD-0030",
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": "BLD-0030",
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:BLD-0030 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
