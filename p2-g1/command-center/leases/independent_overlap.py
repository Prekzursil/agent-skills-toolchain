"""Independent regex/witness overlap — same component-prefix rule as overlap.py."""
from __future__ import annotations

import fnmatch
from typing import Iterable


def _fold(s: str, os_family: str, ignore_case: bool | None) -> str:
    text = str(s).replace("\\", "/")
    fold = ignore_case if ignore_case is not None else (os_family == "windows")
    return text.casefold() if fold else text


def _components(path: str, os_family: str, ignore_case: bool | None) -> tuple[str, ...]:
    text = _fold(path, os_family, ignore_case).strip()
    if text in {"", ".", "./"}:
        return ()
    text = text.strip("/")
    if not text:
        return ()
    return tuple(p for p in text.split("/") if p and p != ".")


def _seg_match(pat: str, val: str) -> bool:
    if pat in {"*", "**"}:
        return True
    if "?" in pat or "*" in pat:
        return fnmatch.fnmatchcase(val, pat)
    return pat == val


def _pattern_matches(pat: tuple[str, ...], val: tuple[str, ...]) -> bool:
    def rec(i: int, j: int) -> bool:
        if i == len(pat):
            return j == len(val)
        if pat[i] == "**":
            if rec(i + 1, j):
                return True
            if j < len(val) and rec(i, j + 1):
                return True
            return False
        if j >= len(val):
            return False
        if not _seg_match(pat[i], val[j]):
            return False
        return rec(i + 1, j + 1)

    return rec(0, 0)


def _is_prefix(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    return len(a) <= len(b) and b[: len(a)] == a


def _glob_overlap(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    wild_a = any(p in {"*", "**"} or "*" in p or "?" in p for p in a)
    wild_b = any(p in {"*", "**"} or "*" in p or "?" in p for p in b)
    if not wild_a and not wild_b:
        return _is_prefix(a, b) or _is_prefix(b, a)
    if wild_a and not wild_b:
        if _pattern_matches(a, b):
            return True
        return any(_pattern_matches(a, b[:k]) for k in range(len(b) + 1))
    if wild_b and not wild_a:
        return _glob_overlap(b, a)
    return _pattern_matches(a, b) or _pattern_matches(b, a)


def paths_overlap(a: str, b: str, *, os_family: str = "posix", ignore_case: bool | None = None) -> bool:
    return _glob_overlap(
        _components(a, os_family, ignore_case),
        _components(b, os_family, ignore_case),
    )


def pathsets_overlap(
    a: Iterable[str],
    b: Iterable[str],
    *,
    os_family: str = "posix",
    ignore_case: bool | None = None,
) -> bool:
    left = [str(x) for x in a]
    right = [str(x) for x in b]
    if not left or not right:
        return False
    for x in left:
        for y in right:
            if paths_overlap(x, y, os_family=os_family, ignore_case=ignore_case):
                return True
    return False
