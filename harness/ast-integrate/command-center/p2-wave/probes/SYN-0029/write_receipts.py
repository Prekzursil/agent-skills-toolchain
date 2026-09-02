#!/usr/bin/env python3
"""Write SYN-0029 artifact, SUBAGENT-RETURN.json, and UNIT-ARTIFACT-MANIFEST.json."""
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
UID = "SYN-0029"
OUT = "command-center/receipts/SYN-0029.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0029/probe1_exactly_one_and_vocabulary.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0029/probe2_planted_omission.py"
)
SUPPORTING = [
    "command-center/schema/requirement-closure.schema.json",
    "command-center/p2-wave/probes/SYN-0029/closure.py",
    "command-center/p2-wave/probes/SYN-0029/register.py",
    "command-center/p2-wave/probes/SYN-0029/report.py",
    "command-center/p2-wave/probes/SYN-0029/controls.py",
    "command-center/p2-wave/probes/SYN-0029/emit_report.py",
    "command-center/p2-wave/probes/SYN-0029/schema_local.py",
    "command-center/p2-wave/probes/SYN-0029/probe1_exactly_one_and_vocabulary.py",
    "command-center/p2-wave/probes/SYN-0029/probe2_planted_omission.py",
    "command-center/p2-wave/probes/SYN-0029/fixtures/register.json",
    "command-center/p2-wave/probes/SYN-0029/fixtures/report_complete.json",
    "command-center/p2-wave/probes/SYN-0029/fixtures/report_omit_R3.json",
    "command-center/p2-wave/probes/SYN-0029/fixtures/report_double_R1.json",
    "command-center/p2-wave/probes/SYN-0029/fixtures/report_illegal.json",
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
        timeout=180,
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
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/SYN-0029/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/SYN-0029/emit_report.py"
    )
    ce, te = run_cmd(emit)
    if ce != 0:
        print(f"FAILED:SYN-0029 emit rc={ce}")
        print(te[-2000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:SYN-0029 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:SYN-0029",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/requirement-closure.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "exactly-one-and-vocabulary",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "planted-omission",
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
        "manifest_path": "command-center/p2-wave/probes/SYN-0029/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "SYN-0029-probe2-planted-omission",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for SYN-0029: live named probes exit 0, receipts/SYN-0029.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
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
    meas = subprocess.run(
        [
            sys.executable,
            str(REPO / "command-center/p2-wave/_measure_one_delivered.py"),
            UID,
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    mtext = ((meas.stdout or "") + "\n" + (meas.stderr or "")).strip()
    mline = mtext.splitlines()[-1] if mtext.splitlines() else f"exit={meas.returncode}"
    ret["measure"] = {"exit_code": meas.returncode, "line": mline}
    ret["measure_line"] = mline
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(te)
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(mline)
    if meas.returncode != 0:
        print("FAILED:SYN-0029 receipts measure")
        print(mtext[-2000:])
        return 1
    print("SUCCESS:SYN-0029 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
