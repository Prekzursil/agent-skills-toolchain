#!/usr/bin/env python3
"""Non-destructive repo/live synchroniser under test for TST-0079.

Classification is a line-set comparison after LF normalisation. A one-directional
copy is refused whenever the destination still holds unique lines. EOL-only
differences are not content drift.

This replaces the defect named by the catalog: a plain Copy-Item -Force /
cp -f in either direction on a two-directional pair destroys content.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

IDENTICAL = "IDENTICAL"
EOL_ONLY = "EOL-ONLY"
REPO_AHEAD = "REPO-AHEAD"
LIVE_AHEAD = "LIVE-AHEAD"
DIVERGED = "DIVERGED"
REPO_ONLY = "REPO-ONLY"
LIVE_ONLY = "LIVE-ONLY"
ABSENT_BOTH = "ABSENT-BOTH"

CONTENT_DRIFT = frozenset({REPO_AHEAD, LIVE_AHEAD, DIVERGED, REPO_ONLY, LIVE_ONLY})
REFUSE = "REFUSE"
PROCEED = "PROCEED"
NOOP = "NOOP"

DIR_REPO_TO_LIVE = "repo-to-live"
DIR_LIVE_TO_REPO = "live-to-repo"


def lf_bytes(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def lf_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def lines_of(text: str) -> list[str]:
    body = lf_text(text)
    if body == "":
        return []
    parts = body.split("\n")
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def line_set(text: str) -> set[str]:
    return set(lines_of(text))


def sha256_raw(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def decode(raw: bytes | None) -> str | None:
    if raw is None:
        return None
    return raw.decode("utf-8", errors="replace")


def classify_pair(repo: bytes | None, live: bytes | None) -> dict[str, Any]:
    """Per-file three-way class plus EOL-only. Never inferred from size alone."""
    rec: dict[str, Any] = {
        "in_repo": repo is not None,
        "in_live": live is not None,
        "repo_bytes": None if repo is None else len(repo),
        "live_bytes": None if live is None else len(live),
        "repo_sha256": None if repo is None else sha256_raw(repo),
        "live_sha256": None if live is None else sha256_raw(live),
        "repo_unique_lines": [],
        "live_unique_lines": [],
        "content_drift": False,
    }
    if repo is None and live is None:
        rec["class"] = ABSENT_BOTH
        return rec
    if repo is None:
        rec["class"] = LIVE_ONLY
        rec["content_drift"] = True
        rec["live_unique_lines"] = lines_of(decode(live) or "")
        return rec
    if live is None:
        rec["class"] = REPO_ONLY
        rec["content_drift"] = True
        rec["repo_unique_lines"] = lines_of(decode(repo) or "")
        return rec

    repo_text = decode(repo) or ""
    live_text = decode(live) or ""
    rs, ls = line_set(repo_text), line_set(live_text)
    repo_unique = sorted(rs - ls)
    live_unique = sorted(ls - rs)
    rec["repo_unique_lines"] = repo_unique
    rec["live_unique_lines"] = live_unique
    rec["repo_unique_count"] = len(repo_unique)
    rec["live_unique_count"] = len(live_unique)

    if repo == live:
        rec["class"] = IDENTICAL
        rec["content_drift"] = False
        return rec
    if lf_bytes(repo) == lf_bytes(live):
        rec["class"] = EOL_ONLY
        rec["content_drift"] = False
        return rec
    if repo_unique and live_unique:
        rec["class"] = DIVERGED
        rec["content_drift"] = True
        return rec
    if repo_unique and not live_unique:
        rec["class"] = REPO_AHEAD
        rec["content_drift"] = True
        return rec
    if live_unique and not repo_unique:
        rec["class"] = LIVE_AHEAD
        rec["content_drift"] = True
        return rec
    # Same line-set, different bytes after LF-norm (order / blank-run). Treat as
    # diverged so a one-directional rewrite cannot silently reorder the other side.
    rec["class"] = DIVERGED
    rec["content_drift"] = True
    rec["reason"] = "lf-normalised-bytes-differ-with-empty-unique-sets"
    return rec


def dest_loses_unique(classification: str, direction: str) -> bool:
    if direction == DIR_REPO_TO_LIVE:
        return classification in {DIVERGED, LIVE_AHEAD, LIVE_ONLY}
    if direction == DIR_LIVE_TO_REPO:
        return classification in {DIVERGED, REPO_AHEAD, REPO_ONLY}
    raise ValueError(f"unknown-direction:{direction}")


def sync_decision(classification: str, direction: str) -> str:
    if classification == ABSENT_BOTH:
        return NOOP
    if dest_loses_unique(classification, direction):
        return REFUSE
    if classification == IDENTICAL:
        return NOOP
    return PROCEED


def apply_sync_pair(
    repo_path: Path,
    live_path: Path,
    direction: str,
) -> dict[str, Any]:
    repo_b = repo_path.read_bytes() if repo_path.is_file() else None
    live_b = live_path.read_bytes() if live_path.is_file() else None
    before = classify_pair(repo_b, live_b)
    klass = before["class"]
    decision = sync_decision(klass, direction)
    result: dict[str, Any] = {
        "path_repo": str(repo_path),
        "path_live": str(live_path),
        "direction": direction,
        "class_before": klass,
        "decision": decision,
        "wrote": False,
        "refused": decision == REFUSE,
        "classification": before,
    }
    if decision != PROCEED:
        result["class_after"] = klass
        result["repo_unchanged"] = True
        result["live_unchanged"] = True
        return result

    if direction == DIR_REPO_TO_LIVE:
        if repo_b is None:
            result["decision"] = REFUSE
            result["refused"] = True
            result["reason"] = "repo-absent"
            return result
        live_path.parent.mkdir(parents=True, exist_ok=True)
        live_path.write_bytes(repo_b)
        result["wrote"] = True
        result["wrote_side"] = "live"
    else:
        if live_b is None:
            result["decision"] = REFUSE
            result["refused"] = True
            result["reason"] = "live-absent"
            return result
        repo_path.parent.mkdir(parents=True, exist_ok=True)
        repo_path.write_bytes(live_b)
        result["wrote"] = True
        result["wrote_side"] = "repo"

    after_repo = repo_path.read_bytes() if repo_path.is_file() else None
    after_live = live_path.read_bytes() if live_path.is_file() else None
    after = classify_pair(after_repo, after_live)
    result["class_after"] = after["class"]
    result["repo_unchanged"] = after_repo == repo_b
    result["live_unchanged"] = after_live == live_b
    result["classification_after"] = after
    return result


def iter_rel_files(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = p
    return out


def classify_trees(repo_root: Path, live_root: Path) -> dict[str, Any]:
    repo = iter_rel_files(repo_root)
    live = iter_rel_files(live_root)
    keys = sorted(set(repo) | set(live))
    counts = {
        IDENTICAL: 0,
        EOL_ONLY: 0,
        REPO_AHEAD: 0,
        LIVE_AHEAD: 0,
        DIVERGED: 0,
        REPO_ONLY: 0,
        LIVE_ONLY: 0,
    }
    rows = []
    for rel in keys:
        rp, lp = repo.get(rel), live.get(rel)
        rec = classify_pair(
            rp.read_bytes() if rp is not None else None,
            lp.read_bytes() if lp is not None else None,
        )
        rec["path"] = rel
        rows.append(rec)
        counts[rec["class"]] = counts.get(rec["class"], 0) + 1
    return {
        "repo_root": str(repo_root),
        "live_root": str(live_root),
        "union_files": len(keys),
        "counts": counts,
        "content_drift_files": sum(1 for r in rows if r["content_drift"]),
        "eol_only_not_content_drift": counts[EOL_ONLY],
        "rows": rows,
    }


def sync_trees(repo_root: Path, live_root: Path, direction: str) -> dict[str, Any]:
    """Refuse the whole tree if any pair would lose unique destination lines."""
    census = classify_trees(repo_root, live_root)
    blocking = [
        r
        for r in census["rows"]
        if dest_loses_unique(r["class"], direction)
    ]
    if blocking:
        return {
            "decision": REFUSE,
            "refused": True,
            "wrote": False,
            "direction": direction,
            "blocking": [r["path"] for r in blocking],
            "census": census,
        }
    applied = []
    repo = iter_rel_files(repo_root)
    live = iter_rel_files(live_root)
    for rel in sorted(set(repo) | set(live)):
        applied.append(
            apply_sync_pair(repo_root / rel, live_root / rel, direction)
        )
    return {
        "decision": PROCEED,
        "refused": False,
        "wrote": any(a.get("wrote") for a in applied),
        "direction": direction,
        "applied": applied,
        "census_before": census,
        "census_after": classify_trees(repo_root, live_root),
    }


def naive_overwrite(src: Path, dst: Path) -> None:
    """Known-broken one-directional copy (Copy-Item -Force analogue)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sync_tool")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("classify")
    c.add_argument("--repo", required=True)
    c.add_argument("--live", required=True)
    s = sub.add_parser("sync")
    s.add_argument("--repo", required=True)
    s.add_argument("--live", required=True)
    s.add_argument("--direction", required=True, choices=[DIR_REPO_TO_LIVE, DIR_LIVE_TO_REPO])
    args = p.parse_args(argv)
    repo, live = Path(args.repo), Path(args.live)
    if args.cmd == "classify":
        doc = classify_trees(repo, live)
        print(json.dumps(doc, indent=2, sort_keys=True))
        return 0
    doc = sync_trees(repo, live, args.direction)
    print(json.dumps(doc, indent=2, sort_keys=True))
    return 2 if doc.get("refused") else 0


if __name__ == "__main__":
    raise SystemExit(main())
