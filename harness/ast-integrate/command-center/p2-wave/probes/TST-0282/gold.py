"""Author-constructed labelled completeness gold set for TST-0282.

Labels are rubric integers 0-10 assigned from the case kind and the rater note
BEFORE scoring. The scorer does not read human_label. This is not an independent
human rater panel; provenance is disclosed as author-constructed fixtures.

Rubric (compensatory, 0-10):
  0 empty
  1 padding or stubs only
  2 one thin real answer
  3 one axis gamed or mostly missing
  4-5 mixed partial
  6-7 mostly there
  8-9 nearly complete (one declared item short)
  10 complete and sourced on all three axes
human_label = rubric / 10.
"""
from __future__ import annotations

import json
from typing import Any

LOREM = (
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed eiusmod tempor "
    "incididunt ut labore et dolore magna aliqua placeholder padding filler "
    "asdf qwerty xxx dummy spam blah boilerplate paddingtext aaaa bbbb cccc"
)

SUBQUESTIONS = [
    ("sq-def", "What operational definition does completeness_score use?"),
    ("sq-val", "Against what labelled set is the 0.90 threshold validated?"),
    ("sq-pad", "Does extra volume raise the score without covering declared items?"),
    ("sq-reach", "Can a genuinely complete output reach the 0.90 threshold?"),
    ("sq-bind", "May the score bind in a stopping rule on this evidence?"),
]
CATEGORIES = ["findings", "options", "risks", "residuals"]
EVIDENCE_CLASSES = ["measurement", "primary-source", "counterexample"]

BODIES = {
    "sq-def": (
        "Operational completeness counts declared subquestions, required "
        "categories, and named evidence classes; extras never mint credit."
    ),
    "sq-val": (
        "Validate 0.90 against a held-out labelled gold set by Spearman rank "
        "correlation plus an interval; unpublished labels stay UNVERIFIED."
    ),
    "sq-pad": (
        "Adversarial padding dumps undeclared answers and lorem volume; the "
        "min-coverage score must stay below the stopping threshold."
    ),
    "sq-reach": (
        "A genuinely complete output covers every declared subquestion, every "
        "required category, and every named evidence class with cited payloads."
    ),
    "sq-bind": (
        "Bind completeness_score in a stopping rule only after labelled "
        "validation; otherwise flag the spec example as under-specified."
    ),
}

EV_PAYLOADS = {
    "measurement": (
        "Held-out Spearman point estimate and bootstrap percentile interval "
        "computed from raw per-case score versus rubric pairs."
    ),
    "primary-source": (
        "Catalog stopping example unique_ideas greater-equal 100 AND "
        "completeness_score greater-equal 0.90 quoted from TST-0265 inputs."
    ),
    "counterexample": (
        "Planted padded fixture with high token volume and zero declared "
        "coverage must not reach the 0.90 stopping threshold."
    ),
}

RATER_PROVENANCE = (
    "Author-constructed fixture labels for TST-0282. Not a held-out production "
    "human panel. Rubric integers assigned from case kind; scorer never reads them."
)

COMPLETE_ID = "heldout.complete-a"
PADDED_ID = "heldout.padded-volume"


def default_objective() -> dict[str, Any]:
    return {
        "subquestions": [{"id": i, "text": t} for i, t in SUBQUESTIONS],
        "required_categories": list(CATEGORIES),
        "evidence_classes": list(EVIDENCE_CLASSES),
    }


def _evidence_items(classes: list[str]) -> list[dict[str, Any]]:
    items = []
    for klass in classes:
        items.append(
            {
                "id": f"ev-{klass}",
                "evidence_class": klass,
                "payload": EV_PAYLOADS[klass],
            }
        )
    return items


def _padding_answers(n: int) -> list[dict[str, Any]]:
    rows = []
    for i in range(n):
        rows.append(
            {
                "id": f"pad-{i}",
                "subquestion_id": f"undeclared-{i}",
                "categories": ["padding"],
                "body": LOREM + f" {i}",
                "cites": [],
            }
        )
    return rows


