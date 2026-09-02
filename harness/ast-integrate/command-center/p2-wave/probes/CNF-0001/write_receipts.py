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
OUT = "command-center/schema/confirmation-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0001/probe1_fixture_suite.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0001/probe2_empty_source_hole.py"
)
SUPPORTING = [
    "command-center/schema/discrepancy-record.schema.json",
    "command-center/schema/validate_confirmation_receipt.py",
    "command-center/p2-wave/probes/CNF-0001/probe1_fixture_suite.py",
    "command-center/p2-wave/probes/CNF-0001/probe2_empty_source_hole.py",
    "command-center/p2-wave/probes/CNF-0001/fixtures/neg-01-confirmed-empty-source.json",
    "command-center/p2-wave/probes/CNF-0001/fixtures/neg-02-same-probe-rerun.json",
    "command-center/p2-wave/probes/CNF-0001/fixtures/neg-03-missing-claim-id.json",
    "command-center/p2-wave/probes/CNF-0001/fixtures/neg-04-missing-confirmer.json",
    "command-center/p2-wave/probes/CNF-0001/fixtures/neg-05-missing-verbatim-output.json",
    "command-center/p2-wave/probes/CNF-0001/fixtures/neg-06-missing-residual.json",
    "command-center/p2-wave/probes/CNF-0001/fixtures/pos-01-complete-receipt.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
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
        "unit_id": "CNF-0001",
        "receipt_path": "command-center/p2-wave/probes/CNF-0001/SUBAGENT-RETURN.json",
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
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "CNF-0001",
        "unit_id": "CNF-0001",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": (
            "SUCCESS:CNF-0001 emitted only when the artifact at output_path exists, "
            "is non-empty, parses against output_schema, and all six negative fixtures "
            "exited non-zero and the positive fixture exited zero in the same invocation. "
            "Any other terminal state is FAILED:CNF-0001 <classification> with the "
            "diagnostic tail attached."
        ),
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/_meta/json-schema-2020-12.json",
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
        "manifest_path": "command-center/p2-wave/probes/CNF-0001/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNF-0001-probe2-empty-source-hole",
            "verdict": "PASS",
            "independent": True,
        },
        "question": "does a receipt with verdict=CONFIRMED and an EMPTY source_probe pass?",
        "answer": "NO",
        "ts": now,
        "notes": (
            "G-1 for CNF-0001: live named probes exit 0, confirmation-receipt "
            "schema is non-BLOCKED and contains the catalog sentinel, per-unit "
            "manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNF-0001",
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
    print("SUCCESS:CNF-0001 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
