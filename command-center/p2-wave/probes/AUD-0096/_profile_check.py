#!/usr/bin/env python3
"""Shared harness-profile detector for AUD-0096.

Imported by BOTH probe1 (the clean-profile measurement) and the control
(fires-on-bad / silent-on-good proof), so the control is not a reimplementation
that could silently diverge from what the probe actually checked -- the same
pattern AUD-0091's `_cache_check.py` uses for its cache-free detector.

SCOPE NOTE (disclosed up front, not buried): the catalog scoped this unit to
"a clean Windows user profile" with Claude/Codex harness state under
%USERPROFILE%. This substrate is Linux Cursor Cloud: there is no Windows
profile, no `pwsh`, and (measured below) no ~/.claude or ~/.codex directory at
all -- this is NOT a Claude Code or Codex CLI harness. The nearest analogous
"profile-level harness state" on THIS substrate is $HOME/.cursor (skills-cursor
side-loaded skill packs, the plugins cache, and agent-hooks), which is what
census_load_set() actually measures. The Claude/Codex paths are kept in
HARNESS_STATE_DIRS for parity with the catalog's original scope and are
expected to read absent=True here -- that absence is itself a measured fact,
not an assumption, and is carried into residual_unknowns rather than silently
dropped.
"""
from __future__ import annotations

from pathlib import Path

HARNESS_STATE_DIRS = [".cursor", ".claude", ".codex"]

# Sub-components under $HOME/.cursor that constitute this substrate's
# profile-level "harness load set" (analogous, at the $HOME layer, to
# AUD-0062's repo-level always-on injection set).
CURSOR_LOAD_COMPONENTS = {
    "cursor_skills_cursor": ".cursor/skills-cursor",
    "cursor_plugins": ".cursor/plugins",
    "cursor_agent_hooks": ".cursor/agent-hooks",
}


def harness_state_present(home: Path) -> dict:
    """Per known harness-state dir under `home`: exists / non-empty / entry
    count. A dir that exists but is empty (e.g. a bare mkdir side effect) does
    not count as leaked profile state."""
    out = {}
    for name in HARNESS_STATE_DIRS:
        p = home / name
        if not p.exists():
            out[name] = {"exists": False, "nonempty": False, "entry_count": 0}
            continue
        try:
            entries = list(p.iterdir())
        except OSError:
            entries = []
        out[name] = {
            "exists": True,
            "nonempty": len(entries) > 0,
            "entry_count": len(entries),
        }
    return out


def is_profile_clean(home: Path) -> dict:
    """A profile is 'clean' iff none of the known harness-state dirs under it
    are non-empty. tests_required: this MUST be proven true of the probe1
    scratch dir BEFORE the load-set measurement runs, otherwise a leaked
    profile would make the clean and current measurements identical by
    construction."""
    state = harness_state_present(home)
    leaked = sorted(k for k, v in state.items() if v["nonempty"])
    return {
        "home": str(home),
        "state": state,
        "leaked_dirs": leaked,
        "clean": len(leaked) == 0,
    }


def _file_stats(root: Path) -> tuple[int, int]:
    if not root.is_dir():
        return 0, 0
    files = [p for p in root.rglob("*") if p.is_file()]
    total_bytes = 0
    for p in files:
        try:
            total_bytes += p.stat().st_size
        except OSError:
            pass
    return len(files), total_bytes


def census_load_set(home: Path) -> dict:
    """Enumerate the profile-level harness load set under `home`.

    Mirrors AUD-0062's repo-level always-on injection census (CLAUDE.md,
    AGENTS.md, always-applied-workspace-rule skills, skill metadata), but at
    the $HOME/profile layer instead of the repo layer: per-user skill packs
    (skills-cursor), the plugin cache, and agent hooks that a Cursor Cloud
    harness merges into a session's available surface IN ADDITION TO (not
    instead of) the repo's own .agents/skills/ tree AUD-0062 already measured.
    Also reports the Claude Code / Codex CLI profile dirs (.claude, .codex)
    the catalog originally scoped, for parity, even though they are expected
    absent on this substrate.
    """
    result: dict = {"home": str(home), "components": {}}

    skills_cursor = home / ".cursor" / "skills-cursor"
    skill_files = (
        sorted(skills_cursor.glob("*/SKILL.md")) if skills_cursor.is_dir() else []
    )
    skill_bytes = 0
    for p in skill_files:
        try:
            skill_bytes += p.stat().st_size
        except OSError:
            pass
    result["components"]["cursor_skills_cursor"] = {
        "path": CURSOR_LOAD_COMPONENTS["cursor_skills_cursor"],
        "exists": skills_cursor.is_dir(),
        "skill_count": len(skill_files),
        "skill_paths": [str(p.relative_to(home)) for p in skill_files],
        "total_bytes": skill_bytes,
    }

    for key in ("cursor_plugins", "cursor_agent_hooks"):
        root = home / Path(CURSOR_LOAD_COMPONENTS[key])
        file_count, total_bytes = _file_stats(root)
        result["components"][key] = {
            "path": CURSOR_LOAD_COMPONENTS[key],
            "exists": root.is_dir(),
            "file_count": file_count,
            "total_bytes": total_bytes,
        }

    for key, rel in (("claude_home", ".claude"), ("codex_home", ".codex")):
        root = home / rel
        file_count, total_bytes = _file_stats(root)
        result["components"][key] = {
            "path": rel,
            "exists": root.is_dir(),
            "file_count": file_count,
            "total_bytes": total_bytes,
        }

    result["total_skill_count"] = result["components"]["cursor_skills_cursor"][
        "skill_count"
    ]
    result["total_file_count"] = sum(
        c.get("file_count", c.get("skill_count", 0))
        for c in result["components"].values()
    )
    result["total_bytes"] = sum(
        c.get("total_bytes", 0) for c in result["components"].values()
    )
    return result
