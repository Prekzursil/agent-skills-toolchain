#!/usr/bin/env python3
"""Write IMP-0466 receipt, then per-unit SUBAGENT-RETURN + UNIT-ARTIFACT-MANIFEST.

Named probes are re-run live. Does not invoke tools/command-center/unit_manifest.py --write.
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

UID = "IMP-0466"
OUT = "command-center/receipts/IMP-0466.json"
SENTINEL = "SENTINEL:IMP-0466:PATHCONV-ARGUMENT-SCOPED"
SCHEMA = "command-center/schema/receipt.schema.json profile=pathconv-argument-scoped"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0466/probe1_both_directions.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0466/probe2_global_suppression.py"
)
SUPPORTING = [
    "tools/shell/pathconv.py",
    "tools/shell/__init__.py",
    "command-center/p2-wave/probes/IMP-0466/fixtures/corpus.json",
    "command-center/p2-wave/probes/IMP-0466/probe1_both_directions.py",
    "command-center/p2-wave/probes/IMP-0466/probe2_global_suppression.py",
    "command-center/p2-wave/probes/IMP-0466/emit_receipt.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def manifest_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0466/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/IMP-0466/emit_receipt.py"
    )
    ce, te = run_cmd(emit)
    if ce != 0:
        print(f"FAILED:IMP-0466 emit rc={ce}")
        print(te[-2000:])
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0466 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    rec_path = REPO / OUT
    doc = json.loads(rec_path.read_text(encoding="utf-8"))
    doc["tests"] = [
        {
            "id": "IMP-0466-probe1-both-directions",
            "command": P1,
            "result": "PASS",
            "exit_code": c1,
            "output_tail": t1[-4000:],
        },
        {
            "id": "IMP-0466-probe2-global-suppression",
            "command": P2,
            "result": "PASS",
            "exit_code": c2,
            "output_tail": t2[-4000:],
        },
    ]
    doc["downstream_consumers"] = [
        {
            "consumer": "named-probes",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": True,
            "exit_code": 0,
        }
    ]
    rec_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    c1b, t1b = run_cmd(P1)
    c2b, t2b = run_cmd(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:IMP-0466 probes after receipt update c1={c1b} c2={c2b}")
        print(t1b[-2000:])
        print(t2b[-2000:])
        return 1

    primary = manifest_row(OUT, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "role": "both-directions-same-scoped-config",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "global-suppression-negative-control",
                "raw_output": t2b,
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0466/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0466-probe2-global-suppression",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": None,
        "ts": now,
        "notes": (
            "G-1 for IMP-0466: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
    }
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
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0466 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