def make_output(
    *,
    sq_ids: list[str],
    categories: list[str],
    evidence_classes: list[str],
    padding_n: int = 0,
    stub: bool = False,
    tag_all_categories_on_first: bool = False,
    uncited_evidence: bool = False,
) -> dict[str, Any]:
    answers: list[dict[str, Any]] = []
    cite_all = [] if uncited_evidence else [f"ev-{k}" for k in evidence_classes]
    for i, sq in enumerate(sq_ids):
        if tag_all_categories_on_first and i == 0:
            cats = list(categories)
        elif categories:
            cats = [categories[i % len(categories)]]
        else:
            cats = []
        body = "ok yes sure" if stub else BODIES[sq]
        answers.append(
            {
                "subquestion_id": sq,
                "categories": cats,
                "body": body,
                "cites": [] if stub or uncited_evidence else cite_all,
            }
        )
    if padding_n:
        answers.extend(_padding_answers(padding_n))
    evidence = _evidence_items(evidence_classes)
    if padding_n:
        evidence.append(
            {
                "id": "ev-padding-orphan",
                "evidence_class": "undeclared-class",
                "payload": LOREM,
            }
        )
    prose = (LOREM + " ") * padding_n if padding_n else ""
    return {
        "answers": answers,
        "evidence": evidence,
        "padding": prose,
    }


def _case(
    cid: str,
    split: str,
    kind: str,
    rubric: int,
    note: str,
    output: dict[str, Any],
) -> dict[str, Any]:
    if rubric < 0 or rubric > 10:
        raise ValueError(cid)
    return {
        "id": cid,
        "split": split,
        "kind": kind,
        "rubric": rubric,
        "human_label": rubric / 10.0,
        "rater_note": note,
        "objective": default_objective(),
        "output": output,
    }


