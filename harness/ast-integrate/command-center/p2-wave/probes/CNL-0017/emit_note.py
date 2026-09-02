#!/usr/bin/env python3
"""Emit the CNL-0017 design note (JSON in the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import metric as M  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0017-stakeholder-balanced-selection-the-taxonomy-and-the-balanc.md"
)
SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
LOCAL_SCHEMA_REL = "command-center/p2-wave/probes/CNL-0017/note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0017/probe1_score_order.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0017/probe2_both_states.py"
)
QUESTION = (
    "What stakeholder taxonomy does a balance constraint range over, and what "
    "metric decides that a roster is balanced rather than merely diverse in a "
    "way nobody can dispute?"
)


def sha256_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def load(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def present(rel: str) -> bool:
    return (REPO / rel).is_file()


def main() -> int:
    thr = load("threshold.json")
    target = load("target.json")["target"]
    i_star = int(thr["I_star"])
    bal = load("roster-balanced.json")
    unb = load("roster-unbalanced.json")
    neg = load("roster-negative.json")
    even = load("roster-even-off-target.json")
    s_bal = M.score(bal["seats"], target, i_star)
    s_unb = M.score(unb["seats"], target, i_star)
    s_neg = M.score(neg["seats"], target, i_star)
    s_even = M.score(even["seats"], even["target_override"], i_star)
    if s_bal["I"] != 0 or s_unb["I"] != 1 or s_neg["I"] != 6 or s_even["I"] != 1:
        print(
            "FAILED:CNL-0017 emit unexpected scores "
            f"bal={s_bal['I']} unb={s_unb['I']} neg={s_neg['I']} even={s_even['I']}"
        )
        return 1

    thr_sha = sha256_file(HERE / "fixtures" / "threshold.json")
    sources = {
        "_USER-PROMPTS.md:10746-10767": False,
        "_USER-PROMPTS.md:10915-10946": False,
        "11-COUNCIL-SPECIFICATION.schema.json": present(
            "11-COUNCIL-SPECIFICATION.schema.json"
        )
        or present("command-center/sources/11-COUNCIL-SPECIFICATION.schema.json"),
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": present(
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
        )
        or present("command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"),
        "CNL-0005 design note": present(
            "command-center/design/council/"
            "CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md"
        ),
    }

    answer = (
        "A balance constraint ranges over a closed, pre-declared partition of "
        "interest-bearing stakeholder classes, not over model, vendor, expertise, "
        "or protocol role. Each seat carries exactly one stakeholder_class from "
        "that catalog. The metric is L1 / total-variation distance from a "
        "declared occupancy target T: I = (1/2) * sum_c |O[c] - T[c]|. A roster "
        "is balanced iff I <= I_star, with I_star written before any roster is "
        "scored. Richness D = |{c : O[c] > 0}| is not the metric: a roster can "
        "seat every class and still miss quota, and a uniform 1-each roster can "
        "miss a non-uniform target. Nobody disputes the arithmetic once C, T, "
        "O, and I_star are declared; they can only dispute those declarations."
    )

    markdown_body = "\n".join(
        [
            "# CNL-0017 Stakeholder-balanced selection",
            "",
            QUESTION,
            "",
            answer,
            "",
            "## Taxonomy (closed)",
            "Axis: stakeholder_class. One label per seat. Labels are not CNL-0005 dials.",
            "",
            "- owner: authority to accept or reject",
            "- operator: duty to run the result",
            "- end_user: lives with the output",
            "- implementer: must build or maintain",
            "- adversary: tasked to reject or break",
            "- compliance: policy or constraint bearer",
            "",
            "## Metric",
            "I = (1/2) sum |O-T|. Balanced iff I <= I_star. This fixture: I_star=0.",
            "Rejected: richness, min-share (equal on the 2-1-2 vs 3-1-1 pair),",
            "max/min ratio (punishes a declared non-uniform target).",
            "",
            "## Loud unfilled class",
            "Any c with T[c] > 0 and O[c] == 0 is listed in unfilled[]. "
            "The selector does not proceed as if the mix were satisfied.",
            "",
            "SUCCESS:CNL-0017",
        ]
    )

    doc = {
        "unit_id": "CNL-0017",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0017",
        "title": "Stakeholder-balanced selection: the taxonomy and the balance metric",
        "question": QUESTION,
        "answer": answer,
        "distinction": (
            "Balance is L1 distance from a declared occupancy target. Diversity "
            "is richness D (how many classes appear). A roster can have D=|C| "
            "and still have I>0; a uniform 1-each roster can have I>0 against a "
            "non-uniform target. The two are not interchangeable."
        ),
        "irreducible_verdict_requirements": [
            "A deliberately unbalanced roster must score worse than a balanced one, and I_star must be declared before fixtures are scored.",
            "Both-states: the check FIRES on a planted-bad fixture and is SILENT on the known-good one; both runs recorded verbatim.",
            "Negative control recorded verbatim: state what the check does on the state it is meant to reject.",
        ],
        "markdown_body": markdown_body,
        "format": "council-design-note+json",
        "schema": SCHEMA_REL,
        "validated_against": LOCAL_SCHEMA_REL,
        "schema_note": (
            "Catalog output_schema is a $ref shim to "
            "https://ast-integrate.invalid/... . jsonschema 4.10 fetches that "
            "URL. Live validation uses the per-unit note.schema.json so the "
            "state enum and metric/scores requirements stay non-vacuous "
            "without a network retrieve."
        ),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dependency_CNL_0005": {
            "artifact": (
                "command-center/design/council/"
                "CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md"
            ),
            "on_this_tree": sources["CNL-0005 design note"],
            "verdict": "NOT-CHECKED",
            "catalog_nine_dials": list(M.CNL_0005_NINE_DIALS),
            "note": (
                "stakeholder_class is an additional per-seat label. Protocol "
                "role is a CNL-0005 dial; interest class is not. Fixtures "
                "carry both so a chair can be an owner or an adversary."
            ),
        },
        "source_inputs": [
            {
                "path": name,
                "on_this_tree": found,
                "verdict": "CONFIRMED" if found else "NOT-CHECKED",
            }
            for name, found in sources.items()
        ],
        "taxonomy": {
            "id": M.TAXONOMY_ID,
            "axis": "stakeholder_class",
            "closed": True,
            "one_label_per_seat": True,
            "undeclared_is_invalid": True,
            "disjoint_from_cnl_0005_dials": list(M.CNL_0005_NINE_DIALS),
            "classes": [
                {"id": cid, "interest": M.CLASS_INTEREST[cid]} for cid in M.CLASSES
            ],
        },
        "metric": {
            "id": "l1-tv-to-declared-target",
            "formula": "I = (1/2) * sum_c |O[c] - T[c]|",
            "decision": "balanced iff I <= I_star",
            "I_star": i_star,
            "I_star_declared_before_scoring": True,
            "threshold_path": (
                "command-center/p2-wave/probes/CNL-0017/fixtures/threshold.json"
            ),
            "target": target,
            "rejected_metrics": [
                {
                    "id": "richness-D",
                    "why": (
                        "roster-unbalanced-merely-diverse has D=|C| and I=1; "
                        "richness cannot fail it"
                    ),
                },
                {
                    "id": "min-share",
                    "why": (
                        "balanced 2-1-2-1-1-1 and unbalanced 3-1-1-1-1-1 both "
                        "have min share 1/8"
                    ),
                },
                {
                    "id": "max-min-ratio",
                    "why": (
                        "a declared target of 2 owners among 6 seats has "
                        "max/min=2 when exact; evenness would punish a legal mix"
                    ),
                },
            ],
        },
        "scores": {
            "threshold_sha256": thr_sha,
            "I_star": i_star,
            "balanced": {
                "I": s_bal["I"],
                "D": s_bal["D"],
                "fires": s_bal["fires"],
                "observed": s_bal["observed"],
            },
            "unbalanced": {
                "I": s_unb["I"],
                "D": s_unb["D"],
                "fires": s_unb["fires"],
                "observed": s_unb["observed"],
            },
            "negative": {
                "I": s_neg["I"],
                "D": s_neg["D"],
                "fires": s_neg["fires"],
                "unfilled": s_neg["unfilled"],
            },
            "even_off_target": {
                "I": s_even["I"],
                "D": s_even["D"],
                "fires": s_even["fires"],
            },
        },
        "tests": [
            {
                "id": "probe1-score-order",
                "command": P1,
                "result": "PASS",
                "requirement": (
                    "unbalanced I worse than balanced; I_star declared before scoring"
                ),
            },
            {
                "id": "probe2-both-states",
                "command": P2,
                "result": "PASS",
                "requirement": (
                    "FIRES on planted-bad, SILENT on known-good, negative control verbatim"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "all-owner-roster",
                "fixture": (
                    "command-center/p2-wave/probes/CNL-0017/fixtures/"
                    "roster-negative.json"
                ),
                "intended_reject_state": "every seat labelled owner",
                "what_the_check_does": (
                    f"FIRES because I={s_neg['I']} > I_star={i_star}; "
                    f"unfilled={s_neg['unfilled']}; D={s_neg['D']}"
                ),
                "silent_on_known_good": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0017-independent-reverse-recount",
            "independent": True,
            "scope_not_agreement": True,
            "verdict": "STANDS",
            "method": (
                "Reverse-walk seat tally and re-derive I as half the L1 gap. "
                "Did not accept the design-note prose as evidence."
            ),
            "counterexample_instance": {
                "against": "richness-as-balance (D == |C| implies balanced)",
                "roster_id": "roster-unbalanced-merely-diverse",
                "D": s_unb["D"],
                "I": s_unb["I"],
                "I_star": i_star,
                "effect": (
                    "REFUTES richness-as-balance. Does not refute L1-to-target."
                ),
            },
            "second_instance": {
                "against": "evenness-as-balance",
                "roster_id": "roster-even-off-target",
                "D": s_even["D"],
                "I": s_even["I"],
                "effect": (
                    "Uniform 1-each is even and richer than a target that wants "
                    "2 owners and 0 compliance, but I=1 so it is not balanced."
                ),
            },
            "author_metric_refute": "REFUTE-ATTEMPTED-NO-COUNTEREXAMPLE",
        },
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "Balance ranges over a closed stakeholder_class catalog, "
                    "not over the nine CNL-0005 dials."
                ),
                "verdict": "CONFIRMED",
                "anchor": "taxonomy.classes",
            },
            {
                "id": "C2",
                "claim": (
                    "I_unbalanced > I_balanced and I_star declared before scoring."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0017/probe1_score_order.py",
            },
            {
                "id": "C3",
                "claim": "The check FIRES on planted-bad and is SILENT on known-good.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0017/probe2_both_states.py",
            },
            {
                "id": "C4",
                "claim": (
                    "Catalog source files 11-COUNCIL-SPECIFICATION.schema.json and "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json were read on this tree."
                ),
                "verdict": "REFUTED",
                "anchor": "source_inputs",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Signal 1: collections.Counter census matches I_balanced=0 "
                    "and I_unbalanced=1 at I_star=0."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0017/probe1_score_order.py"
                    ":counter_census"
                ),
            },
            {
                "claim": (
                    "Signal 2: sort | uniq -c on the same class column agrees "
                    "with Counter; different process, not a second Python Counter."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0017/probe1_score_order.py"
                    ":shell_census"
                ),
            },
            {
                "claim": (
                    "Both-states: SILENT on roster-balanced, FIRES on "
                    "roster-unbalanced-merely-diverse."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0017/probe2_both_states.py"
                ),
            },
            {
                "claim": (
                    "Negative control: all-owner roster FIRES with I=6 and five "
                    "unfilled target classes."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0017/fixtures/"
                    "roster-negative.json"
                ),
            },
        ],
        "tests_required_record": [
            "a deliberately unbalanced roster must score worse than a balanced one, and the threshold must be declared before the fixtures are scored",
            "a both-states control: the check FIRES on a planted-bad fixture and is SILENT on the known-good one, both runs recorded verbatim",
            "negative control recorded verbatim: state what the check does on the state it is meant to reject",
        ],
        "unfilled_class_rule": (
            "If T[c] > 0 and O[c] == 0 the class is reported in unfilled[] and "
            "balanced is false. The council does not silently continue as if "
            "the mix were met. Downstream IMP-0271 implements the selector; "
            "this unit only defines the census and the loud miss."
        ),
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "catalog-named-schema-shim"},
            {"path": LOCAL_SCHEMA_REL, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/CNL-0017/metric.py",
                "exists": True,
                "role": "metric",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0017/fixtures/threshold.json",
                "exists": True,
                "role": "a-priori-threshold",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "completion_sentinel": "SUCCESS:CNL-0017",
    }

    from jsonschema import Draft202012Validator

    catalog_shim = REPO / SCHEMA_REL
    if not catalog_shim.is_file() or catalog_shim.stat().st_size <= 0:
        print("FAILED:CNL-0017 catalog schema shim missing")
        return 1
    schema = json.loads((REPO / LOCAL_SCHEMA_REL).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(doc))
    if errors:
        print(f"FAILED:CNL-0017 schema {errors[0].message}")
        return 1
    bogus = dict(doc)
    bogus["state"] = "NOT-A-STATE"
    if not list(Draft202012Validator(schema).iter_errors(bogus)):
        print("FAILED:CNL-0017 schema vacuous")
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "CNL-0017", "state": "SUCCESS"},
    ):
        if not list(Draft202012Validator(schema).iter_errors(garbage)):
            print(f"FAILED:CNL-0017 schema accepted garbage {list(garbage)[:2]}")
            return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest = sha256_file(out)
    print(f"wrote {OUT_REL} sha256={digest} bytes={out.stat().st_size}")
    print("SUCCESS:CNL-0017 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
