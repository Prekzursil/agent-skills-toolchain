"""Read-only two-directional byte/line classifier for CNF-0101.

Four-way classes for files present on both sides:
  IDENTICAL, EOL_ONLY, content-differ (REPO_AHEAD / LIVE_AHEAD / DIVERGED).
Direction of larger is byte-size of the raw files, reported separately so
EOL-only CRLF inflation is not counted as live-ahead content.

A one-directional 'repo has extra lines' read is exported so probe 2 can
prove it misses DIVERGED (live-unique lines ignored).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

IDENTICAL = "IDENTICAL"
EOL_ONLY = "EOL_ONLY"
REPO_AHEAD = "REPO_AHEAD"
LIVE_AHEAD = "LIVE_AHEAD"
DIVERGED = "DIVERGED"
REPO_ONLY = "REPO_ONLY"
LIVE_ONLY = "LIVE_ONLY"
CONTENT_DIFFER = "CONTENT_DIFFER"


def sha256_raw(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_eol(data: bytes) -> bytes:
    if b"\0" in data:
        return data
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def line_set(data: bytes) -> set[str]:
    text = normalize_eol(data).decode("utf-8", errors="replace")
    if text == "":
        return set()
    parts = text.split("\n")
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return set(parts)


def larger_side(repo_n: int | None, live_n: int | None) -> str:
    if repo_n is None:
        return "live-only"
    if live_n is None:
        return "repo-only"
    if repo_n > live_n:
        return "repo"
    if live_n > repo_n:
        return "live"
    return "equal"


def classify_pair(repo: bytes | None, live: bytes | None) -> dict:
    if repo is None and live is None:
        raise ValueError("both-absent")
    if repo is None:
        live_n = len(live or b"")
        return {
            "class": LIVE_ONLY,
            "four_way": LIVE_ONLY,
            "larger": "live-only",
            "in_repo": False,
            "in_live": True,
            "repo_bytes": None,
            "live_bytes": live_n,
            "repo_sha256": None,
            "live_sha256": sha256_raw(live or b""),
            "repo_sha256_lf": None,
            "live_sha256_lf": sha256_raw(normalize_eol(live or b"")),
            "repo_crlf_count": 0,
            "live_crlf_count": (live or b"").count(b"\r\n"),
            "repo_unique_lines": [],
            "live_unique_lines": sorted(line_set(live or b"")),
            "repo_unique_line_count": 0,
            "live_unique_line_count": len(line_set(live or b"")),
        }
    if live is None:
        repo_n = len(repo)
        return {
            "class": REPO_ONLY,
            "four_way": REPO_ONLY,
            "larger": "repo-only",
            "in_repo": True,
            "in_live": False,
            "repo_bytes": repo_n,
            "live_bytes": None,
            "repo_sha256": sha256_raw(repo),
            "live_sha256": None,
            "repo_sha256_lf": sha256_raw(normalize_eol(repo)),
            "live_sha256_lf": None,
            "repo_crlf_count": repo.count(b"\r\n"),
            "live_crlf_count": 0,
            "repo_unique_lines": sorted(line_set(repo)),
            "live_unique_lines": [],
            "repo_unique_line_count": len(line_set(repo)),
            "live_unique_line_count": 0,
        }

    repo_lf = normalize_eol(repo)
    live_lf = normalize_eol(live)
    rset, lset = line_set(repo), line_set(live)
    repo_unique = sorted(rset - lset)
    live_unique = sorted(lset - rset)
    rec = {
        "in_repo": True,
        "in_live": True,
        "repo_bytes": len(repo),
        "live_bytes": len(live),
        "repo_sha256": sha256_raw(repo),
        "live_sha256": sha256_raw(live),
        "repo_sha256_lf": sha256_raw(repo_lf),
        "live_sha256_lf": sha256_raw(live_lf),
        "repo_crlf_count": repo.count(b"\r\n"),
        "live_crlf_count": live.count(b"\r\n"),
        "repo_unique_lines": repo_unique,
        "live_unique_lines": live_unique,
        "repo_unique_line_count": len(repo_unique),
        "live_unique_line_count": len(live_unique),
        "larger": larger_side(len(repo), len(live)),
        "eol_delta_bytes": abs(len(repo) - len(live)),
    }
    if repo == live:
        rec["class"] = IDENTICAL
        rec["four_way"] = IDENTICAL
        return rec
    if repo_lf == live_lf:
        rec["class"] = EOL_ONLY
        rec["four_way"] = EOL_ONLY
        return rec
    rec["four_way"] = CONTENT_DIFFER
    if repo_unique and live_unique:
        rec["class"] = DIVERGED
    elif repo_unique and not live_unique:
        rec["class"] = REPO_AHEAD
    elif live_unique and not repo_unique:
        rec["class"] = LIVE_AHEAD
    else:
        rec["class"] = CONTENT_DIFFER
    return rec


def classify_one_directional(repo: bytes | None, live: bytes | None) -> str:
    """One-directional read: 'does the repo hold extra lines?'

    Measured estate failure: a DIVERGED pair (unique lines on BOTH sides)
    is reported as REPO_AHEAD because live-unique content is never asked.
    """
    if repo is None:
        return LIVE_ONLY
    if live is None:
        return REPO_ONLY
    if repo == live:
        return IDENTICAL
    rset, lset = line_set(repo), line_set(live)
    repo_extra = rset - lset
    if repo_extra:
        return REPO_AHEAD
    live_extra = lset - rset
    if live_extra:
        return LIVE_AHEAD
    if normalize_eol(repo) == normalize_eol(live):
        return EOL_ONLY
    return CONTENT_DIFFER


def iter_rel_files(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = p
    return out


def fingerprint_tree(root: Path) -> dict[str, str]:
    """Raw sha256 + size + mtime_ns per relative path. Read-only."""
    out: dict[str, str] = {}
    for rel, p in iter_rel_files(root).items():
        raw = p.read_bytes()
        st = p.stat()
        out[rel] = f"{sha256_raw(raw)}:{len(raw)}:{st.st_mtime_ns}"
    return out


def compare_trees(repo_root: Path, live_root: Path) -> dict:
    repo = iter_rel_files(repo_root)
    live = iter_rel_files(live_root)
    keys = sorted(set(repo) | set(live))
    rows = []
    counts = {
        "identical": 0,
        "eol_only": 0,
        "content_differ": 0,
        "content_repo_larger": 0,
        "content_live_larger": 0,
        "content_same_size": 0,
        "repo_only": 0,
        "live_only": 0,
        "diverged_both_unique": 0,
        "repo_ahead": 0,
        "live_ahead": 0,
    }
    for rel in keys:
        rp, lp = repo.get(rel), live.get(rel)
        rb = rp.read_bytes() if rp is not None else None
        lb = lp.read_bytes() if lp is not None else None
        rec = classify_pair(rb, lb)
        rec["path"] = rel
        rec["one_directional_class"] = classify_one_directional(rb, lb)
        clazz = rec["class"]
        if clazz == IDENTICAL:
            counts["identical"] += 1
        elif clazz == EOL_ONLY:
            counts["eol_only"] += 1
        elif clazz == REPO_ONLY:
            counts["repo_only"] += 1
        elif clazz == LIVE_ONLY:
            counts["live_only"] += 1
        else:
            counts["content_differ"] += 1
            if clazz == DIVERGED:
                counts["diverged_both_unique"] += 1
            elif clazz == REPO_AHEAD:
                counts["repo_ahead"] += 1
            elif clazz == LIVE_AHEAD:
                counts["live_ahead"] += 1
            if rec["larger"] == "repo":
                counts["content_repo_larger"] += 1
            elif rec["larger"] == "live":
                counts["content_live_larger"] += 1
            else:
                counts["content_same_size"] += 1
        rows.append(rec)
    both = counts["identical"] + counts["eol_only"] + counts["content_differ"]
    return {
        "repo_root": str(repo_root),
        "live_root": str(live_root),
        "union_files": len(keys),
        "both_sides": both,
        "four_way_counts": {
            "identical": counts["identical"],
            "eol_only": counts["eol_only"],
            "content_differ": counts["content_differ"],
            "content_repo_larger": counts["content_repo_larger"],
            "content_live_larger": counts["content_live_larger"],
            "content_same_size": counts["content_same_size"],
            "repo_only": counts["repo_only"],
            "live_only": counts["live_only"],
            "diverged_both_unique": counts["diverged_both_unique"],
            "repo_ahead": counts["repo_ahead"],
            "live_ahead": counts["live_ahead"],
        },
        "cited_2026_08_09_5_of_88": False,
        "rows": rows,
    }
