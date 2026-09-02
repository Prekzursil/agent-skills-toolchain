"""Attack CC-0015's encoded predicates. Do not re-encode them.

One named mutation per encoded predicate. Each SATISFIABLE encoding MUST
flip TRUE -> FALSE. Encodings that ignore program state (absent_verbatim)
are named individually as unflippable; they are not DECORATIVE because they
never read TRUE. Condition 13 as-written under binding PR-ONLY is the
opposite pathology (FALSE / unsatisfiable) and is never NOT-CHECKED.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CC_DIR = HERE.parent / "CC-0015"
sys.path.insert(0, str(CC_DIR))
import evaluator as Ev  # noqa: E402
import predicate_table as PT  # noqa: E402

GATES = REPO / "command-center/COMPLETION-GATES.json"

# CC-0015 probe2's evaluable / absent split is the live encoding, not ours.
EVALUABLE_IDS = (1, 4, 5, 7, 8, 11, 12, 13, 14, 15, 16, 17, 18, 19)
ABSENT_IDS = (2, 3, 6, 9, 10, 20, 21)
FLIP_IDS = tuple(i for i in EVALUABLE_IDS if i != 13)


def gate_texts() -> dict[int, str]:
    data = json.loads(GATES.read_text(encoding="utf-8"))
    rows = data["gate_b_program_stopping_rule"]["conditions"]
    return {int(r["n"]): str(r["text"]) for r in rows}


def encodings() -> list[dict[str, Any]]:
    return PT.encodings()


def satisfying_state() -> dict[str, Any]:
    """World in which every *evaluable* CC-0015 encoding (incl. amended 13) is TRUE."""
    s = Ev.blank_state()
    s["selected_option_ids"] = ["OPT-A", "OPT-B"]
    s["dispositions"] = {"OPT-A": "IMPLEMENTED", "OPT-B": "SUPERSEDED"}
    s["required_tests"] = [{"id": "t1", "status": "green"}]
    s["suites"] = [{"id": "s1", "negative_control_observed_fail": True}]
    s["compatibility_cells"] = [
        {"id": "c1", "mark": "SUPPORTED", "test_run": "run-1"}
    ]
    s["benchmark"] = {"verdict": "IMPROVED", "run_ids": ["r1"]}
    s["vuln_scan_fresh"] = True
    s["license_scan_fresh"] = True
    s["docs_code_agree"] = True
    s["canary_succeeded"] = False
    s["marketplace_release_succeeded"] = False
    s["merged_pr"] = True
    s["receipts"] = {
        "REL-0004": {"state": "SUCCESS"},
        "REL-0005": {"state": "SUCCESS"},
        "REL-0006": {"state": "SUCCESS"},
    }
    s["rulings"] = {"REL-0003": {"recorded": True}}
    s["rollback_tested"] = True
    s["unknowns"] = [
        {
            "id": "U1",
            "settling_experiment": "named-exp",
            "impact": "owner-visible",
        }
    ]
    s["counts"] = {
        "workflow_candidates_classified": 160,
        "blueprints_executable": 96,
        "council_protocols": 48,
        "presets": 64,
    }
    s["protocol_ids"] = [f"P{i}" for i in range(48)]
    s["preset_ids"] = [f"S{i}" for i in range(64)]
    s["release_mode"] = "PR-ONLY"
    s["canary_channel_present"] = False
    return s


def as_written_pr_only_state() -> dict[str, Any]:
    """Binding world: PR-ONLY, no owner amendment, canary observations False."""
    s = satisfying_state()
    s["rulings"] = {}
    s["merged_pr"] = None
    s["receipts"] = {}
    s["canary_succeeded"] = False
    s["marketplace_release_succeeded"] = False
    s["release_mode"] = "PR-ONLY"
    s["canary_channel_present"] = False
    return s


def canary_world_state() -> dict[str, Any]:
    """Forbidden (non-binding) world where as-written condition 13 can read TRUE."""
    s = as_written_pr_only_state()
    s["canary_succeeded"] = True
    s["canary_channel_present"] = True
    s["release_mode"] = "CANARY"
    return s


MUTATION_NAMES: dict[int, str] = {
    1: "set selected option OPT-B disposition to OPEN",
    2: "flip docs_code_agree (absent_verbatim ignores world state)",
    3: "flip docs_code_agree (absent_verbatim ignores world state)",
    4: "mark required test t1 status=red",
    5: "clear negative_control_observed_fail on suite s1",
    6: "flip docs_code_agree (absent_verbatim ignores world state)",
    7: "mark compatibility cell SUPPORTED with empty test_run",
    8: "set benchmark verdict REGRESSED",
    9: "flip docs_code_agree (absent_verbatim ignores world state)",
    10: "flip docs_code_agree (absent_verbatim ignores world state)",
    11: "set vuln_scan_fresh False",
    12: "set docs_code_agree False",
    13: "assert canary_succeeded=True while release_mode remains PR-ONLY (as-written)",
    14: "clear rollback_tested",
    15: "strip settling_experiment from unknown U1",
    16: "drop workflow_candidates_classified to 12",
    17: "drop blueprints_executable to 1",
    18: "overlap protocol_ids with preset_ids",
    19: "drop presets count to 3",
    20: "flip docs_code_agree (absent_verbatim ignores world state)",
    21: "flip docs_code_agree (absent_verbatim ignores world state)",
}


def mutate(cid: int, state: dict[str, Any]) -> dict[str, Any]:
    s = copy.deepcopy(state)
    if cid == 1:
        s["dispositions"]["OPT-B"] = "OPEN"
    elif cid in ABSENT_IDS:
        s["docs_code_agree"] = not bool(s.get("docs_code_agree"))
    elif cid == 4:
        s["required_tests"][0] = {"id": "t1", "status": "red"}
    elif cid == 5:
        s["suites"][0]["negative_control_observed_fail"] = False
    elif cid == 7:
        s["compatibility_cells"][0] = {
            "id": "c1",
            "mark": "SUPPORTED",
            "test_run": "",
        }
    elif cid == 8:
        s["benchmark"]["verdict"] = "REGRESSED"
    elif cid == 11:
        s["vuln_scan_fresh"] = False
    elif cid == 12:
        s["docs_code_agree"] = False
    elif cid == 13:
        s["canary_succeeded"] = True
        s["marketplace_release_succeeded"] = False
    elif cid == 14:
        s["rollback_tested"] = False
    elif cid == 15:
        s["unknowns"][0]["settling_experiment"] = ""
    elif cid == 16:
        s["counts"]["workflow_candidates_classified"] = 12
    elif cid == 17:
        s["counts"]["blueprints_executable"] = 1
    elif cid == 18:
        s["preset_ids"] = list(s["protocol_ids"])
    elif cid == 19:
        s["counts"]["presets"] = 3
    else:
        raise RuntimeError(f"no mutation for {cid}")
    return s


def mutate_13_canary_false(state: dict[str, Any]) -> dict[str, Any]:
    s = copy.deepcopy(state)
    s["canary_succeeded"] = False
    return s


def mutate_13_amended_false(state: dict[str, Any]) -> dict[str, Any]:
    s = copy.deepcopy(state)
    s["merged_pr"] = False
    return s


def _row_of(result: dict[str, Any], cid: int) -> dict[str, Any]:
    for row in result["conditions"]:
        if row["id"] == cid:
            return row
    raise KeyError(cid)


def decorative_detector(
    eval_fn: Callable[[dict[str, Any]], Any],
    world: dict[str, Any],
    mutate_fn: Callable[[dict[str, Any]], dict[str, Any]],
) -> bool:
    """True when eval_fn reads TRUE on both world and mutate_fn(world)."""
    before = eval_fn(world)
    after = eval_fn(mutate_fn(copy.deepcopy(world)))
    b = before["verdict"] if isinstance(before, dict) else getattr(before, "value", before)
    a = after["verdict"] if isinstance(after, dict) else getattr(after, "value", after)
    return b == "TRUE" and a == "TRUE"


def planted_constant_true_is_decorative() -> bool:
    """Planted encoding: bool docs_code_agree, mutated on a disjoint field."""
    enc = {
        "id": 99,
        "spec_line": 0,
        "text": "planted constant-TRUE decorative control",
        "text_confidence": "QUOTED",
        "catalog_anchor": "TST-0347 planted control",
        "as_written": {"kind": "bool", "key": "docs_code_agree"},
        "settling_probe": "planted",
        "probe_cost": {"class": "control", "approx_seconds": 1, "approx_usd": 0},
    }
    world = satisfying_state()
    return decorative_detector(
        lambda w: Ev.evaluate_encoding(enc, w),
        world,
        lambda w: mutate(1, w),
    )


def attack() -> dict[str, Any]:
    table = encodings()
    by_enc = {e["id"]: e for e in table}
    texts = gate_texts()
    good = satisfying_state()
    binding = as_written_pr_only_state()
    canary = canary_world_state()
    base_good = Ev.run(good, table)
    base_bind = Ev.run(binding, table)
    base_canary = Ev.run(canary, table)

    rows: list[dict[str, Any]] = []
    for spec in table:
        cid = spec["id"]
        mutation_name = MUTATION_NAMES[cid]
        gates_text = texts.get(cid, spec.get("text") or "")
        if cid == 13:
            before = _row_of(base_bind, 13)
            after = _row_of(Ev.run(mutate(13, binding), table), 13)
            canary_before = _row_of(base_canary, 13)
            canary_after = _row_of(
                Ev.run(mutate_13_canary_false(canary), table), 13
            )
            amended_before = _row_of(base_good, 13)
            amended_after = _row_of(
                Ev.run(mutate_13_amended_false(good), table), 13
            )
            canary_flip = (
                canary_before["verdict"] == "TRUE"
                and canary_after["verdict"] == "FALSE"
            )
            amended_flip = (
                amended_before["verdict"] == "TRUE"
                and amended_after["verdict"] == "FALSE"
            )
            forged_true = after["verdict"] == "TRUE"
            row = {
                "id": 13,
                "condition_id": 13,
                "condition": gates_text,
                "encoded_text": spec.get("text"),
                "spec_line": spec["spec_line"],
                "citation": spec.get("catalog_anchor"),
                "encoding_kind": spec["as_written"].get("kind"),
                "text_confidence": spec.get("text_confidence"),
                "mutation_applied": mutation_name,
                "baseline_verdict": before["verdict"],
                "mutated_verdict": after["verdict"],
                "predicate_verdict": before["verdict"],
                "baseline_evidence": before.get("evidence_pointer"),
                "mutated_evidence": after.get("evidence_pointer"),
                "flipped_true_to_false": False,
                "owner_decision_required": True,
                "class": "PERMANENTLY-UNSATISFIABLE-AS-WRITTEN",
                "unsatisfiable_as_written": before.get("unsatisfiable_as_written"),
                "amendment_applied": before.get("amendment_applied"),
                "canary_world": {
                    "baseline_verdict": canary_before["verdict"],
                    "mutated_verdict": canary_after["verdict"],
                    "flipped_true_to_false": canary_flip,
                    "mutation_applied": "in a canary-channel world, set canary_succeeded False",
                },
                "amended_world": {
                    "baseline_verdict": amended_before["verdict"],
                    "mutated_verdict": amended_after["verdict"],
                    "flipped_true_to_false": amended_flip,
                    "mutation_applied": "under REL-0003 ruling, set merged_pr False",
                },
                "forged_true_under_pr_only_label": forged_true,
                "notes": (
                    "Opposite pathology to decorative: under binding PR-ONLY "
                    "with no amendment the as-written referent has no legal "
                    "channel, so the live binding observation is FALSE, never "
                    "NOT-CHECKED. A canary-channel world (forbidden by OQ-3) "
                    "does flip TRUE->FALSE, proving the encoding is not "
                    "TRUE-stuck. The generic evaluator does not itself refuse "
                    "a forged canary_succeeded=True under a PR-ONLY label "
                    f"(forged_true={forged_true}); unsatisfiability is a world "
                    "constraint plus the encoding metadata flag. Owner "
                    "decision required (OQ-9 / REL-0003 already recorded)."
                ),
            }
            rows.append(row)
            continue

        if cid in ABSENT_IDS:
            before = _row_of(base_good, cid)
            after = _row_of(Ev.run(mutate(cid, good), table), cid)
            flipped = before["verdict"] == "TRUE" and after["verdict"] == "FALSE"
            rows.append(
                {
                    "id": cid,
                    "condition_id": cid,
                    "condition": gates_text,
                    "encoded_text": spec.get("text"),
                    "spec_line": spec["spec_line"],
                    "citation": spec.get("catalog_anchor"),
                    "encoding_kind": (spec.get("as_written") or {}).get("kind"),
                    "text_confidence": spec.get("text_confidence"),
                    "mutation_applied": mutation_name,
                    "baseline_verdict": before["verdict"],
                    "mutated_verdict": after["verdict"],
                    "predicate_verdict": after["verdict"],
                    "baseline_evidence": before.get("evidence_pointer"),
                    "mutated_evidence": after.get("evidence_pointer"),
                    "flipped_true_to_false": flipped,
                    "owner_decision_required": False,
                    "class": "UNFLIPPED-ABSENT-VERBATIM",
                    "notes": (
                        "CC-0015 encoded this line as absent_verbatim. The "
                        "evaluator returns NOT-CHECKED for any world. COMPLETION-"
                        "GATES.json quotes the condition text, so this is a "
                        "CC-0015 encoding gap, not a missing spec sentence. "
                        "Named individually. Not DECORATIVE: it never reads TRUE."
                    ),
                }
            )
            continue

        before = _row_of(base_good, cid)
        after = _row_of(Ev.run(mutate(cid, good), table), cid)
        flipped = before["verdict"] == "TRUE" and after["verdict"] == "FALSE"
        rows.append(
            {
                "id": cid,
                "condition_id": cid,
                "condition": gates_text,
                "encoded_text": spec.get("text"),
                "spec_line": spec["spec_line"],
                "citation": spec.get("catalog_anchor"),
                "encoding_kind": (spec.get("as_written") or {}).get("kind"),
                "text_confidence": spec.get("text_confidence"),
                "mutation_applied": mutation_name,
                "baseline_verdict": before["verdict"],
                "mutated_verdict": after["verdict"],
                "predicate_verdict": after["verdict"],
                "baseline_evidence": before.get("evidence_pointer"),
                "mutated_evidence": after.get("evidence_pointer"),
                "flipped_true_to_false": flipped,
                "owner_decision_required": False,
                "class": "FLIPPED" if flipped else "UNFLIPPED",
                "notes": None,
            }
        )

    unflipped = [r for r in rows if r["id"] != 13 and not r["flipped_true_to_false"]]
    decorative = [
        r
        for r in unflipped
        if r["baseline_verdict"] == "TRUE" and r["mutated_verdict"] == "TRUE"
    ]
    unsat = [r for r in rows if r["class"] == "PERMANENTLY-UNSATISFIABLE-AS-WRITTEN"]

    synthetic = []
    for spec in table:
        if spec["id"] == 4:
            synthetic.append(
                {
                    "id": 4,
                    "verdict": "NOT-CHECKED",
                    "settling_probe": "aggregation control",
                }
            )
        else:
            synthetic.append(
                {"id": spec["id"], "verdict": "TRUE", "settling_probe": "n"}
            )
    agg_nc = Ev.aggregate(synthetic)

    planted = planted_constant_true_is_decorative()
    c13 = unsat[0] if unsat else {}
    flipped_ids = [r["id"] for r in rows if r["flipped_true_to_false"]]

    return {
        "row_count": len(rows),
        "rows": rows,
        "unflipped_named": [
            {
                "id": r["id"],
                "condition": r["condition"],
                "baseline": r["baseline_verdict"],
                "mutated": r["mutated_verdict"],
                "class": r["class"],
            }
            for r in unflipped
        ],
        "decorative_named": [
            {"id": r["id"], "condition": r["condition"]} for r in decorative
        ],
        "permanently_unsatisfiable": [
            {
                "id": r["id"],
                "condition": r["condition"],
                "class": r["class"],
                "owner_decision_required": True,
                "silently_not_checked": r["predicate_verdict"] == "NOT-CHECKED",
                "canary_world_flips": (r.get("canary_world") or {}).get(
                    "flipped_true_to_false"
                ),
                "amended_world_flips": (r.get("amended_world") or {}).get(
                    "flipped_true_to_false"
                ),
                "forged_true_under_pr_only_label": r.get(
                    "forged_true_under_pr_only_label"
                ),
            }
            for r in unsat
        ],
        "aggregation_control": {
            "setup": "20 TRUE + 1 NOT-CHECKED (condition 4)",
            "result": agg_nc,
            "must_not_report_complete": agg_nc["program_complete"] is False,
        },
        "planted_decorative_detected": planted,
        "cc0015_modules": {
            "evaluator": "command-center/p2-wave/probes/CC-0015/evaluator.py",
            "predicate_table": "command-center/p2-wave/probes/CC-0015/predicate_table.py",
        },
        "encoding_ids": {
            "evaluable": list(EVALUABLE_IDS),
            "absent_verbatim": list(ABSENT_IDS),
            "flip_expected": list(FLIP_IDS),
        },
        "pass": (
            len(rows) == 21
            and set(r["id"] for r in rows) == set(range(1, 22))
            and flipped_ids == list(FLIP_IDS)
            and [r["id"] for r in unflipped] == list(ABSENT_IDS)
            and not decorative
            and len(unsat) == 1
            and unsat[0]["id"] == 13
            and unsat[0]["predicate_verdict"] == "FALSE"
            and unsat[0]["predicate_verdict"] != "NOT-CHECKED"
            and (unsat[0].get("canary_world") or {}).get("flipped_true_to_false")
            is True
            and (unsat[0].get("amended_world") or {}).get("flipped_true_to_false")
            is True
            and agg_nc["program_complete"] is False
            and planted is True
            and by_enc[13].get("as_written_satisfiability")
            == "UNSATISFIABLE-AS-WRITTEN"
        ),
    }
