"""Isolated live/repo estate fixtures for IMP-0151 probes.

Writes stay under probes/IMP-0151/fixtures/. They never touch ~/.claude or ~/.agents.
"""
from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
READONLY_ROOT = FIXTURES / "readonly-estate"
CLASSIFY_ROOT = FIXTURES / "classify-estate"

SHARED_SKILL = """---
name: shared-skill
---
# shared-skill
shared body for both trees
"""

DIVERGENT_REPO = """---
name: divergent-skill
---
# divergent-skill
repo-side body
"""

DIVERGENT_LIVE = """---
name: divergent-skill
---
# divergent-skill
live-side body — not assumed worse or better
"""

PLUGIN = """{
  "name": "harness",
  "version": "0.0.1"
}
"""

HOOK = """# hook
def check():
    return 0
"""

WORKFLOW = """{
  "id": "wf.shared",
  "discovery_only": true
}
"""


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")


def _wipe(root: Path) -> None:
    if root.exists():
        def _onerror(func, path, _exc):
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            func(path)

        shutil.rmtree(root, onerror=_onerror)


def _layout_shared(root: Path) -> None:
    _write(root / "skills" / "shared-skill" / "SKILL.md", SHARED_SKILL)
    _write(root / "skills" / "shared-skill" / "README.txt", "supporting file, not a capability\n")
    _write(root / "commands" / "shared.md", "# shared command\n")
    _write(root / "agents" / "shared.md", "# shared agent\n")
    _write(root / "hooks" / "pre-tool.py", HOOK)
    _write(root / "plugins" / "harness" / "plugin.json", PLUGIN)
    _write(root / "workflows" / "shared.json", WORKFLOW)


def _layout_orphans(repo: Path, live: Path) -> None:
    _write(repo / "skills" / "repo-only-skill" / "SKILL.md", "# repo-only-skill\nrepo only\n")
    _write(live / "skills" / "live-only-skill" / "SKILL.md", "# live-only-skill\nlive only\n")
    _write(repo / "commands" / "repo-only.md", "# repo-only command\n")
    _write(live / "commands" / "live-only.md", "# live-only command\n")


def _layout_divergent(repo: Path, live: Path) -> None:
    _write(repo / "skills" / "divergent-skill" / "SKILL.md", DIVERGENT_REPO)
    _write(live / "skills" / "divergent-skill" / "SKILL.md", DIVERGENT_LIVE)


def _scratch_not_harvested(live: Path) -> None:
    _write(live / "scratch" / "notes.txt", "not a workflow-shaped capability\n")


def build_readonly_estate() -> tuple[Path, Path]:
    """Estate used by the zero-write probe. Full two-directional split."""
    root = READONLY_ROOT
    repo, live = root / "repo", root / "live"
    _wipe(root)
    _layout_shared(repo)
    _layout_shared(live)
    _layout_orphans(repo, live)
    _layout_divergent(repo, live)
    _scratch_not_harvested(live)
    return repo, live


def build_classify_estate(*, plant_orphans: bool) -> tuple[Path, Path]:
    """Both-states estate: shared+divergent always; orphans optional."""
    root = CLASSIFY_ROOT
    repo, live = root / "repo", root / "live"
    _wipe(root)
    _layout_shared(repo)
    _layout_shared(live)
    _layout_divergent(repo, live)
    _scratch_not_harvested(live)
    if plant_orphans:
        _layout_orphans(repo, live)
    return repo, live


def make_tree_readonly(root: Path) -> None:
    """chmod files 444 / dirs 555 so a write attempt fails at the OS."""
    if not root.exists():
        return
    for dirpath, dirnames, filenames in os.walk(root, topdown=False, followlinks=False):
        for name in filenames:
            os.chmod(Path(dirpath) / name, 0o444)
        for name in dirnames:
            os.chmod(Path(dirpath) / name, 0o555)
        os.chmod(dirpath, 0o555)


def restore_tree_writable(root: Path) -> None:
    if not root.exists():
        return
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        os.chmod(dirpath, 0o755)
        for name in filenames:
            os.chmod(Path(dirpath) / name, 0o644)
