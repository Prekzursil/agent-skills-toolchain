"""Permission-set lattice: widen / narrow / unchanged."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

WIDEN = "widen"
NARROW = "narrow"
UNCHANGED = "unchanged"

WIDEN_PAIR = (frozenset({"read"}), frozenset({"read", "write"}))
NARROW_PAIR = (frozenset({"read", "write"}), frozenset({"read"}))
UNCHANGED_PAIR = (frozenset({"read"}), frozenset({"read"}))


@dataclass
class Delta:
    verdict: str
    added: frozenset
    removed: frozenset
    lattice_atom_agree: bool = True
    atom_verdict: str = ""
    lattice_verdict: str = ""

    @property
    def methods_agree(self) -> bool:
        return self.lattice_atom_agree


def compute_delta(installed: Iterable[str], candidate: Iterable[str]) -> Delta:
    a, b = frozenset(installed), frozenset(candidate)
    added, removed = b - a, a - b
    if added and not removed:
        verdict = WIDEN
    elif removed and not added:
        verdict = NARROW
    elif not added and not removed:
        verdict = UNCHANGED
    else:
        verdict = "mixed"
    raw = raw_set_verdict(a, b)
    lat = lattice_verdict(a, b)
    return Delta(
        verdict=verdict,
        added=added,
        removed=removed,
        lattice_atom_agree=(raw == lat == verdict),
        atom_verdict=raw,
        lattice_verdict=lat,
    )


def raw_set_verdict(installed: Iterable[str], candidate: Iterable[str]) -> str:
    a, b = frozenset(installed), frozenset(candidate)
    if a < b:
        return WIDEN
    if b < a:
        return NARROW
    if a == b:
        return UNCHANGED
    return "mixed"


def lattice_verdict(installed: Iterable[str], candidate: Iterable[str]) -> str:
    return raw_set_verdict(installed, candidate)


def canonicalize(perm) -> str:
    """Stable permission token. Strip only — Bash and Write stay distinct."""
    return str(perm).strip()


def covered_by_set(perm, grant=(), *args, **kwargs) -> bool:
    name = canonicalize(perm)
    granted = {canonicalize(p) for p in (grant or []) if str(p).strip()}
    return name in granted


def decide(installed, candidate) -> Delta:
    return compute_delta(installed, candidate)


def independent_set_containment(installed, candidate) -> str:
    a, b = frozenset(installed or []), frozenset(candidate or [])
    if a < b:
        return "widen"
    if b < a:
        return "narrow"
    if a == b:
        return "unchanged"
    return "mixed"


@dataclass
class Consent:
    package_id: str
    from_version: str
    to_version: str
    widened: tuple = ()

    def key(self) -> tuple[str, str, str]:
        return (self.package_id, self.from_version, self.to_version)


class MemoryConsentStore:
    def __init__(self) -> None:
        self._items: list[Consent] = []

    def persist(self, consent: Consent) -> None:
        self._items.append(consent)

    def find(self, package_id: str, from_version: str, to_version: str) -> Consent | None:
        for item in self._items:
            if item.key() == (package_id, from_version, to_version):
                return item
        return None

    def allows(self, package_id: str, from_version: str, to_version: str, added) -> bool:
        item = self.find(package_id, from_version, to_version)
        if item is None:
            return False
        return set(added or []) <= set(item.widened or [])
