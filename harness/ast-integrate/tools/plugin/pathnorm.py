"""NFC-then-casefold payload path normalisation (IMP-0022)."""
from __future__ import annotations

import unicodedata

NORMALISATION = {
    "case_mapping": "str.casefold",
    "order": ["NFC", "casefold"],
    "form": "NFC",
}


def nfc_casefold(path: str) -> str:
    text = str(path).replace("\\", "/")
    return unicodedata.normalize("NFC", text).casefold()


def normalised_payload_path(path: str) -> str:
    text = str(path).replace("\\", "/").strip().lstrip("./")
    return nfc_casefold(text)


__all__ = ["NORMALISATION", "nfc_casefold", "normalised_payload_path"]
