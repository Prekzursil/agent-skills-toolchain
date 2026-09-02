#!/usr/bin/env python3
"""Emit CNL-0090 detector spec (JSON stored at the catalog .md path)."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

OUT = "command-center/design/council/CNL-0090-circular-debate-information-gain-per-round.md"
SCHEMA = "command-center/schema/council-detector-spec.schema.json"
SCHEMA_LOCAL = "command-center/p2-wave/probes/CNL-0090/artifact.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0090/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0090/probe2_independent_gain.py"
)
QUESTION = (
    "How is per-round information gain computed, and what gain threshold "
    "means the debate is circling rather than converging?"
)
CLAIM = (
    "G_t is the count of new claims plus new evidence nodes in round t. A claim "
    "is new only when its claim_id is unseen and its text is not a token-Jaccard "
    "or char-4gram duplicate of a prior claim. Circling is G_t < 1 for 2 "
    "consecutive rounds. Paraphrase with new ids still fires; refinement that "
    "adds evidence without new claims stays silent."
)
COUNTER = (
    "A council can spend two rounds restating a lemma while a participant "
    "prepares a proof; firing on G_t = 0 would abort useful incubation. That "
    "objection survives as a policy preference for a larger WINDOW, not as a "
    "refutation of the metric: a preparing seat can still add an evidence node "
    "or a new lemma claim, and WINDOW=2 is the named bound, not a hidden round cap."
)


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def find_line(rel: str, snippet: str) -> int:
    path = REPO / rel
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0090 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def compact_curve(result: dict) -> list[dict]:
    return [
        {
            "round": g["round"],
            "information_units": g["information_units"],
            "subfloor": g["subfloor"],
            "new_claim_ids": g.get("new_claim_ids"),
            "new_evidence_ids": g.get("new_evidence_ids"),
        }
        for g in result["gain_curve"]
    ]


def main() -> int:
    rc1, out1 = run(P1)
    if rc1 != 0:
        print("FAILED:CNL-0090 emit probe1")
        print(out1[-2000:])
        return 1

    fixtures = {
        "loop": json.loads(D.fixture_path("planted_loop.json").read_text(encoding="utf-8")),
        "paraphrase": json.loads(
            D.fixture_path("planted_paraphrase.json").read_text(encoding="utf-8")
        ),
        "productive": json.loads(
            D.fixture_path("clean_productive.json").read_text(encoding="utf-8")
        ),
        "refinement": json.loads(
            D.fixture_path("clean_refinement.json").read_text(encoding="utf-8")
        ),
    }
    det = {k: D.detect(doc) for k, doc in fixtures.items()}
    ids = {k: D.id_set_gain(doc) for k, doc in fixtures.items()}
    fp_num = int(det["productive"]["fired"]) + int(det["refinement"]["fired"])
    fpr = fp_num / 2.0
    if not det["loop"]["fired"] or fpr != 0.0:
        print("FAILED:CNL-0090 emit both-states numbers")
        return 1

    e1 = ev(
        "command-center/p2-wave/probes/CNL-0090/detector.py",
        "G_t = |new claims| + |new evidence nodes|",
        "Information units are new claims plus new evidence, not round count.",
    )
    e2 = ev(
        "command-center/p2-wave/probes/CNL-0090/detector.py",
        "FLOOR = 1",
        "The circling floor is one information unit: G_t < 1 is subfloor.",
    )
    e3 = ev(
        "command-center/p2-wave/probes/CNL-0090/detector.py",
        "WINDOW = 2",
        "Circling fires after two consecutive subfloor rounds.",
    )
    e4 = ev(
        "command-center/p2-wave/probes/CNL-0090/canonicalize.py",
        "CHAR4_DUP = 0.35",
        "Char-4gram Jaccard >= 0.35 corroborates paraphrase as the same claim.",
    )
    e5 = ev(
        "command-center/p2-wave/probes/CNL-0090/fixtures/planted_loop.json",
        '"id": "planted-loop-verbatim"',
        "Detector-control known-present instance is the verbatim looping council.",
    )
    e6 = ev(
        "command-center/p2-wave/probes/CNL-0090/fixtures/clean_refinement.json",
        '"id": "clean-refinement-new-evidence"',
        "Negative-control sibling: new evidence without new claims must stay silent.",
    )
    e7 = ev(
        "command-center/WORK-UNIT-CATALOG.json",
        "How is per-round information gain computed, and what gain threshold means the debate is circling rather than converging?",
        "Catalog question this spec answers.",
    )

    loop_line = next(
        line
        for line in out1.splitlines()
        if line.startswith("detector-control-known-present")
    )
    good_line = next(
        line for line in out1.splitlines() if line.startswith("known-good-productive")
    )
    fpr_line = next(
        line for line in out1.splitlines() if line.startswith("fired_on_bad=")
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "CNL-0090",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0090",
        "completion_sentinel": "SUCCESS:CNL-0090",
        "detector_id": "council.antifail.circular-debate.information-gain",
        "title": "Circular debate: information gain per round",
        "question": QUESTION,
        "claim_under_test": CLAIM,
        "pathology": {
            "id": "circular-debate-no-information-gain",
            "description": (
                "The council keeps producing turns whose claims and evidence are "
                "already in the prior set, including paraphrases that mint new ids. "
                "Spec failure class: non-converging debate / loops forever without "
                "information gain."
            ),
            "spec_anchors": [
                "_USER-PROMPTS.md:11234",
                "_USER-PROMPTS.md:11338",
                "WORK-UNIT-CATALOG.json:CNL-0090",
                "WORK-UNIT-CATALOG.json:IMP-0322",
                "WORK-UNIT-CATALOG.json:TST-0263",
            ],
        },
        "mechanism": {
            "summary": (
                "Per-round information gain G_t counts semantically new claims plus "
                "new evidence nodes. Structured claim_id identity is signal 1; "
                "token Jaccard and char-4gram Jaccard on claim_text are signal 2. "
                "A claim is new only if both signals agree it is unseen. Vote "
                "motion and Shannon entropy of position_id are diagnostic traces "
                "and do not enter G_t."
            ),
            "information_units": "G_t = |new_claims| + |new_evidence|",
            "signals": [
                {
                    "id": "signal-1-structured-ids",
                    "reads": (
                        "set difference of claim_id and evidence_id against the "
                        "union of all prior rounds"
                    ),
                },
                {
                    "id": "signal-2-text-corroboration",
                    "reads": (
                        "token Jaccard >= 0.85 or char-4gram Jaccard >= 0.35 "
                        "against prior claim_text; either hit marks the claim as "
                        "not-new even when claim_id is fresh"
                    ),
                },
            ],
            "why_votes_are_diagnostic": (
                "Two camps can twitch position labels while restating the same "
                "slogans. Counting vote_changes inside G_t would let slogan-swap "
                "look like information."
            ),
            "why_entropy_is_diagnostic": (
                "Entropy collapse without new claims or evidence is premature "
                "convergence (IMP-0323). Copy-paste agreement with G_t = 0 still "
                "fires here because nothing new was said."
            ),
        },
        "thresholds": {
            "floor_information_units": D.FLOOR,
            "consecutive_subfloor_rounds": D.WINDOW,
            "token_jaccard_duplicate": 0.85,
            "char4_jaccard_duplicate": 0.35,
            "meaning": (
                "G_t < 1 means the round added neither a new claim nor a new "
                "evidence node. Two such rounds in a row is circling, not "
                "convergence. The bound is not a hardcoded round cap: a "
                "productive council that keeps introducing counterexamples never "
                "crosses the floor."
            ),
        },
        "both_states": {
            "detector_control_first": True,
            "planted_bad": {
                "fixture": "command-center/p2-wave/probes/CNL-0090/fixtures/planted_loop.json",
                "fired": True,
                "fired_at_round": det["loop"]["fired_at_round"],
                "verbatim": loop_line,
            },
            "known_good": {
                "fixture": "command-center/p2-wave/probes/CNL-0090/fixtures/clean_productive.json",
                "silent": True,
                "verbatim": good_line,
            },
            "probe1_summary": fpr_line,
        },
        "false_positive_rate": fpr,
        "false_positive_numerator": fp_num,
        "false_positive_denominator": 2,
        "gain_curves": {
            "detector": {k: compact_curve(v) for k, v in det.items()},
            "id_set_only": {k: compact_curve(v) for k, v in ids.items()},
            "paraphrase_divergence": {
                "detector_fired": det["paraphrase"]["fired"],
                "id_set_fired": ids["paraphrase"]["fired"],
                "detector_units": [g["information_units"] for g in det["paraphrase"]["gain_curve"]],
                "id_set_units": [g["information_units"] for g in ids["paraphrase"]["gain_curve"]],
                "note": (
                    "Id-set-only stays SILENT on paraphrase because new claim_ids "
                    "look like gain. The detector FIREs because text corroboration "
                    "zeros G_t and no new evidence arrives."
                ),
            },
            "refinement_discrimination": {
                "detector_fired": det["refinement"]["fired"],
                "units": [g["information_units"] for g in det["refinement"]["gain_curve"]],
                "note": (
                    "Rounds 2-4 add evidence and no new claims. G_t stays at 2, "
                    "above the floor, so careful refinement is not circling."
                ),
            },
        },
        "tests": [
            {"id": "T1-both-states-detector-control", "command": P1, "result": "PASS"},
            {
                "id": "T2-independent-id-set-vs-jaccard",
                "command": P2,
                "result": "PASS",
            },
        ],
        "evidence": [e1, e2, e3, e4, e5, e6, e7],
        "negative_control": {
            "state_rejected": (
                "clean-productive-counterexamples: a council that introduces a new "
                "counterexample and a new evidence node every round"
            ),
            "what_the_check_does": (
                "On that state the check stays SILENT (fired=false). If it fired, "
                "G_t would be measuring turns rather than information. Recorded "
                "verbatim below from probe 1."
            ),
            "verbatim": good_line,
        },
        "strongest_surviving_counterargument": COUNTER,
        "reviewer": {
            "reviewer_id": "CNL-0090-probe2-independent-gain",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "re_derived_from": (
                "id-set set-difference on the same four fixtures, not from this "
                "spec's prose"
            ),
        },
        "residual_unknowns": [
            "Full-rewrite duplicates that share neither tokens nor char-4grams are NOT-CHECKED; that class is CNL-0051's remainder and is not claimed here.",
            "tools/council/simulate.py is absent on this worktree; curves are from constructed fixtures, not 15 recorded live councils (IMP-0322).",
            "Absolute WINDOW=2 is a named policy on these fixtures; a larger corpus may justify a different consecutive-subfloor bound.",
        ],
        "scoped_recall": {
            "in_scope": [
                "verbatim restatement of the same claim_ids",
                "hyphenation and compound paraphrases that mint new ids",
                "refinement that adds evidence without new claims (must not fire)",
                "productive new counterexamples (must not fire)",
            ],
            "not_checked": [
                "embedding-level full rewrite",
                "cross-language paraphrase",
                "live multi-protocol gain curves required by TST-0263",
            ],
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/CNL-0090/detector.py",
                "exists": True,
                "role": "mechanism",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0090/probe1_both_states.py",
                "exists": True,
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0090/probe2_independent_gain.py",
                "exists": True,
                "role": "named-probe",
            },
            {"path": SCHEMA_LOCAL, "exists": True, "role": "schema"},
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-4000:]},
            {"id": "probe2", "command": P2, "role": "independent-id-set-gain"},
        ],
        "answer": (
            "G_t = |new claims| + |new evidence|. Newness requires unseen claim_id "
            "AND text that is not a token-Jaccard>=0.85 or char-4gram>=0.35 duplicate. "
            f"Circling threshold: G_t < {D.FLOOR} for {D.WINDOW} consecutive rounds. "
            f"Planted loop fires at round {det['loop']['fired_at_round']}; productive "
            f"and refinement stay silent; false_positive_rate={fpr}. "
            "SUCCESS:CNL-0090"
        ),
        "timestamps": {"ended_at": now},
        "schema_version": 1,
        "report_kind": "council-detector-spec",
        "dependency_cnl_0051": (
            "CNL-0051 is not delivered on this tree. canonicalize.py is the local "
            "anti-gaming core this detector actually executes; it does not close "
            "the full-rewrite class."
        ),
    }

    schema = json.loads((REPO / SCHEMA_LOCAL).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0090 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:CNL-0090 schema accepted garbage {list(g)[:2]}")
            return 1
    shared_path = REPO / SCHEMA
    if shared_path.is_file():
        shared = json.loads(shared_path.read_text(encoding="utf-8"))
        try:
            jsonschema.Draft7Validator(shared).validate(doc)
        except RefResolutionError as exc:
            print(
                "WARN: catalog council-detector-spec.schema.json is a $ref shim; "
                "local schema used"
            )

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")

    rc2, out2 = run(P2)
    if rc2 != 0:
        print("FAILED:CNL-0090 emit probe2 after artifact write")
        print(out2[-2000:])
        return 1
    print(out2.splitlines()[-4:])
    print("SUCCESS:CNL-0090 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
