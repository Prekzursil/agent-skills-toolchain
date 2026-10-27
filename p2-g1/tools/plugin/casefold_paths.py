"""IMP-0022 live-path casefold: NFC then casefold, never str.lower."""
from __future__ import annotations

from unicodedata import normalize


def nfc(text: str) -> str:
    return normalize("NFC", str(text))


def casefold_key(path: str) -> str:
    return nfc(str(path).replace("\\", "/")).casefold()
