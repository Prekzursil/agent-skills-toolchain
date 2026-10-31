"""Path-set overlap: glob-match then component-prefix (IMP-0411)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Iterable

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus_40.json"


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
    if pat == "**":
        return True
    if pat == "*":
        return True
    if "?" in pat or "*" in pat:
        import fnmatch

        return fnmatch.fnmatchcase(val, pat)
    return pat == val


def _pattern_matches(pat: tuple[str, ...], val: tuple[str, ...]) -> bool:
    def rec(i: int, j: int) -> bool:
        if i == len(pat):
            return j == len(val)
        if pat[i] == "**":
            # ** matches zero or more components
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
    if len(a) > len(b):
        return False
    return b[: len(a)] == a


def _concrete_or_self(pat: tuple[str, ...]) -> list[tuple[str, ...]]:
    """Treat a pattern with no wildcards as its own exact match."""
    if any(p in {"*", "**"} or "?" in p or "*" in p for p in pat):
        return [pat]
    return [pat]


def _glob_overlap(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    """True if some expansion of a is a prefix of some expansion of b, or vice versa."""
    wild_a = any(p in {"*", "**"} or "*" in p or "?" in p for p in a)
    wild_b = any(p in {"*", "**"} or "*" in p or "?" in p for p in b)
    if not wild_a and not wild_b:
        return _is_prefix(a, b) or _is_prefix(b, a)
    if wild_a and not wild_b:
        # pattern a vs concrete b: overlap if a matches b or a prefix of b
        if _pattern_matches(a, b):
            return True
        for k in range(len(b) + 1):
            if _pattern_matches(a, b[:k]):
                return True
        return False
    if wild_b and not wild_a:
        return _glob_overlap(b, a)
    # both wild: overlap if either can match a prefix-shaped instantiation of the other
    if _pattern_matches(a, b) or _pattern_matches(b, a):
        return True
    # src/*.py vs src/sub/main.py already handled when one is concrete
    return False


def paths_overlap(a: str, b: str, *, os_family: str = "posix", ignore_case: bool | None = None) -> bool:
    ca = _components(a, os_family, ignore_case)
    cb = _components(b, os_family, ignore_case)
    return _glob_overlap(ca, cb)


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


def load_corpus() -> list[dict[str, Any]]:
    if CORPUS.is_file():
        data = json.loads(CORPUS.read_text(encoding="utf-8"))
        rows = data.get("pairs") if isinstance(data, dict) else data
        if isinstance(rows, list) and rows:
            return rows
    receipt = Path(__file__).resolve().parents[1] / "receipts" / "IMP-0411.json"
    if receipt.is_file():
        doc = json.loads(receipt.read_text(encoding="utf-8"))
        table = doc.get("truth_table") or []
        if table:
            return table
    return []


def evaluate_pair(pair: dict[str, Any], overlap_fn: Callable | None = None) -> dict[str, Any]:
    fn = overlap_fn or pathsets_overlap
    os_family = str(pair.get("os_family") or "posix")
    hit = bool(fn(pair["a"], pair["b"], os_family=os_family))
    return {
        "id": pair.get("id"),
        "algorithm_overlap": hit,
        "hand_overlap": pair.get("hand_overlap"),
        "class": pair.get("class"),
    }
