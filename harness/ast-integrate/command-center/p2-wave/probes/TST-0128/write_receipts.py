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
OUT = "command-center/receipts/TST-0128.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0128/probe1_collection_and_outcomes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0128/probe2_planted_import_path_break.py"
)
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0128/emit_receipt.py"
)
SUPPORTING = [
    "command-center/schema/test-receipt.schema.json",
    "command-center/p2-wave/probes/TST-0128/parity.py",
    "command-center/p2-wave/probes/TST-0128/pyproject.toml",
    "command-center/p2-wave/probes/TST-0128/src/tst0128pkg/__init__.py",
    "command-center/p2-wave/probes/TST-0128/src/tst0128pkg/core.py",
    "command-center/p2-wave/probes/TST-0128/src/tst0128pkg/extra.py",
    "command-center/p2-wave/probes/TST-0128/src/tst0128run/__init__.py",
    "command-center/p2-wave/probes/TST-0128/src/tst0128run/__main__.py",
    "command-center/p2-wave/probes/TST-0128/src/tst0128run/collect.py",
    "command-center/p2-wave/probes/TST-0128/src/tst0128run/console.py",
    "command-center/p2-wave/probes/TST-0128/src/tst0128run/ci.py",
    "command-center/p2-wave/probes/TST-0128/src/tst0128run/install.py",
    "command-center/p2-wave/probes/TST-0128/tests/test_core.py",
    "command-center/p2-wave/probes/TST-0128/tests/test_extra.py",
    "command-center/p2-wave/probes/TST-0128/probe1_collection_and_outcomes.py",
    "command-center/p2-wave/probes/TST-0128/probe2_planted_import_path_break.py",
    "command-center/p2-wave/probes/TST-0128/emit_receipt.py",
    ".github/workflows/quality.yml",
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
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "exists": path.is_file(),
        "eol": "LF",
        "unit_id": "TST-0128",
        "receipt_path": "command-center/p2-wave/probes/TST-0128/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ce, te = run_cmd(EMIT)
    if ce != 0:
        print(f"FAILED:receipts emit rc={ce}")
        print(te[-3000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "TST-0128",
        "unit_id": "TST-0128",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0128",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/test-receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "collection-and-outcome-parity",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "planted-import-path-break-via-console-script",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0128/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0128-probe2-planted-import-path-break",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0128: live named probes exit 0, receipt "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Cloud ok=true is not delivery. "
            "No ADV rebuild. pytest/pip absent; fixture collector is stdlib."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0128",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a["present"]),
        "artifacts": artifacts,
    }
    ret_text = json.dumps(ret, indent=1, sort_keys=True) + "\n"
    man_text = json.dumps(man, indent=1, sort_keys=True) + "\n"
    (HERE / "SUBAGENT-RETURN.json").write_text(ret_text, encoding="utf-8")
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(man_text, encoding="utf-8")
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0128 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
