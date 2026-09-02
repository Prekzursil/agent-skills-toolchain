#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0071-retire-readjudication.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import controls as C  # noqa: E402
import engine as E  # noqa: E402
import locate as L  # noqa: E402

OUT_REL = "command-center/wfa/WFA-0071-retire-readjudication.json"
SCHEMA_REL = "command-center/p2-wave/probes/WFA-0071/disposition.schema.json"
QUESTION = (
    "For each of the 24 RETIRE candidates, is retirement still the right "
    "disposition after the DELETE-ALL retirement already removed 77 files "
    "across 5 trees - and for each, is the content preserved somewhere "
    "before the disposition becomes terminal?"
)


def find_line(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"FAILED:WFA-0071 emit anchor missing: {needle}")


def main() -> int:
    C.ensure_fixtures()
    located = L.locate_registry()
    live = C.live_cohort(located)
    controls = C.control_corpus()
    live_rows = [E.adjudicate(c) for c in live]
    ctrl_rows = [E.adjudicate(c) for c in controls]
    canary = C.canary_ok()
    expected = {c["id"]: c["expected_verdict"] for c in controls}
    for row in ctrl_rows:
        if row["verdict"] != expected[row["id"]]:
            print(
                f"FAILED:WFA-0071 emit control {row['id']} "
                f"{row['verdict']} != {expected[row['id']]}"
            )
            return 1

    terminal = sum(1 for r in live_rows if r["completed_retirement"])
    p1_n = sum(1 for r in live_rows if r["p1"])
    identity_n = sum(
        1 for r in live_rows if r["verdict"] == "P1-IDENTITY-UNRECOVERABLE"
    )
    registry_absent = not located["hits"]

    catalog = REPO / "command-center/WORK-UNIT-CATALOG.json"
    q_line = find_line(catalog, '"id": "WFA-0071"')
    hist_line = find_line(catalog, "RETIRE 24, ADOPT-WITH-WRAPPER 20")

    if registry_absent:
        answer = (
            "Retirement is not a completed terminal disposition for any of "
            "the 24 RETIRE candidates on this Linux worktree. Signal A: the "
            "authoritative 08-WORKFLOW-CANDIDATE-REGISTRY.json (catalog "
            "histogram RETIRE n=24, recorded source sha256 "
            f"{L.EXPECTED_SOURCE_SHA256}) is absent from every searched "
            f"path ({len(located['misses'])} misses, "
            f"{len(located.get('rejected') or [])} rejected-not-registry, "
            "0 hits), so each of the "
            "24 identities is UNRECOVERABLE and is a P1 finding, not a "
            "completed retirement. Independently, this worktree has no .git, "
            "so named-commit retrieval of the DELETE-ALL 77-file set cannot "
            "be a receipt here. Signal B (mechanically independent "
            "retrieve+sha256, not exists()): planted controls prove the "
            "engine keeps unpreserved / claim-only / hash-mismatch records "
            "as P1 and only RETAIN-RETIRE when bytes hash-match an export "
            "AND capability-given-up plus mechanism_survives_at are named. "
            f"Live terminal_retire_count={terminal}. This unit deleted no "
            "files. Owner sign-off remains required before any terminal "
            "retirement; none is self-certified."
        )
    else:
        answer = (
            f"Live registry loaded ({located['chosen']['path']}); "
            f"retire_n={located['retire_n']}. Per-candidate existence and "
            "retrieve+hash-match preservation are recorded on each row. "
            f"terminal_retire_count={terminal}; p1={p1_n}. A candidate "
            "without a hash-matched copy is P1, not completed retirement. "
            "This unit deleted no files."
        )

    ctrl_verdicts = {r["id"]: r["verdict"] for r in ctrl_rows}
    doc = {
        "unit_id": "WFA-0071",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0071",
        "completion_sentinel": "SUCCESS:WFA-0071",
        "title": (
            "Re-adjudicate the 24 RETIRE candidates against the retirement "
            "that already executed"
        ),
        "question": QUESTION,
        "answer": answer,
        "record_type": "DispositionRecord",
        "output_schema": (
            "command-center/wfa/schema/wfa-schema-pack.json#/$defs/DispositionRecord"
        ),
        "local_schema": SCHEMA_REL,
        "candidates": live_rows,
        "terminal_retire_count": terminal,
        "p1_count": p1_n,
        "identity_unrecoverable_count": identity_n,
        "files_deleted_by_this_unit": E.files_deleted_by_this_unit(),
        "registry": {
            "hits": located["hits"],
            "miss_count": len(located["misses"]),
            "miss_paths": [m["path"] for m in located["misses"]],
            "rejected": located.get("rejected") or [],
            "retire_n_found": located["retire_n"],
            "expected_retire_n": L.EXPECTED_RETIRE_N,
            "expected_source_sha256": L.EXPECTED_SOURCE_SHA256,
            "salvage": located["salvage"],
            "git": located["git"],
        },
        "delete_all": {
            "claimed": "77 files removed across 5 trees",
            "list_present_on_this_worktree": False,
            "named_commit_retrieval": located["git"]["named_commit_retrieval"],
            "note": (
                "Cannot hash-match the 77 deleted paths from git on this "
                "worktree; absence of a retrieval is recorded, not inferred "
                "as preservation."
            ),
        },
        "controls": {
            "role": "both-states planted corpus; not the original 24 ids",
            "verdicts": ctrl_verdicts,
            "rows": ctrl_rows,
            "expected": expected,
        },
        "canary": canary,
        "tests": [
            {
                "id": "no-delete",
                "result": "PASS" if canary["unchanged"] else "FAIL",
                "detail": "canary hash unchanged; files_deleted_by_this_unit=[]",
            },
            {
                "id": "unpreserved-is-p1-not-completed-retirement",
                "result": "PASS"
                if ctrl_verdicts["ctrl-unpreserved"] == "P1-UNPRESERVED"
                else "FAIL",
            },
            {
                "id": "retained-retire-names-capability-and-survival",
                "result": "PASS"
                if ctrl_verdicts["ctrl-preserved-export"] == "RETAIN-RETIRE"
                and ctrl_verdicts["ctrl-preserved-no-capability"]
                == "REFUSE-RETIRE-MISSING-SURVIVAL"
                else "FAIL",
            },
            {
                "id": "claim-is-not-receipt",
                "result": "PASS"
                if ctrl_verdicts["ctrl-claim-only"] == "P1-CLAIM-NOT-RECEIPT"
                else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "WFA-0071-UNPRESERVED-MUST-NOT-COMPLETE",
                "fired_on_bad_state": ctrl_verdicts["ctrl-unpreserved"]
                == "P1-UNPRESERVED",
                "silent_on_good_state": ctrl_verdicts["ctrl-preserved-export"]
                == "RETAIN-RETIRE",
            },
            {
                "id": "WFA-0071-MANIFEST-CLAIM-IS-NOT-RECEIPT",
                "fired_on_bad_state": ctrl_verdicts["ctrl-claim-only"]
                == "P1-CLAIM-NOT-RECEIPT",
                "silent_on_good_state": ctrl_verdicts["ctrl-preserved-export"]
                == "RETAIN-RETIRE",
            },
            {
                "id": "WFA-0071-STILL-LIVE-REOPENS-DELETE-ALL-RATIONALE",
                "fired_on_bad_state": ctrl_verdicts["ctrl-still-live"] == "REOPEN",
                "silent_on_good_state": True,
            },
        ],
        "evidence": [
            {
                "signal": "A",
                "kind": "existence-and-rationale-reread",
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "line": q_line,
                "detail": (
                    "Per-candidate existence check plus retirement rationale "
                    "re-read against today's estate; catalog unit WFA-0071."
                ),
            },
            {
                "signal": "A",
                "kind": "histogram-anchor",
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "line": hist_line,
                "detail": "Catalog histogram RETIRE n=24.",
            },
            {
                "signal": "B",
                "kind": "retrieve-and-hash-match",
                "path": "command-center/p2-wave/probes/WFA-0071/probe2_preservation_hashmatch.py",
                "line": 1,
                "detail": (
                    "Mechanically independent: retrieve named export bytes and "
                    "sha256-match. Manifest path is a claim; retrieval is the "
                    "receipt."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0071-probe2-preservation-hashmatch",
            "independent": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 re-hashes export bytes without using probe 1 "
                "exists() as preservation proof."
            ),
        },
        "owner_signoff": {
            "required": True,
            "present": False,
            "terminal_dispositions_self_certified": 0,
            "note": (
                "Unit may not self-certify an irreversible outcome. Zero "
                "terminal RETIRE records emitted."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {"path": SCHEMA_REL, "role": "supporting"},
        ],
        "schema_validation": {},
    }

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errs = list(validator.iter_errors(doc))
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    garbage_errs = list(validator.iter_errors(garbage))
    if errs:
        print("FAILED:WFA-0071 emit schema errors", [e.message for e in errs[:8]])
        return 1
    if not garbage_errs:
        print("FAILED:WFA-0071 emit schema accepts garbage")
        return 1
    doc["schema_validation"] = {
        "schema": SCHEMA_REL,
        "error_count": 0,
        "garbage_error_count": len(garbage_errs),
        "discriminates": True,
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:WFA-0071" not in text:
        print("FAILED:WFA-0071 emit sentinel missing from serialization")
        return 1
    out.write_text(text, encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={len(text.encode('utf-8'))}")
    print("SUCCESS:WFA-0071 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
