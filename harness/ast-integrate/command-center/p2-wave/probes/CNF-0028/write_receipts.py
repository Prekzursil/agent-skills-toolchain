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
OUT = "command-center/confirmation/CNF-0028-clean-venv-install.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0028/probe1_clean_venv.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0028/probe2_both_states.py"
)
SUPPORTING = [
    "command-center/schema/packaging-report.schema.json",
    "command-center/p2-wave/probes/CNF-0028/harness.py",
    "command-center/p2-wave/probes/CNF-0028/emit_report.py",
    "command-center/p2-wave/probes/CNF-0028/schema_check.py",
    "command-center/p2-wave/probes/CNF-0028/probe1_clean_venv.py",
    "command-center/p2-wave/probes/CNF-0028/probe2_both_states.py",
    "command-center/p2-wave/probes/CNF-0028/pkg/pyproject.toml",
    "command-center/p2-wave/probes/CNF-0028/pkg/src/cnf0028_fix/__init__.py",
    "command-center/p2-wave/probes/CNF-0028/pkg/src/cnf0028_fix/__main__.py",
    "command-center/p2-wave/probes/CNF-0028/pkg/src/cnf0028_fix/cli.py",
    "command-center/p2-wave/probes/CNF-0028/pkg/src/cnf0028_fix/data/payload.txt",
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
        "unit_id": "CNF-0028",
        "receipt_path": "command-center/p2-wave/probes/CNF-0028/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/CNF-0028/emit_report.py"
    )
    if emit[0] != 0:
        print(f"FAILED:receipts emit rc={emit[0]}")
        print(emit[1][-3000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "CNF-0028",
        "unit_id": "CNF-0028",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0028",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/packaging-report.schema.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
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
        "manifest_path": "command-center/p2-wave/probes/CNF-0028/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNF-0028-probe2-both-states-mutants",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for CNF-0028: live named probes exit 0, "
            "CNF-0028-clean-venv-install.json state=SUCCESS, per-unit manifest "
            "row. Did not run global unit_manifest.py --write. Clean-venv wheel "
            "install; both console-script and python -m; sys.path has no repo path."
        ),
        "emit_raw": emit[1],
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNF-0028",
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
    print("SUCCESS:CNF-0028 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
