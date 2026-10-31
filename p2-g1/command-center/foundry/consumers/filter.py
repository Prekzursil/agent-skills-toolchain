"""Foundry consumer: filter on size_v, never size gloss."""


def by_size_v(records: list, size_v: str) -> list:
    return [r for r in records if r.get("size_v") == size_v]
