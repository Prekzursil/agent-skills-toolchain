"""Six-element library entry contract."""
from __future__ import annotations

REQUIRED_ELEMENTS = (
    "id",
    "title",
    "capabilities",
    "inputs",
    "outputs",
    "run",
)


class ContractError(ValueError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def check_entry(entry: dict) -> list[str]:
    missing = [k for k in REQUIRED_ELEMENTS if k not in entry or entry.get(k) in (None, "", [], ())]
    if missing:
        raise ContractError(f"omit-{missing[0]}", f"missing {missing}")
    return list(REQUIRED_ELEMENTS)


def mutate_omit(entry: dict, element: str) -> dict:
    out = dict(entry)
    out.pop(element, None)
    return out


def omission_codes() -> list[str]:
    return [f"omit-{e}" for e in REQUIRED_ELEMENTS]
