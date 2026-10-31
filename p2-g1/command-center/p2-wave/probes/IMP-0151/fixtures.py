"""IMP-0151 fixtures: build a two-root capability tree in a temp dir."""
from __future__ import annotations

import tempfile
from pathlib import Path

SHARED_MD = "---\nname: shared-skill\ndescription: identical on both sides\n---\nbody\n"
REPO_ONLY_MD = "---\nname: repo-only-skill\ndescription: tracked but never deployed\n---\nbody\n"
LIVE_ONLY_MD = "---\nname: live-only-skill\ndescription: deployed but never tracked\n---\nbody\n"


def build_fixture() -> tuple[Path, Path, Path]:
    """Return (root, repo_root, live_root) with shared + one-only-each skills."""
    root = Path(tempfile.mkdtemp(prefix="imp0151-"))
    repo = root / "repo" / ".agents" / "skills"
    live = root / "live" / ".claude" / "skills"
    (repo / "shared-skill").mkdir(parents=True)
    (repo / "shared-skill" / "SKILL.md").write_text(SHARED_MD, encoding="utf-8", newline="\n")
    (repo / "repo-only-skill").mkdir(parents=True)
    (repo / "repo-only-skill" / "SKILL.md").write_text(REPO_ONLY_MD, encoding="utf-8", newline="\n")
    (live / "shared-skill").mkdir(parents=True)
    (live / "shared-skill" / "SKILL.md").write_text(SHARED_MD, encoding="utf-8", newline="\n")
    (live / "live-only-skill").mkdir(parents=True)
    (live / "live-only-skill" / "SKILL.md").write_text(LIVE_ONLY_MD, encoding="utf-8", newline="\n")
    return root, repo, live
