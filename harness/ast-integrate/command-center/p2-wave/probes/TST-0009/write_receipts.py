#!/usr/bin/env python3
"""Write TST-0009 receipt, SUBAGENT-RETURN.json, and per-unit manifest.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/TST-0009.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0009/probe1_file_line_beyond_eof_and_command.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0009/probe2_inferred_named_source.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0009/resolver.py",
    "command-center/p2-wave/probes/TST-0009/corpus.py",
    "command-center/p2-wave/probes/TST-0009/controls.py",
    "command-center/p2-wave/probes/TST-0009/harvest-snapshot.json",
    "command-center/p2-wave/probes/TST-0009/fixtures/five_lines.txt",
    "command-center/p2-wave/probes/TST-0009/probe1_file_line_beyond_eof_and_command.py",
    "command-center/p2-wave/probes/TST-0009/probe2_inferred_named_source.py",
    "command-center/p2-wave/probes/TST-0009/emit_receipt.py",
    "command-center/schema/conformance-report.schema.json",
    "tools/completion/reducer.py",
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
        timeout=300,
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
        "unit_id": "TST-0009",
        "receipt_path": "command-center/p2-wave/probes/TST-0009/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/TST-0009/emit_receipt.py"
    )
    c0, t0 = run_cmd(emit)
    if c0 != 0:
        print("FAILED:TST-0009 emit_receipt")
        print(t0[-3000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0009 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "TST-0009",
        "unit_id": "TST-0009",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0009",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/conformance-report.schema.json",
        "cloud_ok": False,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "file-line-beyond-eof-and-command-reexec",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "inferred-named-source-and-corpus-recount",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0009/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0009-probe2-inferred-named-source",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for TST-0009: live named probes exit 0, receipts/TST-0009.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. CLAIM-REGISTRY.json is absent; the "
            "per-anchor table is a freeze of the live receipt/confirmation "
            "harvest. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0009",
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
    print("SUCCESS:TST-0009 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
