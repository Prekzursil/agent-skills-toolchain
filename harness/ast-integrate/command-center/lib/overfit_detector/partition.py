"""Independent held-out / visible partition from case hash.

Membership is a pure function of the case id's SHA-256 digest, so a stored
label can never move a case between slices and any caller can recompute the
partition without consulting this module's state.
"""
from __future__ import annotations

import hashlib
from typing import Any, Iterable, Sequence

HELD_OUT = "held-out"
VISIBLE = "visible"


class HeldOutTouchError(RuntimeError):
    """A development-time artefact was trained on held-out case ids."""

    def __init__(self, touched: Sequence[str]) -> None:
        self.touched = list(touched)
        super().__init__(
            f"held-out cases touched during development: {', '.join(self.touched)}"
        )


def independent_slice(case_id: str) -> str:
    """Return ``HELD_OUT`` or ``VISIBLE`` from the low bit of sha256(case_id)."""
    digest = hashlib.sha256(str(case_id).encode("utf-8")).digest()
    return HELD_OUT if digest[0] & 1 else VISIBLE


def slice_of(case_id: str) -> str:
    """Library-side partition lookup; identical to :func:`independent_slice`."""
    return independent_slice(case_id)


def _case_id(case: Any) -> str:
    if isinstance(case, dict):
        return str(case.get("id"))
    return str(getattr(case, "id"))


def split(cases: Iterable[Any]) -> tuple[list[Any], list[Any]]:
    """Partition ``cases`` into ``(visible, heldout)`` preserving input order.

    Each case is placed by :func:`slice_of` on its ``id`` attribute (or key),
    never by any cached label carried on the case itself.
    """
    visible: list[Any] = []
    heldout: list[Any] = []
    for case in cases:
        if slice_of(_case_id(case)) == HELD_OUT:
            heldout.append(case)
        else:
            visible.append(case)
    return visible, heldout


def assert_no_heldout_touch(
    trained_ids: Iterable[str], heldout_ids: Iterable[str]
) -> list[str]:
    """Raise :class:`HeldOutTouchError` if any trained id is a held-out id.

    Returns the (empty) sorted intersection when the check passes so callers
    can record it as evidence.
    """
    held = {str(i) for i in heldout_ids}
    touched = sorted({str(i) for i in trained_ids} & held)
    if touched:
        raise HeldOutTouchError(touched)
    return touched
