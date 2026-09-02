"""Fixture install resolver for ADV-0066.

The worktree has no production installer that consults advisory metadata
as a minimum-version floor (tools/marketplace/disclosure.py stores
fixed_version; nothing in the install path reads it). REL-0004's
install_from_mirror takes the first matching package id in the index.

This client is the measurement substrate: it reads a fixture index (the
required control), honours rollback/pin specs, and can optionally apply
an advisory floor and index expiry. Production-like mode leaves the
floor and freshness check off.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

PACKAGE = "adv0066-fixture"
V1 = "1.0.0"
V2 = "2.0.0"


class StaleIndex(Exception):
    """Index expires_at is in the past and freshness checking is on."""


class AdvisoryBlocked(Exception):
    """Advisory min-version floor removed every candidate."""


class NoCandidate(Exception):
    """Spec matched nothing on the consulted index."""


def parse_ver(text: str) -> tuple[int, ...]:
    parts = []
    for token in str(text).split("."):
        digits = "".join(c for c in token if c.isdigit())
        parts.append(int(digits or "0"))
    return tuple(parts)


def parse_dt(text: str) -> datetime:
    raw = str(text).replace("Z", "+00:00")
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def matches_spec(version: str, spec: str) -> bool:
    spec = (spec or "latest").strip()
    if spec in {"*", "latest", ""}:
        return True
    if spec.startswith("=="):
        return version == spec[2:]
    if spec[0].isdigit() and all(op not in spec for op in ("<", ">", ",")):
        return version == spec
    ver = parse_ver(version)
    for part in spec.split(","):
        part = part.strip()
        if part.startswith(">="):
            if ver < parse_ver(part[2:]):
                return False
        elif part.startswith("<="):
            if ver > parse_ver(part[2:]):
                return False
        elif part.startswith(">"):
            if ver <= parse_ver(part[1:]):
                return False
        elif part.startswith("<"):
            if ver >= parse_ver(part[1:]):
                return False
        elif part.startswith("=="):
            if version != part[2:]:
                return False
        elif part and version != part:
            return False
    return True


def listed_versions(index: dict[str, Any], name: str = PACKAGE) -> list[str]:
    out: list[str] = []
    for row in index.get("packages") or []:
        if row.get("name") == name:
            out.append(str(row.get("version")))
    return out


def first_listed(index: dict[str, Any], name: str = PACKAGE) -> dict[str, Any]:
    """REL-0004-style: first matching id in the index, no version compare."""
    for row in index.get("packages") or []:
        if row.get("name") == name:
            return dict(row)
    raise NoCandidate(f"no listing for {name}")


def resolve(
    index: dict[str, Any],
    spec: str = "latest",
    *,
    advisory: dict[str, Any] | None = None,
    apply_floor: bool = False,
    check_freshness: bool = False,
    now: datetime | None = None,
    mutant: str | None = None,
    name: str = PACKAGE,
) -> dict[str, Any]:
    """Resolve a spec against an index.

    mutant='always-v2' ignores the index (the control that the test
    must catch: a client that always selects v2 proves nothing).
    """
    if mutant == "always-v2":
        return {
            "name": name,
            "version": V2,
            "spec": spec,
            "consulted_index": False,
            "index_versions": listed_versions(index, name),
            "mutant": mutant,
            "floor_applied": False,
            "freshness_checked": False,
            "reason": "hardcoded-v2-ignores-index",
        }

    if check_freshness:
        expires = index.get("expires_at") or index.get("expires_at")
        if expires:
            clock = now or datetime.now(timezone.utc)
            if parse_dt(str(expires)) < clock:
                raise StaleIndex(
                    f"index expired at {expires} (now={clock.isoformat()})"
                )

    pkgs = [dict(p) for p in (index.get("packages") or []) if p.get("name") == name]
    index_versions = [str(p.get("version")) for p in pkgs]
    candidates = [p for p in pkgs if matches_spec(str(p.get("version")), spec)]
    floor_applied = False
    if apply_floor and advisory:
        blocked = {
            str(v) for v in (advisory.get("vulnerable_versions") or [])
        }
        before = list(candidates)
        candidates = [
            p for p in candidates if str(p.get("version")) not in blocked
        ]
        floor_applied = True
        if before and not candidates:
            raise AdvisoryBlocked(
                f"advisory {advisory.get('id')} blocked {spec} "
                f"(vulnerable={sorted(blocked)})"
            )

    if not candidates:
        raise NoCandidate(f"spec {spec!r} matched none of {index_versions}")

    chosen = max(candidates, key=lambda p: parse_ver(str(p.get("version"))))
    return {
        "name": name,
        "version": str(chosen.get("version")),
        "spec": spec,
        "consulted_index": True,
        "index_versions": index_versions,
        "mutant": None,
        "floor_applied": floor_applied,
        "freshness_checked": check_freshness,
        "vulnerable": bool(chosen.get("vulnerable")),
        "reason": "max-matching-from-index",
        "path": chosen.get("path"),
    }
