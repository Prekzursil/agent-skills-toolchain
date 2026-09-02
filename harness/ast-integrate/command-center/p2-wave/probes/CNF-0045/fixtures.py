#!/usr/bin/env python3
"""Deterministic fixture estate for CNF-0045.

Shape matches the catalog-cited 88-file rules census (5 identical, 55 EOL-only,
28 content-differing = 25 repo-larger + 3 live-larger) plus planted both-unique
rows inside the 25 repo-larger bucket. Measured fresh each run; not a citation
of 2026-08-09 host trees (those are absent on this Linux worktree).
"""
from __future__ import annotations

from pathlib import Path

IDENTICAL = [
    "rules/common/agents.md",
    "rules/common/hooks.md",
    "rules/common/logging.md",
    "rules/project/owners.md",
    "rules/project/naming.md",
]

LIVE_LARGER = [
    ("rules/common/owner-ops-authorization.md", 1001),
    ("rules/common/performance.md", 178),
    ("rules/common/security.md", 97),
]

NEEDS_RECONCILE = [
    "rules/common/planted-both-unique.md",
    "rules/project/reviews.md",
    "rules/project/testing.md",
    "rules/project/release.md",
]

REPO_AHEAD_COUNT = 21  # 25 repo-larger - 4 needs-reconcile


def _write(path: Path, body: str, newline: str = "\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = body.replace("\n", newline)
    if not data.endswith(("\n", "\r\n")):
        data += newline
    path.write_bytes(data.encode("utf-8"))


def _pad_lines(tag: str, nbytes: int) -> str:
    lines: list[str] = []
    n = 0
    i = 1
    while n < nbytes:
        line = f"{tag} unique live policy line {i}"
        lines.append(line)
        n += len(line) + 1
        i += 1
    return "\n".join(lines) + "\n"


def materialize(root: Path) -> dict:
    repo = root / "repo"
    live = root / "live"
    if repo.exists():
        for p in sorted(repo.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                try:
                    p.rmdir()
                except OSError:
                    pass
    if live.exists():
        for p in sorted(live.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                try:
                    p.rmdir()
                except OSError:
                    pass

    for rel in IDENTICAL:
        body = f"# {rel}\nshared identical body for both trees\nstable-line\n"
        _write(repo / rel, body, "\n")
        _write(live / rel, body, "\n")

    for i in range(55):
        rel = f"rules/eol/eol-{i:02d}.md"
        body = f"# {rel}\nEOL-only pair: logical content matches\nline-two\n"
        _write(repo / rel, body, "\n")
        _write(live / rel, body, "\r\n")

    shared = "# shared prefix\ncommon policy line\nsecond common line\n"
    for i in range(REPO_AHEAD_COUNT):
        rel = f"rules/repo-ahead/repo-{i:02d}.md"
        live_body = shared
        repo_body = shared + f"REPO-ONLY extra {i}\nREPO-ONLY extra-b {i}\n"
        _write(live / rel, live_body, "\n")
        _write(repo / rel, repo_body, "\n")

    for rel in NEEDS_RECONCILE:
        live_body = shared + f"LIVE-UNIQUE remainder for {rel}\nLIVE-UNIQUE second\n"
        repo_body = shared + f"REPO-UNIQUE remainder for {rel}\nREPO-UNIQUE second\n"
        # Keep repo larger so these sit in the 25 repo-larger bucket.
        repo_body += f"REPO-UNIQUE pad {rel}\n"
        _write(live / rel, live_body, "\n")
        _write(repo / rel, repo_body, "\n")

    for rel, extra in LIVE_LARGER:
        repo_body = f"# {rel}\nshared prefix\ncommon policy line\n"
        live_body = repo_body + _pad_lines(rel, extra)
        _write(repo / rel, repo_body, "\n")
        _write(live / rel, live_body, "\n")

    return {
        "repo_root": str(repo),
        "live_root": str(live),
        "identical": len(IDENTICAL),
        "eol_only": 55,
        "repo_ahead": REPO_AHEAD_COUNT,
        "needs_reconcile": len(NEEDS_RECONCILE),
        "live_larger_named": [p for p, _ in LIVE_LARGER],
        "expected_union": 5 + 55 + REPO_AHEAD_COUNT + len(NEEDS_RECONCILE) + len(LIVE_LARGER),
    }
