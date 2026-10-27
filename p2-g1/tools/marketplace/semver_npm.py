"""npm node-semver 7.6.3-compatible version compare, satisfy, and maxSatisfying."""
from __future__ import annotations

import re
from typing import Iterable

_VERSION_RE = re.compile(
    r"^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)


class Version:
    __slots__ = ("major", "minor", "patch", "prerelease", "build", "raw")

    def __init__(self, raw: str) -> None:
        m = _VERSION_RE.match(raw.strip())
        if not m:
            raise ValueError(f"invalid semver: {raw!r}")
        self.major = int(m.group("major"))
        self.minor = int(m.group("minor"))
        self.patch = int(m.group("patch"))
        pre = m.group("pre")
        self.prerelease = tuple(pre.split(".")) if pre else ()
        self.build = m.group("build") or ""
        self.raw = raw.strip()

    @property
    def core(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)


def parse(raw: str) -> Version | None:
    try:
        return Version(raw)
    except ValueError:
        return None


def _pre_id(part: str) -> tuple[int, int | str]:
    if part.isdigit():
        return (0, int(part))
    return (1, part)


def compare(a: str, b: str) -> int:
    """<0 if a<b, 0 if equal (build ignored), >0 if a>b."""
    va, vb = Version(a), Version(b)
    if va.core != vb.core:
        return -1 if va.core < vb.core else 1
    if not va.prerelease and not vb.prerelease:
        return 0
    if not va.prerelease:
        return 1
    if not vb.prerelease:
        return -1
    n = max(len(va.prerelease), len(vb.prerelease))
    for i in range(n):
        if i >= len(va.prerelease):
            return -1
        if i >= len(vb.prerelease):
            return 1
        ia, ib = _pre_id(va.prerelease[i]), _pre_id(vb.prerelease[i])
        if ia != ib:
            return -1 if ia < ib else 1
    return 0


def _hyphen_expand(expr: str) -> str:
    m = re.match(r"^([^\s]+)\s+-\s+([^\s]+)$", expr.strip())
    if not m:
        return expr
    return f">={m.group(1)} <={m.group(2)}"


def _partial(raw: str) -> tuple[int | None, int | None, int | None, tuple[str, ...]]:
    raw = raw.strip()
    if raw in {"*", "", "x", "X"}:
        return (None, None, None, ())
    m = re.match(
        r"^v?(?P<maj>x|X|\*|0|[1-9]\d*)(?:\.(?P<min>x|X|\*|0|[1-9]\d*)(?:\.(?P<pat>x|X|\*|0|[1-9]\d*)(?:-(?P<pre>[0-9A-Za-z.-]+))?)?)?$",
        raw,
    )
    if not m:
        raise ValueError(raw)

    def num(g: str | None) -> int | None:
        if g is None or g in {"x", "X", "*"}:
            return None
        return int(g)

    pre = tuple((m.group("pre") or "").split(".")) if m.group("pre") else ()
    return (num(m.group("maj")), num(m.group("min")), num(m.group("pat")), pre)


def _caret(raw: str) -> str:
    maj, minor, patch, pre = _partial(raw)
    if maj is None:
        return "*"
    if maj == 0 and minor is None:
        return ">=0.0.0 <1.0.0"
    if maj == 0 and minor == 0 and patch is None:
        return ">=0.0.0 <0.1.0"
    if maj == 0 and minor == 0:
        lo = f"0.0.{patch}"
        if pre:
            lo += "-" + ".".join(pre)
        return f">={lo} <0.0.{patch + 1}"
    if maj == 0:
        lo = f"0.{minor}.{patch or 0}"
        if pre:
            lo += "-" + ".".join(pre)
        return f">={lo} <0.{minor + 1}.0"
    lo_patch = 0 if patch is None else patch
    lo_minor = 0 if minor is None else minor
    lo = f"{maj}.{lo_minor}.{lo_patch}"
    if pre:
        lo += "-" + ".".join(pre)
    return f">={lo} <{maj + 1}.0.0"


def _tilde(raw: str) -> str:
    maj, minor, patch, pre = _partial(raw)
    if maj is None:
        return "*"
    if minor is None:
        return f">={maj}.0.0 <{maj + 1}.0.0"
    if patch is None:
        return f">={maj}.{minor}.0 <{maj}.{minor + 1}.0"
    lo = f"{maj}.{minor}.{patch}"
    if pre:
        lo += "-" + ".".join(pre)
    return f">={lo} <{maj}.{minor + 1}.0"


def _cmp_op(op: str, ver: Version, cand: Version, include_prerelease: bool) -> bool:
    rel = compare(cand.raw, ver.raw)
    if op == ">":
        ok = rel > 0
    elif op == ">=":
        ok = rel >= 0
    elif op == "<":
        ok = rel < 0
    elif op == "<=":
        ok = rel <= 0
    elif op in {"=", "==", ""}:
        ok = rel == 0
    else:
        return False
    if cand.prerelease and not include_prerelease:
        if not ver.prerelease or cand.core != ver.core:
            if op in {">", ">=", "<", "<="}:
                return False
    return ok


def _set_satisfies(expr: str, candidate: str) -> bool:
    cand = parse(candidate)
    if cand is None:
        return False
    expr = _hyphen_expand(expr.strip())
    if expr.startswith("^"):
        expr = _caret(expr[1:])
    elif expr.startswith("~"):
        expr = _tilde(expr[1:])
    parts = [p for p in expr.split() if p]
    if not parts:
        return False
    comparators: list[tuple[str, Version]] = []
    for token in parts:
        m = re.match(r"^(<=|>=|<|>|=)?(.+)$", token)
        if not m:
            return False
        op = m.group(1) or "="
        rhs = m.group(2)
        if any(ch in rhs for ch in "xX*") or rhs.count(".") < 2:
            maj, minor, patch, pre = _partial(rhs)
            if maj is None:
                continue
            if minor is None:
                comparators.append((">=", Version(f"{maj}.0.0")))
                comparators.append(("<", Version(f"{maj + 1}.0.0")))
                continue
            if patch is None:
                comparators.append((">=", Version(f"{maj}.{minor}.0")))
                comparators.append(("<", Version(f"{maj}.{minor + 1}.0")))
                continue
            raw = f"{maj}.{minor}.{patch}"
            if pre:
                raw += "-" + ".".join(pre)
            comparators.append((op, Version(raw)))
        else:
            ver = parse(rhs)
            if ver is None:
                return False
            comparators.append((op, ver))
    # npm prerelease rule: a candidate carrying a prerelease satisfies the
    # set only if some comparator that itself declares a prerelease shares
    # the candidate's core tuple. Precedence itself is always full SemVer
    # ordering, never a string comparison.
    if cand.prerelease:
        pre_cores = {ver.core for (_, ver) in comparators if ver.prerelease}
        if cand.core not in pre_cores:
            return False
    for op, ver in comparators:
        rel = compare(cand.raw, ver.raw)
        if op == ">":
            ok = rel > 0
        elif op == ">=":
            ok = rel >= 0
        elif op == "<":
            ok = rel < 0
        elif op == "<=":
            ok = rel <= 0
        else:
            ok = rel == 0
        if not ok:
            return False
    return True


def satisfies(candidate: str, range_expr: str) -> bool:
    try:
        expr = range_expr.strip()
        if expr in {"", "*", "x", "X"}:
            v = parse(candidate)
            return bool(v) and not v.prerelease
        for alt in expr.split("||"):
            if _set_satisfies(alt.strip(), candidate):
                return True
        return False
    except ValueError:
        return False


def max_satisfying(versions: Iterable[str], range_expr: str) -> str | None:
    best: str | None = None
    for ver in versions:
        if not satisfies(ver, range_expr):
            continue
        if best is None or compare(ver, best) > 0:
            best = ver
    return best
