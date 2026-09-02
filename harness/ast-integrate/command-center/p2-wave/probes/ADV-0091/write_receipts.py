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
sys.path.insert(0, str(HERE))
import constants as C  # noqa: E402

EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0091/emit_artifact.py"
)
SUPPORTING = [
    C.SCHEMA_REL,
    "command-center/p2-wave/probes/ADV-0091/harness.py",
    "command-center/p2-wave/probes/ADV-0091/constants.py",
    "command-center/p2-wave/probes/ADV-0091/probe1_primed_transcript.py",
    "command-center/p2-wave/probes/ADV-0091/probe2_outcome_delta.py",
    "command-center/p2-wave/probes/ADV-0091/emit_artifact.py",
    "command-center/p2-wave/probes/ADV-0091/fixtures/councils.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(C.REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = C.REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "ADV-0091",
        "receipt_path": "command-center/p2-wave/probes/ADV-0091/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ce, te = run_cmd(EMIT)
    if ce != 0:
        print(f"FAILED:ADV-0091 receipts emit c={ce}")
        print(te[-2500:])
        return 1
    c1, t1 = run_cmd(C.P1_CMD)
    c2, t2 = run_cmd(C.P2_CMD)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0091 receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(C.OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "ADV-0091",
        "unit_id": "ADV-0091",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0091",
        "registered": True,
        "output_path": C.OUT_REL,
        "output_schema": C.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": C.P1_CMD,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": C.P2_CMD,
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0091/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0091-probe2-outcome-delta",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0091: live named probes exit 0, instant-unanimity "
            "trigger artifact state=SUCCESS, per-unit manifest row. Did not run "
            "global unit_manifest.py --write. No ADV rebuild circle. cloud_ok "
            "is false and is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ADV-0091",
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
    print("SUCCESS:ADV-0091 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
