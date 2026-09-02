"""Licence lattice: allow-list filter and most-restrictive-wins join."""
from __future__ import annotations

import json
from typing import Any

from constants import CORPUS, UNKNOWN_LICENCES


def load_lattice() -> dict[str, Any]:
    return json.loads((CORPUS / "licence_lattice.json").read_text(encoding="utf-8"))


def normalised(licence: str | None) -> str:
    if licence is None:
        return "UNKNOWN"
    text = str(licence).strip()
    return text if text else "UNKNOWN"


def is_unknown(licence: str | None) -> bool:
    return normalised(licence) in UNKNOWN_LICENCES or normalised(licence) == "UNKNOWN"


def allowed(licence: str | None, allow: list[str] | None) -> bool:
    if is_unknown(licence):
        return False
    if not allow:
        return True
    return normalised(licence) in set(allow)


def restrictiveness(licence: str | None, lattice: dict[str, Any] | None = None) -> int:
    lat = lattice or load_lattice()
    rank = lat.get("rank") or {}
    return int(rank.get(normalised(licence), 50))


def join_most_restrictive(licences: list[str], lattice: dict[str, Any] | None = None) -> str:
    lat = lattice or load_lattice()
    if any(is_unknown(x) for x in licences):
        return "UNKNOWN"
    if not licences:
        return "UNKNOWN"
    return max(licences, key=lambda x: restrictiveness(x, lat))
