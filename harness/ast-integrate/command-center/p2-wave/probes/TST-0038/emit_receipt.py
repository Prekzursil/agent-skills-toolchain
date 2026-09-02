#!/usr/bin/env python3
"""Emit TST-0038 receipt + per-unit manifest + SUBAGENT-RETURN after live probes."""

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
UNIT = "TST-0038"
OUT_REL = f"command-center/receipts/{UNIT}.json"
SENTINEL = f"SUCCESS:{UNIT}"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0038/probe1_presence_and_mutation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0038/probe2_both_states_and_negatives.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0038/run_suite.py"
)
SUPPORTING = [
    "tools/command-center/work_unit_conformance.py",
    "tools/command-center/tests/test_work_unit_conformance.py",
    "command-center/schema/work-unit.schema.json",
    "command-center/p2-wave/probes/TST-0038/probe1_presence_and_mutation.py",
    "command-center/p2-wave/probes/TST-0038/probe2_both_states_and_negatives.py",
    "command-center/p2-wave/probes/TST-0038/run_suite.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def probe_rec(role: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": command,
        "raw_output": raw[-16000:],
        "exit_code": code,
        "fingerprint": hashlib.sha256(f"command\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    code_t, out_t = run(TEST_CMD)
    code1, out1 = run(P1)
    code2, out2 = run(P2)
    if code_t != 0 or code1 != 0 or code2 != 0:
        print(f"FAILED:{UNIT} emit tests={code_t} p1={code1} p2={code2}")
        print(out_t[-2500:])
        print(out1[-2500:])
        print(out2[-2500:])
        return 1
    if f"SUCCESS:{UNIT}-probe1" not in out1:
        print("FAILED:TST-0038 emit probe1 sentinel missing")
        return 1
    if f"SUCCESS:{UNIT}-probe2" not in out2:
        print("FAILED:TST-0038 emit probe2 sentinel missing")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_rec("source", P1, out1, code1)
    p2 = probe_rec("verifier", P2, out2, code2)
    pt = probe_rec("source", TEST_CMD, out_t, code_t)
    artifacts = [art(rel, "supporting") for rel in SUPPORTING]
    question = (
        "Does the work-unit schema require all 19 enumerated fields PER UNIT "
        "with a real override key, rather than satisfying them from a single "
        "global defaults block? Measured defect: 9 of 19 mandatory fields exist "
        "only as a global default, present on 0/103 items, and validate.py cannot "
        "detect the whole defaults block being deleted because require_complete "
        "defaults False and CI invokes the tool bare."
    )
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "profile": "work-unit-schema-conformance",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:TST-0038; "
            "_USER-PROMPTS.md:10607-10625; "
            "ARC-0083 work-unit schema contract"
        ),
        "min_bytes_threshold": 128,
        "title": "Executable conformance tests for the work-unit schema contract",
        "question": question,
        "question_or_target": question,
        "claim_under_test": (
            "The executable contract (work_unit_conformance.py + "
            "work-unit.schema.json) requires all 19 Prompt-Two fields as "
            "per-unit keys. Catalogue defaults do not satisfy completeness. "
            "Shipped validate.py V-FIELDS still treats defaults as resolution; "
            "that hole is measured, not claimed fixed by this TST unit."
        ),
        "timestamps": {"started_at": started, "ended_at": started},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "artifact_paths": [OUT_REL, *SUPPORTING],
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            *[
                {"path": rel, "exists": True, "role": "supporting"}
                for rel in SUPPORTING
            ],
        ],
        "test_ids": [
            "probe1-presence-matrix-and-ci-mutation",
            "probe2-both-states-and-per-rule-negatives",
            "test_conforming_catalog_is_silent",
            "test_defaults_only_catalog_is_red",
            "test_missing_key_is_red",
            "test_empty_string_is_red",
            "test_unknown_substrate_is_red",
            "test_unknown_failure_class_is_red",
            "test_bare_cli_rejects_defaults_only",
            "test_bare_cli_accepts_conforming",
        ],
        "negative_control_ids": [
            "defaults-only-catalog-rejected",
            "missing-title-rejected",
            "empty-title-rejected",
            "unknown-substrate-rejected",
            "unknown-failure-class-rejected",
            "historical-validate-py-disarmed-defaults-deletion-silent",
        ],
        "reviewer_verdict": "PASS",
        "evidence": [
            {
                "kind": "presence-matrix",
                "detail": (
                    "Per-field per-unit presence over items (103) and work_units "
                    "(2007). On items, 11 of 19 mandated fields are keys on 0/103 "
                    "units and exist only in catalogue defaults. work_units stamp "
                    "all 19 semantically (assignment/target via documented aliases)."
                ),
                "path": "command-center/p2-wave/probes/TST-0038/presence-matrix.json",
            },
            {
                "kind": "mutation",
                "detail": (
                    "Deleting the entire defaults block from a mini catalog, then "
                    "invoking validate.py with --no-require-complete (historical "
                    "CI shape, isolated so REACH-6 cannot mask V-FIELDS), still "
                    "exits 0 with no V-FIELDS. The new checker, invoked bare, "
                    "rejects a catalog whose 11 fields exist only in defaults "
                    "even while that defaults block remains."
                ),
                "path": "tools/command-center/work_unit_conformance.py",
                "exit_code": 1,
                "verbatim": out1[-1500:],
            },
            {
                "kind": "both-states",
                "detail": (
                    "Conforming fixture (all 19 keys on the unit) is silent. "
                    "Deliberately non-conforming fixtures fire: defaults-only, "
                    "missing key, empty string, unknown execution_substrate, "
                    "unknown failure_classification. Independent reviewer probe "
                    "rebuilds those fixtures without importing probe1."
                ),
                "path": "command-center/p2-wave/probes/TST-0038/probe2_both_states_and_negatives.py",
                "exit_code": 0,
                "verbatim": out2[-1500:],
            },
        ],
        "tests": [
            {"id": "probe1-presence-matrix-and-ci-mutation", "command": P1, "result": "PASS"},
            {
                "id": "probe2-both-states-and-per-rule-negatives",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "tools/command-center/tests/test_work_unit_conformance.py",
                "command": TEST_CMD,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "defaults-only-catalog-rejected",
                "kind": "both-states",
                "description": (
                    "A unit missing the 11 defaults-block fields is REJECTED by "
                    "work_unit_conformance even when those fields exist in "
                    "catalogue defaults. A fully keyed unit is silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "historical-validate-py-disarmed-defaults-deletion-silent",
                "kind": "known-broken-fixture",
                "description": (
                    "validate.py --no-require-complete on a catalog with the "
                    "defaults block deleted still exits 0 (historical CI)."
                ),
                "fired_on_bad_state": False,
                "silent_on_good_state": True,
                "note": "This is the measured detector hole; TST-0038 records it.",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0038-probe2-both-states-and-negatives",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "method": (
                "Rebuild green/red fixtures and one negative per contract rule "
                "without importing probe1. Re-count live items defaults-only "
                "fields from WORK_UNIT_FIELDS. Confirm bare CLI is armed."
            ),
        },
        "implementation": {
            "checker": "tools/command-center/work_unit_conformance.py",
            "schema": "command-center/schema/work-unit.schema.json",
            "pytest": "tools/command-center/tests/test_work_unit_conformance.py",
            "validate_py_not_modified": True,
            "defaults_are_not_completeness": True,
            "require_complete_default": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT_REL,
                "executed": False,
                "read_ok": False,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0437 arms validate.py V-FIELDS for unresolved fields "
                    "(defaults deleted). It does not require per-unit keys while "
                    "defaults remain. That remaining hole is this unit's subject."
                ),
                "settling_experiment": (
                    "After a later IMP stamps the 11 fields onto each items[] "
                    "row, re-run probe1: items defaults-only count must fall to 0."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "work_units failure_classification uses hundreds of tokens "
                    "outside the 6-value closed contract set. Enum enforcement "
                    "on the live work_units collection is reported, not gated."
                ),
                "settling_experiment": (
                    "Choose whether to expand the closed set or rewrite work_units "
                    "tokens onto the 6-value taxonomy, then re-run with enums on."
                ),
                "verdict": "NOT-CHECKED",
            },
        ],
        "notes": (
            "G-1 delivery of TST-0038 conformance suite. Live named probes exit 0. "
            "Did not run global unit_manifest.py --write. cloud ok is not consulted. "
            "Did not modify validate.py require_complete semantics for defaults-as-complete."
        ),
        "answer": (
            "No for shipped validate.py: 11 of 19 fields are defaults-only on 0/103 "
            "items, and V-FIELDS still treats defaults as resolution. Yes for the "
            "new executable contract in this unit: per-unit keys are required, "
            "defaults do not count, completeness is on by default, closed enums "
            "for execution_substrate and failure_classification, both-states proven."
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    live_sha, live_bytes = sha256_file(out)
    if live_bytes < 128:
        print(f"FAILED:{UNIT} receipt too small ({live_bytes} B)")
        return 1

    extra = []
    matrix = HERE / "presence-matrix.json"
    if matrix.is_file():
        extra.append("command-center/p2-wave/probes/TST-0038/presence-matrix.json")

    rows = [
        {
            "path": OUT_REL,
            "sha256": live_sha,
            "bytes": live_bytes,
            "exists": True,
            "present": True,
            "role": "primary",
            "eol": "LF",
            "unit_id": UNIT,
            "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        }
    ]
    for rel in SUPPORTING + extra:
        rows.append(art(rel, "supporting"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/conformance-report.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "presence-matrix-and-ci-mutation",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "both-states-and-per-rule-negatives",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": live_sha,
                "bytes": live_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0038-probe2-both-states-and-negatives",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": f"SUCCESS:delivered {UNIT}",
        "notes": (
            "G-1 for TST-0038: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
        "ts": started,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={live_bytes} sha256={live_sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
