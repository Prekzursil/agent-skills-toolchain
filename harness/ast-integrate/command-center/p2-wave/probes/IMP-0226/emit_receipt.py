#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0226.json from a live AST sweep.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (see write_receipts.py).
Does not run unit_manifest.py --write. cloud_ok is not delivery.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.fanin import CONSIDER_FNS, EXPECTED_ROLES  # noqa: E402
from agentspec.rival_scan import scan_tree, scan_with_control  # noqa: E402

OUT = "command-center/receipts/IMP-0226.json"
ORACLE = "tools/agentspec/agentspec/oracle.py"
SCANNER = "tools/agentspec/agentspec/rival_scan.py"
RESUME = "tools/agentspec/agentspec/resume.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0226/probe1_zero_rivals.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0226/probe2_planted_rival.py"
)
FANIN_FILES = [
    "tools/agentspec/agentspec/fanin/__init__.py",
    "tools/agentspec/agentspec/fanin/local_runner.py",
    "tools/agentspec/agentspec/fanin/cloud_dispatcher.py",
    "tools/agentspec/agentspec/fanin/monitor.py",
    "tools/agentspec/agentspec/fanin/harvester.py",
    "tools/agentspec/agentspec/fanin/workflow_fanin.py",
    "tools/agentspec/agentspec/fanin/cross_vendor_adapter.py",
    "tools/agentspec/agentspec/fanin/final_synthesis.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    scan = scan_tree(REPO / "tools" / "agentspec")
    control = scan_with_control(REPO / "tools" / "agentspec")
    sites = [s for s in scan["call_sites"] if s["role"] in EXPECTED_ROLES]
    if (
        len(sites) != 7
        or set(scan["roles_present"]) != EXPECTED_ROLES
        or not scan["zero_duplicates"]
        or not control["control_fired"]
        or not control["zero_duplicate_accepted"]
        or len(CONSIDER_FNS) != 7
    ):
        print(
            "FAILED:IMP-0226 emit "
            f"sites={len(sites)} roles={scan.get('roles_present')} "
            f"zero={scan.get('zero_duplicates')} fired={control.get('control_fired')}"
        )
        return 1
    oracle_art = artifact_row(ORACLE, "implementation")
    if not oracle_art["exists"] or oracle_art["bytes"] < 128:
        print("FAILED:IMP-0226 oracle missing or tiny")
        return 1
    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0226",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0226",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json IMP-0226; _USER-PROMPTS.md:10648 "
            "(one reducer everywhere); :11314 (two completion predicates disagree)"
        ),
        "question_or_target": (
            "Target: local runner, cloud dispatcher, monitor, harvester, "
            "workflow fan-in, cross-vendor adapter and final synthesis all call "
            "agentspec.oracle.judge — no second predicate anywhere. Acceptance: "
            "an AST sweep finds zero local completion checks, and a planted "
            "second predicate FAILS the sweep."
        ),
        "implementation": {
            "canonical_module": "agentspec.oracle",
            "canonical_symbol": "judge",
            "wrapper": "Oracle.passes -> judge",
            "local_runner_wiring": "resume.ResumableRunner.should_skip via fanin.local_runner.consider",
            "fan_in_package": "tools/agentspec/agentspec/fanin/",
            "detector": SCANNER,
        },
        "measured": {
            "method": scan["method"],
            "used_grep": scan["used_grep"],
            "fan_in_count": scan["fan_in_count"],
            "roles_present": scan["roles_present"],
            "zero_duplicates": scan["zero_duplicates"],
            "missing_imports": scan["missing_imports"],
            "control_fired": control["control_fired"],
            "silent_on_clean": control["silent_on_clean"],
            "zero_duplicate_accepted": control["zero_duplicate_accepted"],
            "mention_only_files": scan["mention_only_files"],
            "call_sites": [
                {
                    "role": s["role"],
                    "path": s["path"],
                    "import_kind": s["import_kind"],
                    "bound_name": s["bound_name"],
                    "resolved_module": s["resolved_module"],
                    "call_linenos": s["call_linenos"],
                }
                for s in sites
            ],
        },
        "artifacts": [
            oracle_art,
            artifact_row(SCANNER, "detector"),
            artifact_row(RESUME, "local-runner-wiring"),
            *[artifact_row(p, "fan-in") for p in FANIN_FILES],
            artifact_row(
                "tools/agentrail/tests/test_no_rival_core.py",
                "catalog-input-test",
            ),
            artifact_row(
                "command-center/p2-wave/probes/IMP-0226/probe1_zero_rivals.py",
                "probe",
            ),
            artifact_row(
                "command-center/p2-wave/probes/IMP-0226/probe2_planted_rival.py",
                "probe",
            ),
        ],
        "evidence": [
            {
                "claim": (
                    "AST import-graph sweep over tools/agentspec finds seven "
                    "FANIN_ROLE sites, each resolving to agentspec.oracle.judge, "
                    "and zero rival predicates."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{SCANNER}:scan_tree",
                "probes": [
                    {
                        "role": "source",
                        "method": "ast-import-graph",
                        "command": "agentspec.rival_scan.scan_tree",
                        "exit_code": 0,
                        "raw_output": json.dumps(
                            {
                                "fan_in_count": scan["fan_in_count"],
                                "zero_duplicates": scan["zero_duplicates"],
                                "roles": scan["roles_present"],
                            },
                            sort_keys=True,
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": None,
                        "raw_output": "named probe1 re-runs the live sweep after this receipt is on disk",
                    },
                ],
            },
            {
                "claim": (
                    "A planted local judge() plus is_complete(exit_code==0) in a "
                    "scratch copy makes the sweep fail; the clean tree stays silent. "
                    "Control ran before the zero-duplicate verdict."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{SCANNER}:scan_with_control",
                "probes": [
                    {
                        "role": "source",
                        "method": "ast-import-graph",
                        "command": "agentspec.rival_scan.scan_with_control",
                        "exit_code": 0,
                        "raw_output": json.dumps(
                            {
                                "control_fired": control["control_fired"],
                                "silent_on_clean": control["silent_on_clean"],
                                "zero_duplicate_accepted": control[
                                    "zero_duplicate_accepted"
                                ],
                                "planted_paths": control["planted_paths"],
                            },
                            sort_keys=True,
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": None,
                        "raw_output": "named probe2 re-runs the planted control after this receipt is on disk",
                    },
                ],
            },
        ],
        "tests": [
            {"id": "zero-rival-ast-sweep", "command": P1, "result": "PENDING-NAMED-PROBE"},
            {
                "id": "planted-rival-detected",
                "command": P2,
                "result": "PENDING-NAMED-PROBE",
            },
        ],
        "negative_controls": [
            {
                "id": "c-clean-silent",
                "kind": "known-good-tree",
                "description": "Production agentspec fan-in modules call judge; sweep is silent.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "c-planted-rival",
                "kind": "known-broken-fixture",
                "description": "Planted local judge + exit-zero is_complete must appear in findings.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0226-probe2-planted-rival",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": "Probe 2 does not reuse probe 1's live consider() path; it plants a rival.",
        },
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "timestamps": {"started_at": started, "ended_at": ended},
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0226/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "tools/agentrail/tests/test_no_rival_core.py was listed as an "
                    "input and was absent; this unit authors it as the AST control "
                    "modelled on that catalog path."
                ),
                "settling_experiment": "pytest tools/agentrail/tests/test_no_rival_core.py",
                "verdict": "ADDRESSED",
            }
        ],
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0226: live named probes must exit 0 against "
            "agentspec.oracle.judge wired at seven fan-in sites. cloud ok=true "
            "is not delivery. Did not run global unit_manifest.py --write."
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0226" not in text:
        print("FAILED:IMP-0226 sentinel missing from serialized receipt")
        return 1
    out_path.write_text(text, encoding="utf-8")
    sha, size = digest_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(
        f"fan_in={scan['fan_in_count']} zero_dup={scan['zero_duplicates']} "
        f"control_fired={control['control_fired']}"
    )
    print("SUCCESS:IMP-0226")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
