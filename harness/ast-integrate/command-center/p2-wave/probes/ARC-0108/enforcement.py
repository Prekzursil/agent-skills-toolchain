#!/usr/bin/env python3
"""Single permission choke point for ARC-0108.

Every capability invocation must call `invoke()`, which is the only function
that may ALLOW a side effect. `evaluate()` is the decision procedure.
A wildcard grant of class `credential` is rejected at validation time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Callable, Iterable

CLASSES = ("tool", "path", "net", "subprocess", "credential")
EFFECTS = ("grant", "deny")
ENFORCEMENT_MODULE = (
    "command-center/p2-wave/probes/ARC-0108/enforcement.py"
)
ENFORCEMENT_FUNCTION = "invoke"


class DeclarationError(ValueError):
    """Invalid declared permission set (rejected before evaluation)."""


@dataclass(frozen=True)
class Permission:
    cls: str
    name: str
    effect: str = "grant"

    def key(self) -> str:
        return f"{self.cls}:{self.name}"

    @classmethod
    def from_dict(cls, row: dict) -> "Permission":
        klass = str(row.get("class") or row.get("cls") or "")
        name = str(row.get("name") or "")
        effect = str(row.get("effect") or "grant")
        if klass not in CLASSES or not name or effect not in EFFECTS:
            raise DeclarationError(f"invalid permission row {row!r}")
        return cls(cls=klass, name=name, effect=effect)


@dataclass(frozen=True)
class Decision:
    verdict: str
    reason: str

    @property
    def allow(self) -> bool:
        return self.verdict == "ALLOW"


@dataclass
class Record:
    seq: int
    capability_id: str
    permission: str
    decision: str
    reason: str
    enforcement_point: str
    kind: str


def validate_declaration(declared: Iterable[Permission]) -> tuple[Permission, ...]:
    rows = tuple(declared)
    if not rows:
        raise DeclarationError("empty declaration")
    for p in rows:
        if p.cls not in CLASSES or p.effect not in EFFECTS or not p.name:
            raise DeclarationError(f"invalid permission {p!r}")
        if p.cls == "credential" and p.name in {"*", "**"} and p.effect == "grant":
            raise DeclarationError(
                "wildcard credential grant rejected at validation time"
            )
    return rows


def _path_ok(requested: str) -> bool:
    if not requested or requested.startswith("/") or requested.startswith("\\"):
        return False
    parts = requested.replace("\\", "/").split("/")
    return ".." not in parts and not any(p == "" for p in parts[:-1])


def matches(declared: Permission, requested: Permission) -> bool:
    if declared.cls != requested.cls:
        return False
    if declared.cls == "path":
        if not _path_ok(requested.name):
            return False
        want = declared.name.replace("\\", "/")
        got = requested.name.replace("\\", "/")
        return fnmatch(got, want)
    if declared.name in {"*", "**"}:
        return True
    return declared.name == requested.name


def evaluate(declared: Iterable[Permission], requested: Permission) -> Decision:
    """Decision table: deny-match wins; else grant-match; else undeclared DENY."""
    rows = validate_declaration(declared)
    if requested.cls == "path" and not _path_ok(requested.name):
        return Decision("DENY", "path-escape")
    denies = [p for p in rows if p.effect == "deny" and matches(p, requested)]
    if denies:
        return Decision("DENY", "deny-rule")
    grants = [p for p in rows if p.effect == "grant" and matches(p, requested)]
    if grants:
        return Decision("ALLOW", "grant")
    return Decision("DENY", "undeclared")


_SEQ = 0


def reset_seq() -> None:
    global _SEQ
    _SEQ = 0


def invoke(
    capability_id: str,
    kind: str,
    declared: Iterable[Permission],
    requested: Permission,
    side_effect: Callable[[], None] | None = None,
) -> Record:
    """THE choke point. Side effects run only after ALLOW."""
    global _SEQ
    _SEQ += 1
    decision = evaluate(declared, requested)
    if decision.allow and side_effect is not None:
        side_effect()
    return Record(
        seq=_SEQ,
        capability_id=capability_id,
        permission=requested.key(),
        decision=decision.verdict,
        reason=decision.reason,
        enforcement_point=f"{ENFORCEMENT_MODULE}:{ENFORCEMENT_FUNCTION}",
        kind=kind,
    )


def declared_keys(declared: Iterable[Permission]) -> set[str]:
    return {p.key() for p in declared if p.effect == "grant"}
