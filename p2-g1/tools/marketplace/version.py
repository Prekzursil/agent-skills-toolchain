"""SemVer parse/compare for marketplace packs (WFA-0152)."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

_SEMVER = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int
    pre: str = ""
    build: str = ""

    @property
    def core(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def __str__(self) -> str:
        core = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre:
            core += f"-{self.pre}"
        if self.build:
            core += f"+{self.build}"
        return core


def parse_version(value: Any) -> Version:
    if isinstance(value, Version):
        return value
    text = str(value).strip()
    text = text.lstrip("^~=<>")
    m = _SEMVER.match(text)
    if not m:
        parts = text.split(".")
        while len(parts) < 3:
            parts.append("0")
        try:
            return Version(int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError as exc:
            raise ValueError(f"not a semver: {value!r}") from exc
    return Version(
        int(m.group("major")),
        int(m.group("minor")),
        int(m.group("patch")),
        m.group("pre") or "",
        m.group("build") or "",
    )


def _tuple(v: Version) -> tuple[int, int, int, int, str]:
    # pre-release is less than release (empty pre sorts last via 1).
    return (v.major, v.minor, v.patch, 1 if not v.pre else 0, v.pre)


def cmp_version(a: Any, b: Any) -> int:
    return compare(a, b)


def compare(a: Any, b: Any) -> int:
    va, vb = parse_version(a), parse_version(b)
    ta, tb = _tuple(va), _tuple(vb)
    if ta < tb:
        return -1
    if ta > tb:
        return 1
    return 0


def _token_ok(version: Any, tok: str) -> bool:
    tok = str(tok).strip()
    if tok in {"*", ""}:
        return True
    if tok.startswith(">="):
        return compare(version, tok[2:].strip()) >= 0
    if tok.startswith("<="):
        return compare(version, tok[2:].strip()) <= 0
    if tok.startswith(">"):
        return compare(version, tok[1:].strip()) > 0
    if tok.startswith("<"):
        return compare(version, tok[1:].strip()) < 0
    if tok.startswith("^") or tok.startswith("~"):
        return True
    if tok.startswith("==") or tok.startswith("="):
        return compare(version, tok.lstrip("=").strip()) == 0
    return compare(version, tok) == 0


def satisfies(version: Any, spec: str, include_prerelease: bool = False) -> bool:
    parts = [p.strip() for p in str(spec).replace(",", " ").split() if p.strip()]
    if not parts:
        return True
    return all(_token_ok(version, p) for p in parts)


def events_to_range(events: list) -> str:
    introduced = None
    fixed = None
    for ev in events:
        if isinstance(ev, dict):
            if ev.get("introduced"):
                introduced = ev["introduced"]
            if ev.get("fixed"):
                fixed = ev["fixed"]
        else:
            if introduced is None:
                introduced = str(ev)
            else:
                fixed = str(ev)
    if introduced and fixed:
        return f">={introduced} <{fixed}"
    if introduced:
        return f">={introduced}"
    if fixed:
        return f"<{fixed}"
    return "*"
