#!/usr/bin/env python3
"""Three-way line-set classification after LF normalisation (ADV-0017 probe 1)."""
from __future__ import annotations

from typing import Any


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


def decode(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


def classify(repo_text: str | None, live_text: str | None) -> str:
    if repo_text is None and live_text is None:
        return "ABSENT-BOTH"
    if repo_text is None:
        return "LIVE-ONLY"
    if live_text is None:
        return "REPO-ONLY"
    rs, ls = line_set(repo_text), line_set(live_text)
    if lf(repo_text) == lf(live_text):
        return "BYTE-IDENTICAL-LF"
    if rs == ls:
        return "EOL-ONLY"
    if rs < ls:
        return "LIVE-SUPERSET"
    if ls < rs:
        return "REPO-SUPERSET"
    if rs & ls and (rs - ls) and (ls - rs):
        return "BOTH-UNIQUE"
    if not (rs & ls) and rs and ls:
        return "BOTH-UNIQUE-DISJOINT"
    return "BOTH-UNIQUE"


def three_way(repo_raw: bytes | None, live_raw: bytes | None) -> dict[str, Any]:
    repo_text = decode(repo_raw) if repo_raw is not None else None
    live_text = decode(live_raw) if live_raw is not None else None
    kind = classify(repo_text, live_text)
    rs = line_set(repo_text or "") if repo_text is not None else set()
    ls = line_set(live_text or "") if live_text is not None else set()
    repo_only = sorted(rs - ls)
    live_only = sorted(ls - rs)
    shared = sorted(rs & ls)
    repo_bytes = len(repo_raw) if repo_raw is not None else 0
    live_bytes = len(live_raw) if live_raw is not None else 0
    if kind in {"BOTH-UNIQUE", "BOTH-UNIQUE-DISJOINT"}:
        size_dir = "both-unique"
    elif live_bytes > repo_bytes and repo_raw is not None and live_raw is not None:
        size_dir = "live-larger"
    elif repo_bytes > live_bytes and repo_raw is not None and live_raw is not None:
        size_dir = "repo-larger"
    elif repo_raw is not None and live_raw is not None:
        size_dir = "same-size"
    elif repo_raw is None:
        size_dir = "live-only"
    else:
        size_dir = "repo-only"
    return {
        "classification": kind,
        "size_direction": size_dir,
        "repo_bytes": repo_bytes,
        "live_bytes": live_bytes,
        "repo_only_line_n": len(repo_only),
        "live_only_line_n": len(live_only),
        "shared_line_n": len(shared),
        "repo_only_lines": repo_only,
        "live_only_lines": live_only,
        "lf_identical": (
            repo_text is not None
            and live_text is not None
            and lf(repo_text) == lf(live_text)
        ),
        "bytes_identical": repo_raw is not None
        and live_raw is not None
        and repo_raw == live_raw,
        "destroy_if_sync_live_to_repo": bool(repo_only),
        "destroy_if_sync_repo_to_live": bool(live_only),
        "destroy_if_either_direction": bool(repo_only) and bool(live_only),
    }


def classify_trees(repo_files: dict, live_files: dict) -> dict[str, Any]:
    keys = sorted(set(repo_files) | set(live_files))
    rows = []
    counts = {
        "BYTE-IDENTICAL-LF": 0,
        "EOL-ONLY": 0,
        "LIVE-SUPERSET": 0,
        "REPO-SUPERSET": 0,
        "BOTH-UNIQUE": 0,
        "BOTH-UNIQUE-DISJOINT": 0,
        "REPO-ONLY": 0,
        "LIVE-ONLY": 0,
        "ABSENT-BOTH": 0,
    }
    either = []
    live_larger = []
    repo_larger = []
    for rel in keys:
        rp = repo_files.get(rel)
        lp = live_files.get(rel)
        rb = rp.read_bytes() if rp is not None else None
        lb = lp.read_bytes() if lp is not None else None
        tw = three_way(rb, lb)
        rec = {"path": rel, "in_repo": rp is not None, "in_live": lp is not None, **tw}
        rows.append(rec)
        counts[tw["classification"]] = counts.get(tw["classification"], 0) + 1
        if tw["destroy_if_either_direction"]:
            either.append(rel)
        if tw["size_direction"] == "live-larger" or (
            tw["classification"] in {"LIVE-SUPERSET"} and tw["live_bytes"] > tw["repo_bytes"]
        ):
            live_larger.append(rel)
        if tw["size_direction"] == "repo-larger" or (
            tw["classification"] in {"REPO-SUPERSET"} and tw["repo_bytes"] > tw["live_bytes"]
        ):
            repo_larger.append(rel)
        if tw["classification"] in {"LIVE-SUPERSET", "BOTH-UNIQUE", "BOTH-UNIQUE-DISJOINT"}:
            if tw["live_bytes"] > tw["repo_bytes"] and rel not in live_larger:
                live_larger.append(rel)
        if tw["classification"] in {"REPO-SUPERSET", "BOTH-UNIQUE", "BOTH-UNIQUE-DISJOINT"}:
            if tw["repo_bytes"] > tw["live_bytes"] and rel not in repo_larger:
                repo_larger.append(rel)
    paired = [r for r in rows if r["in_repo"] and r["in_live"]]
    return {
        "union_files": len(keys),
        "paired_files": len(paired),
        "counts": counts,
        "either_direction_destroy_paths": either,
        "either_direction_destroy_n": len(either),
        "live_larger_paths": sorted(set(live_larger)),
        "repo_larger_paths": sorted(set(repo_larger)),
        "rows": rows,
    }
