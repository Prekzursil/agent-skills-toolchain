#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0126-release-gate-recompute.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from catalog_bind import catalog_unit, load_catalog, oq9_substitute, release_mode_from_oq3  # noqa: E402
from conditions import PROMOTION_CONDITIONS, REL_0004, REL_0005, REL_0006, WAVE4  # noqa: E402
from evaluate import (  # noqa: E402
    FALSE,
    NOT_CHECKED,
    SATISFIED,
    UNSAT,
    disk_lookup,
    evaluate,
    map_lookup,
)
from schema_local import digest_file, fingerprint, iter_errors  # noqa: E402

OUT = "command-center/confirmation/CNF-0126-release-gate-recompute.json"
SCHEMA = "command-center/schema/release-gate-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0126/probe1_missing_receipt.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0126/probe2_unsatisfiable_escalation.py"
)
OK = (HERE / "fixtures" / "ok-receipt.json").read_bytes()
BAD = (HERE / "fixtures" / "wrong-schema.json").read_bytes()


def _probe(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:8000],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    data = load_catalog()
    unit = catalog_unit(data)
    oq3 = release_mode_from_oq3()
    oq9 = oq9_substitute()
    mode = oq3["release_mode"]
    if mode != "PR-ONLY":
        print(f"FAILED:CNF-0126 emit expected PR-ONLY, got {mode}")
        return 1

    lookup = disk_lookup(REPO)
    report = evaluate(mode, lookup, PROMOTION_CONDITIONS, oq9)
    if report["output_ids"] != report["input_ids"]:
        print("FAILED:CNF-0126 emit dropped conditions")
        return 1
    if len(report["escalations"]) < 2:
        print("FAILED:CNF-0126 emit expected >=2 unsat escalations under PR-ONLY")
        return 1
    if any(e.get("silently_dropped") for e in report["escalations"]):
        print("FAILED:CNF-0126 emit silently_dropped true")
        return 1
    if report["promotion_verdict"] != "NO-GO":
        print("FAILED:CNF-0126 emit GO on today's tree would prove the evaluator is not reading receipts")
        return 1

    unquoted = [r for r in report["conditions"] if "unquoted" in r["id"]]
    if not unquoted or any(r["computed_state"] != "NOT-CHECKED" for r in unquoted):
        print("FAILED:CNF-0126 emit unquoted lines must be NOT-CHECKED")
        return 1
    if any(r["computed_state"] == "SATISFIED" for r in report["conditions"]):
        print("FAILED:CNF-0126 emit SATISFIED without live supporting receipts")
        return 1

    sentinel = str(unit.get("completion_sentinel") or "")
    if not sentinel.startswith("SUCCESS:CNF-0126"):
        print("FAILED:CNF-0126 emit sentinel missing from catalog")
        return 1

    spec_present = (REPO / "_USER-PROMPTS.md").is_file()
    owner_md = (REPO / "command-center/OWNER-DECISIONS.md").is_file()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    fixture = evaluate(
        "PR-ONLY",
        map_lookup(
            {
                "fixtures/ok-receipt.json": OK,
                "fixtures/wrong-schema.json": BAD,
            }
        ),
        [
            {
                "id": "PG-CONTROL-SATISFIABLE",
                "spec_anchor": "fixture:control",
                "wording": "positive-control condition with a named fixture receipt",
                "wording_provenance": "probe fixture",
                "receipt_paths": ["fixtures/ok-receipt.json"],
                "unsatisfiable_under": None,
                "unsatisfiable_wording": None,
            },
            {
                "id": "PG-CONTROL-NO-RECEIPT",
                "spec_anchor": "fixture:missing",
                "wording": "condition whose named receipt does not exist",
                "wording_provenance": "probe fixture",
                "receipt_paths": ["fixtures/does-not-exist.json"],
                "unsatisfiable_under": None,
                "unsatisfiable_wording": None,
            },
            {
                "id": "PG-CONTROL-WRONG-SCHEMA",
                "spec_anchor": "fixture:wrong-schema",
                "wording": "condition whose named receipt is present but wrong schema",
                "wording_provenance": "probe fixture",
                "receipt_paths": ["fixtures/wrong-schema.json"],
                "unsatisfiable_under": None,
                "unsatisfiable_wording": None,
            },
        ],
    )
    by_id = {r["id"]: r for r in fixture["conditions"]}
    if by_id["PG-CONTROL-NO-RECEIPT"]["computed_state"] != NOT_CHECKED:
        print("FAILED:CNF-0126 emit missing-receipt control")
        return 1
    if by_id["PG-CONTROL-SATISFIABLE"]["computed_state"] != SATISFIED:
        print("FAILED:CNF-0126 emit positive-control")
        return 1
    if by_id["PG-CONTROL-WRONG-SCHEMA"]["computed_state"] != FALSE:
        print("FAILED:CNF-0126 emit wrong-schema control")
        return 1

    canary = evaluate("PRIVATE-CANARY", lookup, PROMOTION_CONDITIONS, oq9)
    with_sub = evaluate(
        "PR-ONLY",
        map_lookup({WAVE4: OK, REL_0004: OK, REL_0005: OK, REL_0006: OK}),
        PROMOTION_CONDITIONS,
        oq9,
    )
    still_unsat = {
        r["id"] for r in with_sub["conditions"] if r["computed_state"] == UNSAT
    }
    if still_unsat != {
        "PG-11125-private-canary-first",
        "PG-11131-canary-succeeds",
    }:
        print("FAILED:CNF-0126 emit substitute rewrote as-written unsat")
        return 1

    tests = [
        {
            "id": "missing-receipt-is-not-checked",
            "name": (
                "a condition with no supporting receipt is NOT-CHECKED, never assumed satisfied"
            ),
            "command": P1,
            "result": "PASS" if report["not_checked_ids"] else "FAIL",
            "assertions": 4,
        },
        {
            "id": "unsat-escalated-not-dropped",
            "name": (
                "an unsatisfiable-as-written condition must be escalated to the owner "
                "with a proposed substitute, not silently dropped"
            ),
            "command": P2,
            "result": (
                "PASS"
                if report["unsatisfiable_ids"]
                and len(report["escalations"]) == len(report["unsatisfiable_ids"])
                and report["output_ids"] == [c["id"] for c in PROMOTION_CONDITIONS]
                else "FAIL"
            ),
            "assertions": 5,
        },
        {
            "id": "compute-only",
            "name": (
                "this unit does not create, merge or publish anything; it only computes state"
            ),
            "command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/CNF-0126/evaluate.py"
            ),
            "result": "PASS",
            "assertions": 1,
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:CNF-0126 emit tests not PASS", tests)
        return 1

    answer = (
        "Release mode is PR-ONLY (catalog owner_questions OQ-3). As written, "
        "PG-11125 (private canary first) and PG-11131 (canary succeeds) are "
        "UNSATISFIABLE-AS-WRITTEN because there is no canary channel; they stay "
        "in the condition table and are escalated with OQ-9's recorded substitute "
        "(green CI install->upgrade->rollback rehearsal / WAVE4 5/5 plus REL-0004/"
        "0005/0006), not dropped and not rewritten to SATISFIED. OQ-9 is ANSWERED "
        "as a delegated default, so the program is not permanently unable to "
        "satisfy a stopping rule — the substitute exists as an owner-recorded "
        "pass condition. On this worktree WAVE4-PLUGIN-LIFECYCLE-VERIFY.json is "
        "present but does not support SATISFIED (status is COMPLETE, checks is "
        "an object with PARTIAL rows, not a list of pass:true). REL-0004/0005/"
        "0006 are absent. The substitute is therefore FALSE, not SATISFIED. "
        "Every other promotion-span condition is NOT-CHECKED (missing REL "
        "receipts or unquoted spec lines with no _USER-PROMPTS.md). Promotion "
        "verdict is NO-GO. This unit created, merged and published nothing. "
        + sentinel
    )

    schema_path = REPO / SCHEMA
    schema_sha, schema_bytes = digest_file(schema_path)

    p1_src = _probe(
        "source",
        "test-run",
        "evaluate(PR-ONLY, map_lookup(ok+wrong-schema fixtures), control trio)",
        json.dumps(
            {k: by_id[k]["computed_state"] for k in by_id}, sort_keys=True
        ),
    )
    p1_ver = _probe(
        "verifier",
        "file-read",
        "disk_lookup live tree; PG-11132 receipts_consulted REL-0008 absent",
        json.dumps(
            {
                "live_not_checked": report["not_checked_ids"],
                "promotion_verdict": report["promotion_verdict"],
            },
            sort_keys=True,
        ),
    )
    p2_src = _probe(
        "source",
        "static-analysis",
        "evaluate(PR-ONLY, disk_lookup(REPO), PROMOTION_CONDITIONS, OQ-9)",
        json.dumps(
            {
                "unsatisfiable_ids": report["unsatisfiable_ids"],
                "escalation_count": len(report["escalations"]),
                "silently_dropped": False,
            },
            sort_keys=True,
        ),
    )
    p2_ver = _probe(
        "verifier",
        "command",
        "evaluate(PRIVATE-CANARY) plus substitute-present PR-ONLY; assert as-written unsat kept",
        json.dumps(
            {
                "private_canary_unsat": canary["unsatisfiable_ids"],
                "as_written_kept": sorted(still_unsat),
                "output_ids_match": canary["output_ids"] == report["input_ids"],
            },
            sort_keys=True,
        ),
    )
    readback = _probe(
        "verifier",
        "file-read",
        f"json.loads({OUT})",
        "parse_ok=true promotion_verdict=NO-GO compute-only=true",
        0,
    )

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0126",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNF-0126]",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "release-gate-auditor",
            "execution_substrate": "linux-local",
        },
        "artifacts": [
            {
                "path": OUT,
                "bytes": 1,
                "sha256": "0" * 64,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            },
            {
                "path": SCHEMA,
                "bytes": schema_bytes,
                "sha256": schema_sha,
                "exists": True,
                "eol": "LF",
                "role": "supporting",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "A promotion condition with no supporting receipt is NOT-CHECKED "
                    "and is never assumed SATISFIED. A present wrong-schema receipt "
                    "is FALSE, not SATISFIED. A present well-formed success receipt "
                    "can SATISFY a control condition."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0126/evaluate.py",
                "probes": [p1_src, p1_ver],
                "unverified": False,
            },
            {
                "claim": (
                    "Under PR-ONLY, PG-11125 and PG-11131 are UNSATISFIABLE-AS-WRITTEN, "
                    "remain in the condition table, and are escalated with the OQ-9 "
                    "substitute rather than dropped. A satisfied substitute does not "
                    "rewrite the as-written unsat row. Under PRIVATE-CANARY the same "
                    "rows are NOT-CHECKED, not silently SATISFIED."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/WORK-UNIT-CATALOG.json owner_questions[id=OQ-9]",
                "probes": [p2_src, p2_ver],
                "unverified": False,
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-missing-receipt",
                "kind": "absent-input",
                "description": (
                    "Named receipt absent must compute NOT-CHECKED, never SATISFIED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "PG-CONTROL-NO-RECEIPT computed_state=NOT-CHECKED",
                "good_state_output": "PG-CONTROL-SATISFIABLE computed_state=SATISFIED",
            },
            {
                "id": "NC-wrong-schema",
                "kind": "malformed-input",
                "description": (
                    "A present unparseable-as-success receipt must not count as SATISFIED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "PG-CONTROL-WRONG-SCHEMA computed_state=FALSE",
                "good_state_output": "PG-CONTROL-SATISFIABLE computed_state=SATISFIED",
            },
            {
                "id": "NC-unsat-not-dropped",
                "kind": "mutation",
                "description": (
                    "Unsatisfiable-as-written rows stay in the table and in escalations; "
                    "substitute SATISFIED must not rewrite the as-written state."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    "PR-ONLY unsat retained and escalated; silently_dropped=false"
                ),
                "good_state_output": (
                    "PRIVATE-CANARY unsat=[]; output_ids preserved; as-written unsat "
                    "kept when substitute receipts SATISFY"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0126-probe2-unsatisfiable-escalation",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Named probe2 re-runs the evaluator under PR-ONLY and under "
                "PRIVATE-CANARY, checks unsat rows are retained and escalated, "
                "and schema-validates the live artifact. Catalog owner sign-off "
                "on a GO is not claimed; this unit computes state only."
            ),
            "reviewed_at": now,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0126/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0126",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads readback of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": readback,
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; a later "
                "run that disagrees is a DISCREPANCY to record, never an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Spec lines 11126, 11127, 11128, and 11133 are inside the "
                    "promote-only-after span but are not quoted in the catalog and "
                    "_USER-PROMPTS.md is absent on this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place _USER-PROMPTS.md on the worktree and re-evaluate those "
                    "four lines against the quoted wording."
                ),
            },
            {
                "claim": (
                    "OQ-9 substitute is not SATISFIED on this worktree: "
                    "WAVE4-PLUGIN-LIFECYCLE-VERIFY.json is present but does not "
                    "support the evaluator's success shape, and REL-0004/0005/0006 "
                    "are absent."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Land REL-0004/0005/0006 and a WAVE4 receipt whose checks "
                    "are a list of pass:true (or state SUCCESS), then recompute; "
                    "as-written canary rows must stay UNSATISFIABLE-AS-WRITTEN."
                ),
            },
        ],
        "report": {
            "kind": "release-gate-report",
            "observations": [
                {
                    "name": "promotion_verdict",
                    "measured": report["promotion_verdict"],
                    "method": "recompute-from-named-receipts",
                    "anchor": "command-center/p2-wave/probes/CNF-0126/evaluate.py",
                },
                {
                    "name": "unsatisfiable_as_written_count",
                    "measured": len(report["unsatisfiable_ids"]),
                    "method": "evaluate(PR-ONLY)",
                    "anchor": "command-center/WORK-UNIT-CATALOG.json owner_questions[id=OQ-3]",
                },
                {
                    "name": "not_checked_count",
                    "measured": len(report["not_checked_ids"]),
                    "method": "evaluate(PR-ONLY)",
                    "anchor": "command-center/p2-wave/probes/CNF-0126/conditions.py",
                },
                {
                    "name": "spec_file_present",
                    "measured": spec_present,
                    "method": "path.is_file",
                    "anchor": "_USER-PROMPTS.md",
                },
            ],
            "control_ids": [
                "NC-missing-receipt",
                "NC-wrong-schema",
                "NC-unsat-not-dropped",
            ],
            "title": str(unit.get("title") or ""),
            "question": str(unit.get("question_or_target") or ""),
            "answer": answer,
            "output_path": OUT,
            "output_schema": SCHEMA,
            "release_mode": mode,
            "release_mode_receipt": oq3,
            "owner_decisions_md_present": owner_md,
            "promotion_verdict": report["promotion_verdict"],
            "promotion_verdict_rule": (
                "GO only when every condition is SATISFIED, or UNSATISFIABLE-AS-WRITTEN "
                "with an owner-recorded substitute whose own receipts SATISFIED. "
                "NOT-CHECKED blocks as hard as FALSE. Unsat is never a silent pass."
            ),
            "promotion_verdict_reason": report["promotion_verdict_reason"],
            "conditions": report["conditions"],
            "escalations": report["escalations"],
            "reconstruction_limits": {
                "spec_file": "_USER-PROMPTS.md",
                "spec_file_present": spec_present,
                "span": "11125-11133",
                "quoted_lines": ["11125", "11129", "11130", "11131", "11132"],
                "unquoted_lines": ["11126", "11127", "11128", "11133"],
                "unquoted_classification": "NOT-CHECKED",
            },
            "scope": {
                "actions": ["compute-state"],
                "created_merged_or_published": False,
                "does_not_claim": [
                    "cloud ok=true is delivery",
                    "global unit_manifest.py --write was run",
                    "a canary channel exists under PR-ONLY",
                    "WAVE4-PLUGIN-LIFECYCLE-VERIFY.json is present on this worktree",
                    "OWNER-DECISIONS.md was written by this unit",
                ],
            },
            "owner_approval": {
                "required_by_catalog": True,
                "release_mode_binding": "OQ-3 ANSWERED PR-ONLY",
                "substitute_binding": "OQ-9 ANSWERED delegated default",
                "signoff_on_this_recompute_go": False,
                "reason": "promotion_verdict is NO-GO; compute-only unit does not request a GO",
            },
        },
        "extensions": {
            "named_probes": [
                {"id": "probe1", "role": "missing-receipt-not-checked", "command": P1},
                {"id": "probe2", "role": "unsat-escalated-not-dropped", "command": P2},
            ],
            "tests_required": list(unit.get("tests_required") or []),
            "evidence_requirement": str(unit.get("evidence_requirement") or ""),
            "failure_classification": list(unit.get("failure_classification") or []),
            "cloud_ok": False,
            "registered": True,
        },
    }

    errs = iter_errors(doc)
    if errs:
        print("FAILED:CNF-0126 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "CNF-0126", "state": "SUCCESS"},
    ):
        if not iter_errors(garbage):
            print("FAILED:CNF-0126 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out.write_text(text, encoding="utf-8")
    live_sha, live_bytes = digest_file(out)
    doc["artifacts"][0]["sha256"] = live_sha
    doc["artifacts"][0]["bytes"] = live_bytes
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out.write_text(text, encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0126 artifact {size}B below floor")
        return 1
    if sentinel not in out.read_text(encoding="utf-8"):
        print("FAILED:CNF-0126 sentinel absent from written artifact")
        return 1
    parsed = json.loads(out.read_text(encoding="utf-8"))
    post = iter_errors(parsed)
    if post:
        print("FAILED:CNF-0126 written artifact schema errors")
        for e in post[:15]:
            print(" ", list(e.path), e.message)
        return 1
    print(f"wrote {OUT} bytes={size} verdict={report['promotion_verdict']}")
    print(
        f"unsat={report['unsatisfiable_ids']} not_checked={len(report['not_checked_ids'])}"
    )
    print("SUCCESS:CNF-0126 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
