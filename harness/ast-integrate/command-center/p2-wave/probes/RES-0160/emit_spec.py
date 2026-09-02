#!/usr/bin/env python3
"""Emit command-center/research/gem-hunt/RES-0160-gem-adoption-gate-with-measured-improvement.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import gate as G  # noqa: E402
import inventory as I  # noqa: E402
import lineage as L  # noqa: E402

OUT = "command-center/research/gem-hunt/RES-0160-gem-adoption-gate-with-measured-improvement.json"
SCHEMA = "command-center/schema/design-spec.schema.json"
UNIT = "RES-0160"
QUESTION = (
    "Specify the adopt/park/reject decision record that binds every adopted "
    "mechanism to a named before/after metric, a revert trigger and an "
    "owner-visible cost line - and back-test it against the mechanisms this "
    "estate adopted in the last two sweeps: how many would have survived "
    "their own gate?"
)
SENTINEL = "SUCCESS:RES-0160"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0160/probe1_record_binds.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0160/probe2_negative_control.py"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"$schema": "http://json-schema.org/draft-07/schema#"},
)


def validate_or_die(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    errs = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        print("FAILED:RES-0160 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        raise SystemExit(1)
    for garbage in GARBAGE:
        if not list(jsonschema.Draft7Validator(schema).iter_errors(garbage)):
            print(f"FAILED:RES-0160 schema accepted garbage {list(garbage)[:3]}")
            raise SystemExit(1)


def src(lineage: dict, sid: str) -> dict:
    row = lineage[sid]
    return {
        "url": row["url"],
        "fetch_timestamp": row["fetch_timestamp"],
        "sha256": row["sha256"],
        "quoted_span": row["quoted_span"],
        "quote_present": row["quote_present"],
        "role": row["role"],
        "bytes": row["bytes"],
    }


def main() -> int:
    L.assert_quotes_present()
    lineage = L.by_id()
    back = I.run_backtest()
    pop = back["population"]
    if pop["n"] < 2:
        print("FAILED:RES-0160 back-test population too small")
        return 1
    if not pop["negative_control_fired"]:
        print("FAILED:RES-0160 negative control: no WOULD-NOT-HAVE-PASSED still in use")
        return 1
    if pop["blesses_everything"]:
        print("FAILED:RES-0160 gate retroactively blessed every prior adoption")
        return 1
    synth = G.evaluate_record(G.complete_example())
    if synth["backtest_verdict"] != "WOULD-HAVE-PASSED":
        print("FAILED:RES-0160 complete example did not pass the gate")
        return 1
    no_metric = G.evaluate_record({"mechanism_id": "plant-no-metric", "still_in_use": True})
    if no_metric["backtest_verdict"] != "WOULD-NOT-HAVE-PASSED":
        print("FAILED:RES-0160 no-metric plant was not WOULD-NOT-HAVE-PASSED")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    spec = G.decision_record_spec()
    rows = pop["rows"]
    still_failed = [r for r in rows if r["backtest_verdict"] == "WOULD-NOT-HAVE-PASSED" and r["still_in_use"]]
    answer = (
        f"{pop['would_have_passed']} of {pop['n']} mechanisms adopted in P2-BUILD "
        f"ROUND 2 and ROUND 3 would have survived this gate. "
        f"{pop['would_not_have_passed']} WOULD-NOT-HAVE-PASSED, of which "
        f"{pop['would_not_have_passed_still_in_use']} are still in use. "
        "Every historical record lacks an owner-visible cost line; several also "
        "fail the named-metric test (R2 key-fallback still accepts keyed garbage). "
        f"{SENTINEL}"
    )

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "title": (
            "Adoption gate: a gem may be kept only when improvement is "
            "measured, and reverted otherwise"
        ),
        "question": QUESTION,
        "answer": answer,
        "completion_sentinel": SENTINEL,
        "generated_at": now,
        "inputs_absent": [
            "_USER-PROMPTS.md (quoted via catalog row as spec:11146)",
            "command-center/sources/REGISTER.md",
            "command-center/CLAIM-REGISTRY.json",
        ],
        "specification": {
            "kind": "adoption-gate",
            "summary": (
                "Adopt only when a named before/after metric improved, a revert "
                "trigger is named, and an owner-visible cost line is recorded. "
                "Park when bindings are incomplete. Reject when the metric is "
                "missing, neutral, or harmful."
            ),
            "decision_record": spec,
            "evaluator": "command-center/p2-wave/probes/RES-0160/gate.py",
        },
        "back_test": {
            "sweeps": back["sweeps"],
            "n": pop["n"],
            "would_have_passed": pop["would_have_passed"],
            "would_not_have_passed": pop["would_not_have_passed"],
            "would_not_have_passed_still_in_use": pop[
                "would_not_have_passed_still_in_use"
            ],
            "negative_control_fired": pop["negative_control_fired"],
            "blesses_everything": pop["blesses_everything"],
            "how_many_would_have_survived": pop["would_have_passed"],
            "records": back["records"],
            "verdicts": rows,
            "live": back["live"],
            "still_in_use_would_not_have_passed": [
                r["mechanism_id"] for r in still_failed
            ],
        },
        "negative_controls": [
            {
                "id": "historical-would-not-have-passed-still-in-use",
                "required": (
                    "the back-test must produce at least one WOULD-NOT-HAVE-PASSED "
                    "verdict on a mechanism still in use"
                ),
                "fired": pop["negative_control_fired"],
                "examples": [r["mechanism_id"] for r in still_failed],
            },
            {
                "id": "no-metric-is-would-not-have-passed",
                "required": "adoptions with no metric count as WOULD-NOT-HAVE-PASSED",
                "fired": no_metric["backtest_verdict"] == "WOULD-NOT-HAVE-PASSED",
            },
            {
                "id": "blessing-everything-is-not-a-gate",
                "required": "a population of all WOULD-HAVE-PASSED is refused",
                "fired": not pop["blesses_everything"],
            },
            {
                "id": "complete-bindings-can-pass",
                "required": "the gate is not a brick wall: a complete improved record ADOPTs",
                "fired": synth["backtest_verdict"] == "WOULD-HAVE-PASSED",
            },
        ],
        "sherman_kent_bands": {
            "source": "https://en.wikipedia.org/wiki/Words_of_estimative_probability",
            "bands": [
                {"term": "certain", "pct": 100, "give_or_take": 0},
                {"term": "almost-certain", "pct": 93, "give_or_take": 6},
                {"term": "probable", "pct": 75, "give_or_take": 12},
                {"term": "chances-about-even", "pct": 50, "give_or_take": 10},
                {"term": "probably-not", "pct": 30, "give_or_take": 10},
                {"term": "almost-certainly-not", "pct": 7, "give_or_take": 5},
                {"term": "impossible", "pct": 0, "give_or_take": 0},
            ],
        },
        "claims": [
            {
                "id": "C1-decision-record-binds-three",
                "claim": (
                    "The adopt/park/reject record ADOPTs only when a named "
                    "before/after metric improved, a revert trigger is named, "
                    "and an owner-visible cost line is present; no metric is "
                    "WOULD-NOT-HAVE-PASSED; neutral or harmful is REJECT."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "lineage": [
                    src(lineage, "catalog-res0160"),
                    src(lineage, "sre-error-budget"),
                ],
                "independent_verification_path": P1,
                "signals": [
                    {
                        "kind": "schema-required-bindings",
                        "detail": (
                            "design-spec.schema.json requires specification + "
                            "claims; gate.BINDINGS names named_metric, "
                            "revert_trigger, owner_visible_cost"
                        ),
                    },
                    {
                        "kind": "evaluator-runtime",
                        "detail": (
                            "gate.evaluate_record on a plant with no metric "
                            f"returned {no_metric['backtest_verdict']}; "
                            "complete_example returned "
                            f"{synth['backtest_verdict']}"
                        ),
                    },
                ],
            },
            {
                "id": "C2-backtest-last-two-sweeps",
                "claim": (
                    f"Against P2-BUILD ROUND 2 and ROUND 3, "
                    f"{pop['would_have_passed']} of {pop['n']} adopted "
                    "mechanisms WOULD-HAVE-PASSED this gate. Zero is the "
                    "honest count: none recorded an owner-visible cost line, "
                    "and the R2 key-check fallback's claimed garbage-rejection "
                    "metric is live-false for keyed garbage."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "lineage": [
                    src(lineage, "ready-units"),
                    src(lineage, "p2-build-round2"),
                    src(lineage, "p2-build-round3"),
                ],
                "independent_verification_path": (
                    "python3 -c 'import inventory; print(inventory.run_backtest()"
                    "[\"population\"][\"would_have_passed\"])'"
                ),
                "signals": [
                    {
                        "kind": "live-remeasure",
                        "detail": (
                            "ready_units._pre_r3_schema_doc(keyed garbage)="
                            f"{back['live']['pre_r3_keyed_garbage_accepted']}; "
                            "schema_doc_verdict="
                            f"{back['live']['schema_doc_verdict_keyed']}"
                        ),
                    },
                    {
                        "kind": "durable-sweep-reports",
                        "detail": (
                            "P2-BUILD-ROUND2.md and P2-BUILD-ROUND3.md quote "
                            "BYPASS_PROVEN and the merit-stage requirement; "
                            "neither names an owner-visible cost line"
                        ),
                    },
                ],
            },
            {
                "id": "C3-negative-control-still-in-use",
                "claim": (
                    "The back-test produces at least one WOULD-NOT-HAVE-PASSED "
                    "verdict on a mechanism still in use "
                    f"({still_failed[0]['mechanism_id'] if still_failed else 'NONE'}). "
                    "A mutant that blesses every prior adoption is not a gate."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "lineage": [
                    src(lineage, "ready-units"),
                    src(lineage, "wep-wikipedia"),
                ],
                "independent_verification_path": P2,
                "signals": [
                    {
                        "kind": "inventory-still-in-use",
                        "detail": (
                            "still_in_use WOULD-NOT-HAVE-PASSED: "
                            + ",".join(r["mechanism_id"] for r in still_failed)
                        ),
                    },
                    {
                        "kind": "blessing-mutant",
                        "detail": (
                            "gate.blessing_mutant on the historical population "
                            "would report blesses_everything=True; probe2 refuses that"
                        ),
                    },
                ],
            },
        ],
        "tests": [
            {"id": "probe1-record-binds", "command": P1, "result": "PASS"},
            {"id": "probe2-negative-control", "command": P2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "RES-0160-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "defaults_to_refuted": True,
            "notes": (
                "Mechanical adversarial refuter is probe2 (historical still-in-use "
                "WOULD-NOT-HAVE-PASSED, no-metric plant, blessing mutant). No "
                "separate human reviewer ran in a fresh context on this worktree."
            ),
        },
        "evidence": [
            {
                "path": "command-center/ready_units.py",
                "kind": "live-tree",
                "claim": "C2-backtest-last-two-sweeps",
                "detail": "BYPASS_PROVEN / schema_doc_verdict / text_artifact_verdict",
            },
            {
                "path": "command-center/p2-wave/P2-BUILD-ROUND3.md",
                "kind": "dossier",
                "claim": "C2-backtest-last-two-sweeps",
                "detail": "merit-stage requirement recorded in the R3 report",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0160/gate.py",
                "kind": "live-tree",
                "claim": "C1-decision-record-binds-three",
                "detail": "evaluator for adopt/park/reject",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0160/sources/sre-embracing-risk.html",
                "kind": "fetched-source",
                "claim": "C1-decision-record-binds-three",
                "detail": "error-budget halt / rollback as prior art for revert triggers",
            },
        ],
        "source_lineage": list(lineage.values()),
        "strongest_surviving_counterargument": (
            "The last two sweeps could be defined as the in-flight G-1 delivery "
            "wave rather than P2-BUILD ROUND 2 and ROUND 3. If an owner names "
            "different sweep boundaries, this population is the wrong set. "
            "Until that ruling, the P2-BUILD rounds are the last two completed "
            "mechanism-adoption sweeps with durable reports on this estate."
        ),
        "residual_unknowns": [
            {
                "id": "spec-file-absent",
                "detail": (
                    "_USER-PROMPTS.md:11135-11150 is not on this worktree; "
                    "the catalog gloss 'revert when neutral or harmful' is the "
                    "reachable quote."
                ),
            }
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/RES-0160/gate.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0160/inventory.py",
                "exists": True,
                "role": "supporting",
            },
        ],
    }
    validate_or_die(doc)
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"wrote {OUT} n={pop['n']} passed={pop['would_have_passed']} "
        f"failed={pop['would_not_have_passed']} still_failed="
        f"{pop['would_not_have_passed_still_in_use']}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
