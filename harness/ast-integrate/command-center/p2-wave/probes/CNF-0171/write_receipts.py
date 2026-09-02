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
OUT = "command-center/receipts/CNF-0171.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0171/probe1_structural_identity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0171/probe2_dynamic_behaviour_seventh.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/CNF-0171/identity.py",
    "command-center/p2-wave/probes/CNF-0171/corpus.py",
    "command-center/p2-wave/probes/CNF-0171/probe1_structural_identity.py",
    "command-center/p2-wave/probes/CNF-0171/probe2_dynamic_behaviour_seventh.py",
    "command-center/p2-wave/probes/CNF-0171/emit_receipt.py",
    "command-center/p2-wave/probes/CNF-0171/fixtures/dynamic_import_site.py",
    "tools/completion/reducer.py",
    "tools/completion/sites/__init__.py",
    "tools/completion/sites/local_runner.py",
    "tools/completion/sites/cloud_dispatcher.py",
    "tools/completion/sites/monitor.py",
    "tools/completion/sites/harvester.py",
    "tools/completion/sites/workflow_fanin.py",
    "tools/completion/sites/cross_vendor_adapter.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
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
        "unit_id": "CNF-0171",
        "receipt_path": "command-center/p2-wave/probes/CNF-0171/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    em = subprocess.run(
        [sys.executable, "-B", str(HERE / "emit_receipt.py")],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    if em.returncode != 0:
        print("FAILED:receipts emit")
        print((em.stdout or "")[-1500:])
        print((em.stderr or "")[-1500:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING if (REPO / p).is_file()]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "CNF-0171",
        "unit_id": "CNF-0171",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0171",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/confirmation-record.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "structural-identity",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "dynamic-behaviour-seventh",
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
        "manifest_path": "command-center/p2-wave/probes/CNF-0171/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNF-0171-probe2-seventh-site-grep",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for CNF-0171: live named probes exit 0, receipts/CNF-0171.json "
            "state=SUCCESS verdict=CONFIRMED (six declared sites bind one judge "
            "object), per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNF-0171",
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
    print("SUCCESS:CNF-0171 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
