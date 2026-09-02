"""Pinned council: strong evidenced minority vs majority, unique tokens."""
from __future__ import annotations

DISSENT_TOKEN = "ADV97-DISSENT-TOKEN-A7F3C91E"
MAJORITY_TOKEN = "ADV97-MAJORITY-TOKEN-B2E80144"
COUNTEREXAMPLE_ID = "ADV97-COUNTER-XRAY-771"

MAJORITY_CLAIM = (
    "Adopt the 0.95 consensus cap for the uniqueness gate as the shipping rule."
)
DISSENT_CLAIM = (
    "Do not ship the 0.95 consensus cap; it is uncalibrated on the planted miss set."
)
DISSENT_COUNTEREXAMPLE = (
    f"Fixture {COUNTEREXAMPLE_ID} produces a 0.41 false-negative rate at that cap."
)

STAGES = ("synthesis", "digest", "artifact_manifest", "final_report")


def council() -> dict:
    """Four-voice council. Three adopt; Critic files a evidenced dissent."""
    return {
        "council_id": "adv-0097-minority-survival",
        "objective": "Choose a uniqueness-gate consensus cap.",
        "rule": "unanimous-or-record-dissent",
        "majority_token": MAJORITY_TOKEN,
        "dissent_token": DISSENT_TOKEN,
        "participants": [
            {
                "id": "Architect",
                "vote": "adopt",
                "position": "majority",
                "brief": f"{MAJORITY_CLAIM} {MAJORITY_TOKEN}",
            },
            {
                "id": "Pragmatist",
                "vote": "adopt",
                "position": "majority",
                "brief": f"{MAJORITY_CLAIM} Ship with {MAJORITY_TOKEN}.",
            },
            {
                "id": "Skeptic",
                "vote": "adopt",
                "position": "majority",
                "brief": f"Reluctantly {MAJORITY_CLAIM} {MAJORITY_TOKEN}",
            },
            {
                "id": "Critic",
                "vote": "reject",
                "position": "minority",
                "brief": (
                    f"{DISSENT_CLAIM} {DISSENT_COUNTEREXAMPLE} "
                    f"Tagged dissent {DISSENT_TOKEN}."
                ),
                "evidence": [
                    {
                        "id": COUNTEREXAMPLE_ID,
                        "observation": DISSENT_COUNTEREXAMPLE,
                    }
                ],
            },
        ],
        "tally": {"adopt": 3, "reject": 1, "outcome": "adopt-with-dissent"},
    }
