#!/usr/bin/env python3
"""Write TST-0119 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""
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
UNIT = "TST-0119"
OUT = "command-center/receipts/TST-0119.json"
SENTINEL = "SUCCESS:TST-0119"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0119/probe1_baseline_per_module.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0119/probe2_gate_surviving_mutant.py"
)
SUPPORTING = [
    "command-center/schema/detector-control.schema.json",
    "tools/mutation/__init__.py",
    "tools/mutation/operators.py",
    "tools/mutation/runner.py",
    "tools/mutation/gate.py",
    "tools/mutation/tree.py",
    "command-center/p2-wave/probes/TST-0119/subjects/completion_predicate.py",
    "command-center/p2-wave/probes/TST-0119/subjects/detector.py",
    "command-center/p2-wave/probes/TST-0119/subjects/helper_util.py",
    "command-center/p2-wave/probes/TST-0119/subjects/tests.py",
    "command-center/p2-wave/probes/TST-0119/subjects/run_suite.py",
    "command-center/p2-wave/probes/TST-0119/probe1_baseline_per_module.py",
    "command-center/p2-wave/probes/TST-0119/probe2_gate_surviving_mutant.py",
    "command-center/p2-wave/probes/TST-0119/emit_receipt.py",
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


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0119/SUBAGENT-RETURN.json",
    }


def main() -> int:
    emit = subprocess.run(
        [sys.executable, "-B", str(HERE / "emit_receipt.py")],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        timeout=180,
    )
    if emit.returncode != 0:
        print("FAILED:TST-0119 receipts emit")
        print((emit.stdout or "")[-2000:])
        print((emit.stderr or "")[-2000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0119 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = art(OUT, "primary")
    if not primary["present"] or not primary["sha256"]:
        print("FAILED:TST-0119 primary missing")
        return 1
    rows = [primary] + [art(p, "supporting") for p in SUPPORTING]
    missing = [r["path"] for r in rows if not r["present"]]
    if missing:
        print(f"FAILED:TST-0119 missing artifacts {missing}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/detector-control.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "baseline-per-module-survival",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "gate-fails-on-predicate-survivor",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0119/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0119-probe2-gate-surviving-mutant",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0119: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Cloud ok=true is not delivery. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0119 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
