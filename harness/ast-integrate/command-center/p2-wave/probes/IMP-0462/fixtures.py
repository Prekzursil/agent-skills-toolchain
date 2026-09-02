#!/usr/bin/env python3
"""Deterministic fixture trees for IMP-0462.

Host `rules/` and `~/.claude/rules` are absent on this Linux worktree. The
five-way census is measured on these fixtures, not cited from the 2026-08-09
5/88 Windows estate.
"""
from __future__ import annotations

from pathlib import Path

IDENTICAL = [
    "rules/common/agents.md",
    "rules/common/hooks.md",
]
EOL_ONLY = [
    "rules/eol/eol-00.md",
    "rules/eol/eol-01.md",
]
REPO_LARGER = [
    "rules/repo-ahead/repo-00.md",
    "rules/repo-ahead/repo-01.md",
    "rules/repo-ahead/repo-02.md",
]
LIVE_LARGER = [
    "rules/common/owner-ops-authorization.md",
    "rules/common/performance.md",
]
DIVERGED = [
    "rules/common/planted-both-unique.md",
    "rules/project/reviews.md",
]
REFUSE_ONLY = "rules/common/planted-both-unique.md"
PERMIT_ONLY = "rules/repo-ahead/repo-00.md"
EOL_ONLY_FILE = "rules/eol/eol-00.md"

SHARED = "# shared prefix\ncommon policy line\nsecond common line\n"


def _write(path: Path, body: str, newline: str = "\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = body.replace("\n", newline)
    if not data.endswith(("\n", "\r\n")):
        data += newline
    path.write_bytes(data.encode("utf-8"))


def _wipe(root: Path) -> None:
    if not root.exists():
        return
    for p in sorted(root.rglob("*"), reverse=True):
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            try:
                p.rmdir()
            except OSError:
                pass


def _fill_pair(repo: Path, live: Path) -> None:
    for rel in IDENTICAL:
        body = f"# {rel}\nshared identical body for both trees\nstable-line\n"
        _write(repo / rel, body, "\n")
        _write(live / rel, body, "\n")
    for rel in EOL_ONLY:
        body = f"# {rel}\nEOL-only pair: logical content matches\nline-two\n"
        _write(repo / rel, body, "\n")
        _write(live / rel, body, "\r\n")
    for i, rel in enumerate(REPO_LARGER):
        live_body = SHARED
        repo_body = SHARED + f"REPO-ONLY extra {i}\nREPO-ONLY extra-b {i}\n"
        _write(live / rel, live_body, "\n")
        _write(repo / rel, repo_body, "\n")
    for rel in LIVE_LARGER:
        repo_body = f"# {rel}\nshared prefix\ncommon policy line\n"
        live_body = repo_body + f"LIVE-ONLY remainder for {rel}\nLIVE-ONLY second\n"
        _write(repo / rel, repo_body, "\n")
        _write(live / rel, live_body, "\n")
    for rel in DIVERGED:
        live_body = SHARED + f"LIVE-UNIQUE remainder for {rel}\nLIVE-UNIQUE second\n"
        repo_body = SHARED + f"REPO-UNIQUE remainder for {rel}\nREPO-UNIQUE second\n"
        repo_body += f"REPO-UNIQUE pad {rel}\n"
        _write(live / rel, live_body, "\n")
        _write(repo / rel, repo_body, "\n")


def materialize(root: Path) -> dict:
    census_repo = root / "census" / "repo"
    census_live = root / "census" / "live"
    refuse_repo = root / "refuse" / "repo"
    refuse_live = root / "refuse" / "live"
    permit_repo = root / "permit" / "repo"
    permit_live = root / "permit" / "live"
    eol_repo = root / "eol" / "repo"
    eol_live = root / "eol" / "live"
    for p in (
        census_repo,
        census_live,
        refuse_repo,
        refuse_live,
        permit_repo,
        permit_live,
        eol_repo,
        eol_live,
    ):
        _wipe(p)

    _fill_pair(census_repo, census_live)

    live_div = SHARED + f"LIVE-UNIQUE remainder for {REFUSE_ONLY}\nLIVE-UNIQUE second\n"
    repo_div = SHARED + f"REPO-UNIQUE remainder for {REFUSE_ONLY}\nREPO-UNIQUE second\n"
    repo_div += f"REPO-UNIQUE pad {REFUSE_ONLY}\n"
    _write(refuse_live / REFUSE_ONLY, live_div, "\n")
    _write(refuse_repo / REFUSE_ONLY, repo_div, "\n")

    permit_live_body = SHARED
    permit_repo_body = SHARED + "REPO-ONLY extra 0\nREPO-ONLY extra-b 0\n"
    _write(permit_live / PERMIT_ONLY, permit_live_body, "\n")
    _write(permit_repo / PERMIT_ONLY, permit_repo_body, "\n")

    eol_body = f"# {EOL_ONLY_FILE}\nEOL-only pair: logical content matches\nline-two\n"
    _write(eol_repo / EOL_ONLY_FILE, eol_body, "\n")
    _write(eol_live / EOL_ONLY_FILE, eol_body, "\r\n")

    expected_union = (
        len(IDENTICAL) + len(EOL_ONLY) + len(REPO_LARGER) + len(LIVE_LARGER) + len(DIVERGED)
    )
    return {
        "census_repo": str(census_repo),
        "census_live": str(census_live),
        "refuse_repo": str(refuse_repo),
        "refuse_live": str(refuse_live),
        "permit_repo": str(permit_repo),
        "permit_live": str(permit_live),
        "eol_repo": str(eol_repo),
        "eol_live": str(eol_live),
        "expected": {
            "union_files": expected_union,
            "identical": len(IDENTICAL),
            "eol_only": len(EOL_ONLY),
            "repo_larger": len(REPO_LARGER),
            "live_larger": len(LIVE_LARGER),
            "diverged_both_unique": len(DIVERGED),
        },
        "refuse_path": REFUSE_ONLY,
        "permit_path": PERMIT_ONLY,
        "eol_path": EOL_ONLY_FILE,
        "estate": "IMP-0462 fixture (host live trees absent on this Linux worktree)",
        "cited_2026_08_09_5_of_88": False,
    }
