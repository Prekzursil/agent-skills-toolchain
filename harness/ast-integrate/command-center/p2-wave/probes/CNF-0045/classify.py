#!/usr/bin/env python3
"""Two-directional live-versus-repo classifier for CNF-0045.

Line-set comparison after LF normalisation. Size is a direction signal only;
it never authorises overwrite when the discarded side still holds unique lines.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

IDENTICAL = "IDENTICAL"
EOL_ONLY = "EOL-ONLY"
REPO_AHEAD = "REPO-AHEAD"
LIVE_AHEAD = "LIVE-AHEAD"
NEEDS_RECONCILE = "NEEDS-RECONCILE"
REPO_ONLY = "REPO-ONLY"
LIVE_ONLY = "LIVE-ONLY"
ABSENT_BOTH = "ABSENT-BOTH"

NO_OP = "NO-OP"
WOULD_REPLACE_LIVE = "WOULD-REPLACE-LIVE"
WOULD_REWRITE_EOL = "WOULD-REWRITE-EOL"
WOULD_CREATE_ON_LIVE = "WOULD-CREATE-ON-LIVE"
REFUSE = "REFUSE"


def lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def lines_of(text: str) -> list[str]:
    body = lf(text)
    if body == "":
        return []
    parts = body.split("\n")
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def line_set(text: str) -> set[str]:
    return set(lines_of(text))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def walk_rel(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = p
    return out


def read_text(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    # Decode bytes directly so CRLF is not eaten (Path.read_text universal newlines).
    return path.read_bytes().decode("utf-8", errors="replace")


def read_bytes(path: Path | None) -> bytes | None:
    if path is None or not path.is_file():
        return None
    return path.read_bytes()


def classify_pair(repo_text: str | None, live_text: str | None) -> str:
    if repo_text is None and live_text is None:
        return ABSENT_BOTH
    if repo_text is None:
        return LIVE_ONLY
    if live_text is None:
        return REPO_ONLY
    repo_raw_eq = repo_text == live_text
    if repo_raw_eq:
        return IDENTICAL
    if lf(repo_text) == lf(live_text):
        return EOL_ONLY
    rs, ls = line_set(repo_text), line_set(live_text)
    repo_unique = rs - ls
    live_unique = ls - rs
    if live_unique and repo_unique:
        return NEEDS_RECONCILE
    if live_unique and not repo_unique:
        return LIVE_AHEAD
    if repo_unique and not live_unique:
        return REPO_AHEAD
    return NEEDS_RECONCILE


def size_direction(repo_bytes: int | None, live_bytes: int | None) -> str:
    if repo_bytes is None and live_bytes is None:
        return "absent"
    if repo_bytes is None:
        return "live-only"
    if live_bytes is None:
        return "repo-only"
    if repo_bytes == live_bytes:
        return "same-size"
    if repo_bytes > live_bytes:
        return "repo-larger"
    return "live-larger"


def rollback_action(classification: str) -> str:
    """What a deploy-target rollback (repo -> live) would do.

    LIVE-AHEAD / NEEDS-RECONCILE / LIVE-ONLY hold live-only content: refuse.
    IDENTICAL is a no-op. Everything else is a planned mutation that dry-run
    must not execute.
    """
    return {
        IDENTICAL: NO_OP,
        EOL_ONLY: WOULD_REWRITE_EOL,
        REPO_AHEAD: WOULD_REPLACE_LIVE,
        LIVE_AHEAD: REFUSE,
        NEEDS_RECONCILE: REFUSE,
        LIVE_ONLY: REFUSE,
        REPO_ONLY: WOULD_CREATE_ON_LIVE,
        ABSENT_BOTH: NO_OP,
    }.get(classification, REFUSE)


def naive_one_directional_action(classification: str) -> str:
    """Repo-is-SSOT overwrite. Misses two-directional unique live content."""
    if classification in {IDENTICAL}:
        return NO_OP
    if classification == LIVE_ONLY:
        return "NAIVE-DELETE-LIVE-ONLY"
    if classification == ABSENT_BOTH:
        return NO_OP
    return "NAIVE-OVERWRITE-LIVE"


def pair_record(rel: str, repo_path: Path | None, live_path: Path | None) -> dict[str, Any]:
    rb, lb = read_bytes(repo_path), read_bytes(live_path)
    rt, lt = read_text(repo_path), read_text(live_path)
    classification = classify_pair(rt, lt)
    rs = line_set(rt or "")
    ls = line_set(lt or "")
    repo_unique = sorted(rs - ls)
    live_unique = sorted(ls - rs)
    repo_n = len(rb) if rb is not None else None
    live_n = len(lb) if lb is not None else None
    live_unique_blob = ("\n".join(live_unique) + "\n").encode("utf-8") if live_unique else b""
    return {
        "path": rel,
        "in_repo": rb is not None,
        "in_live": lb is not None,
        "repo_bytes": repo_n,
        "live_bytes": live_n,
        "repo_sha256": sha256_bytes(rb) if rb is not None else None,
        "live_sha256": sha256_bytes(lb) if lb is not None else None,
        "direction": size_direction(repo_n, live_n),
        "classification": classification,
        "rollback_action": rollback_action(classification),
        "naive_action": naive_one_directional_action(classification),
        "repo_unique_line_count": len(repo_unique),
        "live_unique_line_count": len(live_unique),
        "shared_line_count": len(rs & ls),
        "live_unique_lines_sample": live_unique[:5],
        "live_unique_sha256": sha256_bytes(live_unique_blob) if live_unique else None,
        "live_unique_bytes": len(live_unique_blob),
        "naive_would_destroy_live_unique": bool(
            live_unique and naive_one_directional_action(classification).startswith("NAIVE-")
        ),
    }


def classify_trees(repo_root: Path, live_root: Path) -> dict[str, Any]:
    repo = walk_rel(repo_root)
    live = walk_rel(live_root)
    keys = sorted(set(repo) | set(live))
    rows = [pair_record(rel, repo.get(rel), live.get(rel)) for rel in keys]
    counts: dict[str, int] = {}
    directions: dict[str, int] = {}
    actions: dict[str, int] = {}
    for row in rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
        directions[row["direction"]] = directions.get(row["direction"], 0) + 1
        actions[row["rollback_action"]] = actions.get(row["rollback_action"], 0) + 1
    content_differing = [
        r
        for r in rows
        if r["classification"]
        in {REPO_AHEAD, LIVE_AHEAD, NEEDS_RECONCILE, REPO_ONLY, LIVE_ONLY}
    ]
    content_repo_larger = sum(1 for r in content_differing if r["direction"] == "repo-larger")
    content_live_larger = sum(1 for r in content_differing if r["direction"] == "live-larger")
    return {
        "repo_root": str(repo_root),
        "live_root": str(live_root),
        "union_files": len(keys),
        "classification_counts": counts,
        "direction_counts": directions,
        "action_counts": actions,
        "identical": counts.get(IDENTICAL, 0),
        "eol_only": counts.get(EOL_ONLY, 0),
        "content_differing": len(content_differing),
        "byte_repo_larger": directions.get("repo-larger", 0),
        "byte_live_larger": directions.get("live-larger", 0),
        "repo_larger": content_repo_larger,
        "live_larger": content_live_larger,
        "needs_reconcile": counts.get(NEEDS_RECONCILE, 0),
        "rows": rows,
    }
