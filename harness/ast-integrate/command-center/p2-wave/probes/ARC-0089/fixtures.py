"""Deterministic skill-tree fixtures for ARC-0089 probes."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

ALWAYS_ON = """\
---
name: always-on
description: Known always-on skill. Router consumes name and description. No paths key, so the body is injected at turn zero.
---

# Always-on

TURN0-BODY:always-on
Use this skill for the turn-zero injection control.
"""

LAZY = """\
---
name: lazy-scoped
description: Path-scoped skill. Router still indexes name and description at turn zero. Body loads only on a matching touch.
paths:
  - "src/**/*.py"
---

# Lazy scoped

LAZY-BODY:lazy-scoped
This body must not appear in the turn-zero context bag.
"""

COUNCIL = """\
---
name: council
description: Four-voice prompt skill (Architect, Skeptic, Pragmatist, Critic). Not a CouncilSpec compiler.
---

Invoke the four named roles as static prompt sections. No executable policy. No CouncilSpec expression tree.

Roles: Architect, Skeptic, Pragmatist, Critic
TURN0-BODY:council
"""

REPO_ONLY = """\
---
name: repo-only
description: Present in the repository skill tree and absent from both live trees. This is the named failure class.
---

# Repo only

TURN0-BODY:repo-only
"""

CLAUDE_ONLY = """\
---
name: claude-only
description: Live Claude tree only. Not in repo, not in the agents tree.
---

# Claude only

LIVE-BODY:claude-only
"""

AGENTS_ONLY = """\
---
name: agents-only
description: Live agents tree only. Not in repo, not in the Claude tree.
---

# Agents only

LIVE-BODY:agents-only
"""

DRIFT_REPO = """\
---
name: shared-drift
description: Same package id in all three trees; live Claude copy has drifted.
---

# Shared drift repo

TURN0-BODY:shared-drift-repo
"""

DRIFT_CLAUDE = """\
---
name: shared-drift
description: Same package id in all three trees; live Claude copy has drifted.
---

# Shared drift claude

TURN0-BODY:shared-drift-claude
"""

BARE_RULE = """\
# Bare rule with no frontmatter

TURN0-BODY:bare-rule
Absence of a fence is always-on, not never-loaded.
"""

PATH_RULE = """\
---
paths:
  - "tests/**/*.py"
---

# Path-scoped rule

LAZY-BODY:path-rule
Believed always-on if someone treats any frontmatter as an arming switch.
"""


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")


def _wipe_files(root: Path) -> None:
    if not root.exists():
        return
    for p in root.rglob("*"):
        if p.is_file():
            p.unlink()


def skill(root: Path, sid: str, body: str) -> None:
    _write(root / sid / "SKILL.md", body)


def build_parity_fail() -> dict[str, Path]:
    repo = FIX / "parity-fail" / "repo"
    claude = FIX / "parity-fail" / "live-claude"
    agents = FIX / "parity-fail" / "live-agents"
    for p in (repo, claude, agents):
        _wipe_files(p)
    for tree in (repo, claude, agents):
        skill(tree, "always-on", ALWAYS_ON)
        skill(tree, "lazy-scoped", LAZY)
        skill(tree, "council", COUNCIL)
    skill(repo, "repo-only", REPO_ONLY)
    skill(claude, "claude-only", CLAUDE_ONLY)
    skill(agents, "agents-only", AGENTS_ONLY)
    skill(repo, "shared-drift", DRIFT_REPO)
    skill(agents, "shared-drift", DRIFT_REPO)
    skill(claude, "shared-drift", DRIFT_CLAUDE)
    return {"repo": repo, "live_claude": claude, "live_agents": agents}


def build_parity_ok() -> dict[str, Path]:
    repo = FIX / "parity-ok" / "repo"
    claude = FIX / "parity-ok" / "live-claude"
    agents = FIX / "parity-ok" / "live-agents"
    for p in (repo, claude, agents):
        _wipe_files(p)
    for tree in (repo, claude, agents):
        skill(tree, "always-on", ALWAYS_ON)
        skill(tree, "lazy-scoped", LAZY)
        skill(tree, "council", COUNCIL)
    return {"repo": repo, "live_claude": claude, "live_agents": agents}


def build_scratch() -> Path:
    root = FIX / "scratch"
    _wipe_files(root)
    skill(root, "always-on", ALWAYS_ON)
    skill(root, "lazy-scoped", LAZY)
    _write(root / "rules" / "common" / "no-frontmatter.md", BARE_RULE)
    _write(root / "rules" / "common" / "path-scoped.md", PATH_RULE)
    return root
