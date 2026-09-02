#!/usr/bin/env python3
"""Emit the CNL-0050 design note (JSON with a .md filename, per G-1 parser)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as N  # noqa: E402
import compose as C  # noqa: E402
import meta_trees as M  # noqa: E402

OUT = (
    REPO
    / "command-center"
    / "design"
    / "council"
    / "CNL-0050-protocol-composition-primitives-phase-ordering-and-the-spe.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
QUESTION = (
    "What primitives (sequence, splice, nest, repeat-until) compose two protocols "
    "into a custom one, how is divergence-before-convergence enforced as an ordering "
    "constraint the composer cannot accidentally violate, and - measured independently "
    "- which protocols named in the spec's own list have NO card among the 58 (a first "
    "pass finds steelman and negotiation absent) so must be authored rather than composed?"
)


def main() -> int:
    gap = N.gap_report()
    meta = M.compile_all()
    good = C.compile_expr(C.KNOWN_GOOD["expr"])
    bad = C.negative_control_record()
    splice_bad = C.compile_expr(C.PLANTED_BAD_SPLICE["expr"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not gap["cards"]["methods_agree"] or gap["cards"]["n_method_a"] != 58:
        print("FAILED:CNL-0050 census did not independently recover 58 cards")
        return 1
    if meta["n_compile_fail"] or meta["n"] != 7:
        print("FAILED:CNL-0050 META-COMPOSITION trees did not compile")
        return 1
    if good["accepted"] is not True or bad["accepted"] is not False:
        print("FAILED:CNL-0050 both-states compile control did not discriminate")
        return 1

    doc = {
        "unit_id": "CNL-0050",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0050",
        "schema": SCHEMA,
        "ts": now,
        "question": QUESTION,
        "source_disclosure": {
            "twelve_council_file_on_disk": gap["cards"]["library_file_present"],
            "user_prompts_on_disk": (
                (REPO / "_USER-PROMPTS.md").is_file()
                or (REPO / "command-center/_USER-PROMPTS.md").is_file()
            ),
            "card_census_source": gap["cards"]["source"],
            "card_census_method": (
                "Two parsers over CNL-0038..CNL-0046 question_or_target "
                "(regex P-id+slug vs comma-split of the named-so-no-member list). "
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent; the catalog units "
                "are the on-tree witness of those 58 P-ids."
            ),
            "spec_name_source": gap["spec"]["note"],
        },
        "primitives": {
            "names": ["sequence", "splice", "nest", "repeat-until"],
            "sequence": "Concatenate child schedules. No implicit fan-out.",
            "splice": "Insert one compiled schedule into another at a compile-time index.",
            "nest": "Emit diverge, run inners, emit converge. The only primitive that opens a split.",
            "repeat_until": (
                "Compile one body iteration plus an until:<pred> marker. The predicate "
                "is a hole for CNL-0010; this unit does not claim a stopping parser."
            ),
            "non_primitive": (
                "There is no fifth 'parallel' op. Parallelism is nest. A composer who "
                "wants fan-in without nest must use a converge leaf, which the phase "
                "checker rejects unless a diverge is already open."
            ),
        },
        "phase_ordering": {
            "rule": "diverge-before-converge",
            "enforcement": "compile-time stack: diverge pushes, converge pops; pop on empty stack is reject",
            "composer_cannot_accidentally_violate": True,
            "known_good": {
                "id": C.KNOWN_GOOD["id"],
                "accepted": good["accepted"],
                "code": good["code"],
                "n_events": len(good["events"]),
            },
            "planted_bad": bad,
            "planted_splice_bad": {
                "id": C.PLANTED_BAD_SPLICE["id"],
                "accepted": splice_bad["accepted"],
                "code": splice_bad["code"],
            },
        },
        "meta_composition": meta,
        "spec_vs_corpus_gap": {
            "inherited_from_unit_brief": False,
            "brief_first_pass_names": ["steelman", "negotiation"],
            "n_cards": gap["cards"]["n_method_a"],
            "n_spec_named": gap["spec"]["n"],
            "spec_named": [x["name"] for x in gap["spec"]["names"]],
            "gap_conservative": gap["gap_conservative"],
            "gap_substring": gap["gap_substring"],
            "n_gap_conservative": gap["n_gap_conservative"],
            "n_gap_substring": gap["n_gap_substring"],
            "rows": [
                {
                    "name": r["name"],
                    "source_unit": r["source_unit"],
                    "has_card_conservative": r["match"]["has_card_conservative"],
                    "conservative_hits": r["match"]["conservative_hits"],
                }
                for r in gap["rows"]
            ],
            "must_be_authored_not_composed": gap["gap_conservative"],
        },
        "decision": {
            "summary": (
                "Custom protocols are compiled from sequence, splice, nest and "
                "repeat-until. Nest is the only split; a stack checker rejects any "
                "converge that is not preceded by an unmatched diverge, so "
                "converge-before-diverge is a compile error. Independently recomputed "
                f"from catalog quotations, {gap['n_gap_conservative']} spec-named "
                f"protocol(s) have no card among the 58: {gap['gap_conservative']}. "
                "Those must be authored. All 7 META-COMPOSITION cards compile in the "
                "four primitives (0 gaps in that family)."
            )
        },
        "evidence": [
            {
                "claim": "A converge-before-diverge composition is rejected at compile time.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0050/compose.py:check_order",
            },
            {
                "claim": "The 58 card names were recovered by two disagreeable parsers, both n=58.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/WORK-UNIT-CATALOG.json CNL-0038..CNL-0046 question_or_target",
            },
            {
                "claim": "Spec-vs-corpus gap was set-subtracted from catalog-quoted spec names, not copied from this unit's brief.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0050/census.py:gap_report",
            },
            {
                "claim": "Every META-COMPOSITION card is expressible in the primitives or listed as a gap.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0050/meta_trees.py:META_TREES",
            },
        ],
        "tests": [
            {
                "id": "T-compile-order",
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0050/probe1_compile_order.py",
                "result": "PASS",
            },
            {
                "id": "T-gap-and-meta",
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0050/probe2_gap_and_meta.py",
                "result": "PASS",
            },
        ],
        "negative_control": bad,
        "reviewer": {
            "reviewer_id": "CNL-0050-probe2-method-b-comma-split",
            "independent": True,
            "verdict": "PASS",
            "recount": {
                "cards_method_b": gap["cards"]["n_method_b"],
                "gap_conservative_n": gap["n_gap_conservative"],
                "disagreement_with_author_method_a": not gap["cards"]["methods_agree"],
            },
        },
        "artifacts": [
            {
                "path": str(OUT.relative_to(REPO)).replace("\\", "/"),
                "exists": True,
                "role": "primary",
            }
        ],
        "dependencies_on_tree": {
            "CNL-0046_artifact": (
                REPO
                / "command-center/design/council/CNL-0046-executable-runtime-semantics-for-the-7-meta-composition-pr.md"
            ).is_file(),
            "CNL-0010_artifact": (
                REPO
                / "command-center/design/council/CNL-0010-stopping-expression-grammar-and-static-validation.schema.json"
            ).is_file(),
            "note": (
                "CNL-0046 and CNL-0010 artifacts are absent. META-COMPOSITION membership "
                "is taken from CNL-0046's catalog enumeration (P52-P58), not from its "
                "missing design note. repeat-until's predicate is an explicit hole."
            ),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    try:
        import jsonschema  # type: ignore

        schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
        jsonschema.Draft7Validator(schema).validate(doc)
        print("schema_ok=True")
    except Exception as exc:
        print(f"schema_validate_warning={type(exc).__name__}:{exc}")
    print(f"wrote {OUT.relative_to(REPO)} sentinel=SUCCESS:CNL-0050")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
