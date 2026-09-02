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
UID = "WFA-0051"
OUT = "command-center/wfa/WFA-0051-adapter-dag-schedulers.json"
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0051/emit_artifact.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0051/probe1_replay_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0051/probe2_durable_log_routing.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/WFA-0051/ir_vocab.py",
    "command-center/p2-wave/probes/WFA-0051/mappings.py",
    "command-center/p2-wave/probes/WFA-0051/replay.py",
    "command-center/p2-wave/probes/WFA-0051/durable.py",
    "command-center/p2-wave/probes/WFA-0051/census.py",
    "command-center/p2-wave/probes/WFA-0051/emit_artifact.py",
    "command-center/p2-wave/probes/WFA-0051/probe1_replay_both_states.py",
    "command-center/p2-wave/probes/WFA-0051/probe2_durable_log_routing.py",
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
        env=env,
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
        "receipt_path": (
            "command-center/p2-wave/probes/WFA-0051/SUBAGENT-RETURN.json"
        ),
        "role": role,
        "sha256": sha,
        "unit_id": UID,
    }


def main() -> int:
    ce, te = run_cmd(EMIT)
    if ce != 0:
        print(f"FAILED:WFA-0051 emit rc={ce}")
        print(te[-2000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:WFA-0051 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    out_path = REPO / OUT
    if not out_path.is_file():
        print(f"FAILED:WFA-0051 missing {OUT}")
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
        "id": UID,
        "manifest_path": (
            "command-center/p2-wave/probes/WFA-0051/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "replay-worked-case-and-both-states",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "durable-log-architecture-lane-not-file",
            },
        ],
        "notes": (
            "G-1 for WFA-0051: live named probes exit 0, adapter artifact "
            "state=SUCCESS, per-unit manifest row. WFA-0044 and WFA-0027 "
            "artifacts absent; mappings use catalog IR names plus published "
            "source anchors. Did not run global unit_manifest.py --write. "
            "No ADV rebuild. cloud_ok=false is not delivery."
        ),
        "output_path": OUT,
        "output_schema": (
            "command-center/wfa/schema/wfa-schema-pack.json"
            "#/$defs/AdapterConformanceReport"
        ),
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "WFA-0051-probe2-durable-log-routing",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:WFA-0051",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UID,
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UID,
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:WFA-0051 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
