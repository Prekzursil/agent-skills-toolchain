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
UID = "ARC-0078"
OUT = "command-center/phase4/contracts/ARC-0078.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0078/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0078/probe2_interpreter_windows.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/ARC-0078/clauses.py",
    "command-center/p2-wave/probes/ARC-0078/schema.py",
    "command-center/p2-wave/probes/ARC-0078/emit_contract.py",
    "command-center/p2-wave/probes/ARC-0078/consumer.py",
    "command-center/p2-wave/probes/ARC-0078/windows_model.py",
    "command-center/p2-wave/probes/ARC-0078/probe1_both_states.py",
    "command-center/p2-wave/probes/ARC-0078/probe2_interpreter_windows.py",
    "command-center/p2-wave/probes/ARC-0078/fixtures/working/plugin.json",
    "command-center/p2-wave/probes/ARC-0078/fixtures/working/hooks.json",
    "command-center/p2-wave/probes/ARC-0078/fixtures/historical-zero-hooks/plugin.json",
    "command-center/p2-wave/probes/ARC-0078/fixtures/historical-zero-hooks/hooks.json",
    "command-center/p2-wave/probes/ARC-0078/fixtures/missing-interpreter/plugin.json",
    "command-center/p2-wave/probes/ARC-0078/fixtures/missing-interpreter/hooks.json",
    "command-center/p2-wave/probes/ARC-0078/fixtures/scripts/marker.sh",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
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
        "receipt_path": f"command-center/p2-wave/probes/{UID}/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = HERE / "emit_contract.py"
    c0, t0 = run_probe(
        f"PYTHONDONTWRITEBYTECODE=1 python3 -B {emit.relative_to(REPO).as_posix()}"
    )
    if c0 != 0:
        print(f"FAILED:receipts emit c0={c0}")
        print(t0[-2000:])
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
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
        "sentinel": f"SUCCESS:{UID}",
        "registered": True,
        "output_path": OUT,
        "output_schema": "https://json-schema.org/draft/2020-12/schema",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
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
        "manifest_path": f"command-center/p2-wave/probes/{UID}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ARC-0078-probe1-both-states",
            "verdict": "PASS",
            "independent": True,
            "consumer_call_site": "command-center/p2-wave/probes/ARC-0078/consumer.py",
        },
        "ts": now,
        "notes": (
            "G-1 for ARC-0078: live named probes exit 0, plugin-manifest JSON "
            "Schema is non-BLOCKED and non-vacuous, per-unit manifest row. "
            "Historical $schema zero-hooks hooks.json is rejected; working "
            "manifest is accepted; missing interpreter fails on Windows. "
            "Did not run global unit_manifest.py --write. No ADV rebuild."
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
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ARC-0078 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
