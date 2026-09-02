#!/usr/bin/env python3
"""Planted both-states fixtures for TST-0079.

Every class the unit names is present: identical, EOL-only, repo-ahead,
live-ahead, diverged. Trees are written under a caller-supplied root so probes
are hermetic.
"""
from __future__ import annotations

from pathlib import Path

SHARED = "# shared prefix\ncommon line\n"

FILES = {
    "common/identical.md": {
        "repo": SHARED + "identical tail\n",
        "live": SHARED + "identical tail\n",
        "want": "IDENTICAL",
    },
    "common/eol-only.md": {
        "repo": "line one\nline two\n",
        "live": "line one\r\nline two\r\n",
        "want": "EOL-ONLY",
    },
    "common/repo-ahead.md": {
        "repo": SHARED + "REPO-UNIQUE-LINE:alpha\n",
        "live": SHARED,
        "want": "REPO-AHEAD",
    },
    "common/live-ahead.md": {
        "repo": SHARED,
        "live": SHARED + "LIVE-UNIQUE-LINE:beta\n",
        "want": "LIVE-AHEAD",
    },
    "common/diverged.md": {
        "repo": SHARED + "REPO-UNIQUE-LINE:gamma\n",
        "live": SHARED + "LIVE-UNIQUE-LINE:delta\n",
        "want": "DIVERGED",
    },
}


def write_trees(root: Path) -> dict[str, Path]:
    repo = root / "repo"
    live = root / "live"
    for rel, spec in FILES.items():
        rp = repo / rel
        lp = live / rel
        rp.parent.mkdir(parents=True, exist_ok=True)
        lp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_bytes(spec["repo"].encode("utf-8"))
        lp.write_bytes(spec["live"].encode("utf-8"))
    return {"repo": repo, "live": live}
