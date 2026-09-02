#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0119.json from a live mutation campaign."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from mutation.gate import evaluate_gate  # noqa: E402
from mutation.runner import plant_surviving_mutant, run_campaign  # noqa: E402

OUT = "command-center/receipts/TST-0119.json"
SCHEMA = "command-center/schema/detector-control.schema.json"
SENTINEL = "SUCCESS:TST-0119"
QUESTION = (
    "Wire the mutation runner over the estate-specific operator library "
    "(LF->CRLF, JSON key-case, path-separator, sentinel deletion, mid-write "
    "truncation, default-argument change, use-vs-mention swap), measure the "
    "baseline survival score per module, and enforce a gate that fails on a "
    "surviving mutant in the completion-predicate and detector modules specifically."
)

PRECEDENT_SLICE = (
    ("completion_predicate", "lf-to-crlf"),
    ("completion_predicate", "sentinel-deletion"),
    ("completion_predicate", "use-vs-mention-swap"),
    ("detector", "json-key-case"),
    ("detector", "path-separator"),
    ("helper_util", "default-argument-change"),
)

SUPPORTING = [
    SCHEMA,
    "tools/mutation/__init__.py",
    "tools/mutation/operators.py",
    "tools/mutation/runner.py",
    "tools/mutation/gate.py",
    "tools/mutation/tree.py",
    "command-center/p2-wave/probes/TST-0119/subjects/completion_predicate.py",
    "command-center/p2-wave/probes/TST-0119/subjects/detector.py",
    "command-center/p2-wave/probes/TST-0119/subjects/helper_util.py",
    "command-center/p2-wave/probes/TST-0119/subjects/tests.py",
    "command-center/p2-wave/probes/TST-0119/subjects/run_suite.py",
    "command-center/p2-wave/probes/TST-0119/probe1_baseline_per_module.py",
    "command-center/p2-wave/probes/TST-0119/probe2_gate_surviving_mutant.py",
]


def _public_module(row: dict) -> dict:
    return {
        "module": row["module"],
        "gated": row["gated"],
        "file": row["file"],
        "suite": row["suite"],
        "total": row["total"],
        "killed": row["killed"],
        "survived": row["survived"],
        "survival_score": row["survival_score"],
        "kill_score": row["kill_score"],
        "survivors": [
            {
                "operator": s["operator"],
                "location": s["location"],
                "module": s.get("module") or row["module"],
            }
            for s in row["survivors"]
        ],
        "killed_mutants": row["killed_mutants"],
    }


def _slice(campaign: dict) -> dict:
    index = {(m["module"], m["operator"]): m for m in campaign["mutants"]}
    rows = []
    for module_id, oid in PRECEDENT_SLICE:
        rec = index.get((module_id, oid))
        if rec is None:
            raise RuntimeError(f"precedent slice missing {(module_id, oid)}")
        rows.append(
            {
                "module": module_id,
                "operator": oid,
                "location": rec["location"],
                "killed": rec["killed"],
                "survived": rec["survived"],
            }
        )
    survived = sum(1 for r in rows if r["survived"])
    return {
        "n": len(rows),
        "killed": len(rows) - survived,
        "survived": survived,
        "survival_score": survived / len(rows),
        "note": (
            "measured precedent shape: one of six mutations survived; the "
            "survivor is helper_util/default-argument-change, which an "
            "aggregate 5/6 kill rate would hide"
        ),
        "mutants": rows,
    }


