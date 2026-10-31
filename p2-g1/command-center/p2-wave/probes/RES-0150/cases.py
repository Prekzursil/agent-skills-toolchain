"""Constructed corpora, genuine objections, and deliberately padded fillers."""
from __future__ import annotations

from typing import Any

TOKEN = "FIXTURE-RES-0150-UNIQUE-9f3a"
SRC = "command-center/p2-wave/probes/RES-0150/fixtures/sources"

CLAIM_G_TEXT = (
    "All birds achieve powered flight: every avian taxon, extant or extinct, "
    "uses wings for aerial locomotion."
)
CLAIM_N_TEXT = (
    f"Every document in closed corpus N contains the token {TOKEN}, and the "
    "corpus contains zero DISCONFIRM documents for that statement."
)


def _doc(did: str, label: str, name: str, mechanism: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": did,
        "label": label,
        "path": f"{SRC}/{name}.txt",
        "filename": f"{name}.txt",
    }
    if mechanism:
        row["mechanism_id"] = mechanism
    return row


CORPUS_G = [
    _doc("g-ostrich", "DISCONFIRM", "ostrich", "ratite-flightless"),
    _doc("g-penguin", "DISCONFIRM", "penguin", "penguin-flightless"),
    _doc("g-kiwi", "DISCONFIRM", "kiwi", "kiwi-flightless"),
    _doc("g-moa", "DISCONFIRM", "moa", "extinct-flightless"),
    _doc("g-sparrow", "SUPPORT", "sparrow"),
    _doc("g-eagle", "SUPPORT", "eagle"),
]
CORPUS_N = [
    _doc("n1", "SUPPORT", "n1"),
    _doc("n2", "SUPPORT", "n2"),
    _doc("n3", "SUPPORT", "n3"),
    _doc("n4", "SUPPORT", "n4"),
    _doc("n5", "SUPPORT", "n5"),
]

CLAIM_G = {
    "id": "G-all-birds-fly",
    "text": CLAIM_G_TEXT,
    "corpus": CORPUS_G,
    "closed_world": False,
    "has_genuine_counterevidence": True,
}
CLAIM_N = {
    "id": "N-closed-token-corpus",
    "text": CLAIM_N_TEXT,
    "corpus": CORPUS_N,
    "closed_world": True,
    "has_genuine_counterevidence": False,
}


def genuine_g() -> list[dict[str, Any]]:
    rows = [
        {
            "id": "u-ostrich",
            "polarity": "disconfirming",
            "source_id": "g-ostrich",
            "mechanism_id": "ratite-flightless",
            "path": f"{SRC}/ostrich.txt",
            "url": f"file://{SRC}/ostrich.txt",
            "fetched_at": "2026-08-24T00:00:00Z",
            "text": "Ostriches are extant ratite birds that do not achieve powered flight.",
            "falsifier": "Observe an adult ostrich in powered flight; none is recorded.",
            "confidence_band": "almost certain",
            "independent_verification_path": "rehash fixtures/sources/ostrich.txt; label DISCONFIRM",
        },
        {
            "id": "u-penguin",
            "polarity": "disconfirming",
            "source_id": "g-penguin",
            "mechanism_id": "penguin-flightless",
            "path": f"{SRC}/penguin.txt",
            "url": f"file://{SRC}/penguin.txt",
            "fetched_at": "2026-08-24T00:00:00Z",
            "text": "Penguins are birds that swim with flippers and do not fly.",
            "falsifier": "Document a penguin taxon with sustained aerial powered flight.",
            "confidence_band": "almost certain",
            "independent_verification_path": "rehash fixtures/sources/penguin.txt; label DISCONFIRM",
        },
        {
            "id": "u-kiwi",
            "polarity": "disconfirming",
            "source_id": "g-kiwi",
            "mechanism_id": "kiwi-flightless",
            "path": f"{SRC}/kiwi.txt",
            "url": f"file://{SRC}/kiwi.txt",
            "fetched_at": "2026-08-24T00:00:00Z",
            "text": "Kiwi have vestigial wings and are flightless New Zealand endemics.",
            "falsifier": "Show Apteryx performing powered aerial locomotion.",
            "confidence_band": "almost certain",
            "independent_verification_path": "rehash fixtures/sources/kiwi.txt; label DISCONFIRM",
        },
        {
            "id": "u-moa",
            "polarity": "disconfirming",
            "source_id": "g-moa",
            "mechanism_id": "extinct-flightless",
            "path": f"{SRC}/moa.txt",
            "url": f"file://{SRC}/moa.txt",
            "fetched_at": "2026-08-24T00:00:00Z",
            "text": "Moa (Dinornithiformes) were flightless; the claim fails for extinct taxa too.",
            "falsifier": "Produce evidence moa used wings for powered flight.",
            "confidence_band": "probable",
            "independent_verification_path": "rehash fixtures/sources/moa.txt; label DISCONFIRM",
        },
    ]
    return rows


