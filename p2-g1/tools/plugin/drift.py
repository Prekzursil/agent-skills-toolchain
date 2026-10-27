"""Two-directional live-versus-repo drift classifier."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable

IDENTICAL = "IDENTICAL"
IDENTICAL_MODULO_EOL = "IDENTICAL-MODULO-EOL"
REPO_AHEAD = "REPO-AHEAD"
LIVE_AHEAD = "LIVE-AHEAD"
DIVERGED = "DIVERGED"
CLASSES = (IDENTICAL, IDENTICAL_MODULO_EOL, REPO_AHEAD, LIVE_AHEAD, DIVERGED)
REPAIRABLE = frozenset({IDENTICAL_MODULO_EOL, REPO_AHEAD})


def _norm_eol(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def classify_pair(repo_b: bytes, live_b: bytes, one_directional: bool = False) -> str:
    if repo_b == live_b:
        return IDENTICAL
    rn = _norm_eol(repo_b)
    ln = _norm_eol(live_b)
    if rn == ln:
        return IDENTICAL_MODULO_EOL
    if one_directional:
        if len(repo_b) > len(live_b):
            return REPO_AHEAD
        if len(live_b) > len(repo_b):
            return LIVE_AHEAD
        return DIVERGED
    rc = Counter(rn.splitlines())
    lc = Counter(ln.splitlines())
    only_repo = rc - lc
    only_live = lc - rc
    if only_repo and only_live:
        return DIVERGED
    if only_repo and not only_live:
        return REPO_AHEAD
    if only_live and not only_repo:
        return LIVE_AHEAD
    return DIVERGED


def _files(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            out[rel] = p
    return out


def classify_trees(repo_root: Path | str, live_root: Path | str) -> list[dict]:
    repo = Path(repo_root)
    live = Path(live_root)
    a = _files(repo)
    b = _files(live)
    rows = []
    for rel in sorted(set(a) | set(b)):
        rb = a[rel].read_bytes() if rel in a else b""
        lb = b[rel].read_bytes() if rel in b else b""
        if rel not in a:
            klass = LIVE_AHEAD
        elif rel not in b:
            klass = REPO_AHEAD
        else:
            klass = classify_pair(rb, lb, one_directional=False)
        rows.append(
            {
                "path": rel,
                "classification": klass,
                "repo_bytes": len(rb),
                "live_bytes": len(lb),
            }
        )
    return rows


def tally(rows: Iterable[dict]) -> dict[str, int]:
    counts = {c: 0 for c in CLASSES}
    n = 0
    for row in rows:
        n += 1
        k = row.get("classification")
        if k in counts:
            counts[k] += 1
    counts["union"] = n
    return counts
