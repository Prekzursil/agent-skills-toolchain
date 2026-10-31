"""Foundry consumer: tally state_v."""
from collections import Counter


def tally_state_v(records: list) -> dict:
    return dict(Counter(r.get("state_v") for r in records if r.get("state_v")))
