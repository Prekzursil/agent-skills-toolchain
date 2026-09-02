"""Five-way line-set classification of paired repo/live trees."""
from __future__ import annotations

from pathlib import Path
from typing import Any

IDENTICAL = "identical"
EOL_ONLY = "eol-only"
REPO_LARGER = "repo-larger"
LIVE_LARGER = "live-larger"
DIVERGED_BOTH_UNIQUE = "diverged-both-unique"


def _files(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = p
    return out


def _lines(raw: bytes) -> list[str]:
    text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    if text == "":
        return []
    parts = text.split("\n")
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def classify_pair(repo_raw: bytes | None, live_raw: bytes | None) -> dict[str, Any]:
    if repo_raw is None and live_raw is None:
        kind = "absent"
    elif repo_raw is None:
        kind = "live-only"
    elif live_raw is None:
        kind = "repo-only"
    else:
        rl, ll = _lines(repo_raw), _lines(live_raw)
        rs, ls = set(rl), set(ll)
        if repo_raw == live_raw:
            kind = IDENTICAL
        elif rl == ll:
            kind = EOL_ONLY
        elif rs < ls:
            kind = LIVE_LARGER
        elif ls < rs:
            kind = REPO_LARGER
        else:
            kind = DIVERGED_BOTH_UNIQUE
    repo_set = set(_lines(repo_raw or b"")) if repo_raw is not None else set()
    live_set = set(_lines(live_raw or b"")) if live_raw is not None else set()
    rb = len(repo_raw or b"")
    lb = len(live_raw or b"")
    if rb > lb:
        byte_dir = "repo-larger"
    elif lb > rb:
        byte_dir = "live-larger"
    else:
        byte_dir = "same-size"
    naive = IDENTICAL if rb == lb else byte_dir
    return {
        "classification": kind,
        "content_divergence": kind not in {IDENTICAL, EOL_ONLY, "absent"},
        "repo_unique_line_count": len(repo_set - live_set),
        "live_unique_line_count": len(live_set - repo_set),
        "repo_bytes": rb,
        "live_bytes": lb,
        "byte_direction": byte_dir,
        "naive_size_class": naive,
    }


def classify_trees(repo_root: Path, live_root: Path) -> dict[str, Any]:
    repo = _files(Path(repo_root))
    live = _files(Path(live_root))
    union = sorted(set(repo) | set(live))
    rows = []
    counts: dict[str, int] = {
        IDENTICAL: 0,
        EOL_ONLY: 0,
        REPO_LARGER: 0,
        LIVE_LARGER: 0,
        DIVERGED_BOTH_UNIQUE: 0,
    }
    for rel in union:
        rp, lp = repo.get(rel), live.get(rel)
        info = classify_pair(
            rp.read_bytes() if rp else None,
            lp.read_bytes() if lp else None,
        )
        info["path"] = rel
        info["action"] = None
        rows.append(info)
        if info["classification"] in counts:
            counts[info["classification"]] += 1
    naive_misses = [
        r["path"]
        for r in rows
        if r["classification"] == DIVERGED_BOTH_UNIQUE
        and r.get("naive_size_class") != DIVERGED_BOTH_UNIQUE
    ]
    return {
        "rows": rows,
        "union_files": len(union),
        "classification_counts": counts,
        "naive_misses_both_unique": naive_misses,
    }
