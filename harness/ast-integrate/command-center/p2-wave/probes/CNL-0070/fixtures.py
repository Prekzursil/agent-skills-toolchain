"""Deterministic council fixtures for CNL-0070."""
from __future__ import annotations

import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

CLAIM_ALPHA = (
    "Consensus 0.95 is undefined when one seat is silent; "
    "a silent seat is not reasoned dissent."
)
TOKEN_ALPHA = "CNL0070-DISSENT-ALPHA"
CLAIM_BETA = (
    "A 90-percent stop that deletes the minority claim has not preserved dissent."
)
TOKEN_BETA = "CNL0070-DISSENT-BETA"


def _base_meta() -> dict:
    return {
        "unit_id": "CNL-0070",
        "protocols": [
            {"id": "P56", "name": "minority-report-mandatory"},
        ],
        "voting": {"quorum": 4, "rule": "unanimous-or-record-dissent"},
        "stopping": {
            "expression": "90 percent consensus with a mandatory minority report",
            "mandatory_minority_report": True,
            "threshold": 0.9,
        },
    }


def _dissent_alpha() -> dict:
    return {
        "dissent_id": "D-ALPHA",
        "participant_id": "seat-D",
        "claim": CLAIM_ALPHA,
        "evidence": "turn:r2.seat-D",
        "verbatim_token": TOKEN_ALPHA,
    }


def _dissent_beta() -> dict:
    return {
        "dissent_id": "D-BETA",
        "participant_id": "seat-C",
        "claim": CLAIM_BETA,
        "evidence": "turn:r2.seat-C",
        "verbatim_token": TOKEN_BETA,
    }


def known_good() -> dict:
    alpha = _dissent_alpha()
    doc = _base_meta()
    doc["label"] = "known-good"
    doc["transcript"] = {
        "votes": [
            {"participant_id": "seat-A", "vote": "yes"},
            {"participant_id": "seat-B", "vote": "yes"},
            {"participant_id": "seat-C", "vote": "yes"},
            {
                "participant_id": "seat-D",
                "vote": "no",
                "dissent_id": "D-ALPHA",
                "claim": CLAIM_ALPHA,
                "evidence": "turn:r2.seat-D",
                "verbatim_token": TOKEN_ALPHA,
            },
        ],
        "turns": [
            {
                "id": "turn:r2.seat-D",
                "kind": "dissent",
                "dissent_id": "D-ALPHA",
                "participant_id": "seat-D",
                "claim": CLAIM_ALPHA,
                "evidence": "turn:r2.seat-D",
                "verbatim_token": TOKEN_ALPHA,
            }
        ],
        "dissents": [copy.deepcopy(alpha)],
    }
    doc["outcome"] = {"variant": "dissent-with-minority-report"}
    doc["synthesis"] = {
        "recommendation": "Adopt the majority option.",
        "majority": "yes",
        "minority_report": [copy.deepcopy(alpha)],
        "outcome": {"variant": "dissent-with-minority-report"},
    }
    return doc


def dropped_dissent() -> dict:
    doc = known_good()
    doc["label"] = "planted-bad-dropped-dissent"
    doc["synthesis"] = {
        "recommendation": "Adopt the majority option.",
        "majority": "yes",
        "minority_report": [],
        "outcome": {"variant": "decision"},
    }
    return doc


def footnote_only() -> dict:
    doc = known_good()
    doc["label"] = "footnote-only"
    doc["synthesis"]["minority_report"] = [
        {
            "dissent_id": "D-ALPHA",
            "participant_id": "seat-D",
            "claim": "dissent noted",
            "evidence": "n/a",
            "verbatim_token": "",
        }
    ]
    return doc


def unattributed() -> dict:
    doc = known_good()
    doc["label"] = "unattributed"
    row = copy.deepcopy(_dissent_alpha())
    row["participant_id"] = ""
    doc["synthesis"]["minority_report"] = [row]
    return doc


def partial_drop() -> dict:
    alpha = _dissent_alpha()
    beta = _dissent_beta()
    doc = known_good()
    doc["label"] = "partial-drop"
    doc["transcript"]["votes"][2] = {
        "participant_id": "seat-C",
        "vote": "no",
        "dissent_id": "D-BETA",
        "claim": CLAIM_BETA,
        "evidence": "turn:r2.seat-C",
        "verbatim_token": TOKEN_BETA,
    }
    doc["transcript"]["turns"].append(
        {
            "id": "turn:r2.seat-C",
            "kind": "dissent",
            "dissent_id": "D-BETA",
            "participant_id": "seat-C",
            "claim": CLAIM_BETA,
            "evidence": "turn:r2.seat-C",
            "verbatim_token": TOKEN_BETA,
        }
    )
    doc["transcript"]["dissents"] = [copy.deepcopy(alpha), copy.deepcopy(beta)]
    doc["synthesis"]["minority_report"] = [copy.deepcopy(alpha)]
    return doc


def no_dissent() -> dict:
    doc = _base_meta()
    doc["label"] = "no-dissent-unanimous"
    doc["voting"] = {"quorum": 4, "rule": "unanimous-or-record-dissent"}
    doc["transcript"] = {
        "votes": [
            {"participant_id": "seat-A", "vote": "yes"},
            {"participant_id": "seat-B", "vote": "yes"},
            {"participant_id": "seat-C", "vote": "yes"},
            {"participant_id": "seat-D", "vote": "yes"},
        ],
        "turns": [],
        "dissents": [],
    }
    doc["outcome"] = {"variant": "decision"}
    doc["synthesis"] = {
        "recommendation": "Adopt the unanimous option.",
        "majority": "yes",
        "minority_report": [],
        "outcome": {"variant": "decision"},
    }
    return doc


FIXTURES = {
    "known-good": known_good,
    "dropped-dissent": dropped_dissent,
    "footnote-only": footnote_only,
    "unattributed": unattributed,
    "partial-drop": partial_drop,
    "no-dissent": no_dissent,
}


def write_fixture_files() -> list[str]:
    FIX.mkdir(parents=True, exist_ok=True)
    written = []
    for name, builder in FIXTURES.items():
        path = FIX / f"{name}.json"
        path.write_text(
            json.dumps(builder(), indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        written.append(path.relative_to(HERE.parents[3]).as_posix())
    return written
