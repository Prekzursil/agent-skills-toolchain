#!/usr/bin/env python3
"""Planted skill trees for TST-0083.

Five skills:
  shared-identical  — same bytes on both sides
  eol-twin          — same text, repo LF vs live CRLF (must NOT be divergent)
  plant-repo-only   — repo SKILL.md, absent from live
  plant-live-only   — live SKILL.md, absent from repo
  plant-divergent   — same id, different SKILL.md body
"""
from __future__ import annotations

from pathlib import Path

REPO_ONLY_ID = "plant-repo-only"
LIVE_ONLY_ID = "plant-live-only"
DIVERGENT_ID = "plant-divergent"
IDENTICAL_ID = "shared-identical"
EOL_ID = "eol-twin"

SKILL_BODY = """---
name: {name}
---

# {name}

{body}
"""


def _write(path: Path, text: str, newline: str = "\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))


def skill_md(name: str, body: str) -> str:
    return SKILL_BODY.format(name=name, body=body)


def build_planted_pair(root: Path) -> dict[str, Path]:
    """Create repo/ and live/ skill trees under root. Returns the two roots."""
    repo = root / "repo" / "skills"
    live = root / "live" / "skills"
    if repo.exists():
        for p in repo.rglob("*"):
            if p.is_file():
                p.unlink()
    if live.exists():
        for p in live.rglob("*"):
            if p.is_file():
                p.unlink()

    ident = skill_md(IDENTICAL_ID, "byte-identical on both trees")
    _write(repo / IDENTICAL_ID / "SKILL.md", ident)
    _write(live / IDENTICAL_ID / "SKILL.md", ident)
    _write(repo / IDENTICAL_ID / "notes.txt", "shared helper\n")
    _write(live / IDENTICAL_ID / "notes.txt", "shared helper\n")

    eol_text = skill_md(EOL_ID, "same characters; only newline encoding differs")
    _write(repo / EOL_ID / "SKILL.md", eol_text, newline="\n")
    _write(live / EOL_ID / "SKILL.md", eol_text, newline="\r\n")

    _write(
        repo / REPO_ONLY_ID / "SKILL.md",
        skill_md(REPO_ONLY_ID, "PLANTED repo-only skill TST-0083"),
    )
    _write(repo / REPO_ONLY_ID / "extra.md", "repo-only extra file\n")

    _write(
        live / LIVE_ONLY_ID / "SKILL.md",
        skill_md(LIVE_ONLY_ID, "PLANTED live-only skill TST-0083"),
    )

    _write(
        repo / DIVERGENT_ID / "SKILL.md",
        skill_md(DIVERGENT_ID, "repo body of the planted divergent skill"),
    )
    _write(
        live / DIVERGENT_ID / "SKILL.md",
        skill_md(DIVERGENT_ID, "live body of the planted divergent skill"),
    )

    return {"repo": repo, "live": live}


def expected_ids() -> dict[str, str]:
    return {
        "repo_only": REPO_ONLY_ID,
        "live_only": LIVE_ONLY_ID,
        "divergent": DIVERGENT_ID,
        "identical_a": IDENTICAL_ID,
        "identical_b": EOL_ID,
    }
