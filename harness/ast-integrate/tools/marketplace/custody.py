"""Key custody policy: the program consumes keys, it does not mint them."""
from __future__ import annotations

class CustodyViolation(Exception):
    pass


POLICY = {
    "holder": "owner",
    "program_role": "consume-and-window-check-only",
    "forbidden": ("generate", "rotate", "mint", "export-private"),
}


def refuse_lifecycle(action: str) -> None:
    raise CustodyViolation(f"lifecycle action refused: {action}")
