"""Foundry consumer: admit on state_v, never state gloss."""

VOCAB = {"FOUND", "REPAIRED", "MERGED", "NEW"}


def admitted(records: list) -> list:
    return [r for r in records if r.get("state_v") in VOCAB]
