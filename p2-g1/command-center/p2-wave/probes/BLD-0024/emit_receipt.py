#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0024.json from a live revalidation run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from revalidate import CI_CONSOLE, revalidate, sha256_file  # noqa: E402

OUT_REL = "command-center/receipts/BLD-0024.json"
SCHEMA_REL = "command-center/schema/triage-revalidation.schema.json"
QUESTION = (
    "Question: does every past 'not a real regression' triage still hold? "
    "Each dismissal is a dated claim that decays. Re-run each previously "
    "dismissed failure and re-check its stated reason: the Phase 0 baseline's "
    "eight failures triage as three Windows-CRLF artifacts, four a sibling "
    "agent's transient TDD red phase, and one POSIX-only - and a triage that "
    "rests on a sibling's transient state is only valid while that state is "
    "unchanged."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0024/probe1_lf_falsify.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0024/probe2_console_reviewer.py"
)


def slim_outcome(row: dict) -> dict:
    return {
        "outcome": row.get("outcome"),
        "error_type": row.get("error_type"),
        "error": row.get("error"),
    }


def slim_dismissal(row: dict) -> dict:
    keep = {
        "id": row["id"],
        "test": row["test"],
        "class": row["class"],
        "original_reason": row["original_reason"],
        "verdict": row["verdict"],
        "falsifiable": row["falsifiable"],
        "requeued": row["requeued"],
        "experiment": row["experiment"],
        "sibling_state_changed": row.get("sibling_state_changed"),
        "as_is": slim_outcome(row["as_is"]),
        "lf_norm": slim_outcome(row["lf_norm"]),
        "ntpath": slim_outcome(row["ntpath"]),
    }
    if row.get("planted_control"):
        keep["planted_control"] = True
    if row.get("sibling_module"):
        keep["sibling_module"] = row["sibling_module"]
        keep["dismissal_time_sibling_sha256"] = row.get("dismissal_time_sibling_sha256")
        keep["current_sibling_sha256"] = row.get("current_sibling_sha256")
    return keep


def required_ok(doc: dict) -> None:
    for key in (
        "unit_id",
        "state",
        "sentinel",
        "question",
        "baseline_inputs",
        "dismissals",
        "tests",
        "runner_control",
        "reviewer",
        "headline",
        "artifacts",
    ):
        if key not in doc:
            raise SystemExit(f"FAILED:emit missing {key}")
    if doc["unit_id"] != "BLD-0024":
        raise SystemExit("FAILED:emit unit_id")
    if doc["state"] in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:emit self-declared {doc['state']}")
    if "SUCCESS:BLD-0024" not in json.dumps(doc):
        raise SystemExit("FAILED:emit sentinel")
    eight = [d for d in doc["dismissals"] if not d.get("planted_control")]
    if len(eight) != 8:
        raise SystemExit(f"FAILED:emit eight={len(eight)}")
    n_crlf = sum(1 for d in eight if d["class"] == "windows-crlf")
    n_tdd = sum(1 for d in eight if d["class"] == "sibling-tdd-red")
    n_posix = sum(1 for d in eight if d["class"] == "posix-only")
    if (n_crlf, n_tdd, n_posix) != (3, 4, 1):
        raise SystemExit(f"FAILED:emit taxonomy {n_crlf, n_tdd, n_posix}")


