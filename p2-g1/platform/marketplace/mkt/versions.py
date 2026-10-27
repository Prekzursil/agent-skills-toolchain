"""Semver parsing and the deliberately small range grammar.

WHY SO SMALL
    Every published range grammar (npm, cargo, pip) is large enough that no reviewer can
    enumerate what a given string admits, which is how a dependency resolves to something
    nobody intended. The grammar here is five forms -- ``*``, a bare/``=`` exact pin, a
    comparator, ``^``, ``~`` -- and it is the SAME grammar the schema pattern in
    ``common.schema.json#/$defs/version_range`` admits, so a range that parses here is a
    range that validates there.

    Prerelease handling is stated explicitly rather than left to folklore: a prerelease
    version NEVER satisfies a range unless the range itself names a prerelease. That is the
    conservative direction -- an accidental ``1.2.0-rc1`` install is a supply-chain event,
    an accidental miss is a build failure.
"""

from __future__ import annotations

import re
from typing import NamedTuple

SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)
RANGE_RE = re.compile(
    r"^(?:(?P<star>\*)|(?P<op>=|>=|<=|>|<|\^|~)?"
    r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?)$"
)


class VersionError(ValueError):
    """A version or range string is not in the grammar."""


class Version(NamedTuple):
    major: int
    minor: int
    patch: int
    pre: str

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return f"{self.major}.{self.minor}.{self.patch}" + (
            f"-{self.pre}" if self.pre else ""
        )

    @property
    def is_prerelease(self) -> bool:
        return bool(self.pre)


def parse(text: str) -> Version:
    m = SEMVER_RE.match(text or "")
    if not m:
        raise VersionError(f"not a semver: {text!r}")
    return Version(int(m["major"]), int(m["minor"]), int(m["patch"]), m["pre"] or "")


def _pre_key(pre: str) -> list[tuple[int, int, str]]:
    """Precedence key for a prerelease string, per semver 11.4.

    Numeric identifiers compare numerically and rank BELOW alphanumeric ones. The tuple
    shape ``(kind, number, text)`` keeps ints and strings from ever being compared.
    """
    out: list[tuple[int, int, str]] = []
    for part in pre.split("."):
        if part.isdigit():
            out.append((0, int(part), ""))
        else:
            out.append((1, 0, part))
    return out


def compare(a: str | Version, b: str | Version) -> int:
    """-1 / 0 / +1. Build metadata is ignored, as semver requires."""
    va = a if isinstance(a, Version) else parse(a)
    vb = b if isinstance(b, Version) else parse(b)
    core_a = (va.major, va.minor, va.patch)
    core_b = (vb.major, vb.minor, vb.patch)
    if core_a != core_b:
        return -1 if core_a < core_b else 1
    if va.pre == vb.pre:
        return 0
    if not va.pre:
        return 1  # a release outranks any prerelease of the same core
    if not vb.pre:
        return -1
    ka, kb = _pre_key(va.pre), _pre_key(vb.pre)
    if ka == kb:
        return 0
    return -1 if ka < kb else 1


def satisfies(version: str, range_text: str) -> bool:
    """Does ``version`` satisfy ``range_text``? Unknown grammar raises, never returns True."""
    m = RANGE_RE.match(range_text or "")
    if not m:
        raise VersionError(f"not a supported version range: {range_text!r}")
    v = parse(version)
    if m["star"]:
        # `*` admits releases only. A wildcard that silently pulled a prerelease would be
        # the widening-on-absence defect this build refuses to reproduce.
        return not v.is_prerelease
    target = Version(int(m["major"]), int(m["minor"]), int(m["patch"]), m["pre"] or "")
    if v.is_prerelease and not target.is_prerelease:
        return False
    op = m["op"] or "="
    c = compare(v, target)
    if op == "=":
        return c == 0
    if op == ">=":
        return c >= 0
    if op == "<=":
        return c <= 0
    if op == ">":
        return c > 0
    if op == "<":
        return c < 0
    if op == "^":
        # compatible-within-major, except major 0 where minor is the breaking axis
        if c < 0:
            return False
        if target.major > 0:
            return v.major == target.major
        if target.minor > 0:
            return v.major == 0 and v.minor == target.minor
        return v.major == 0 and v.minor == 0
    # op == "~": compatible-within-minor
    return c >= 0 and v.major == target.major and v.minor == target.minor


def best(versions: list[str], range_text: str) -> str | None:
    """Highest version in ``versions`` satisfying ``range_text``, or ``None``."""
    ok = [v for v in versions if satisfies(v, range_text)]
    if not ok:
        return None
    winner = ok[0]
    for candidate in ok[1:]:
        if compare(candidate, winner) > 0:
            winner = candidate
    return winner
