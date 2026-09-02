#!/usr/bin/env python3
"""Write WFA-0035 artifact, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import emit_report as E  # noqa: E402

UID = "WFA-0035"
OUT = E.OUT_REL
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0035/probe1_assignment_and_gaps.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0035/probe2_blind_discrimination.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/WFA-0035/taxonomy.py",
    "command-center/p2-wave/probes/WFA-0035/candidates.py",
    "command-center/p2-wave/probes/WFA-0035/assign.py",
    "command-center/p2-wave/probes/WFA-0035/discriminate.py",
    "command-center/p2-wave/probes/WFA-0035/emit_report.py",
    "command-center/p2-wave/probes/WFA-0035/probe1_assignment_and_gaps.py",
    "command-center/p2-wave/probes/WFA-0035/probe2_blind_discrimination.py",
    "command-center/p2-wave/probes/WFA-0035/fixtures/planted_candidates.json",
    "command-center/p2-wave/probes/WFA-0035/fixtures/on_tree_sources.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/WFA-0035/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    E.write_artifact()
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0035",
        "registered": True,
        "output_path": OUT,
        "output_schema": E.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "assignment-quotes-multi-class-zero-coverage-recount",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "blind-discrimination-both-states-floor-gate",
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
        "manifest_path": "command-center/p2-wave/probes/WFA-0035/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0035-probe2-blind-discrimination",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for WFA-0035: live named probes exit 0, honest non-BLOCKED "
            "ExtractionReport with SUCCESS:WFA-0035, per-unit manifest row. "
            "Did not run global unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a["present"]),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:WFA-0035 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