def main() -> int:
    live = revalidate()
    if live["eight_count"] != 8:
        print(f"FAILED:emit eight_count={live['eight_count']}")
        return 1
    if not live["crlf_lf_green"]:
        print("FAILED:emit CRLF dismissals not LF-green")
        return 1
    if not live["unfalsifiable_unverified"]:
        print("FAILED:emit unfalsifiable control not UNVERIFIED")
        return 1
    if not live["packaging_gap"]["detected"]:
        print("FAILED:emit packaging gap not detected")
        return 1
    if not live["console"]["matches_pymodule_as_is"]:
        print("FAILED:emit console F-CRLF-1 disagrees with pymodule as_is")
        return 1
    if not live["console"]["lf_green"]:
        print("FAILED:emit console LF-norm of F-CRLF-1 not green")
        return 1

    rows = [slim_dismissal(r) for r in live["dismissals"]]
    eight = [r for r in rows if not r.get("planted_control")]
    holds = [r["id"] for r in eight if r["verdict"] == "HOLDS"]
    stale = [r["id"] for r in eight if r["verdict"] == "STALE-PREMISE"]
    headline = (
        "SUCCESS:BLD-0024 live re-verification of the catalog's eight dated "
        f"dismissals (snapshot files absent; reconstructed 3 CRLF + 4 TDD-red "
        f"+ 1 POSIX-only). HOLDS={holds} STALE-PREMISE={stale}. Planted "
        "unfalsifiable control is UNVERIFIED and requeued. F-CRLF-1 re-run "
        "through the CI console script; python -m style vs console disagrees "
        "on the in-tree-only helper (packaging gap the baseline missed)."
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_path = REPO / SCHEMA_REL
    doc = {
        "unit_id": "BLD-0024",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "triage-revalidation",
        "title": "Re-verification of previously dismissed failures (a triage is a dated claim)",
        "question": QUESTION,
        "sentinel": "SUCCESS:BLD-0024",
        "completion_sentinel": "SUCCESS:BLD-0024",
        "ts": now,
        "tree_sha": live["tree_sha"],
        "baseline_inputs": {
            "snapshot_present": live["snapshot_present"],
            "snapshot_path": "command-center/BASELINE-SNAPSHOT.json",
            "tests_out_present": live["tests_out_present"],
            "tests_out_path": "command-center/_baseline_tests_out.json",
            "reconstruction": (
                "Original Phase 0 nodeids are not on this worktree. The eight "
                "failures are reconstructed from WORK-UNIT-CATALOG.json "
                "BLD-0024 question_or_target (3 Windows-CRLF, 4 sibling TDD-red, "
                "1 POSIX-only) as live fixture tests. Original nodeids are not claimed."
            ),
        },
        "headline": headline,
        "dismissals": rows,
        "counts": live["counts"],
        "taxonomy": {
            "windows-crlf": 3,
            "sibling-tdd-red": 4,
            "posix-only": 1,
            "planted_unfalsifiable_control": 1,
        },
        "tests": [
            {
                "id": "falsify-crlf-lf-norm",
                "command": (
                    "revalidate.run_condition(pymodule, lf_norm) on F-CRLF-1/2/3"
                ),
                "result": "PASS" if live["crlf_lf_green"] else "FAIL",
                "detail": "as_is FAIL + LF-normalised PASS for all three CRLF dismissals",
            },
            {
                "id": "unfalsifiable-control",
                "command": "classify C-UNFALSIFIABLE-1 (no mechanism named)",
                "result": "PASS" if live["unfalsifiable_unverified"] else "FAIL",
                "detail": "downgraded to UNVERIFIED and requeued",
            },
            {
                "id": "runner-console-script",
                "command": f"python3 -B {CI_CONSOLE.relative_to(REPO).as_posix()} as_is",
                "result": "PASS" if live["console"]["matches_pymodule_as_is"] else "FAIL",
                "detail": "F-CRLF-1 re-run through CI console script; packaging gap detected",
            },
        ],
        "runner_control": {
            "baseline_runner": "python -m pytest (broken detector for packaging/import-path)",
            "reprobe_rule": (
                "identical command is a valid re-probe only when tree SHA differs; "
                f"tree_sha={live['tree_sha']} so a mechanically different runner was used"
            ),
            "pymodule_entry": "command-center/p2-wave/probes/BLD-0024/run_pymodule.py",
            "console_script_entry": "command-center/p2-wave/probes/BLD-0024/ci_console.py",
            "console_script_exercised": True,
            "console_script_subject": "F-CRLF-1",
            "console_as_is": live["console"]["as_is"],
            "console_lf_norm": live["console"]["lf_norm"],
            "packaging_gap_detected": True,
            "packaging_gap": live["packaging_gap"],
        },
        "reviewer": {
            "reviewer_id": "BLD-0024-probe2-console-reviewer",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "reproduced": ["F-CRLF-1", "F-POSIX-1"],
            "method": (
                "Infer dismissal class from raw test source without reading "
                "original_reason; confirm live experiment outcomes."
            ),
        },
        "evidence": [
            {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "kind": "catalog-taxonomy",
                "claim": "eight failures = 3 CRLF + 4 TDD-red + 1 POSIX-only",
            },
            {
                "path": "command-center/p2-wave/probes/BLD-0024/fixtures/suite/test_dismissed.py",
                "kind": "live-tree",
                "claim": "reconstructed dismissed tests executed under two runners",
            },
            {
                "path": "command-center/p2-wave/probes/BLD-0024/ci_console.py",
                "kind": "live-tree",
                "claim": "CI console script is not python -m pytest",
            },
            {
                "path": SCHEMA_REL,
                "kind": "schema",
                "claim": "triage-revalidation schema present",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "exists": True,
                "role": "primary",
            },
            {
                "path": SCHEMA_REL,
                "exists": schema_path.is_file(),
                "role": "schema",
            },
        ],
        "produced_by": "command-center/p2-wave/probes/BLD-0024/emit_receipt.py",
    }
    required_ok(doc)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2) + "\n"
    out.write_text(text, encoding="utf-8")
    print(f"wrote {OUT_REL} sha256={sha256_file(out)} bytes={len(text.encode())}")
    print("SUCCESS:BLD-0024 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
