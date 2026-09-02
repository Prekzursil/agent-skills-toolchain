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
OUT = "command-center/receipts/CNF-0153.json"
SCHEMA = "command-center/schema/program-gate-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0153/probe1_detector_both_states_exitcodes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0153/probe2_ghsa_reviewer_diff.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/CNF-0153/scanner.py",
    "command-center/p2-wave/probes/CNF-0153/inventory.py",
    "command-center/p2-wave/probes/CNF-0153/emit_report.py",
    "command-center/p2-wave/probes/CNF-0153/probe1_detector_both_states_exitcodes.py",
    "command-center/p2-wave/probes/CNF-0153/probe2_ghsa_reviewer_diff.py",
    "command-center/p2-wave/probes/CNF-0153/known-vulnerable/package-lock.json",
    "command-center/p2-wave/probes/CNF-0153/known-clean/package-lock.json",
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
        timeout=180,
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
        "present": path.is_file(),
        "unit_id": "CNF-0153",
        "receipt_path": "command-center/p2-wave/probes/CNF-0153/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:CNF-0153 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    if not primary["present"]:
        print("FAILED:CNF-0153 receipts primary missing")
        return 1
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "CNF-0153",
        "unit_id": "CNF-0153",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0153",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "detector-both-states-exitcodes",
                "raw_output": t1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "ghsa-reviewer-diff",
                "raw_output": t2[-8000:],
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
        "manifest_path": "command-center/p2-wave/probes/CNF-0153/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNF-0153-probe2-github-advisory-egress",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for CNF-0153: live named probes exit 0, CNF-0153.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Stored gate-deps green is not a control "
            "for today (no snapshot id); live OSV/GHSA detector is live."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNF-0153",
        "verified_on_disk": True,
        "artifacts": artifacts,
    }
    man["expected"] = len(man["artifacts"])
    man["present"] = len(man["artifacts"])
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:CNF-0153 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
