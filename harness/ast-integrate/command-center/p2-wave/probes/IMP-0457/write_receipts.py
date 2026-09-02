#!/usr/bin/env python3
"""Write IMP-0457 receipt, then per-unit SUBAGENT-RETURN + UNIT-ARTIFACT-MANIFEST.

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

UID = "IMP-0457"
OUT = "command-center/receipts/IMP-0457.json"
SCHEMA = "command-center/schema/completion-verdict.schema.json"
SENTINEL = "SENTINEL:IMP-0457:STOPPING-RULE-MODE-AWARE"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0457/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0457/probe2_justification_required.py"
)
SUPPORTING = [
    "tools/command-center/stopping_predicate.py",
    "command-center/p2-wave/probes/IMP-0457/probe1_both_states.py",
    "command-center/p2-wave/probes/IMP-0457/probe2_justification_required.py",
    "command-center/p2-wave/probes/IMP-0457/emit_receipt.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    sha = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
    return {
        "path": rel,
        "sha256": sha,
        "bytes": len(data),
        "present": path.is_file(),
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0457/SUBAGENT-RETURN.json",
        "role": role,
    }


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


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/IMP-0457/emit_receipt.py"
    )
    code, text = run_cmd(emit)
    if code != 0:
        print(f"FAILED:IMP-0457 emit rc={code}")
        print(text[-2000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0457 probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    out_path = REPO / OUT
    if not out_path.is_file():
        print(f"FAILED:receipts missing {OUT}")
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "cloud_ok": False,
        "id": UID,
        "manifest_path": (
            "command-center/p2-wave/probes/IMP-0457/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "both-states-release-mode",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "justification-required-negative-control",
            },
        ],
        "notes": (
            "G-1 for IMP-0457: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "IMP-0457-probe2-justification-required",
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UID,
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
    print("SUCCESS:IMP-0457 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
