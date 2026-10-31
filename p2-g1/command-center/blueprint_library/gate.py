"""Structural fingerprint registry vs lexical (id-only) control."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from blueprint_library.fingerprint import fingerprint


@dataclass
class Decision:
    accepted: bool
    reason: str = "ok"
    incumbent_id: str | None = None


class Registry:
    def __init__(self) -> None:
        self._by_fp: dict[str, dict[str, Any]] = {}

    def register(self, entry: Mapping[str, Any]) -> Decision:
        fp = fingerprint(entry)
        incumbent = self._by_fp.get(fp)
        if incumbent is not None:
            return Decision(
                accepted=False,
                reason="fingerprint-collision",
                incumbent_id=str(incumbent.get("id")),
            )
        self._by_fp[fp] = dict(entry)
        return Decision(accepted=True, reason="registered", incumbent_id=None)


class _LexicalRegistry:
    def __init__(self) -> None:
        self._ids: set[str] = set()

    def register(self, entry: Mapping[str, Any]) -> Decision:
        eid = str(entry.get("id") or "")
        if eid in self._ids:
            return Decision(accepted=False, reason="id-collision", incumbent_id=eid)
        self._ids.add(eid)
        return Decision(accepted=True, reason="registered")


def lexical_registry() -> _LexicalRegistry:
    return _LexicalRegistry()
