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
UID = "TST-0019"
OUT = "command-center/receipts/TST-0019.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0019/probe1_self_match.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0019/probe2_both_states.py"
)
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0019/emit_receipt.py"
)
SUPPORTING = [
    "command-center/schema/detector-control.schema.json",
    "command-center/p2-wave/probes/TST-0019/session_probe.py",
    "command-center/p2-wave/probes/TST-0019/scenario.py",
    "command-center/p2-wave/probes/TST-0019/emit_receipt.py",
    "command-center/p2-wave/probes/TST-0019/schema_local.py",
    "command-center/p2-wave/probes/TST-0019/probe1_self_match.py",
    "command-center/p2-wave/probes/TST-0019/probe2_both_states.py",
    "command-center/p2-wave/probes/TST-0019/fixtures/decoy_session.py",
    "command-center/p2-wave/probes/TST-0019/fixtures/win32_dead_session.json",
    "command-center/p2-wave/probes/TST-0019/fixtures/win32_live_session.json",
    "command-center/p2-wave/probes/TST-0019/captures/before_unguarded.json",
    "command-center/p2-wave/probes/TST-0019/captures/after_guarded.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
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
        "present": path.is_file(),
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/TST-0019/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ce, te = run_cmd(EMIT)
    if ce != 0:
        print(f"FAILED:receipts emit c={ce}")
        print(te[-4000:])
        return 1
    print(te.splitlines()[-4:])
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    if not primary["present"] or primary["bytes"] <= 0:
        print("FAILED:receipts primary missing")
        return 1
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in artifacts if not a["present"]]
    if missing:
        print("FAILED:receipts missing", missing)
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0019",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/detector-control.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "self-match-before-after",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "both-states-controls",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0019/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0019-probe2-both-states",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0019: live named probes exit 0, receipts/TST-0019.json "
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
        "present": sum(1 for a in artifacts if a.get("present") is True),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0019 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
