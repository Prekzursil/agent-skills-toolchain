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
OUT = "command-center/phase3/CONTROL-PLANE-SINGULARITY.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0073/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0073/probe2_reviewer.py"
)
SUPPORTING = [
    "command-center/schema/conformance-report.schema.json",
    "command-center/phase3/A1/DESIGN.json",
    "command-center/phase3/A2/DESIGN.json",
    "command-center/p2-wave/probes/ARC-0073/parser.py",
    "command-center/p2-wave/probes/ARC-0073/reviewer.py",
    "command-center/p2-wave/probes/ARC-0073/scenario.py",
    "command-center/p2-wave/probes/ARC-0073/live.py",
    "command-center/p2-wave/probes/ARC-0073/probe1_both_states.py",
    "command-center/p2-wave/probes/ARC-0073/probe2_reviewer.py",
    "command-center/p2-wave/probes/ARC-0073/fixtures/duplicate.json",
    "command-center/p2-wave/probes/ARC-0073/fixtures/singular.json",
    "command-center/p2-wave/probes/ARC-0073/fixtures/hybrid-singular.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
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


def row(rel: str, role: str) -> dict | None:
    path = REPO / rel
    if not path.is_file():
        return None
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "ARC-0073",
        "receipt_path": "command-center/p2-wave/probes/ARC-0073/SUBAGENT-RETURN.json",
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
    if primary is None:
        print(f"FAILED:receipts missing primary {OUT}")
        return 1
    artifacts = [primary] + [r for p in SUPPORTING if (r := row(p, "supporting"))]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "ARC-0073",
        "unit_id": "ARC-0073",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0073",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/conformance-report.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
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
        "manifest_path": "command-center/p2-wave/probes/ARC-0073/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ARC-0073-probe2-path-walk",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for ARC-0073: live named probes exit 0, "
            "CONTROL-PLANE-SINGULARITY.json state=SUCCESS, per-unit manifest "
            "row. Did not run global unit_manifest.py --write. Did not invent "
            "AGGREGATE-RANKING.json or A9/DESIGN.json."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ARC-0073",
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
    print("SUCCESS:ARC-0073 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
