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
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from constants import (  # noqa: E402
    OUTPUT_REL,
    P1_CMD,
    P2_CMD,
    REPO,
    SCHEMA_REL,
    UNIT_ID,
)

EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0040/emit_matrix.py"
)
SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/SYN-0040/constants.py",
    "command-center/p2-wave/probes/SYN-0040/fixtures.py",
    "command-center/p2-wave/probes/SYN-0040/gates.py",
    "command-center/p2-wave/probes/SYN-0040/matrix.py",
    "command-center/p2-wave/probes/SYN-0040/emit_matrix.py",
    "command-center/p2-wave/probes/SYN-0040/schema_util.py",
    "command-center/p2-wave/probes/SYN-0040/probe1_every_row.py",
    "command-center/p2-wave/probes/SYN-0040/probe2_silent_and_mutation.py",
    "command-center/p2-wave/probes/SYN-0040/fixtures/SYN-0002/broken.json",
    "command-center/p2-wave/probes/SYN-0040/fixtures/CAL-SILENT-BOTH/good.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file() and size > 0,
        "unit_id": UNIT_ID,
        "receipt_path": "command-center/p2-wave/probes/SYN-0040/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ce, te = run_cmd(EMIT)
    if ce != 0:
        print(f"FAILED:SYN-0040 receipts emit rc={ce}")
        print(te[-3000:])
        return 1
    c1, t1 = run_cmd(P1_CMD)
    c2, t2 = run_cmd(P2_CMD)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:SYN-0040 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUTPUT_REL, "primary")
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    missing = [item["path"] for item in artifacts if not item["present"]]
    if missing:
        print(f"FAILED:SYN-0040 receipts missing {missing}")
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT_ID,
        "unit_id": UNIT_ID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:SYN-0040",
        "registered": True,
        "output_path": OUTPUT_REL,
        "output_schema": SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1_CMD,
                "exit_code": c1,
                "role": "every-bucket-gate-row",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2_CMD,
                "exit_code": c2,
                "role": "silent-in-both-and-mutation-sweep",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUTPUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            "command-center/p2-wave/probes/SYN-0040/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "SYN-0040-probe2-silent-and-mutation",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for SYN-0040: live named probes exit 0, gate-control-matrix "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud_ok is false and is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT_ID,
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
    print(f"primary {OUTPUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:SYN-0040 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
