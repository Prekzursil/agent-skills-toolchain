"""Machine consumer that reads decomposed *_v fields. Lint MUST pass."""


def admit(blueprint: dict) -> bool:
    return blueprint["state_v"] in {"FOUND", "REPAIRED", "MERGED", "NEW"}


def by_size(records: list, size_v: str) -> list:
    return [r for r in records if r.get("size_v") == size_v]
