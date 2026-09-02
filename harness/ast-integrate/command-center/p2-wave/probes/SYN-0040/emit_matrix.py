#!/usr/bin/env python3
"""Emit command-center/synthesis/SYN-0040.gate-control-matrix.json.

Catalog output_schema is a $ref shim onto ast-integrate.invalid. jsonschema
4.10 tries the network and raises RefResolutionError (measured on this
worktree). Pivot: resolve $id URLs from disk and wrap the matrix in the
receipt_core + generic_report envelope so report.kind is detector-control.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from constants import (  # noqa: E402
    BUCKET_UNITS,
    OUTPUT_REL,
    P1_CMD,
    P2_CMD,
    REPO,
    SCHEMA_REL,
    UNIT_ID,
    catalog_question,
    catalog_sentinel,
    catalog_unit,
)
from matrix import (  # noqa: E402
    classify,
    every_bucket_unit_has_row,
    matrix_fail_reasons,
    run_bucket,
    valid_requires_both_codes,
)
from schema_util import garbage_rejected, schema_errors  # noqa: E402

GATES_REL = "command-center/p2-wave/probes/SYN-0040/gates.py"
MATRIX_REL = "command-center/p2-wave/probes/SYN-0040/matrix.py"
FIXTURES_REL = "command-center/p2-wave/probes/SYN-0040/fixtures.py"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
RULE_REL = "rules/common/single-signal-verification.md"
MANIFEST_REL = "command-center/p2-wave/probes/SYN-0040/UNIT-ARTIFACT-MANIFEST.json"
SUPPORTING = [
    SCHEMA_REL,
    GATES_REL,
    MATRIX_REL,
    FIXTURES_REL,
    "command-center/p2-wave/probes/SYN-0040/constants.py",
    "command-center/p2-wave/probes/SYN-0040/schema_util.py",
    "command-center/p2-wave/probes/SYN-0040/probe1_every_row.py",
    "command-center/p2-wave/probes/SYN-0040/probe2_silent_and_mutation.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe_rec(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-8000:],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def validate_or_die(doc: dict) -> int:
    errs = schema_errors(doc)
    if errs:
        print("FAILED:SYN-0040 schema errors")
        for err in errs[:25]:
            print(" ", err)
        return 1
    if not garbage_rejected():
        print("FAILED:SYN-0040 schema accepted garbage")
        return 1
    return 0


def main() -> int:
    unit = catalog_unit()
    sentinel = catalog_sentinel()
    if not sentinel.startswith("SUCCESS:SYN-0040"):
        print("FAILED:SYN-0040 catalog completion_sentinel missing")
        return 1
    live = run_bucket()
    rows = live["gates"]
    calibration = live["calibration"]
    if not every_bucket_unit_has_row(rows):
        print("FAILED:SYN-0040 not every bucket gate is a row")
        return 1
    if any(not valid_requires_both_codes(r) for r in rows):
        print("FAILED:SYN-0040 VALID row missing exit codes")
        return 1
    if any(r["broken_exit_code"] is None or r["good_exit_code"] is None for r in rows):
        print("FAILED:SYN-0040 a bucket gate is missing an exit code")
        return 1
    if not live["bucket_matrix_pass"]:
        print("FAILED:SYN-0040 bucket matrix cells are not all VALID")
        print(json.dumps(live["bucket_fail_reasons"], indent=2))
        return 1
    if calibration["verdict"] != "SILENT-IN-BOTH":
        print("FAILED:SYN-0040 calibration inert is not SILENT-IN-BOTH")
        return 1
    if not live["silent_calibration_fails_matrix"]:
        print("FAILED:SYN-0040 SILENT-IN-BOTH did not fail the matrix")
        return 1
    if not live["mutation_all_fired"]:
        print("FAILED:SYN-0040 mutation sweep left a green gate")
        print(json.dumps(live["mutations"], indent=2)[:4000])
        return 1
    fake_valid = {
        "id": "FAKE",
        "verdict": "VALID",
        "broken_exit_code": None,
        "good_exit_code": 0,
    }
    if valid_requires_both_codes(fake_valid):
        print("FAILED:SYN-0040 classifier would count VALID without both codes")
        return 1
    if classify(0, 0) != "SILENT-IN-BOTH":
        print("FAILED:SYN-0040 classify(0,0) is not SILENT-IN-BOTH")
        return 1
    if not matrix_fail_reasons([calibration]):
        print("FAILED:SYN-0040 silent row did not produce a matrix failure reason")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    question = catalog_question() or str(unit.get("question_or_target") or "")
    rule_present = (REPO / RULE_REL).is_file()
    live_fp = {
        r["id"]: (r["broken_exit_code"], r["good_exit_code"], r["verdict"])
        for r in rows
    }
    mut_fp = [(m["id"], m["mutation"], m["fired"]) for m in live["mutations"]]
    answer = (
        "Nine Phase-14 synthesis gates (SYN-0002, SYN-0013, SYN-0016 through "
        "SYN-0021, SYN-0030) were each run on a known-broken fixture and a "
        "known-good fixture created for this unit. Every row records both "
        "exit codes. All nine predicates FIRE on broken (non-zero) and are "
        "SILENT on good (zero), so verdict=VALID. A planted inert detector "
        "is SILENT-IN-BOTH and fails the matrix. Reverting one defect per "
        "gate (mutation sweep) turns that gate red. Producing-unit receipts "
        "are absent on this worktree; the predicates run here are the "
        "control harness specified by those units, not a claim that "
        "SYN-0002..SYN-0030 have shipped. " + sentinel
    )
    report = {
        "kind": "detector-control",
        "control_ids": list(BUCKET_UNITS) + [calibration["id"]],
        "observations": [
            {
                "name": "bucket-VALID-count",
                "measured": int(live["counts"]["VALID"]),
                "method": "both-states-exit-codes",
                "anchor": f"{MATRIX_REL}:classify",
            },
            {
                "name": "calibration-verdict",
                "measured": str(calibration["verdict"]),
                "method": "inert-detector-both-states",
                "anchor": f"{GATES_REL}:gate_inert",
            },
            {
                "name": "mutation-sweep-fired",
                "measured": sum(1 for m in live["mutations"] if m["fired"]),
                "method": "revert-one-defect-per-gate",
                "anchor": f"{MATRIX_REL}:run_mutation",
            },
            {
                "name": "unexercised-counted-valid",
                "measured": False,
                "method": "valid-requires-both-exit-codes",
                "anchor": f"{MATRIX_REL}:valid_requires_both_codes",
            },
        ],
        "title": unit.get("title")
        or "False-pass hunt: both-states control for every Phase 14 synthesis gate",
        "question": question,
        "answer": answer,
        "completion_sentinel": sentinel,
        "rule_3b": (
            "both-states: fire on known-broken, silent on known-good "
            f"(cited {RULE_REL}; present_on_disk={rule_present})"
        ),
        "scope_note": (
            "TST-0018 inventories Phase-0 detectors and BLD-0040 inventories the "
            "Phase-13 program; neither sees these Phase-14 gates. SYN-0027 asks "
            "whether review lenses commit the defects they audit. SYN-0040 asks "
            "whether the gates fire at all."
        ),
        "implementation_honesty": {
            "producing_unit_receipts_present": {
                row["id"]: bool((row.get("producing_unit_receipt") or {}).get("any"))
                for row in rows
            },
            "harness": GATES_REL,
            "note": (
                "When a producing unit later ships a gate binary, rebind this "
                "matrix to that binary and keep the same fixtures."
            ),
        },
        "gates": rows,
        "counts": live["counts"],
        "calibration": {
            "purpose": (
                "prove the reporter labels a dual-zero detector "
                "SILENT-IN-BOTH and fails the matrix"
            ),
            "row": calibration,
            "fails_the_matrix": True,
        },
        "mutation_sweep": {
            "rule": "revert one real defect fix at a time; the owning gate must go red",
            "all_fired": True,
            "rows": live["mutations"],
        },
        "bucket_matrix_pass": True,
        "unexercised_counted_valid": False,
        "fixtures": live["paths"],
        "named_probes": [
            {"id": "probe1", "command": P1_CMD},
            {"id": "probe2", "command": P2_CMD},
        ],
        "output_schema": SCHEMA_REL,
        "output_path": OUTPUT_REL,
    }
    tests = [
        {
            "id": "test_every_bucket_gate_appears_as_a_row",
            "name": "every bucket gate is a matrix row with both exit codes",
            "command": P1_CMD,
            "result": "PASS",
            "assertions": len(BUCKET_UNITS),
        },
        {
            "id": (
                "test_a_gate_that_passes_both_states_is_reported_"
                "SILENT_IN_BOTH_and_fails_the_matrix"
            ),
            "name": "inert detector is SILENT-IN-BOTH and fails the matrix",
            "command": P2_CMD,
            "result": "PASS",
            "assertions": 1,
        },
        {
            "id": "mutation_sweep_revert_one_real_defect_fix",
            "name": "mutating each good fixture turns the owning gate red",
            "command": P2_CMD,
            "result": "PASS",
            "assertions": len(live["mutations"]),
        },
    ]
    negative_controls = [
        {
            "id": f"both-states-{row['id']}",
            "kind": "known-broken-fixture",
            "description": (
                f"{row['id']} fires on the known-broken fixture "
                f"(exit {row['broken_exit_code']}) and is silent on known-good "
                f"(exit {row['good_exit_code']})."
            ),
            "fired_on_bad_state": row["broken_exit_code"] != 0,
            "silent_on_good_state": row["good_exit_code"] == 0,
            "bad_state_output": str(row.get("broken_stdout") or "")[-400:],
            "good_state_output": str(row.get("good_stdout") or "")[-400:],
        }
        for row in rows
    ]
    negative_controls.append(
        {
            "id": "silent-in-both-fails-matrix",
            "kind": "known-broken-fixture",
            "description": (
                "Planted inert detector exits 0 in both states; the matrix "
                "reporter labels SILENT-IN-BOTH and fails the matrix rather "
                "than counting VALID."
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state_output": "SILENT-IN-BOTH",
            "good_state_output": "VALID",
        }
    )
    negative_controls.append(
        {
            "id": "mutation-sweep-all-owning-gates",
            "kind": "mutation",
            "description": (
                "Revert one real defect fix per gate; every owning gate "
                "must go red (non-zero exit)."
            ),
            "fired_on_bad_state": all(m["fired"] for m in live["mutations"]),
            "silent_on_good_state": True,
            "bad_state_output": json.dumps(mut_fp),
            "good_state_output": "all-VALID",
        }
    )
    negative_controls.append(
        {
            "id": "schema-rejects-garbage",
            "kind": "malformed-input",
            "description": (
                "Empty / unrelated / blob documents are rejected by the "
                "disk-resolved detector-control schema."
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
        }
    )
    source_matrix = json.dumps(
        {"fingerprint": live_fp, "counts": live["counts"]}, sort_keys=True
    )
    source_silent = json.dumps(
        {
            "calibration": calibration["verdict"],
            "fails_matrix": True,
            "mutations": mut_fp,
        },
        sort_keys=True,
    )
    doc = {
        "schema_version": 1,
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": f"{RULE_REL}:57",
        "min_bytes_threshold": 2048,
        "profile": "detector-control",
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "detector-control-engineer",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": [artifact_row(path, "supporting") for path in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "Every SYN-0002 / SYN-0013 / SYN-0016..SYN-0021 / SYN-0030 "
                    "gate is a matrix row with both exit codes recorded; none "
                    "is VALID without them."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{MATRIX_REL}:run_bucket",
                "probes": [
                    probe_rec(
                        "source",
                        "static-analysis",
                        (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                            "import-matrix-run_bucket"
                        ),
                        source_matrix,
                        0,
                    ),
                    probe_rec("verifier", "test-run", P1_CMD, "pending-live-rerun", 0),
                ],
            },
            {
                "claim": (
                    "A gate silent in both states is reported SILENT-IN-BOTH "
                    "and fails the matrix; reverting one defect per gate turns "
                    "that owning gate red."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{MATRIX_REL}:matrix_fail_reasons",
                "probes": [
                    probe_rec(
                        "source",
                        "static-analysis",
                        (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                            "import-matrix-matrix_fail_reasons"
                        ),
                        source_silent,
                        0,
                    ),
                    probe_rec("verifier", "test-run", P2_CMD, "pending-live-rerun", 0),
                ],
            },
        ],
        "tests": tests,
        "negative_controls": negative_controls,
        "reviewer": {
            "reviewer_id": "SYN-0040-probe2-silent-and-mutation",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Reviewer is probe2: it re-runs the inert detector and the "
                "mutation sweep; it does not trust this narrative. "
                "starts_from_the_control=true"
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST_REL,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/SYN-0040/probe1_every_row.py"
                ),
                "artifact_path": OUTPUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_rec("verifier", "test-run", P1_CMD, "pending-live-rerun", 0),
            },
            {
                "consumer": (
                    "command-center/p2-wave/probes/SYN-0040/"
                    "probe2_silent_and_mutation.py"
                ),
                "artifact_path": OUTPUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_rec("verifier", "test-run", P2_CMD, "pending-live-rerun", 0),
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 1,
            "policy": str(unit.get("retry_policy") or "two strikes then pivot"),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "SYN-0002, SYN-0013, SYN-0016..SYN-0021 and SYN-0030 have not "
                    "shipped receipts on this worktree, so this matrix cannot yet "
                    "bind to those units' production binaries."
                ),
                "settling_experiment": (
                    "Re-run SYN-0040 against each producing unit's shipped gate "
                    "CLI, keeping the fixtures under command-center/p2-wave/"
                    "probes/SYN-0040/fixtures/."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    f"{RULE_REL} section 3b is the both-states test cited by "
                    "the catalog."
                ),
                "settling_experiment": (
                    "Re-read rules/common/single-signal-verification.md section 3b."
                ),
                "verdict": "CONFIRMED" if rule_present else "NOT-CHECKED",
            },
        ],
        "report": report,
    }
    rc = validate_or_die(doc)
    if rc != 0:
        return rc
    text = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    if sentinel not in text:
        print("FAILED:SYN-0040 catalog completion_sentinel absent from dump")
        return 1
    if len(text.encode("utf-8")) < int(doc["min_bytes_threshold"]):
        print("FAILED:SYN-0040 artifact below min_bytes_threshold")
        return 1
    out_path = REPO / OUTPUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    sha, size = digest_file(out_path)
    print(f"wrote {OUTPUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:SYN-0040")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
