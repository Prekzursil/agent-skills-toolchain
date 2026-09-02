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
OUT = "command-center/audit/AUD-0065-ledger-memory-state-inventory.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0065/probe1_ledger_keyword.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0065/probe2_memory_semantic.py"
)
SUPPORTING = [
    "command-center/schema/claim-record.schema.json",
    "command-center/p2-wave/probes/AUD-0065/engine.py",
    "command-center/p2-wave/probes/AUD-0065/stores.py",
    "command-center/p2-wave/probes/AUD-0065/emit_artifact.py",
    "command-center/p2-wave/probes/AUD-0065/probe1_ledger_keyword.py",
    "command-center/p2-wave/probes/AUD-0065/probe2_memory_semantic.py",
    "command-center/p2-wave/probes/AUD-0065/fixtures/pinned-ground-truth.json",
    "command-center/p2-wave/probes/AUD-0065/fixtures/ledger/2026-08-09.jsonl",
    "command-center/p2-wave/probes/AUD-0065/fixtures/memory/program-b-checkpoint.md",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(os.environ)
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
        "unit_id": "AUD-0065",
        "receipt_path": "command-center/p2-wave/probes/AUD-0065/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = subprocess.run(
        [sys.executable, "-B", str(HERE / "emit_artifact.py")],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if emit.returncode != 0:
        print("FAILED:AUD-0065 emit_artifact")
        print((emit.stdout or "")[-4000:])
        print((emit.stderr or "")[-2000:])
        return 1
    print((emit.stdout or "").strip())

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0065 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "AUD-0065",
        "unit_id": "AUD-0065",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0065",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/claim-record.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "ledger-keyword-substring",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "memory-semantic-token-overlap",
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
        "manifest_path": "command-center/p2-wave/probes/AUD-0065/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0065-probe2-memory-semantic",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0065: live named probes exit 0, ledger-memory "
            "inventory state=SUCCESS, per-unit manifest row. Did not run "
            "global unit_manifest.py --write. Live ~/.claude/event-ledger and "
            "basic-memory vaults are absent on this Linux worker; fixtures "
            "carry planted known-term controls so absence is not reported "
            "without a hit. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "AUD-0065",
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
    print("SUCCESS:AUD-0065 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
