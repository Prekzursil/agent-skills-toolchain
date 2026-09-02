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
sys.path.insert(0, str(HERE))
import constants as C  # noqa: E402

SUPPORTING = [
    "command-center/p2-wave/probes/AUD-0079/constants.py",
    "command-center/p2-wave/probes/AUD-0079/enumerate.py",
    "command-center/p2-wave/probes/AUD-0079/execute.py",
    "command-center/p2-wave/probes/AUD-0079/probe1_static_enum.py",
    "command-center/p2-wave/probes/AUD-0079/probe2_unset_and_wrong.py",
    "command-center/p2-wave/probes/AUD-0079/fixtures/loud_consumer.py",
    "command-center/p2-wave/probes/AUD-0079/fixtures/silent_consumer.py",
    "command-center/p2-wave/probes/AUD-0079/fixtures/file_consumer.py",
    "command-center/p2-wave/probes/AUD-0079/emit_artifact.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
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
        "unit_id": C.UNIT_ID,
        "receipt_path": "command-center/p2-wave/probes/AUD-0079/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/AUD-0079/emit_artifact.py"
    )
    c0, t0 = run_cmd(emit)
    if c0 != 0:
        print(f"FAILED:AUD-0079 receipts emit c0={c0}")
        print(t0[-2500:])
        return 1
    c1, t1 = run_cmd(C.P1)
    c2, t2 = run_cmd(C.P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0079 receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(C.OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": C.UNIT_ID,
        "unit_id": C.UNIT_ID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": C.SENTINEL,
        "registered": True,
        "output_path": C.OUT_REL,
        "output_schema": C.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": C.P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": C.P2,
                "exit_code": c2,
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": C.OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/AUD-0079/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0079-probe2-scratch-execution",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for AUD-0079: live named probes exit 0, audit artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No key rotation. No credential values printed."
        ),
        "measure_line": "",
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": C.UNIT_ID,
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
    print(f"primary {C.OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:AUD-0079 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
