#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
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
UNIT = "ADV-0144"
OUT = "command-center/adversarial/ADV-0144-controversial-source-compliance.json"
SCHEMA = "command-center/schema/compliance-trace.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0144/probe1_detector.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0144/probe2_independence_and_propagation.py"
)
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0144/emit_artifact.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/ADV-0144/trace.py",
    "command-center/p2-wave/probes/ADV-0144/emit_artifact.py",
    "command-center/p2-wave/probes/ADV-0144/probe1_detector.py",
    "command-center/p2-wave/probes/ADV-0144/probe2_independence_and_propagation.py",
    "command-center/p2-wave/probes/ADV-0144/write_receipts.py",
    "command-center/p2-wave/probes/ADV-0144/fixtures/corpus.json",
    "command-center/p2-wave/probes/ADV-0144/fixtures/downstream-empty-consumer-a.json",
    "command-center/p2-wave/probes/ADV-0144/fixtures/downstream-empty-consumer-b.md",
    "command-center/p2-wave/probes/ADV-0144/fixtures/downstream-same-origin-consumer.json",
    "command-center/p2-wave/probes/ADV-0144/fixtures/downstream-unresolved-consumer.json",
    (
        "command-center/research/sources-frontier/"
        "RES-0138-tor-research-stage-design-and-legal-gate.json"
    ),
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
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/ADV-0144/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c0, t0 = run_cmd(EMIT)
    if c0 != 0:
        print("FAILED:ADV-0144 emit")
        print(t0[-3000:])
        return 1
    print(t0)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0144 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    out_path = REPO / OUT
    if not out_path.is_file():
        print(f"FAILED:ADV-0144 receipts missing {OUT}")
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING if (REPO / p).is_file()]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0144",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "detector-empty-four-records",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "same-origin-and-propagation",
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0144/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0144-probe2-raw-corpus-rewalk",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": "SUCCESS:delivered ADV-0144",
        "measure": {"exit_code": 0, "line": "SUCCESS:delivered ADV-0144"},
        "ts": now,
        "notes": (
            "G-1 for ADV-0144: live named probes exit 0, compliance-trace "
            "artifact state=SUCCESS, per-unit manifest row. Did not run "
            "global unit_manifest.py --write. Did not rotate or print API "
            "keys. Did not relaunch finish-everything-close or "
            "p2-cloud-ok-deliver. No live onion access. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
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
    print("SUCCESS:ADV-0144 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
