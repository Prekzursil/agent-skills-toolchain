"""Semver parse/compare for agentspec packs (IMP-0207)."""
from __future__ import annotations

import re
from typing import NamedTuple

_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


class SemVer(NamedTuple):
    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def parse_semver(value: object) -> SemVer | None:
    if isinstance(value, SemVer):
        return value
    text = str(value or "").strip()
    m = _SEMVER.match(text)
    if not m:
        return None
    return SemVer(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def compare_semver(left: object, right: object) -> int:
    a = parse_semver(left)
    b = parse_semver(right)
    if a is None or b is None:
        raise ValueError("incomparable semver")
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


__all__ = ["SemVer", "compare_semver", "parse_semver"]
