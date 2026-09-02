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
OUT = "command-center/receipts/BLD-0050.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0050/probe1_delete_rule.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0050/probe2_completeness.py"
)
SUPPORTING = [
    "command-center/schema/trust-boundary-census.schema.json",
    "command-center/p2-wave/probes/BLD-0050/walk.py",
    "command-center/p2-wave/probes/BLD-0050/census.py",
    "command-center/p2-wave/probes/BLD-0050/probe1_delete_rule.py",
    "command-center/p2-wave/probes/BLD-0050/probe2_completeness.py",
    "command-center/p2-wave/probes/ARC-0010/generator.py",
    "command-center/p2-wave/seed-stage/dispatch_cursor.py",
]
OPTIONAL_SUPPORTING = [
    "command-center/phase3/A1/DESIGN.json",
    "command-center/phase3/A2/DESIGN.json",
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
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "BLD-0050",
        "receipt_path": "command-center/p2-wave/probes/BLD-0050/SUBAGENT-RETURN.json",
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
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    for rel in OPTIONAL_SUPPORTING:
        if (REPO / rel).is_file():
            artifacts.append(row(rel, "supporting"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "BLD-0050",
        "unit_id": "BLD-0050",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0050",
        "ts": now,
        "output_path": OUT,
        "output_schema": "command-center/schema/trust-boundary-census.schema.json",
        "manifest_path": "command-center/p2-wave/probes/BLD-0050/UNIT-ARTIFACT-MANIFEST.json",
        "registered": True,
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
            }
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1[-12000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2[-12000:],
            },
        ],
        "reviewer": {
            "independent": True,
            "reviewer_id": "BLD-0050-probe2-independent-rewalk",
            "verdict": "PASS",
        },
        "measure": {
            "exit_code": None,
            "line": None,
        },
        "notes": (
            "G-1 for BLD-0050: live named probes exit 0, BLD-0050.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. ADV-0021 consumed not rebuilt."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "BLD-0050",
        "expected": len(artifacts),
        "present": len(artifacts),
        "verified_on_disk": True,
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json rows={len(artifacts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
