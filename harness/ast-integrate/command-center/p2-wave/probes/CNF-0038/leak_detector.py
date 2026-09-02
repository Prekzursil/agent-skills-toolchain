"""Leak detector: conclusion / author-test / diff fragments in a brief."""
from __future__ import annotations

from typing import Iterable

from paths import AUTHOR_MARKER, CONCLUSION_MARKER, DIFF_MARKER

MARKERS = {
    "author_test": AUTHOR_MARKER,
    "diff": DIFF_MARKER,
    "conclusion": CONCLUSION_MARKER,
}


def scan(text: str, extra_needles: Iterable[str] = ()) -> list[str]:
    hits: list[str] = []
    blob = text or ""
    for name, needle in MARKERS.items():
        if needle and needle in blob:
            hits.append(name)
    for needle in extra_needles:
        if needle and needle in blob and needle not in hits:
            hits.append(needle)
    return hits


def fired(text: str) -> bool:
    return bool(scan(text))
