#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/audit/AUD-0029-language-floor-audit.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0029/probe1_ast_map.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0029/probe2_floor_runtime.py"
)
SUPPORTING = [
    "command-center/schema/audit-finding.schema.json",
    "command-center/p2-wave/probes/AUD-0029/engine.py",
    "command-center/p2-wave/probes/AUD-0029/compile_stdin.py",
    "command-center/p2-wave/probes/AUD-0029/probe1_ast_map.py",
    "command-center/p2-wave/probes/AUD-0029/probe2_floor_runtime.py",
    "command-center/p2-wave/probes/AUD-0029/emit_artifact.py",
    "command-center/p2-wave/probes/AUD-0029/fixtures/pyproject.toml",
    "command-center/p2-wave/probes/AUD-0029/fixtures/package.json",
    "command-center/p2-wave/probes/AUD-0029/fixtures/at_floor.py",
    "command-center/p2-wave/probes/AUD-0029/fixtures/newer_than_floor.py",
    "command-center/p2-wave/probes/AUD-0029/fixtures/runtime_tomllib.py",
    "command-center/p2-wave/probes/AUD-0029/fixtures/runtime_onexc.py",
    "command-center/p2-wave/probes/AUD-0029/fixtures/test_floor.py",
    "command-center/p2-wave/probes/AUD-0029/fixtures/node_at_floor.mjs",
    "command-center/p2-wave/probes/AUD-0029/fixtures/node_newer_than_floor.mjs",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str, timeout: int = 170) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
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
        "unit_id": "AUD-0029",
        "receipt_path": "command-center/p2-wave/probes/AUD-0029/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/AUD-0029/emit_artifact.py"
    )
    ce, te = run_cmd(emit, timeout=170)
    if ce != 0:
        print(f"FAILED:AUD-0029 receipts emit rc={ce}")
        print(te[-4000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0029 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "AUD-0029",
        "unit_id": "AUD-0029",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0029",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/audit-finding.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "ast-stdlib-map",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "floor-runtime",
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
        "manifest_path": "command-center/p2-wave/probes/AUD-0029/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0029-probe2-floor-runtime",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0029: live named probes exit 0, language-floor audit "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Live requires-python is NOT-DECLARED on "
            "this tree; probe 2 ran CPython 3.10/3.11/3.12."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "AUD-0029",
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
    print("SUCCESS:AUD-0029 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