def supporting_g() -> list[dict[str, Any]]:
    return [
        {
            "id": "s-sparrow",
            "polarity": "supporting",
            "source_id": "g-sparrow",
            "path": f"{SRC}/sparrow.txt",
            "url": f"file://{SRC}/sparrow.txt",
            "fetched_at": "2026-08-24T00:00:00Z",
            "text": "House sparrows achieve powered flight.",
            "falsifier": "n/a-supporting",
            "confidence_band": "almost certain",
            "independent_verification_path": "rehash fixtures/sources/sparrow.txt",
        },
        {
            "id": "s-eagle",
            "polarity": "supporting",
            "source_id": "g-eagle",
            "path": f"{SRC}/eagle.txt",
            "url": f"file://{SRC}/eagle.txt",
            "fetched_at": "2026-08-24T00:00:00Z",
            "text": "Bald eagles achieve powered flight.",
            "falsifier": "n/a-supporting",
            "confidence_band": "almost certain",
            "independent_verification_path": "rehash fixtures/sources/eagle.txt",
        },
    ]


def padded_g() -> list[dict[str, Any]]:
    """Deliberate padding: variants, vacuous hedges, restatements, unsourced, polarity lies."""
    return [
        {
            "id": "p-ostrich-reword",
            "polarity": "disconfirming",
            "source_id": "g-ostrich",
            "mechanism_id": "ratite-flightless",
            "path": f"{SRC}/ostrich.txt",
            "url": f"file://{SRC}/ostrich.txt",
            "fetched_at": "2026-08-24T00:00:00Z",
            "text": "The ostrich is a bird that does not fly; ratites lack powered flight.",
            "falsifier": "Same ostrich observation restated as a second objection.",
            "confidence_band": "almost certain",
            "independent_verification_path": "should-collapse-against-u-ostrich",
        },
        {
            "id": "p-emu-as-ostrich",
            "polarity": "disconfirming",
            "source_id": "g-ostrich",
            "mechanism_id": "ratite-flightless",
            "path": f"{SRC}/ostrich.txt",
            "url": f"file://{SRC}/ostrich.txt",
            "fetched_at": "2026-08-24T00:00:00Z",
            "text": "Emus also cannot fly just like ostriches; another ratite count.",
            "falsifier": "Count a second ratite as if it were a new mechanism.",
            "confidence_band": "probable",
            "independent_verification_path": "should-collapse-ratite",
        },
        {
            "id": "p-vacuous",
            "polarity": "disconfirming",
            "source_id": "",
            "text": "Some people disagree; birds might not necessarily all fly; more research needed.",
            "falsifier": "perhaps",
            "confidence_band": "chances about even",
            "independent_verification_path": "none",
        },
        {
            "id": "p-restate",
            "polarity": "disconfirming",
            "source_id": "",
            "text": CLAIM_G_TEXT,
            "falsifier": "the claim itself restated as an objection",
            "confidence_band": "probable",
            "independent_verification_path": "none",
        },
        {
            "id": "p-unsourced",
            "polarity": "disconfirming",
            "source_id": "g-penguin",
            "mechanism_id": "penguin-flightless",
            "text": "Penguins cannot fly either, trust me.",
            "falsifier": "Anecdote without fetch, timestamp, or sha256.",
            "confidence_band": "probable",
            "independent_verification_path": "none",
        },
        {
            "id": "p-support-as-disconfirm",
            "polarity": "disconfirming",
            "source_id": "g-sparrow",
            "path": f"{SRC}/sparrow.txt",
            "url": f"file://{SRC}/sparrow.txt",
            "fetched_at": "2026-08-24T00:00:00Z",
            "text": "Sparrows fly, which somehow disconfirms the universal claim.",
            "falsifier": "Cite a SUPPORT document as if it were DISCONFIRM.",
            "confidence_band": "probably not",
            "independent_verification_path": "corpus label is SUPPORT",
        },
        {
            "id": "p-invented-source",
            "polarity": "disconfirming",
            "source_id": "g-unicorn-bird",
            "text": "A secret flightless swan in an unfetched URL disconfirms the claim.",
            "falsifier": "Named source is not in the corpus.",
            "confidence_band": "almost certainly not",
            "independent_verification_path": "none",
        },
    ]


