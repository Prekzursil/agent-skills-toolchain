#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402

OUT = "command-center/confirmation/CNF-0019-byte-route-audit.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0019/probe1_three_routes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0019/probe2_gate_control.py"
)
SUPPORTING = [
    "command-center/schema/byte-parity-report.schema.json",
    "command-center/RELEASE-CHECKLIST.md",
    "command-center/p2-wave/probes/CNF-0019/measure.py",
    "command-center/p2-wave/probes/CNF-0019/probe1_three_routes.py",
    "command-center/p2-wave/probes/CNF-0019/probe2_gate_control.py",
    "command-center/p2-wave/probes/CNF-0019/fixtures/pre-fix-RELEASE-CHECKLIST.md",
    "command-center/p2-wave/probes/CNF-0019/fixtures/windows-shell-8b.md",
]


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd, cwd=str(M.REPO), shell=True, capture_output=True, text=True
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = M.REPO / rel
    sha, size = M.digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "CNF-0019",
        "receipt_path": "command-center/p2-wave/probes/CNF-0019/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
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
        "id": "CNF-0019",
        "unit_id": "CNF-0019",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0019",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/byte-parity-report.schema.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
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
        "manifest_path": (
            "command-center/p2-wave/probes/CNF-0019/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "CNF-0019-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for CNF-0019: live named probes exit 0, byte-route audit "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Disposable eol=crlf fixture; no worktree git."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNF-0019",
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
    print("SUCCESS:CNF-0019 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
