"""Scripted councils for CNL-0097: lost-dissent both-states fixtures.

The transcript is shared. Only the synthesis changes between planted-bad
and known-good. Clean fixtures keep dissent content in the synthesis.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

QUESTION = (
    "Should the release ship tonight without a tested rollback plan for the "
    "schema migration?"
)

SKEPTIC_DISSENT = (
    "Shipping without a tested rollback plan is an irreversible production "
    "risk because a failed schema migration cannot be undone inside the "
    "four-hour maintenance window."
)
CRITIC_DISSENT = (
    "The release also lacks a customer-visible feature flag, so a partial "
    "outage cannot be isolated to one cohort."
)
DISSENT_ID = "d-rollback-required"
DISSENT_ID_2 = "d-feature-flag"


def _transcript(*, extra_dissent: bool = False) -> dict:
    turns = [
        {
            "turn_id": "t1",
            "speaker": "architect",
            "role": "Architect",
            "kind": "proposal",
            "text": (
                "Ship tonight. The migration is backward compatible enough; "
                "rollback can be a follow-up ticket."
            ),
        },
        {
            "turn_id": "t2",
            "speaker": "pragmatist",
            "role": "Pragmatist",
            "kind": "agreement",
            "text": "Agree. Customer pressure outweighs the residual migration risk.",
        },
        {
            "turn_id": "t3",
            "speaker": "skeptic",
            "role": "Skeptic",
            "kind": "dissent",
            "stance": "against",
            "dissent_id": DISSENT_ID,
            "claim_id": "c-rollback-required",
            "text": SKEPTIC_DISSENT,
        },
    ]
    votes = [
        {"speaker": "architect", "vote": "for", "option_id": "ship-tonight"},
        {"speaker": "pragmatist", "vote": "for", "option_id": "ship-tonight"},
        {
            "speaker": "skeptic",
            "vote": "against",
            "option_id": "ship-tonight",
            "dissent_id": DISSENT_ID,
            "claim_id": "c-rollback-required",
            "reason": SKEPTIC_DISSENT,
        },
    ]
    if extra_dissent:
        turns.append(
            {
                "turn_id": "t4",
                "speaker": "critic",
                "role": "Critic",
                "kind": "dissent",
                "stance": "against",
                "dissent_id": DISSENT_ID_2,
                "claim_id": "c-feature-flag",
                "text": CRITIC_DISSENT,
            }
        )
        votes.append(
            {
                "speaker": "critic",
                "vote": "against",
                "option_id": "ship-tonight",
                "dissent_id": DISSENT_ID_2,
                "reason": CRITIC_DISSENT,
            }
        )
    return {
        "question": QUESTION,
        "adopted_option_id": "ship-tonight",
        "turns": turns,
        "votes": votes,
        "minority_reports": [
            {
                "dissent_id": DISSENT_ID,
                "speaker": "skeptic",
                "text": SKEPTIC_DISSENT,
            }
        ],
    }


def planted_bad() -> dict:
    """Pathology present: transcript dissent omitted from synthesis."""
    return {
        "id": "planted-bad-dropped-dissent",
        "label": "planted-bad",
        "expected_fire": True,
        "transcript": _transcript(),
        "synthesis": {
            "text": (
                "The council unanimously recommends shipping tonight. Residual "
                "migration risk is acceptable. Rollback can be scheduled later. "
                "All concerns were addressed."
            ),
            "acknowledged_dissent_ids": [],
            "self_attestation": {"all_dissent_preserved": True},
        },
    }


def planted_void_id_only() -> dict:
    """Id listed, body absent — presence-only checks must still FIRE."""
    return {
        "id": "planted-void-id-only",
        "label": "planted-bad",
        "expected_fire": True,
        "transcript": _transcript(),
        "synthesis": {
            "text": (
                "The council recommends shipping tonight. Dissent d-rollback-required "
                "is noted and closed."
            ),
            "acknowledged_dissent_ids": [DISSENT_ID],
            "self_attestation": {"all_dissent_preserved": True},
        },
    }


def planted_generic_mention() -> dict:
    """Generic 'there was dissent' without the claim body."""
    return {
        "id": "planted-generic-mention",
        "label": "planted-bad",
        "expected_fire": True,
        "transcript": _transcript(),
        "synthesis": {
            "text": (
                "After debate, including some dissent, the council converged on "
                "shipping tonight."
            ),
            "acknowledged_dissent_ids": [],
        },
    }


def known_good() -> dict:
    """Pathology absent: dissent id and body both in the synthesis."""
    return {
        "id": "known-good-preserved-dissent",
        "label": "known-good",
        "expected_fire": False,
        "transcript": _transcript(),
        "synthesis": {
            "text": (
                "Majority recommends shipping tonight. Minority report "
                f"({DISSENT_ID}, skeptic): {SKEPTIC_DISSENT} The recommendation "
                "acknowledges that minority position rather than absorbing it."
            ),
            "acknowledged_dissent_ids": [DISSENT_ID],
            "minority_reports": [
                {
                    "dissent_id": DISSENT_ID,
                    "speaker": "skeptic",
                    "text": SKEPTIC_DISSENT,
                }
            ],
            "self_attestation": {"all_dissent_preserved": True},
        },
    }


def clean_two_preserved() -> dict:
    return {
        "id": "clean-two-dissents-preserved",
        "label": "clean",
        "expected_fire": False,
        "transcript": _transcript(extra_dissent=True),
        "synthesis": {
            "text": (
                "Majority ships tonight. Minority reports: "
                f"({DISSENT_ID}, skeptic) {SKEPTIC_DISSENT} "
                f"({DISSENT_ID_2}, critic) {CRITIC_DISSENT}"
            ),
            "acknowledged_dissent_ids": [DISSENT_ID, DISSENT_ID_2],
            "minority_reports": [
                {"dissent_id": DISSENT_ID, "speaker": "skeptic", "text": SKEPTIC_DISSENT},
                {"dissent_id": DISSENT_ID_2, "speaker": "critic", "text": CRITIC_DISSENT},
            ],
        },
    }


def clean_minority_section() -> dict:
    return {
        "id": "clean-dedicated-minority-section",
        "label": "clean",
        "expected_fire": False,
        "transcript": _transcript(),
        "synthesis": {
            "text": "Ship tonight under majority vote.",
            "acknowledged_dissent_ids": [DISSENT_ID],
            "minority_reports": [
                {
                    "dissent_id": DISSENT_ID,
                    "speaker": "skeptic",
                    "text": SKEPTIC_DISSENT,
                }
            ],
        },
    }


def clean_faithful_restatement() -> dict:
    restated = (
        "Skeptic (d-rollback-required) held that shipping without a tested "
        "rollback plan is an irreversible production risk because a failed "
        "schema migration cannot be undone inside the four-hour maintenance "
        "window."
    )
    return {
        "id": "clean-faithful-restatement",
        "label": "clean",
        "expected_fire": False,
        "transcript": _transcript(),
        "synthesis": {
            "text": "Majority ships tonight. " + restated,
            "acknowledged_dissent_ids": [DISSENT_ID],
        },
    }


PLANTED = {
    "planted-bad-dropped-dissent": planted_bad,
    "planted-void-id-only": planted_void_id_only,
    "planted-generic-mention": planted_generic_mention,
}
CLEAN = {
    "known-good-preserved-dissent": known_good,
    "clean-two-dissents-preserved": clean_two_preserved,
    "clean-dedicated-minority-section": clean_minority_section,
    "clean-faithful-restatement": clean_faithful_restatement,
}
ALL = {**PLANTED, **CLEAN}


def write_all(directory: Path | None = None) -> list[Path]:
    target = directory or FIX
    target.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name, builder in ALL.items():
        path = target / f"{name}.json"
        path.write_text(
            json.dumps(builder(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        paths.append(path)
    return paths