def supporting_n() -> list[dict[str, Any]]:
    rows = []
    for i in range(1, 6):
        rows.append(
            {
                "id": f"s-n{i}",
                "polarity": "supporting",
                "source_id": f"n{i}",
                "path": f"{SRC}/n{i}.txt",
                "url": f"file://{SRC}/n{i}.txt",
                "fetched_at": "2026-08-24T00:00:00Z",
                "text": f"Document n{i} contains {TOKEN}.",
                "falsifier": "n/a-supporting",
                "confidence_band": "certain",
                "independent_verification_path": f"rehash fixtures/sources/n{i}.txt",
            }
        )
    return rows


def padded_n() -> list[dict[str, Any]]:
    """Fillers for a claim with no real counterevidence. Counting them is the failure."""
    return [
        {
            "id": "pn-maybe-missing",
            "polarity": "disconfirming",
            "source_id": "",
            "text": f"The token {TOKEN} might be missing from some documents; more research needed.",
            "falsifier": "might",
            "confidence_band": "chances about even",
            "independent_verification_path": "none",
        },
        {
            "id": "pn-false-absent",
            "polarity": "disconfirming",
            "source_id": "n1",
            "path": f"{SRC}/n1.txt",
            "url": f"file://{SRC}/n1.txt",
            "fetched_at": "2026-08-24T00:00:00Z",
            "text": f"Document n1 does not contain {TOKEN} (false filler to hit quota).",
            "falsifier": "Cite a SUPPORT document as DISCONFIRM to manufacture an objection.",
            "confidence_band": "almost certainly not",
            "independent_verification_path": "corpus label SUPPORT; token is present",
        },
        {
            "id": "pn-reword",
            "polarity": "disconfirming",
            "source_id": "",
            "text": "Some sources disagree; the token is perhaps not in every file; it depends.",
            "falsifier": "perhaps it depends",
            "confidence_band": "probably not",
            "independent_verification_path": "none",
        },
        {
            "id": "pn-unsourced",
            "polarity": "disconfirming",
            "text": "I could not find the token, so the claim is false.",
            "falsifier": "Search failure is not a DISCONFIRM document.",
            "confidence_band": "improbable",
            "independent_verification_path": "none",
        },
    ]


def run_has_counter() -> dict[str, Any]:
    return {
        "id": "run-G-has-counterevidence",
        "claim": CLAIM_G,
        "items": genuine_g() + supporting_g() + padded_g(),
        "search_exhausted": True,
        "queries": [
            "flightless bird taxon ostrich penguin kiwi moa",
            "powered flight universal avian claim counterexample",
        ],
        "source_classes_exhausted": [
            "constructed-corpus-G-disconfirm-docs",
            "constructed-corpus-G-support-docs",
        ],
    }


def run_no_counter() -> dict[str, Any]:
    return {
        "id": "run-N-no-counterevidence",
        "claim": CLAIM_N,
        "items": supporting_n() + padded_n(),
        "search_exhausted": True,
        "queries": [
            f"{TOKEN} DISCONFIRM",
            "corpus N documents missing token",
        ],
        "source_classes_exhausted": [
            "constructed-corpus-N-all-five-docs",
        ],
    }
