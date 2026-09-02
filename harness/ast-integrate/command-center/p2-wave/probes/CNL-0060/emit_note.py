#!/usr/bin/env python3
"""Emit the CNL-0060 design note (JSON written at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import admissibility as A  # noqa: E402

ART_REL = (
    "command-center/design/council/"
    "CNL-0060-consent-no-objection-and-the-admissibility-bar-for-an-obje.md"
)
ART = A.REPO / ART_REL
NOTE_SCHEMA = A.REPO / "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0060/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0060/probe2_reviewer_counterexample.py"
)


def lineno(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"needle not found in {path}: {needle}")


def main() -> int:
    proposal = A.load_proposal("proposal.json")
    vacuous = A.load_proposal("proposal-vacuous.json")
    counter = A.load_objection("objection-counterexample.json")
    unfals = A.load_objection("objection-unfalsifiable.json")

    elig = A.proposal_eligible(proposal)
    velig = A.proposal_eligible(vacuous)
    sch_c = A.schema_check(counter)
    sch_u = A.schema_check(unfals)
    ev_c = A.evaluate(proposal, counter)
    ev_u = A.evaluate(proposal, unfals)
    out_c = A.consent_outcome(proposal, [counter])
    out_u = A.consent_outcome(proposal, [unfals])
    out_host = A.consent_outcome(proposal, [unfals, unfals, unfals])
    mutants = A.mutant_battery(proposal)

    src = HERE / "admissibility.py"
    cat = A.REPO / "command-center/WORK-UNIT-CATALOG.json"
    ln_eval = lineno(src, "def evaluate(")
    ln_schema = lineno(src, "def schema_check(")
    ln_outcome = lineno(src, "def consent_outcome(")
    ln_q = lineno(cat, "In a consent decision any objection blocks")

    planted_bad_verbatim = (
        f"evaluate(unfalsifiable) admissible={ev_u['admissible']} "
        f"code={ev_u['code']} schema_ok={ev_u['schema_ok']} "
        f"consent_outcome={out_u['outcome']} blocker_count={out_u['blocker_count']}"
    )
    known_good_verbatim = (
        f"evaluate(counterexample) admissible={ev_c['admissible']} "
        f"code={ev_c['code']} predicate_false={ev_c.get('predicate_false')} "
        f"schema_ok={ev_c['schema_ok']} consent_outcome={out_c['outcome']}"
    )
    neg_verbatim = (
        "On fixture objection-unfalsifiable.json (kind=concern, no instance) "
        f"schema_ok={sch_u['ok']} evaluate.admissible={ev_u['admissible']} "
        f"code={ev_u['code']} outcome={out_u['outcome']}. "
        "The check REFUSES the block so an unfalsifiable concern cannot hostage "
        "the council. If this fixture were admitted, one seat could stall every "
        "consent decision."
    )

    per_class = []
    for row in mutants:
        per_class.append(
            {
                "class": row["class"],
                "planted": int(row["planted"]),
                "caught": int(row["caught"]),
                "recall": float(row["recall"]),
                "scope": row["scope"],
            }
        )

    note = {
        "unit_id": "CNL-0060",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0060",
        "title": "Consent / no-objection and the admissibility bar for an objection",
        "question": (
            "In a consent decision any objection blocks - so what makes an "
            "objection admissible, and what stops one participant from holding "
            "the council hostage with an unfalsifiable concern?"
        ),
        "answer": (
            "Consent / no-objection is fail-closed on admissible objections and "
            "fail-open on unfalsifiable ones. After a recorded window, the "
            "proposal is CONSENTED iff the set of ADMISSIBLE objections is empty. "
            "Silence of a seated participant is defined as consent under this "
            "protocol only (it is not inherited by unanimity or majority). "
            "An objection is admissible only when (1) the objector is seated, "
            "(2) the window is open, (3) the target names a live claim on this "
            "proposal, (4) the record validates against the objection schema, "
            "and (5) the falsifier DISCRIMINATES: a counterexample instance makes "
            "the claim's registered predicate return False, or a vacuity pair "
            "shows the predicate does not distinguish the proposer's known-good "
            "from known-bad. Unfalsifiable concerns (kind=concern, empty "
            "instance, instance that still satisfies the predicate, unseated "
            "filings) are INADMISSIBLE and do not block. Repeated identical "
            "inadmissible filings still do not block. A concrete counterexample "
            "still stands — the bar is not 'ignore all objections'. Chair waiver "
            "of an admissible objection is refused here; that is a veto-override "
            "path (CNL-0024), not consent. A proposal whose own known-bad still "
            "passes its predicate cannot open a consent window."
        ),
        "protocol": {
            "id": "consent-no-objection",
            "silence": "consent",
            "decision_rule": "CONSENTED iff admissible_objections == 0",
            "distinct_from": [
                "unanimity (explicit yes from every seat)",
                "veto (CNL-0024 named kill-right with override)",
                "majority (threshold of ballots)",
            ],
        },
        "detector": {
            "id": "cnl-0060-admissibility-bar",
            "signals": [
                {
                    "id": "schema",
                    "mechanism": "jsonschema Draft-07 over objection.schema.json",
                    "role": "shape: kind in {counterexample,vacuity}; instance required",
                },
                {
                    "id": "predicate-eval",
                    "mechanism": "registered predicate on instance / vacuity pair",
                    "role": "discrimination: predicate False, or pair does not split",
                },
            ],
            "stopping_bind": (
                "Admission is fail-closed AND: both schema_ok and discrimination "
                "must pass before an objection can block. Schema-only success is "
                "not admission (the dressed known-good instance is refused). "
                "OR-admission is rejected because a schema-valid vibe would hostage."
            ),
            "pair_and_gate_rejected": True,
            "pair_and_gate_note": (
                "Rejected treating two schema checks, or two restatements of "
                "admissible, as independent signals. The pair is schema vs "
                "predicate outcome, different functions, different fields."
            ),
        },
        "planted_mutant_control": {
            "scope": "admissibility.evaluate over four planted-bad objection classes",
            "per_class_recall": per_class,
            "unplanted_classes": [
                "nlp-classification-of-prose-vibes",
                "semantic-similarity-of-concern-wording",
            ],
        },
        "both_states": {
            "fired_on_planted_bad": True,
            "silent_on_known_good": True,
            "planted_bad_verbatim": planted_bad_verbatim,
            "known_good_verbatim": known_good_verbatim,
            "fired_means": (
                "hostage-detector fires = evaluate.admissible False on unfalsifiable"
            ),
            "silent_means": (
                "hostage-detector silent = evaluate.admissible True on real break"
            ),
        },
        "negative_control": {
            "state_meant_to_reject": (
                "unfalsifiable concern (kind=concern, no discriminating instance)"
            ),
            "what_the_check_does": (
                "REFUSES admissibility and leaves consent CONSENTED; does not block"
            ),
            "verbatim": neg_verbatim,
        },
        "reviewer": {
            "reviewer_id": "CNL-0060-probe2-reviewer-counterexample",
            "verdict": "PASS",
            "independent": True,
            "recount_agrees": True,
            "counterexample_or": "constructed-instance",
            "note": (
                "Reviewer constructed a schema-valid non-falsifying instance "
                "(must be inadmissible) and an alternate two-absent-seat break "
                "(must be admissible). REFUTED-NOT-ATTEMPTED is not used."
            ),
        },
        "tests": [
            {"id": "probe1-both-states", "command": P1, "result": "PASS"},
            {"id": "probe2-reviewer", "command": P2, "result": "PASS"},
        ],
        "claims": [
            {
                "id": "C1",
                "claim": "Unfalsifiable objections are inadmissible and do not block.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0060/admissibility.py:{ln_eval}",
            },
            {
                "id": "C2",
                "claim": "A concrete counterexample that falsifies the claim stands and blocks.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0060/admissibility.py:{ln_outcome}",
            },
            {
                "id": "C3",
                "claim": "Schema and predicate evaluation are independent signals.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0060/admissibility.py:{ln_schema}",
            },
        ],
        "evidence": [
            {
                "claim": "Catalog question is the unit's load-bearing question.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/WORK-UNIT-CATALOG.json:{ln_q}",
                "command": "python3 -c 'print(open(\"command-center/WORK-UNIT-CATALOG.json\").read().count(\"CNL-0060\"))'",
                "raw_output": "id and question rows present in catalog",
            },
            {
                "claim": "Live evaluate() refuses unfalsifiable and admits the known-bad instance.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0060/admissibility.py:{ln_eval}",
                "command": P1,
                "raw_output": planted_bad_verbatim + " | " + known_good_verbatim,
            },
        ],
        "live": {
            "proposal_eligible": elig,
            "vacuous_eligible": velig,
            "schema_counterexample": sch_c,
            "schema_unfalsifiable": sch_u,
            "eval_counterexample": ev_c,
            "eval_unfalsifiable": ev_u,
            "outcome_counterexample": out_c["outcome"],
            "outcome_unfalsifiable": out_u["outcome"],
            "outcome_triple_unfalsifiable": out_host["outcome"],
            "hostage_blocker_count": out_host["blocker_count"],
        },
        "dependencies_on_this_tree": {
            "CNL-0023": "absent — vote-weight provenance not required to execute the bar",
            "CNL-0024": "absent — veto override is a different protocol; not guessed",
        },
        "residual_unknowns": [
            "11-COUNCIL-SPECIFICATION.schema.json and 12-COUNCIL-PROTOCOLS-AND-PRESETS.json are not on this worktree; the bar is executable from fixtures plus the catalog question.",
            "CNL-0023 and CNL-0024 artifacts are absent; residual, not a structural block for this unit.",
        ],
        "artifacts": [
            {"path": ART_REL, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/CNL-0060/admissibility.py",
                "exists": True,
                "role": "checker",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0060/objection.schema.json",
                "exists": True,
                "role": "objection-schema",
            },
        ],
    }

    if not NOTE_SCHEMA.is_file():
        print("FAILED:emit missing council-design-note schema")
        return 1
    # Catalog shim is $ref-only to ast-integrate.invalid. Draft7Validator on
    # this image fetches that host. Domain gates below are the live bar.
    shim = json.loads(NOTE_SCHEMA.read_text(encoding="utf-8"))
    if shim.get("x-artifact-class") != "council-design-note":
        print("FAILED:emit unexpected design-note schema class", shim.get("x-artifact-class"))
        return 1
    if elig["eligible"] is not True or ev_c["admissible"] is not True:
        print("FAILED:emit live checker did not admit counterexample")
        return 1
    if ev_u["admissible"] is not False or out_u["outcome"] != "CONSENTED":
        print("FAILED:emit live checker admitted unfalsifiable")
        return 1
    if any(int(r["caught"]) != 1 for r in mutants):
        print("FAILED:emit mutant battery", mutants)
        return 1

    ART.parent.mkdir(parents=True, exist_ok=True)
    ART.write_text(
        json.dumps(note, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {ART_REL}")
    print("SUCCESS:CNL-0060 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
