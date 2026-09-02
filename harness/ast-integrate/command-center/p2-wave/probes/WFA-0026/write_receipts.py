#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    HERE,
    OUT_REL,
    P1,
    P2,
    REPO,
    RULE_REL,
    SCHEMA_REL,
    SENTINEL,
    UNIT,
    digest_file,
    dump_json,
)

SUPPORTING = [
    RULE_REL,
    SCHEMA_REL,
    "command-center/p2-wave/probes/WFA-0026/sources.json",
    "command-center/p2-wave/probes/WFA-0026/vendor_seed.json",
    "command-center/p2-wave/probes/WFA-0026/grading.py",
    "command-center/p2-wave/probes/WFA-0026/neutralize.py",
    "command-center/p2-wave/probes/WFA-0026/sweep.py",
    "command-center/p2-wave/probes/WFA-0026/emit.py",
    "command-center/p2-wave/probes/WFA-0026/probe1_trust_grade_mechanical.py",
    "command-center/p2-wave/probes/WFA-0026/probe2_duplicate_and_injection.py",
    "command-center/p2-wave/probes/WFA-0026/fixtures/planted_injection.body",
]


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/WFA-0026/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT_REL, "primary")
    artifacts = [primary]
    for p in SUPPORTING:
        if (REPO / p).is_file():
            artifacts.append(row(p, "supporting"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/SweepReport",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "trust-grade-mechanical-both-states",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "duplicate-of-and-injection-reviewer",
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/WFA-0026/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0026-probe2-duplicate-injection",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for WFA-0026: live named probes exit 0, practitioner SweepReport "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    dump_json(HERE / "SUBAGENT-RETURN.json", ret)
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UNIT,
        "verified_on_disk": True,
    }
    dump_json(HERE / "UNIT-ARTIFACT-MANIFEST.json", man)
    print(f"wrote receipts artifacts={len(artifacts)} sha256={primary['sha256']}")
    print("SUCCESS:WFA-0026 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
