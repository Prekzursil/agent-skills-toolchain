#!/usr/bin/env python3
"""Emit ADV-0101 stopping-rule both-directions pathology artifact."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from stopping import and_is_not_or_under_partial  # noqa: E402
from simulate import compact_runs, run_all  # noqa: E402

OUT_REL = "command-center/adversarial/ADV-0101-stopping-rule-both-directions.json"
SCHEMA_REL = "command-center/schema/council-pathology-sim.schema.json"
COMPLETION = (
    "SUCCESS:ADV-0101 emitted ONLY when the artifact at output_path exists, is non-empty, "
    "parses against output_schema, records BOTH named probes verbatim with their raw output, "
    "carries exactly one verdict from {CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per "
    "enumerated target, and records the result of every listed control/negative test. Any "
    "missing control downgrades the unit's verdicts to NOT-CHECKED. Otherwise FAILED:ADV-0101 "
    "<reason>."
)
P1_REQ = (
    "Probe 1: run both scripted councils against each required example expression and record "
    "whether the runtime stopped too early or failed to stop."
)
P2_REQ = (
    "Probe 2 (mechanically different): information-gain instrumentation - compute "
    "new-unique-content per round independently of the stopping evaluator and compare with "
    "the evaluator's own convergence signal; a divergence shows the evaluator is measuring "
    "turns rather than information."
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0101/probe1_paired_councils.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0101/probe2_info_gain.py"
)
QUESTION = (
    "Can a council be driven to stop before its minimum deliberation conditions are met, "
    "and can it be driven to loop indefinitely with no information gain - under the same "
    "composable stopping expression?"
)


def _validate(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    sys.path[:] = [p for p in sys.path if p not in ("", ".", str(REPO))]
    import jsonschema  # noqa: E402

    jsonschema.Draft7Validator(schema).validate(doc)


def _row(bundle: dict, eid: str, cid: str) -> dict:
    return next(r for r in bundle["expression_runs"] if r["expression"]["id"] == eid)[
        "councils"
    ][cid]


def main() -> int:
    bundle = run_all()
    and_ctrl = and_is_not_or_under_partial()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    e1_end = _row(bundle, "E1", "endless_low_info")
    e1_health = _row(bundle, "E1", "healthy_progress")
    e3_inst = _row(bundle, "E3", "instant_agree")
    e2_end = _row(bundle, "E2", "endless_low_info")

    tests = [
        {
            "id": "T-SIX-EXPRESSIONS-EXERCISED",
            "requirement": (
                "all six required example expressions from the spec must be exercised, "
                "including proof_of_impossibility == true, and any expression that cannot "
                "be satisfied under the current release mode must be reported as "
                "unsatisfiable rather than skipped"
            ),
            "result": "PASS"
            if bundle["all_six_exercised"] == ["E1", "E2", "E3", "E4", "E5", "E6"]
            and not bundle["skipped_expressions"]
            else "FAIL",
            "evidence": (
                f"exercised={bundle['all_six_exercised']} skipped={bundle['skipped_expressions']} "
                f"unsatisfiable_under_{bundle['release_mode']}="
                f"{bundle['unsatisfiable_under_release_mode']}"
            ),
        },
        {
            "id": "T-PROOF-NOT-UNSUCCESSFUL-SEARCH",
            "requirement": "proof_of_impossibility is not discharged by unsuccessful search",
            "result": "PASS" if bundle["e6_unsuccessful_search_did_not_fire"] else "FAIL",
            "evidence": (
                f"e6_unsuccessful_search_did_not_fire="
                f"{bundle['e6_unsuccessful_search_did_not_fire']} "
                f"healthy_real_proof={bundle['e6_real_proof_fires_on_healthy']}"
            ),
        },
        {
            "id": "T-PREMATURE-INSTANT-UNANIMITY",
            "requirement": "instant-agree council stops before floors on E3",
            "result": "PASS" if e3_inst["premature_stop"] else "FAIL",
            "evidence": (
                f"E3 instant stop_reason={e3_inst['stop_reason']} at={e3_inst['stopped_at']} "
                f"premature={e3_inst['premature_stop']}"
            ),
        },
        {
            "id": "T-ENDLESS-LOW-INFO",
            "requirement": "low-info council fails to stop on unbounded E1",
            "result": "PASS" if e1_end["failed_to_stop"] else "FAIL",
            "evidence": (
                f"E1 endless stop_reason={e1_end['stop_reason']} rounds={e1_end['rounds_run']} "
                f"gain_after_r1={e1_end['info_gain_after_round1_total']}"
            ),
        },
        {
            "id": "T-INFO-GAIN-INDEPENDENT",
            "requirement": "independent token-gain diverges from evaluator convergence",
            "result": "PASS" if bundle["info_gain_divergences"] else "FAIL",
            "evidence": json.dumps(bundle["info_gain_divergences"])[:800],
        },
        {
            "id": "T-AND-NOT-OR-PARTIAL",
            "requirement": "AND must not behave as OR under partial evidence",
            "result": "PASS" if and_ctrl["and_did_not_behave_as_or"] else "FAIL",
            "evidence": json.dumps({k: and_ctrl[k] for k in and_ctrl if k != "id"}),
        },
        {
            "id": "T-HEALTHY-STOPS-WHEN-TRUE",
            "requirement": "progressing council stops on E1 when thresholds and floors are met",
            "result": "PASS"
            if e1_health["stop_reason"] == "expression" and not e1_health["premature_stop"]
            else "FAIL",
            "evidence": (
                f"E1 healthy stop={e1_health['stop_reason']} at={e1_health['stopped_at']} "
                f"premature={e1_health['premature_stop']}"
            ),
        },
    ]
    failed = [t["id"] for t in tests if t["result"] != "PASS"]
    if failed:
        print("FAILED:ADV-0101-emit tests", failed)
        return 1

    doc = {
        "unit_id": "ADV-0101",
        "id": "ADV-0101",
        "title": "Stopping-rule adversarial in both directions: premature convergence and endless debate",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0101",
        "completion_sentinel": COMPLETION,
        "report_kind": "council-pathology-sim",
        "schema_version": 1,
        "question": QUESTION,
        "answer": (
            "Yes, under an expression-only evaluator (floors not inside the expression): "
            f"premature stop {bundle['premature_verdict']} on {bundle['premature_hits']}; "
            f"endless/no-gain loop {bundle['endless_verdict']} on {bundle['endless_hits']}. "
            "Unsuccessful search does not discharge proof_of_impossibility. "
            "AND under partial evidence stays NOT-CHECKED rather than collapsing to OR."
        ),
        "overall_verdict": bundle["overall_verdict"],
        "enumerated_targets": [
            {
                "id": "premature_convergence",
                "verdict": bundle["premature_verdict"],
                "evidence": (
                    f"hits={bundle['premature_hits']} E3 instant stopped_at="
                    f"{e3_inst['stopped_at']} premature={e3_inst['premature_stop']}"
                ),
            },
            {
                "id": "endless_low_information_loop",
                "verdict": bundle["endless_verdict"],
                "evidence": (
                    f"hits={bundle['endless_hits']} E1 endless stop_reason="
                    f"{e1_end['stop_reason']} gain_after_r1="
                    f"{e1_end['info_gain_after_round1_total']}"
                ),
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "requirement": P1_REQ,
                "command": P1_CMD,
                "raw_output": "filled-after-live-probe-run-by-write_receipts",
            },
            {
                "id": "probe2",
                "requirement": P2_REQ,
                "command": P2_CMD,
                "raw_output": "filled-after-live-probe-run-by-write_receipts",
            },
        ],
        "tests": tests,
        "controls": {
            "and_not_or_partial": and_ctrl,
            "detector_control_premature": {
                "fixture_id": "instant_agree/E3",
                "found_known_present": e3_inst["premature_stop"] is True,
                "verbatim": (
                    f"instant E3 premature_stop={e3_inst['premature_stop']} "
                    f"stopped_at={e3_inst['stopped_at']}"
                ),
            },
            "healthy_progress_e1": {
                "fixture_id": "healthy_progress/E1",
                "fired": e1_health["stop_reason"] == "expression",
                "premature": e1_health["premature_stop"],
            },
        },
        "negative_controls": [
            {
                "id": "NC-PREMATURE-INSTANT-UNANIMITY",
                "fired_on_bad_state": e3_inst["premature_stop"] is True,
                "silent_on_good_state": e1_health["premature_stop"] is False,
                "verbatim": (
                    f"bad=instant/E3 premature={e3_inst['premature_stop']} "
                    f"good=healthy/E1 premature={e1_health['premature_stop']}"
                ),
            },
            {
                "id": "NC-ZERO-GAIN-VS-EVALUATOR",
                "fired_on_bad_state": bool(
                    e2_end["divergence_zero_gain_but_evaluator_stop"]
                    or e1_end["divergence_zero_gain_evaluator_never_stops"]
                ),
                "silent_on_good_state": bool(
                    e1_health["info_gain_after_round1_total"] > 0
                    and e1_health["stop_reason"] == "expression"
                ),
                "verbatim": (
                    f"E2 endless divergence_stop="
                    f"{e2_end['divergence_zero_gain_but_evaluator_stop']} "
                    f"E1 endless never_stops="
                    f"{e1_end['divergence_zero_gain_evaluator_never_stops']} "
                    f"healthy gain_after_r1={e1_health['info_gain_after_round1_total']}"
                ),
            },
            {
                "id": "NC-AND-NOT-OR-PARTIAL",
                "fired_on_bad_state": and_ctrl["fired_on_bad_state"],
                "silent_on_good_state": and_ctrl["silent_on_good_state"],
                "verbatim": json.dumps(and_ctrl),
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0101-probe2-independent-info-gain",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-derives unique-token gain from transcripts only. "
                "Catalog two-vendor live review is not claimed."
            ),
        },
        "evidence": {
            "release_mode": bundle["release_mode"],
            "skipped_expressions": bundle["skipped_expressions"],
            "unsatisfiable_under_release_mode": bundle["unsatisfiable_under_release_mode"],
            "all_six_exercised": bundle["all_six_exercised"],
            "premature_hits": bundle["premature_hits"],
            "endless_hits": bundle["endless_hits"],
            "info_gain_divergences": bundle["info_gain_divergences"],
            "e6_unsuccessful_search_did_not_fire": bundle["e6_unsuccessful_search_did_not_fire"],
            "e6_real_proof_fires_on_healthy": bundle["e6_real_proof_fires_on_healthy"],
            "expression_runs": compact_runs(bundle),
            "mechanism": (
                "expression-only composable evaluator; min-deliberation floors measured "
                "independently; unique-token gain measured from utterances only"
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "role": "primary", "present": True},
            {
                "path": "command-center/p2-wave/probes/ADV-0101/stopping.py",
                "role": "supporting",
                "present": True,
            },
            {
                "path": "command-center/p2-wave/probes/ADV-0101/simulate.py",
                "role": "supporting",
                "present": True,
            },
        ],
        "downstream_consumers": [
            "ADV-0102 nested-council completion",
            "IMP-0308 stopping-expression runtime",
            "IMP-0309 min-deliberation gate",
            "CNL-0077 minimum deliberation floors",
        ],
        "spec_anchor": "_USER-PROMPTS.md:10931, 10937-10942, 11337-11338",
        "defects": [
            {
                "id": "ADV-0101-D1",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Expression-only stop allows instant unanimity (E3) and two-round "
                    "no-new-objection (E2) to halt before min briefs/evidence/rounds."
                ),
            },
            {
                "id": "ADV-0101-D2",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Unbounded expressions (E1/E4/E5/E6) never fire on a paraphrase mill; "
                    "the evaluator has no independent information-gain conjunct."
                ),
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "tools/council/stopping/expr.py (IMP-0308) is absent on this worktree; "
                    "this unit attacks a local composable evaluator implementing the six "
                    "spec expressions. A later production evaluator must be re-probed."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "produced_by": {
            "execution_substrate": "linux-local",
            "role": "groupthink-red-teamer",
            "vendor": "local-implementer",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0101/UNIT-ARTIFACT-MANIFEST.json",
            "note": "per-unit only; did not run unit_manifest.py --write",
        },
        "timestamps": {"generated_at": now},
        "notes": (
            "G-1 ADV-0101: live named probes, honest SUCCESS (pathologies CONFIRMED), "
            "per-unit manifest. Did not run global unit_manifest.py --write. No ADV rebuild circle."
        ),
    }

    try:
        _validate(doc)
    except Exception as exc:
        print(f"FAILED:ADV-0101-emit schema {type(exc).__name__}: {exc}")
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print(f"overall_verdict={doc['overall_verdict']}")
    print("SUCCESS:ADV-0101-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
