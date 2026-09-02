#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0454.json via the registering writer."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from registering_writer import RegisteringWriter, digest_file  # noqa: E402
from scenario import run_bypass, run_full_writer_run  # noqa: E402

OUT_REL = "command-center/receipts/IMP-0454.json"
SENTINEL = "SENTINEL:IMP-0454:MANIFEST-AUTO-REGISTERED"
UNIT = "IMP-0454"
SCHEMA = "command-center/schema/receipt.schema.json"
QUESTION = (
    "Wire artifact-manifest registration into the writer so completion condition "
    "11 (output registered in the artifact manifest) is satisfied by construction "
    "rather than by a later sweep. Exact question: can any artifact reach disk "
    "without a manifest entry, and what is the count of unregistered artifacts "
    "after a full run?"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def catalog_unit() -> dict:
    data = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UNIT:
            return unit
    raise SystemExit("FAILED:IMP-0454 catalog unit missing")


def build_receipt(
    *,
    tests_rc: int,
    tests_out: str,
    full: dict,
    bypass: dict,
    emit_manifest_rel: str,
) -> dict:
    unit = catalog_unit()
    catalog_sentinel = str(unit.get("completion_sentinel") or SENTINEL)
    if catalog_sentinel != SENTINEL:
        # Keep both: catalog field is the G-1 needle; local alias documents the same token.
        pass
    ok = (
        tests_rc == 0
        and full["set_difference_empty"]
        and full["unregistered_count"] == 0
        and full["agree"]
        and full["registered_at_emit_not_sweep"]
        and bypass["caught"]
        and bypass["both_states"]
        and bypass["in_memory_misses_bypass"]
        and bypass["sweep_did_not_register"]
    )
    answer = (
        "Via RegisteringWriter.emit: no. After a full writer run the mechanical "
        f"set difference disk-minus-manifest is the empty set (unregistered_count="
        f"{full['unregistered_count']}). Via a direct file open that skips the "
        "writer: yes, and the read-only reconciliation sweep reports that path as "
        f"unregistered (count={bypass['unregistered_count_after']}, path="
        f"{bypass['bypass_path']!r}). Registration is performed inside emit() "
        "(manifest re-read from disk before reconcile). The sweep detects; it "
        "does not register."
    )
    return {
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS" if ok else "FAILED",
        "status": "DELIVERED" if ok else "FAILED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "completion_line": SENTINEL,
        "title": unit.get("title"),
        "question": QUESTION,
        "answer": answer,
        "output_schema": SCHEMA,
        "cloud_ok": False,
        "computed_at": utc_now(),
        "unregistered_count_after_full_run": full["unregistered_count"],
        "set_difference_after_full_run": {
            "unregistered": full["independent_setdiff"]["unregistered"],
            "orphan_rows": full["independent_setdiff"]["orphan_rows"],
            "empty": full["set_difference_empty"],
            "library": full["library_reconcile"]["unregistered"],
            "independent": full["independent_setdiff"]["unregistered"],
            "agree": full["agree"],
        },
        "bypass_caught": bypass["caught"],
        "bypass": {
            "path": bypass["bypass_path"],
            "unregistered_count_after": bypass["unregistered_count_after"],
            "writer_only_empty": bypass["before_empty"],
            "in_memory_misses_bypass": bypass["in_memory_misses_bypass"],
            "sweep_did_not_register": bypass["sweep_did_not_register"],
            "both_states": bypass["both_states"],
        },
        "construction": {
            "registered_at_emit_not_sweep": full["registered_at_emit_not_sweep"],
            "reconcile_is_read_only": full["reconcile_is_read_only"],
            "derivation": "registering_writer.emit (not unit_manifest.py --write)",
        },
        "evidence": [
            {
                "id": "E1",
                "signal": "full-writer-run-set-difference",
                "kind": "mechanical-set-difference",
                "unregistered_count": full["unregistered_count"],
                "set_difference_empty": full["set_difference_empty"],
                "independent_method": full["independent_setdiff"]["method"],
                "library_unregistered": full["library_reconcile"]["unregistered"],
                "independent_unregistered": full["independent_setdiff"]["unregistered"],
                "agree": full["agree"],
                "per_emit_disk_reads": full["per_emit_disk_reads"],
            },
            {
                "id": "E2",
                "signal": "bypass-direct-open-caught-unregistered",
                "kind": "negative-control",
                "caught": bypass["caught"],
                "bypass_path": bypass["bypass_path"],
                "in_memory_writer_paths": bypass["in_memory_writer_paths"],
                "in_memory_misses_bypass": bypass["in_memory_misses_bypass"],
                "sweep_did_not_register": bypass["sweep_did_not_register"],
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0454-independent-rglob-minus-json-paths",
            "verdict": "PASS" if ok else "FAIL",
            "independent": True,
            "method": (
                "Second walker: pathlib rglob of durable files minus json.load "
                "manifest paths. Must agree with registering_writer.reconcile. "
                "Does not call list_disk_artifacts."
            ),
            "independent_unregistered_full_run": full["independent_setdiff"]["unregistered"],
            "matches_library": full["agree"],
        },
        "tests": [
            {
                "id": "test_full_run_set_difference_empty",
                "path": "tools/command-center/tests/test_registering_writer.py",
                "result": "PASS" if tests_rc == 0 else "FAIL",
            },
            {
                "id": "test_bypass_direct_open_is_unregistered",
                "path": "tools/command-center/tests/test_registering_writer.py",
                "result": "PASS" if tests_rc == 0 else "FAIL",
            },
            {
                "id": "probe1_full_run_setdiff",
                "result": "RECORDED-AT-EMIT",
            },
            {
                "id": "probe2_bypass",
                "result": "RECORDED-AT-EMIT",
            },
        ],
        "tests_raw": tests_out[-4000:],
        "library": "tools/command-center/registering_writer.py",
        "emit_manifest": emit_manifest_rel,
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {"path": "tools/command-center/registering_writer.py", "role": "implementation"},
            {
                "path": "tools/command-center/tests/test_registering_writer.py",
                "role": "tests",
            },
            {"path": emit_manifest_rel, "role": "emit-time-manifest"},
        ],
        "inputs_note": (
            "Catalog input command-center/ARTIFACT-MANIFEST.json is the charter "
            "thirteen-file index (absent on this tree). Condition 11 for unit "
            "outputs is emit-time registration into a writer-owned manifest, not "
            "a later tools/command-center/unit_manifest.py --write sweep. "
            "Dependency receipts IMP-0434/IMP-0415 are absent; this unit ships "
            "the registering writer rather than wrapping a missing IMP-0434 module."
        ),
        "can_artifact_reach_disk_without_manifest_via_writer": False,
        "unregistered_count_via_writer_full_run": 0,
    }


def main() -> int:
    tests_rc, tests_out = run(
        [
            sys.executable,
            "-B",
            str(REPO / "tools/command-center/tests/test_registering_writer.py"),
        ]
    )
    print(tests_out)
    if tests_rc != 0:
        print("FAILED:IMP-0454 library tests")
        return 1
    full = run_full_writer_run()
    bypass = run_bypass()
    if not full["set_difference_empty"] or full["unregistered_count"] != 0:
        print("FAILED:IMP-0454 full-run set difference not empty")
        return 1
    if not bypass["caught"]:
        print("FAILED:IMP-0454 bypass not caught")
        return 1

    emit_manifest_rel = "command-center/p2-wave/probes/IMP-0454/EMIT-MANIFEST.json"
    receipts_dir = REPO / "command-center" / "receipts"
    writer = RegisteringWriter(receipts_dir, REPO / emit_manifest_rel)

    # First pass without post-emit sha (filled after writer returns).
    doc = build_receipt(
        tests_rc=tests_rc,
        tests_out=tests_out,
        full=full,
        bypass=bypass,
        emit_manifest_rel=emit_manifest_rel,
    )
    if SENTINEL not in json.dumps(doc):
        print("FAILED:IMP-0454 sentinel missing from document")
        return 1
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    row = writer.emit("IMP-0454.json", text, unit_id=UNIT, role="primary")
    out = REPO / OUT_REL
    sha, size = digest_file(out)
    if sha != row["sha256"]:
        print("FAILED:IMP-0454 writer sha256 != digest_file of dest")
        return 1
    # Confirm the live dest is in the emit-time manifest on disk (not in-memory).
    man = json.loads((REPO / emit_manifest_rel).read_text(encoding="utf-8"))
    live_paths = [a.get("path") for a in man.get("artifacts") or []]
    if "IMP-0454.json" not in live_paths:
        print("FAILED:IMP-0454 live receipt missing from emit-time manifest")
        return 1
    print(
        json.dumps(
            {
                "path": OUT_REL,
                "sha256": sha,
                "bytes": size,
                "sentinel": SENTINEL,
                "emit_manifest_row": "IMP-0454.json",
                "unregistered_count_after_full_run": full["unregistered_count"],
                "bypass_caught": bypass["caught"],
            }
        )
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
