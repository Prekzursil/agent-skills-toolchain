#!/usr/bin/env python3
"""Planted mutants written for CNF-0189."""
from __future__ import annotations

SEED_ID = "plant.seed.unanimous-four-voice-halt8"
SEED_TITLE = "Four-voice unanimous halt-at-eight"
SEED_BODY = (
    "Four named voices each cast one equal-weight ballot. The motion carries "
    "only when every ballot assents. The sitting ends after eight rounds or "
    "when the clock expires, whichever comes first. Dissent is recorded in "
    "the transcript. There is no chair override and no secret weight on any seat."
)

DEEP_ID = "plant.deep.unanimous-four-voice-halt8"
DEEP_TITLE = "Quartet must all agree then stop at eight cycles"
DEEP_BODY = (
    "A quartet of speakers each submits one peer-weighted ticket. Passage "
    "requires total agreement from every ticket. The session terminates after "
    "eight cycles or when allotted time elapses, whichever arrives sooner. "
    "Disagreement is written into the minutes. No moderator may force a result "
    "and no hidden multiplier applies to any occupant."
)

RENAME_ID = "plant.rename.unanimous-four-voice-halt8"
ONEPARAM_ID = "plant.oneparam.unanimous-four-voice-halt12"
SURFACE_ID = "plant.surface.unanimous-four-voice-halt8"
DISTINCT_ID = "plant.distinct.static-scan-halt-on-error"

NEAR_DUP_CLASSES = frozenset(
    {"rename", "one_parameter", "surface", "deep_paraphrase"}
)
DISTINCT_CLASSES = frozenset({"distinct"})
SEED_ID = SEED_ID
NEAR_DUP_CLASSES = NEAR_DUP_CLASSES


def records() -> list[dict]:
    return [
        {
            "id": SEED_ID,
            "kind": "council_protocol",
            "family": "planted",
            "mutant_class": "seed",
            "mutant_class": "seed",
            "title": SEED_TITLE,
            "body": SEED_BODY,
            "source": "planted-for-CNF-0189",
        },
        {
            "id": RENAME_ID,
            "kind": "council_protocol",
            "family": "planted",
            "mutant_class": "rename",
            "mutant_class": "rename",
            "title": SEED_TITLE + " (alias)",
            "body": SEED_BODY,
            "source": "planted-for-CNF-0189",
            "pair_of": SEED_ID,
        },
        {
            "id": ONEPARAM_ID,
            "kind": "council_protocol",
            "family": "planted",
            "mutant_class": "one_parameter",
            "mutant_class": "one_parameter",
            "title": "Four-voice unanimous halt-at-twelve",
            "body": SEED_BODY.replace("eight rounds", "twelve rounds"),
            "source": "planted-for-CNF-0189",
            "pair_of": SEED_ID,
        },
        {
            "id": SURFACE_ID,
            "kind": "council_protocol",
            "family": "planted",
            "mutant_class": "surface",
            "mutant_class": "surface",
            "title": "Four voices unanimous stop after eight rounds",
            "body": (
                "Four named voices each cast one equal-weight ballot. The motion "
                "carries only when every ballot assents. The sitting ends after "
                "eight rounds or when the clock expires, whichever comes first. "
                "Dissent is recorded in the transcript. Chair override is absent "
                "and secret weight on any seat is absent."
            ),
            "source": "planted-for-CNF-0189",
            "pair_of": SEED_ID,
        },
        {
            "id": DEEP_ID,
            "kind": "council_protocol",
            "family": "planted",
            "mutant_class": "deep_paraphrase",
            "mutant_class": "deep_paraphrase",
            "title": DEEP_TITLE,
            "body": DEEP_BODY,
            "source": "planted-for-CNF-0189",
            "pair_of": SEED_ID,
        },
        {
            "id": DISTINCT_ID,
            "kind": "workflow_blueprint",
            "family": "planted",
            "mutant_class": "distinct",
            "mutant_class": "distinct",
            "title": "Two-stage static repository scan with halt-on-error",
            "body": (
                "A filesystem walk over the repository emits candidates.json. A "
                "second-stage writer emits blueprint.json and halt-on-error if the "
                "writer returns nonzero. No ballots, no voices, no rounds, no "
                "unanimous sitting."
            ),
            "source": "planted-for-CNF-0189",
            "pair_of": SEED_ID,
        },
    ]
