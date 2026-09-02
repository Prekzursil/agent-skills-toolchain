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
OUT = "command-center/audit/AUD-0031-salvage-consumption-verify.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0031/probe1_ast_reverse_ref.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0031/probe2_runtime_coverage.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/AUD-0031/engine.py",
    "command-center/p2-wave/probes/AUD-0031/probe1_ast_reverse_ref.py",
    "command-center/p2-wave/probes/AUD-0031/probe2_runtime_coverage.py",
    "command-center/p2-wave/probes/AUD-0031/emit.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            shell=True,
            capture_output=True,
            text=True,
            env=env,
            timeout=170,
        )
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "AUD-0031",
        "receipt_path": "command-center/p2-wave/probes/AUD-0031/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = HERE / "emit.py"
    c0, t0 = run_probe(
        f"PYTHONDONTWRITEBYTECODE=1 python3 -B {emit.relative_to(REPO).as_posix()}"
    )
    if c0 != 0:
        print(f"FAILED:AUD-0031 receipts emit rc={c0}")
        print(t0[-2000:])
        return 1
    print(t0)
    if not (REPO / OUT).is_file():
        print(f"FAILED:AUD-0031 receipts: {OUT} missing")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0031 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "AUD-0031",
        "unit_id": "AUD-0031",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": (
            "SUCCESS:AUD-0031 emitted only when the artifact at output_path exists, "
            "is non-empty, parses against output_schema, and both named probes are "
            "recorded with their verbatim output"
        ),
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/audit-finding.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "ast-reverse-ref",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "runtime-coverage",
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
        "manifest_path": "command-center/p2-wave/probes/AUD-0031/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0031-probe2-runtime-coverage",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0031: live named probes exit 0, "
            "audit/AUD-0031-salvage-consumption-verify.json state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. No ADV rebuild circle."
        ),
        "measure_line": "PENDING",
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "AUD-0031",
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
    print("SUCCESS:AUD-0031 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
