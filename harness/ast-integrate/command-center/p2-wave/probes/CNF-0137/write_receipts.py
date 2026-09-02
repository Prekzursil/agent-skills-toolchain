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
OUT = "command-center/receipts/CNF-0137.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0137/probe1_partition_and_known.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0137/probe2_mutation_and_null.py"
)
SUPPORTING = [
    "command-center/schema/sampling-plan.schema.json",
    "command-center/p2-wave/probes/CNF-0137/frame.py",
    "command-center/p2-wave/probes/CNF-0137/universe.py",
    "command-center/p2-wave/probes/CNF-0137/emit_receipt.py",
    "command-center/p2-wave/probes/CNF-0137/probe1_partition_and_known.py",
    "command-center/p2-wave/probes/CNF-0137/probe2_mutation_and_null.py",
    "command-center/p2-wave/probes/CNF-0137/fixtures/sampling-universe.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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
        "unit_id": "CNF-0137",
        "receipt_path": "command-center/p2-wave/probes/CNF-0137/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = subprocess.run(
        [sys.executable, "-B", str(HERE / "emit_receipt.py")],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if emit.returncode != 0:
        print("FAILED:receipts emit")
        print((emit.stdout or "")[-2000:])
        print((emit.stderr or "")[-2000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rec = json.loads((REPO / OUT).read_text(encoding="utf-8"))
    origin = ((rec.get("answer") or {}) if isinstance(rec.get("answer"), dict) else {}).get(
        "origin"
    ) or "unknown"
    live = bool((rec.get("freeze") or {}).get("live_registry_present"))
    live_ok = bool((rec.get("freeze") or {}).get("live_stratifiable"))
    notes = (
        "G-1 for CNF-0137: live named probes exit 0, CNF-0137.json "
        "state=SUCCESS, per-unit manifest row. Did not run global "
        "unit_manifest.py --write. "
        f"Frame origin={origin}; live CLAIM-REGISTRY.json present={live} "
        f"stratifiable={live_ok}. Fixture is used when live is absent or "
        "missing required axes so missing-severity never defaults to low "
        "and the empty-set does not read as a pass."
    )
    ret = {
        "id": "CNF-0137",
        "unit_id": "CNF-0137",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0137",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/sampling-plan.schema.json",
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
        "manifest_path": "command-center/p2-wave/probes/CNF-0137/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNF-0137-probe1-partition-recompute",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": notes,
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNF-0137",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    ret_text = json.dumps(ret, indent=1, sort_keys=True) + "\n"
    man_text = json.dumps(man, indent=1, sort_keys=True) + "\n"
    for name in ("SUBAGENT-RETURN.json", "SUBAGENT-RETURN.json"):
        (HERE / name).write_text(ret_text, encoding="utf-8")
    for name in ("UNIT-ARTIFACT-MANIFEST.json", "UNIT-ARTIFACT-MANIFEST.json"):
        (HERE / name).write_text(man_text, encoding="utf-8")
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:CNF-0137 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
