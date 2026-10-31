"""The permission model: one subsumption function, used by both the linter and the installer.

THE DEFECT THIS MODULE EXISTS TO PREVENT
    A permission ceiling is only real if the linter and the installer agree on what
    "within the ceiling" means. Two implementations of that predicate is two ceilings, and
    the looser one is the one an attacker uses. :func:`subsumes` is therefore the single
    physical definition and both callers import it.

THE GRAMMAR
    ``<capability>:<scope>``. The capability half is a CLOSED set (see
    ``common.schema.json#/$defs/permission``) so a novel capability cannot arrive as free
    text. The scope half is a path-ish glob with exactly two wildcards:

      * ``*``  - one segment
      * ``**`` - one or more trailing segments (only legal as the LAST segment)

    ``fs:read:*`` is therefore NOT a universal grant -- it is one segment. The universal
    grant must be spelled ``fs:read:**``, which is deliberately conspicuous.

EXCESSIVE, DEFINED
    A permission is *excessive* when it is (a) forbidden outright, (b) not subsumed by any
    grant, or (c) a member of the always-dangerous set below whose scope reaches ``**``.
    The third clause exists because a trust policy can be written laxly by accident;
    ``secrets:read:**`` should require a deliberate, named exception, not merely a wide
    ceiling.
"""

from __future__ import annotations

import re
from typing import NamedTuple

CAPABILITIES = (
    "fs:read",
    "fs:write",
    "net:egress",
    "exec:process",
    "secrets:read",
    "env:read",
    "hook:register",
    "mcp:mount",
)

#: Capabilities that are dangerous at any width and unacceptable at ``**`` width.
DANGEROUS = frozenset({"secrets:read", "exec:process", "net:egress", "fs:write"})

PERMISSION_RE = re.compile(
    r"^("
    + "|".join(re.escape(c) for c in CAPABILITIES)
    + r"):(?P<scope>[A-Za-z0-9_.:*/@-]+)$"
)


class PermissionError_(ValueError):
    """A permission string is not in the grammar. Named with a trailing underscore so it
    cannot be confused with the builtin ``PermissionError``, which means something else."""


class Permission(NamedTuple):
    capability: str
    scope: str

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return f"{self.capability}:{self.scope}"


def parse(text: str) -> Permission:
    m = PERMISSION_RE.match(text or "")
    if not m:
        raise PermissionError_(
            f"not a permission in the closed grammar: {text!r} "
            f"(capabilities: {', '.join(CAPABILITIES)})"
        )
    capability = text[: len(text) - len(m["scope"]) - 1]
    return Permission(capability, m["scope"])


def _scope_subsumes(grant: str, want: str) -> bool:
    g = grant.split("/")
    w = want.split("/")
    for i, seg in enumerate(g):
        if seg == "**":
            if i != len(g) - 1:
                raise PermissionError_(
                    f"'**' is only legal as the last scope segment: {grant!r}"
                )
            return len(w) >= i + 1
        if i >= len(w):
            return False
        if seg == "*":
            continue
        if seg != w[i]:
            return False
    return len(w) == len(g)


def subsumes(grant: str, want: str) -> bool:
    """Does ``grant`` allow ``want``? Both must be in the grammar or this raises."""
    g = parse(grant)
    w = parse(want)
    if g.capability != w.capability:
        return False
    return _scope_subsumes(g.scope, w.scope)


def widest_reach(permission: str) -> str:
    """``'universal'`` if the scope ends in ``**``, ``'segment'`` if it uses ``*``, else ``'exact'``."""
    p = parse(permission)
    segments = p.scope.split("/")
    if segments[-1] == "**":
        return "universal"
    if any(s == "*" for s in segments):
        return "segment"
    return "exact"


class Verdict(NamedTuple):
    admissible: bool
    excessive: list[str]
    reasons: dict[str, str]


def evaluate(
    requested: list[str],
    *,
    max_permissions: list[str],
    grant_permissions: list[str] | None = None,
    forbidden_permissions: list[str] | None = None,
) -> Verdict:
    """Decide whether every requested permission is admissible.

    Order matters and is fixed: FORBIDDEN is checked first and cannot be re-enabled by a
    per-publisher grant, otherwise the ceiling would be advisory. Then the dangerous-at-
    universal-width rule. Then subsumption by (ceiling + grant).
    """
    grants = list(max_permissions) + list(grant_permissions or [])
    forbidden = list(forbidden_permissions or [])
    excessive: list[str] = []
    reasons: dict[str, str] = {}

    for want in requested:
        parse(want)  # grammar first: an unparseable permission is never admissible
        hit = next((f for f in forbidden if _forbid_matches(f, want)), None)
        if hit is not None:
            excessive.append(want)
            reasons[want] = f"forbidden by policy pattern {hit!r}"
            continue
        p = parse(want)
        if p.capability in DANGEROUS and widest_reach(want) == "universal":
            explicit = any(g == want for g in grants)
            if not explicit:
                excessive.append(want)
                reasons[want] = (
                    f"{p.capability} at universal ('**') width requires an EXACT explicit grant, "
                    "not a wildcard ceiling"
                )
                continue
        if not any(subsumes(g, want) for g in grants):
            excessive.append(want)
            reasons[want] = "not subsumed by any ceiling or publisher grant"

    return Verdict(admissible=not excessive, excessive=excessive, reasons=reasons)


def _forbid_matches(pattern: str, want: str) -> bool:
    """A forbidden entry may be a full permission or a bare capability prefix.

    ``secrets:read`` forbids every scope of that capability; ``fs:write:C:/**`` forbids
    only that scope tree. Prefix matching is anchored at a segment boundary so
    ``fs:write`` cannot accidentally match a capability named ``fs:write2`` -- there is no
    such capability today, and the anchor is what keeps that true if one is added.
    """
    if pattern == want:
        return True
    if want.startswith(pattern + ":"):
        return True
    try:
        return subsumes(pattern, want)
    except PermissionError_:
        return False