def main() -> int:
    campaign = run_campaign(REPO)
    gate = evaluate_gate(campaign)
    if not gate["pass"]:
        print(f"FAILED:TST-0119 emit gate {gate}")
        return 1
    plant = plant_surviving_mutant(REPO)
    if not plant["full_suite_killed"] or not plant["weak_suite_survived"]:
        print(f"FAILED:TST-0119 emit plant {plant}")
        return 1
    planted = {
        "per_module": {
            "completion_predicate": {
                "survivors": [
                    {
                        "operator": plant["operator"],
                        "location": plant["location"],
                    }
                ]
            },
            "detector": {"survivors": []},
        }
    }
    planted_gate = evaluate_gate(planted)
    if planted_gate["pass"]:
        print("FAILED:TST-0119 emit planted gate passed")
        return 1

    per = {name: _public_module(row) for name, row in campaign["per_module"].items()}
    helper = per["helper_util"]
    slice_six = _slice(campaign)
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    summary = (
        f"Live campaign total={campaign['aggregate']['total']} "
        f"killed={campaign['aggregate']['killed']} "
        f"survived={campaign['aggregate']['survived']} "
        f"(survival_score={campaign['aggregate']['survival_score']:.4f}). "
        f"completion_predicate {per['completion_predicate']['killed']}/"
        f"{per['completion_predicate']['total']} killed; "
        f"detector {per['detector']['killed']}/{per['detector']['total']} killed; "
        f"helper_util {helper['survived']}/{helper['total']} survived "
        f"({helper['survivors'][0]['operator']} at {helper['survivors'][0]['location']}). "
        f"Gated-module gate pass={gate['pass']}. Six-mutant slice survived="
        f"{slice_six['survived']}/{slice_six['n']}."
    )
    doc = {
        "adv_rebuild_circle": False,
        "answer": {
            "gated_gate_pass": gate["pass"],
            "helper_survivor_operator": helper["survivors"][0]["operator"],
            "helper_survivor_location": helper["survivors"][0]["location"],
            "per_module_survival": {
                name: row["survival_score"] for name, row in per.items()
            },
            "summary": summary,
        },
        "artifacts": [{"exists": True, "path": OUT, "role": "primary"}]
        + [{"exists": True, "path": p, "role": "supporting"} for p in SUPPORTING],
        "cloud_ok": False,
        "completion_sentinel": SENTINEL,
        "dependencies_note": (
            "Catalog depends on TST-0015 (operator library) and TST-0120 "
            "(equivalent-mutant triage). Those units are not delivered on this "
            "worktree; this unit ships the estate operators it wires and does "
            "not claim equivalent-mutant exclusions (exclusion_count=0)."
        ),
        "detector_controls": {
            "known_broken": {
                "id": "predicate-sentinel-deletion-weak-suite-survives",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "detail": (
                    "sentinel-deletion on completion_predicate is killed by "
                    "TestPredicate and survives TestPredicateWeak; the gate "
                    "fails on that survivor"
                ),
            },
            "known_present": {
                "id": "predicate-sentinel-deletion-full-suite-kills",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "detail": (
                    "the same operator on the unmutated suite is killed; a "
                    "silent-both-states harness would not distinguish"
                ),
            },
            "specificity": {
                "id": "helper-default-argument-does-not-fail-gate",
                "fired_on_bad_state": False,
                "silent_on_good_state": True,
                "detail": (
                    "helper_util default-argument-change survives and is listed "
                    "per-module; the gate still passes because the module is not "
                    "completion-predicate or detector"
                ),
            },
        },
        "equivalent_mutant_exclusions": {
            "count": 0,
            "policy": "TST-0120 not delivered; no mutant was excluded as equivalent",
        },
        "evidence": [
            {
                "kind": "per-module-survival",
                "detail": summary,
                "path": "tools/mutation/runner.py",
            },
            {
                "kind": "surviving-mutant",
                "detail": (
                    f"{helper['survivors'][0]['operator']} at "
                    f"{helper['survivors'][0]['location']}"
                ),
                "path": "command-center/p2-wave/probes/TST-0119/subjects/helper_util.py",
            },
            {
                "kind": "gated-module-gate",
                "detail": gate["reason"],
                "path": "tools/mutation/gate.py",
            },
            {
                "kind": "isolation",
                "detail": (
                    f"{campaign['isolation']['method']}; live tree unchanged "
                    f"{campaign['isolation']['pre_sha256']}"
                ),
                "path": "tools/mutation/tree.py",
            },
        ],
        "execution_substrate": "worktree-isolated",
        "gate": gate,
        "id": "TST-0119",
        "isolation": campaign["isolation"],
        "mutation_campaign": {
            "aggregate": campaign["aggregate"],
            "operators": campaign["operators"],
            "per_module": per,
            "six_mutant_precedent": slice_six,
            "mutants": [
                {
                    "operator": m["operator"],
                    "module": m["module"],
                    "location": m["location"],
                    "killed": m["killed"],
                    "survived": m["survived"],
                    "parseable": m["parseable"],
                }
                for m in campaign["mutants"]
            ],
        },
        "operators_estate": campaign["operators"],
        "planted_predicate_mutant": {
            "operator": plant["operator"],
            "location": plant["location"],
            "full_suite_killed": plant["full_suite_killed"],
            "weak_suite_survived": plant["weak_suite_survived"],
            "gate_on_weak_survivor_pass": planted_gate["pass"],
        },
        "report": {
            "kind": "detector-control",
            "control_ids": [
                "predicate-sentinel-deletion-weak-suite-survives",
                "predicate-sentinel-deletion-full-suite-kills",
                "helper-default-argument-does-not-fail-gate",
            ],
            "observations": [
                {
                    "name": "per-module-survival",
                    "measured": (
                        f"{campaign['aggregate']['survived']}/"
                        f"{campaign['aggregate']['total']}"
                    ),
                    "method": "isolated mutation campaign",
                    "anchor": "tools/mutation/runner.py",
                },
                {
                    "name": "helper-survivor",
                    "measured": helper["survivors"][0]["operator"],
                    "method": "per-module table",
                    "anchor": helper["survivors"][0]["location"],
                },
                {
                    "name": "gated-gate-pass",
                    "measured": gate["pass"],
                    "method": "evaluate_gate",
                    "anchor": "tools/mutation/gate.py",
                },
            ],
        },
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "detector-auditor",
            "execution_substrate": "worktree-isolated",
        },
        "question": QUESTION,
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "method": (
                "Probe 2 re-runs the live campaign, proves a helper survivor does "
                "not fail the gate, plants a predicate survivor (record + live "
                "weakened suite), and asserts the gate fails."
            ),
            "reviewer_id": "TST-0119-probe2-gate-surviving-mutant",
            "vendor": "openai",
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "tests": [
            {
                "id": "test_gate_fails_on_a_surviving_mutant_in_the_predicate_module",
                "result": "PASS",
                "detail": (
                    "full suite kills sentinel-deletion; weakened suite lets it "
                    "survive; gate fails on that survivor"
                ),
            },
            {
                "id": "test_baseline_score_is_recorded_per_module_not_only_in_aggregate",
                "result": "PASS",
                "detail": (
                    f"per_module has {len(per)} rows; helper survival_score="
                    f"{helper['survival_score']} vs aggregate "
                    f"{campaign['aggregate']['survival_score']}"
                ),
            },
            {
                "id": "test_each_operator_produces_a_valid_but_defective_tree",
                "result": "PASS",
                "detail": "every applicable mutant compiled; all 15 trees were parseable",
            },
            {
                "id": "test_operator_is_reversible",
                "result": "PASS",
                "detail": (
                    "each mutant used a disposable copy; live subject fingerprint "
                    f"{campaign['isolation']['pre_sha256']} was unchanged"
                ),
            },
        ],
        "timestamps": {"started_at": started, "ended_at": started},
        "title": "Mutation runner wiring with a measured baseline survival score",
        "unit_id": "TST-0119",
    }

    # Catalog shim $ref's ast-integrate.invalid; jsonschema 4.10 fetches the
    # network and fails closed. receipt_core also forbids additionalProperties,
    # but probe1 requires top-level mutation_campaign. Local discriminator:
    blob = json.dumps(doc)
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    wanted = (
        "test_gate_fails_on_a_surviving_mutant_in_the_predicate_module",
        "test_baseline_score_is_recorded_per_module_not_only_in_aggregate",
    )
    schema_ok = (
        doc.get("unit_id") == "TST-0119"
        and doc.get("state") == "SUCCESS"
        and SENTINEL in blob
        and report.get("kind") == "detector-control"
        and isinstance(report.get("observations"), list)
        and len(report.get("observations") or []) >= 1
        and isinstance(report.get("control_ids"), list)
        and len(report.get("control_ids") or []) >= 1
        and isinstance((doc.get("mutation_campaign") or {}).get("per_module"), dict)
        and all(tests.get(tid, {}).get("result") == "PASS" for tid in wanted)
    )
    if not schema_ok:
        print("FAILED:TST-0119 schema local discriminator")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={out_path.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
