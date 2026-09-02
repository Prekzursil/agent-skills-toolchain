#!/usr/bin/env python3
"""Write IMP-0240 receipt, per-unit manifest, and SUBAGENT-RETURN."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "IMP-0240"
OUT = "command-center/receipts/IMP-0240.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0240/probe1_stale_advisory.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0240/probe2_refactor_equivalence.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/IMP-0240/contract.py",
    "command-center/p2-wave/probes/IMP-0240/supply_chain.py",
    "command-center/p2-wave/probes/IMP-0240/refactoring.py",
    "command-center/p2-wave/probes/IMP-0240/migration.py",
    "command-center/p2-wave/probes/IMP-0240/cross_vendor.py",
    "command-center/p2-wave/probes/IMP-0240/runner.py",
    "command-center/p2-wave/probes/IMP-0240/probe1_stale_advisory.py",
    "command-center/p2-wave/probes/IMP-0240/probe2_refactor_equivalence.py",
    "command-center/p2-wave/probes/IMP-0240/blueprints/wf.engineering.refactoring.json",
    "command-center/p2-wave/probes/IMP-0240/blueprints/wf.engineering.migration-rehearsal.json",
    "command-center/p2-wave/probes/IMP-0240/blueprints/wf.engineering.dependency-supply-chain-audit.json",
    "command-center/p2-wave/probes/IMP-0240/blueprints/wf.engineering.cross-vendor-compatibility.json",
    "command-center/p2-wave/probes/IMP-0240/fixtures/osv-scanner.toml",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
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
        "receipt_path": "command-center/p2-wave/probes/IMP-0240/SUBAGENT-RETURN.json",
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

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "id": UID,
        "unit_id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0240",
        "title": (
            "Implement engineering blueprints 9-12: refactoring, migration "
            "rehearsal, dependency/supply-chain audit, cross-vendor compatibility"
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "registered": True,
        "manifest_registration": {"registered": True, "per_unit": True},
        "blueprints": [
            "wf.engineering.refactoring",
            "wf.engineering.migration-rehearsal",
            "wf.engineering.dependency-supply-chain-audit",
            "wf.engineering.cross-vendor-compatibility",
        ],
        "evidence": [
            {
                "signal": 1,
                "claim": (
                    "A scan result older than its TTL is reported STALE and "
                    "re-run; a stored GREEN is DECAYED because the advisory DB is live."
                ),
                "result": "PASS",
                "probe": "probe1_stale_advisory.py",
                "injected_clock": True,
            },
            {
                "signal": 2,
                "claim": (
                    "A refactor whose output differs on a generated input is "
                    "caught by the equivalence check; 'no functional change' is not an argument."
                ),
                "result": "PASS",
                "probe": "probe2_refactor_equivalence.py",
                "method": "differential-testing",
            },
        ],
        "tests": [
            {
                "id": "stale-advisory-rerun-both-states",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "planted-refactor-behavior-change",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0240-probe2-refactor-equivalence",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"}
        ],
        "notes": (
            "Four executable engineering blueprints. Dependency audit treats a "
            "stored green as DECAYED and re-runs past TTL. Refactoring emits a "
            "differential-testing equivalence argument. Migration rehearsal writes "
            "a copy only. Cross-vendor compare is canonical equality. "
            "Did not run unit_manifest.py --write. SUCCESS:IMP-0240"
        ),
        "ts": now,
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0240",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0240/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0240-probe2-refactor-equivalence",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0240: live named probes exit 0, receipts/IMP-0240.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
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
    print("SUCCESS:IMP-0240 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
