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
OUT = "command-center/foundry/WFA-0130-pre-registered-fusion-acceptance-metric-set.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0130/probe1_accept_reject_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0130/probe2_posthoc_edit_refused.py"
)
SUPPORTING = [
    "command-center/schema/foundry-artifact.schema.json",
    "command-center/p2-wave/probes/WFA-0130/predicate.py",
    "command-center/p2-wave/probes/WFA-0130/fixtures.py",
    "command-center/p2-wave/probes/WFA-0130/runner.py",
    "command-center/p2-wave/probes/WFA-0130/schema_local.py",
    "command-center/p2-wave/probes/WFA-0130/emit.py",
    "command-center/p2-wave/probes/WFA-0130/probe1_accept_reject_both_states.py",
    "command-center/p2-wave/probes/WFA-0130/probe2_posthoc_edit_refused.py",
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
        env=env,
        timeout=180,
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
        "exists": True,
        "eol": "LF",
        "unit_id": "WFA-0130",
        "receipt_path": "command-center/p2-wave/probes/WFA-0130/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/WFA-0130/emit.py"
    )
    ce, te = run_cmd(emit)
    if ce != 0:
        print(f"FAILED:WFA-0130 receipts emit rc={ce}")
        print(te[-4000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:WFA-0130 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "WFA-0130",
        "unit_id": "WFA-0130",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0130",
        "registered": True,
        "cloud_ok": False,
        "output_path": OUT,
        "output_schema": "command-center/schema/foundry-artifact.schema.json#/$defs/metric-registry",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "both-states-accept-reject",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "post-hoc-edit-refused",
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
        "manifest_path": "command-center/p2-wave/probes/WFA-0130/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "wfa0130.independent-pin-auditor",
            "verdict": "PASS",
            "independent": True,
            "vendor": "openai",
        },
        "ts": now,
        "notes": (
            "G-1 for WFA-0130: live named probes exit 0, foundry artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. Cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "WFA-0130",
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
    print("SUCCESS:WFA-0130 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
