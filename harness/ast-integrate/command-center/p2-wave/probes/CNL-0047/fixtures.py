"""Named fixtures for CNL-0047."""
from __future__ import annotations

from scheduler import bag_speaker, greedy_speaker, yield_speaker

# Dominant wants infinite airtime. Prolific has 45 tokens of real content
# under a 50-token quota. Quiet always yields. Observer has no speaking right.
QUOTA_STARVATION = {
    "id": "quota-starvation",
    "turn_length_tokens": 20,
    "seats": [
        {"id": "dominant", "speaking_right": True, "quota_tokens": 50},
        {"id": "prolific", "speaking_right": True, "quota_tokens": 50},
        {"id": "quiet", "speaking_right": True, "quota_tokens": 50},
        {"id": "observer", "speaking_right": False, "quota_tokens": 50},
    ],
    "speakers": "dominant-greedy / prolific-bag-45 / quiet-yield / observer-unused",
}

REMAINDER_CAP = {
    "id": "remainder-cap",
    "turn_length_tokens": 20,
    "seats": [
        {"id": "partial", "speaking_right": True, "quota_tokens": 25},
        {"id": "other", "speaking_right": True, "quota_tokens": 25},
    ],
    "speakers": "both greedy-20",
}

KNOWN_GOOD = QUOTA_STARVATION
PLANTED_BAD = QUOTA_STARVATION


def speakers_for(name: str) -> dict:
    if name in {"quota-starvation", "known-good", "planted-bad"}:
        return {
            "dominant": greedy_speaker(20),
            "prolific": bag_speaker([20, 20, 5]),
            "quiet": yield_speaker(),
            "observer": greedy_speaker(20),
        }
    if name == "remainder-cap":
        return {
            "partial": greedy_speaker(20),
            "other": greedy_speaker(20),
        }
    raise KeyError(name)
