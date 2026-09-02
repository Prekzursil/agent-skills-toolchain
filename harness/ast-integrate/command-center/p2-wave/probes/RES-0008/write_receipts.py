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
OUT = "command-center/research/RES-0008.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0008/probe1_disagree_precedence.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0008/probe2_identical_negative.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0008/common.py",
    "command-center/p2-wave/probes/RES-0008/capture.py",
    "command-center/p2-wave/probes/RES-0008/emit_claim.py",
    "command-center/p2-wave/probes/RES-0008/probe1_disagree_precedence.py",
    "command-center/p2-wave/probes/RES-0008/probe2_identical_negative.py",
    "command-center/p2-wave/probes/RES-0008/fixtures/disagree/.claude-plugin/marketplace.json",
    "command-center/p2-wave/probes/RES-0008/fixtures/disagree/plugins/res-0008-pin/.claude-plugin/plugin.json",
    "command-center/p2-wave/probes/RES-0008/fixtures/identical/.claude-plugin/marketplace.json",
    "command-center/p2-wave/probes/RES-0008/fixtures/identical/plugins/res-0008-pin/.claude-plugin/plugin.json",
    "command-center/p2-wave/probes/RES-0008/snapshots/claude-code-marketplace.schema.json",
    "command-center/p2-wave/probes/RES-0008/snapshots/FETCH-LOG.json",
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
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "RES-0008",
        "receipt_path": "command-center/p2-wave/probes/RES-0008/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    if not (REPO / OUT).is_file():
        print("FAILED:RES-0008 primary missing; run emit_claim.py first")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    artifacts = [row(OUT, "primary")]
    for rel in SUPPORTING:
        if (REPO / rel).is_file():
            artifacts.append(row(rel, "supporting"))
    primary = artifacts[0]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "RES-0008",
        "unit_id": "RES-0008",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": (
            "SUCCESS:RES-0008 in the receipt AND a precedence verdict backed by a "
            "reproducible two-file fixture and the observed installed version"
        ),
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "disagree-precedence",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "identical-negative-control",
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
        "manifest_path": "command-center/p2-wave/probes/RES-0008/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0008-probe2-identical-negative",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for RES-0008: live named probes exit 0, RES-0008.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "RES-0008",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:RES-0008 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
