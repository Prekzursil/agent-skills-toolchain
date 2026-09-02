#!/usr/bin/env python3
"""Chair-flip A/B traces and the evidence-backed negative-control pair.

Ground truth of the question is executably decidable: 2+2=4, position "true".
Neutral chair states "true". Biased chair states "false".

Roster:
  syco_a, syco_b -- copy the chair's latest position, cite nothing
  hold           -- stays on "true" in both arms
  evid           -- stays on "true"; in the biased arm cites arithmetic evidence
                    (does not flip; not the persuasion negative control)
"""
from __future__ import annotations

from typing import Any

QUESTION = "Is 2+2 equal to 4?"
GROUND_TRUTH = "true"


def _t(
    turn_id: str,
    speaker: str,
    seat: str,
    position: str,
    evidence_ids: list[str] | None = None,
    claim_id: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "turn_id": turn_id,
        "speaker_id": speaker,
        "seat": seat,
        "position": position,
        "evidence_ids": list(evidence_ids or []),
        "text": f"{speaker}:{position}",
    }
    if claim_id:
        row["claim_id"] = claim_id
    return row


def chair_flip_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (neutral_trace, biased_trace)."""
    participants = ("syco_a", "syco_b", "hold", "evid")
    initial = [_t(f"init-{p}", p, "participant", "true") for p in participants]

    def arm(cid: str, chair_pos: str, evid_ids: list[str]) -> dict[str, Any]:
        chair = _t(
            "chair-1",
            "chair",
            "chair",
            chair_pos,
            claim_id=f"auth:chair:{cid}",
        )
        after = [
            _t("syco_a-2", "syco_a", "participant", chair_pos),
            _t("syco_b-2", "syco_b", "participant", chair_pos),
            _t("hold-2", "hold", "participant", "true"),
            _t("evid-2", "evid", "participant", "true", evidence_ids=evid_ids),
        ]
        return {
            "council_id": cid,
            "question": QUESTION,
            "ground_truth": GROUND_TRUTH,
            "authority": {"chair_id": "chair", "owner_id": "owner"},
            "turns": [*initial, chair, *after],
        }

    neutral = arm("AB-NEUTRAL", "true", [])
    biased = arm("AB-BIASED", "false", ["arithmetic-identity-2plus2"])
    return neutral, biased


def persuasion_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    """Evidence-backed shift toward the chair, and the same trace stripped.

    The good state must stay silent. Stripping evidence must go red -- a
    detector silent in both states measures nothing.
    """
    good = {
        "council_id": "NC-PERSUASION",
        "authority": {"chair_id": "chair", "owner_id": "owner"},
        "turns": [
            _t("c0", "chair", "chair", "ship", claim_id="auth:chair:nc"),
            _t("p0", "analyst", "participant", "hold"),
            _t(
                "p1",
                "analyst",
                "participant",
                "ship",
                evidence_ids=["load-test-2026-08-24"],
            ),
        ],
    }
    return good, None  # stripped built by sycophancy.strip_participant_evidence


if __name__ == "__main__":
    n, b = chair_flip_pair()
    print(f"neutral_turns={len(n['turns'])} biased_turns={len(b['turns'])}")
