"""Deliberate machine consumer that reads the free-text gloss. Lint MUST fail."""


def admit(blueprint: dict) -> bool:
    return blueprint["state"] in {"FOUND", "REPAIRED", "MERGED", "NEW"}


def by_size(records: list, size: str) -> list:
    return [r for r in records if r.get("size") == size]
