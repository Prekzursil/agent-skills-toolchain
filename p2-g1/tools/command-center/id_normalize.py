"""NFC identity for command-center identifiers.

Two Unicode strings that differ only by NFC vs NFD must not resolve to
different entities after they cross this boundary. A raw Python dict still
treats them as distinct keys; that disagreement is the mixed-resolver hazard
TST-0057 measures.

Canonical form is NFC. Byte identity is the raw UTF-8 of the string as given,
not the canonical form — otherwise an NFC/NFD pair would not be byte-distinct.
"""

from __future__ import annotations

import unicodedata
from collections import UserDict
from collections.abc import Iterable
from typing import Any

CANONICAL_FORM = "NFC"


class NormalizationCollision(ValueError):
    """Two byte-distinct ids that NFC-fold to the same key."""


def canonical_id(text: str) -> str:
    """NFC-fold an identifier. Every lookup and store key goes through this."""
    return unicodedata.normalize(CANONICAL_FORM, str(text))


def nfd_form(text: str) -> str:
    return unicodedata.normalize("NFD", str(text))


def byte_key(text: str) -> bytes:
    """Raw UTF-8 of the given spelling. Not NFC-folded."""
    return str(text).encode("utf-8")


def is_ascii(text: str) -> bool:
    return str(text).isascii()


def is_nfc(text: str) -> bool:
    value = str(text)
    return value == unicodedata.normalize("NFC", value)


def is_nfd(text: str) -> bool:
    value = str(text)
    return value == unicodedata.normalize("NFD", value)


def collision_groups(ids: Iterable[str]) -> list[dict[str, Any]]:
    """Group spellings that NFC-fold together but are not the same string.

    Unique canonical ids (including ASCII TST-0057) are omitted so a live
    census of zero collisions is distinguishable from a dead detector.
    """
    order: dict[str, list[str]] = {}
    seen: dict[str, set[str]] = {}
    for raw in ids:
        text = str(raw)
        canon = canonical_id(text)
        bucket = seen.setdefault(canon, set())
        if text in bucket:
            continue
        bucket.add(text)
        order.setdefault(canon, []).append(text)
    groups: list[dict[str, Any]] = []
    for canon, forms in order.items():
        if len(forms) < 2:
            continue
        groups.append(
            {
                "canonical_nfc": canon,
                "form_count": len(forms),
                "forms": forms,
                "utf8_hex": [byte_key(form).hex() for form in forms],
            }
        )
    return groups


class CanonicalIdMap(UserDict):
    """dict whose keys are NFC-folded on insert and lookup.

    Storing under an NFC spelling makes the NFD spelling resolve to the same
    object. Iterating yields the canonical (NFC) keys.
    """

    def __getitem__(self, key: Any) -> Any:
        return self.data[canonical_id(str(key))]

    def __setitem__(self, key: Any, value: Any) -> None:
        self.data[canonical_id(str(key))] = value

    def __delitem__(self, key: Any) -> None:
        del self.data[canonical_id(str(key))]

    def __contains__(self, key: object) -> bool:
        return canonical_id(str(key)) in self.data


def index_by_canonical_id(rows: Iterable[dict[str, Any]]) -> CanonicalIdMap:
    """Index records by NFC id. Dual-form input is refused, not last-wins."""
    out = CanonicalIdMap()
    first_raw: dict[str, str] = {}
    for row in rows:
        raw = str(row.get("id", ""))
        key = canonical_id(raw)
        prior = first_raw.get(key)
        if prior is not None and prior != raw:
            raise NormalizationCollision(
                f"NFC collision: {prior!r} vs {raw!r} (canonical={key!r})"
            )
        first_raw[key] = raw
        out[raw] = row
    return out
