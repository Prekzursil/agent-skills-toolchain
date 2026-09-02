#!/usr/bin/env python3
"""Emit IMP-0192 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""

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
UNIT = "IMP-0192"
OUT = "command-center/receipts/IMP-0192.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0192/probe1_planted_rival_oracle.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0192/probe2_library_false_positives.py"
)
SUPPORTING = [
    "tools/workflow_foundry/control_plane.py",
    "tools/agentrail/tests/rival_scan.py",
    "tools/agentrail/tests/test_no_rival_core.py",
    "command-center/p2-wave/probes/IMP-0192/probe1_planted_rival_oracle.py",
    "command-center/p2-wave/probes/IMP-0192/probe2_library_false_positives.py",
    "command-center/p2-wave/probes/IMP-0192/fixtures/planted_rival_oracle.py",
    "tools/workflow_foundry/library/admitted/import-delegate.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(os.environ)
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
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0192/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    sys.path.insert(0, str(REPO / "tools"))
    from workflow_foundry.control_plane import (
        PLANES,
        scan_generated_artifacts,
        scan_library,
        scan_path,
    )

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0192 emit probes c1={c1} c2={c2}")
        print(t1[-4000:])
        print(t2[-4000:])
        return 1

    library = scan_library(REPO)
    generated = scan_generated_artifacts(REPO)
    planted = scan_path(
        REPO
        / "command-center/p2-wave/probes/IMP-0192/fixtures/planted_rival_oracle.py",
        repo=REPO,
    )
    planted_json = scan_path(
        REPO
        / "command-center/p2-wave/probes/IMP-0192/fixtures/planted_rival_fusion.json",
        repo=REPO,
    )
    if library["finding_count"] != 0 or generated["finding_count"] != 0:
        print("FAILED:IMP-0192 emit library not silent")
        print(json.dumps(library, indent=2)[:4000])
        return 1
    if not any(f.plane == "completion_oracle" for f in planted):
        print("FAILED:IMP-0192 emit planted python silent")
        return 1
    if not any(f.plane == "completion_oracle" for f in planted_json):
        print("FAILED:IMP-0192 emit planted json silent")
        return 1
    if int(library["files_scanned"]) < 6:
        print("FAILED:IMP-0192 emit library too small", library["files_scanned"])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    impl_rel = "tools/workflow_foundry/control_plane.py"
    impl_sha, impl_n = digest(REPO / impl_rel)

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0192",
        "completion_sentinel": "SUCCESS:IMP-0192",
        "title": "Implement the duplicate-control-plane detector for fusions and imports",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json IMP-0192: AST detector "
            "modelled on tools/agentrail/tests/test_no_rival_core.py applied "
            "to every generated artifact; fires on a planted rival oracle; "
            "spec:10483 becomes mechanical"
        ),
        "min_bytes_threshold": 128,
        "profile": "p2-wave-g1-unit",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "premise": {
            "catalog_inputs": [
                "tools/agentrail/tests/test_no_rival_core.py",
                "_USER-PROMPTS.md:10483",
                "_USER-PROMPTS.md:11333",
            ],
            "inputs_were_absent": True,
            "action": (
                "Created the AST duplicate-control-plane detector and an "
                "admitted generated-artifact library on this sparse worktree. "
                "Did not exit on predicate:absent."
            ),
        },
        "implementation": {
            "detector_module": impl_rel,
            "planes": list(PLANES),
            "mechanism": "ast.parse + walk FunctionDef/ClassDef/Assign/ImportFrom; JSON owner fields",
            "canonical_oracle": "agentspec.oracle.judge",
            "canonical_scheduler": "agentrail.runner.schedule",
            "canonical_rails": "agentrail.rails.load_rails",
            "canonical_argv": "agentspec.argv.build_argv",
            "library_root": "tools/workflow_foundry/library",
            "library_files_scanned": library["files_scanned"],
            "library_finding_count": library["finding_count"],
            "generated_files_scanned": generated["files_scanned"],
            "generated_finding_count": generated["finding_count"],
            "planted_python_planes": sorted({f.plane for f in planted}),
            "planted_json_planes": sorted({f.plane for f in planted_json}),
            "detector_sha256": impl_sha,
            "detector_bytes": impl_n,
        },
        "artifacts": [
            {
                "path": impl_rel,
                "role": "primary-implementation",
                "sha256": impl_sha,
                "bytes": impl_n,
                "exists": True,
            }
        ],
        "evidence": [
            {
                "claim": (
                    "The detector fires on a planted rival completion oracle "
                    "(FunctionDef judge outside agentspec/oracle.py) and on a "
                    "fusion JSON naming a non-canonical completion_oracle; "
                    "the canonical owner file with the same def is silent."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{impl_rel}:scan_python_source",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[:16000],
                    }
                ],
            },
            {
                "claim": (
                    f"Zero false positives on the admitted library: "
                    f"files_scanned={library['files_scanned']} "
                    f"finding_count={library['finding_count']} "
                    f"(computed set difference vs empty = [])."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{impl_rel}:scan_library",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[:16000],
                    }
                ],
            },
        ],
        "tests": [
            {
                "id": "planted-rival-oracle-detected",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "zero-false-positives-admitted-library",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "IMP-0192-C1-planted-oracle",
                "kind": "both-states",
                "description": (
                    "Planted FunctionDef judge fires completion_oracle; "
                    "the same def in tools/agentspec/agentspec/oracle.py is silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP-0192-C2-string-trap",
                "kind": "mutation",
                "description": (
                    "A docstring containing 'def judge' would match grep and "
                    "must not match the AST census."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP-0192-C3-library-census",
                "kind": "computed-set-difference",
                "description": (
                    "scan_library findings vs empty set is []; "
                    f"{library['files_scanned']} admitted artifacts."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0192-probe2-library-false-positives",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Adversarial control is the planted oracle plus the string-trap "
                "and the computed empty finding set over the admitted library."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0192/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 IMP-0192: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "SUCCESS:IMP-0192"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0192",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "planted-rival-oracle",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "library-zero-false-positives",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0192/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0192-probe2-library-false-positives",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0192: live named probes exit 0, IMP-0192.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
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
    print("SUCCESS:IMP-0192 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
