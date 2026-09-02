"""IMP-0401 planted detector-control trees.

capability_id values match directory names so an independent directory-name
set difference (probe 2) must agree with frontmatter-based detect() (probe 1).
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures" / "control"
REPO_SKILLS = FIX / "repo" / "skills"
LIVE_CLAUDE = FIX / "live" / "claude" / "skills"
LIVE_AGENTS = FIX / "live" / "agents" / "skills"
INDEX_PATH = FIX / "index.json"

PLANTED_BOTH = "skill:imp0401-both"
PLANTED_REPO_ONLY = "skill:imp0401-repo-only"
PLANTED_LIVE_ONLY = "skill:imp0401-live-only"
PLANTED_INDEX_ONLY = "skill:imp0401-index-only"


def fixture_repo_roots() -> list[Path]:
    return [REPO_SKILLS]


def fixture_live_roots() -> list[Path]:
    return [LIVE_CLAUDE, LIVE_AGENTS]
