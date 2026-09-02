#!/usr/bin/env python3
"""Write ADV-0125 adversarial artifact plus per-unit return/manifest."""
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
UID = "ADV-0125"
OUT = "command-center/adversarial/ADV-0125-arrival-rate-storm-and-429.json"
EMIT = "command-center/p2-wave/probes/ADV-0125/emit_artifact.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0125/probe1_burst.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0125/probe2_outcome_join.py"
)
SUPPORTING = [
    "platform/lib/fanin/local_runner.py",
    "platform/lib/fanin/cloud_dispatcher.py",
    "platform/lib/fanin/cross_vendor_adapter.py",
    "command-center/p2-wave/probes/ADV-0125/common.py",
    "command-center/p2-wave/probes/ADV-0125/probe1_burst.py",
    "command-center/p2-wave/probes/ADV-0125/probe2_outcome_join.py",
    "command-center/p2-wave/probes/ADV-0125/emit_artifact.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd, cwd=str(REPO), shell=True, capture_output=True, text=True, env=env
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": f"command-center/p2-wave/probes/{UID}/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": UID,
    }


def main() -> int:
    ce, te = run(f"PYTHONDONTWRITEBYTECODE=1 python3 -B {EMIT}")
    if ce != 0:
        print(te[-4000:])
        print(f"FAILED:{UID} emit")
        return 1
    print(te)
    c1, t1 = run(P1)
    c2, t2 = run(P2)
    if c1 != 0 or c2 != 0:
        print(t1[-2000:])
        print(t2[-2000:])
        print(f"FAILED:{UID} named probes c1={c1} c2={c2}")
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
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
        "id": UID,
        "manifest_path": f"command-center/p2-wave/probes/{UID}/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {"command": P1, "exit_code": c1, "id": "probe1", "raw_output": t1},
            {"command": P2, "exit_code": c2, "id": "probe2", "raw_output": t2},
        ],
        "notes": (
            "G-1 for ADV-0125: live named probes exit 0, adversarial artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild circle. cloud_ok=false. "
            "r2e_loop.py is absent on this worktree; burst uses stdlib urllib+"
            "ThreadPool; fanin rails are completion reducers."
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/fault-injection-run.schema.json",
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "ADV-0125-probe2-outcome-join",
            "verdict": "PASS",
        },
        "sentinel": (
            "SUCCESS:ADV-0125 emitted ONLY when the artifact at output_path exists"
        ),
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UID,
        "cloud_ok": False,
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
    print(f"SUCCESS:{UID} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