def all_cases() -> list[dict[str, Any]]:
    sq_all = [s[0] for s in SUBQUESTIONS]
    return [
        _case(
            "train.empty",
            "train",
            "empty",
            0,
            "No answers, no evidence.",
            {"answers": [], "evidence": [], "padding": ""},
        ),
        _case(
            "train.padded",
            "train",
            "padded",
            1,
            "Volume only; no declared ids.",
            make_output(
                sq_ids=[],
                categories=[],
                evidence_classes=[],
                padding_n=16,
            ),
        ),
        _case(
            "train.stubs",
            "train",
            "stub",
            1,
            "All ids present as three-word stubs.",
            make_output(
                sq_ids=sq_all,
                categories=CATEGORIES,
                evidence_classes=EVIDENCE_CLASSES,
                stub=True,
            ),
        ),
        _case(
            "train.one-sq",
            "train",
            "thin",
            2,
            "One real subquestion, one category, no evidence cites.",
            make_output(
                sq_ids=["sq-def"],
                categories=["findings"],
                evidence_classes=[],
                uncited_evidence=True,
            ),
        ),
        _case(
            "train.sq-cats-no-ev",
            "train",
            "unsourced",
            5,
            "All questions and categories, zero named evidence classes. "
            "Compensatory rubric 5; min-coverage will be 0.",
            make_output(
                sq_ids=sq_all,
                categories=CATEGORIES,
                evidence_classes=[],
                uncited_evidence=True,
            ),
        ),
        _case(
            "train.partial",
            "train",
            "partial",
            5,
            "Three subquestions, two categories, one evidence class.",
            make_output(
                sq_ids=["sq-def", "sq-val", "sq-pad"],
                categories=["findings", "options"],
                evidence_classes=["measurement"],
            ),
        ),
        _case(
            "train.near",
            "train",
            "near",
            8,
            "Misses one subquestion; other axes full.",
            make_output(
                sq_ids=["sq-def", "sq-val", "sq-pad", "sq-reach"],
                categories=CATEGORIES,
                evidence_classes=EVIDENCE_CLASSES,
            ),
        ),
        _case(
            "train.complete",
            "train",
            "complete",
            10,
            "All declared items covered and cited.",
            make_output(
                sq_ids=sq_all,
                categories=CATEGORIES,
                evidence_classes=EVIDENCE_CLASSES,
            ),
        ),
        _case(
            "heldout.empty",
            "heldout",
            "empty",
            0,
            "Empty held-out control.",
            {"answers": [], "evidence": [], "padding": ""},
        ),
        _case(
            PADDED_ID,
            "heldout",
            "padded",
            1,
            "Deliberate volume padding; must not reach 0.90.",
            make_output(
                sq_ids=[],
                categories=[],
                evidence_classes=[],
                padding_n=24,
            ),
        ),
        _case(
            "heldout.stubs",
            "heldout",
            "stub",
            1,
            "Stub-filled declared ids.",
            make_output(
                sq_ids=sq_all,
                categories=CATEGORIES,
                evidence_classes=EVIDENCE_CLASSES,
                stub=True,
            ),
        ),
        _case(
            "heldout.one-axis-sq",
            "heldout",
            "gamed",
            3,
            "All questions, one category, one evidence class.",
            make_output(
                sq_ids=sq_all,
                categories=["findings"],
                evidence_classes=["measurement"],
            ),
        ),
        _case(
            "heldout.gamed-cats-ev",
            "heldout",
            "gamed",
            3,
            "One real question tagged with every category plus all evidence.",
            make_output(
                sq_ids=["sq-def"],
                categories=CATEGORIES,
                evidence_classes=EVIDENCE_CLASSES,
                tag_all_categories_on_first=True,
            ),
        ),
        _case(
            "heldout.partial-mid",
            "heldout",
            "partial",
            5,
            "Three questions, two categories, two evidence classes.",
            make_output(
                sq_ids=["sq-def", "sq-val", "sq-pad"],
                categories=["findings", "options"],
                evidence_classes=["measurement", "primary-source"],
            ),
        ),
        _case(
            "heldout.miss-one-sq",
            "heldout",
            "near",
            8,
            "Four of five subquestions; categories and evidence full.",
            make_output(
                sq_ids=["sq-def", "sq-val", "sq-pad", "sq-reach"],
                categories=CATEGORIES,
                evidence_classes=EVIDENCE_CLASSES,
            ),
        ),
        _case(
            "heldout.miss-one-cat",
            "heldout",
            "near",
            8,
            "All questions, three of four categories, all evidence.",
            make_output(
                sq_ids=sq_all,
                categories=["findings", "options", "risks"],
                evidence_classes=EVIDENCE_CLASSES,
            ),
        ),
        _case(
            "heldout.miss-one-ev",
            "heldout",
            "near",
            8,
            "All questions and categories; two of three evidence classes.",
            make_output(
                sq_ids=sq_all,
                categories=CATEGORIES,
                evidence_classes=["measurement", "primary-source"],
            ),
        ),
        _case(
            COMPLETE_ID,
            "heldout",
            "complete",
            10,
            "Genuinely complete held-out output; must reach 0.90.",
            make_output(
                sq_ids=sq_all,
                categories=CATEGORIES,
                evidence_classes=EVIDENCE_CLASSES,
            ),
        ),
        _case(
            "heldout.complete-padded-extra",
            "heldout",
            "complete",
            9,
            "Complete coverage plus extra undeclared padding (padding must not punish).",
            make_output(
                sq_ids=sq_all,
                categories=CATEGORIES,
                evidence_classes=EVIDENCE_CLASSES,
                padding_n=12,
            ),
        ),
        _case(
            "heldout.thin-two",
            "heldout",
            "thin",
            2,
            "Two real subquestions, one category, no evidence.",
            make_output(
                sq_ids=["sq-def", "sq-val"],
                categories=["findings"],
                evidence_classes=[],
                uncited_evidence=True,
            ),
        ),
    ]


def gold_document() -> dict[str, Any]:
    cases = all_cases()
    return {
        "id": "TST-0282-labelled-completeness-gold",
        "label_provenance": RATER_PROVENANCE,
        "rubric": (
            "Integer 0-10 assigned from case kind; human_label = rubric/10. "
            "Independent of min() aggregation."
        ),
        "formula_id": "min-three-axis-declared-coverage-v1",
        "threshold": 0.90,
        "n": len(cases),
        "n_train": sum(1 for c in cases if c["split"] == "train"),
        "n_heldout": sum(1 for c in cases if c["split"] == "heldout"),
        "complete_id": COMPLETE_ID,
        "padded_id": PADDED_ID,
        "cases": cases,
    }


def dump_gold(path) -> dict[str, Any]:
    doc = gold_document()
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return doc
