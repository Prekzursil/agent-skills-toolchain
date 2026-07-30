"""R4/AGENTS.md §9: a cloned repo can carry auto-loaded agent config (CVE-2026-47751 class).
Neutralize the TOP-LEVEL entries listed in `_TARGETS` to inert data before any backend runs an
agent/CI in the tree. ENFORCEMENT point for the Databricks BUILD tier = the node runner,
post-clone/pre-codex-exec (deferred; see Roadmap).

TWO limits MUST travel with any caller. Both are measured, not theorised:
- DEPTH-0 ONLY. Every `_TARGETS` entry is joined to `clone_dir` directly, so only a top-level hit is
  renamed. Executed on a tree holding `AGENTS.md`, `sub/AGENTS.md` and `sub/.claude`: the return value
  was `['AGENTS.md']` and BOTH nested paths SURVIVED. Codex and Claude each discover a NESTED
  `AGENTS.md`/`CLAUDE.md`, so a nested one remains live instruction-injection surface. Recursion is
  Roadmap work for the enforcement task, not a one-line `rglob`: it needs a `.git/` exclusion and a
  symlink-escape policy first.
- NEUTRALIZATION IS NOT EXECUTION SAFETY. This moves AGENT config only; it does not make an untrusted
  clone safe to RUN. Measured to survive a full pass: `conftest.py` (pytest AUTO-IMPORTS it before it
  collects a single test), `pyproject.toml` (`[tool.pytest.ini_options]` `addopts` / `-p` plugin
  autoload), and `Makefile`/task-runner scripts. A caller that then runs the repo's own suite or build
  is executing repo-controlled code regardless of this call — so "safe to execute" is NOT the property
  this function provides. Sandbox that step separately.

Also known, Windows-measured: NOT idempotent. A second pass over a tree that already holds a stale
`<name>.UNTRUSTED` raises `FileExistsError` (WinError 183) — `Path.rename` does not overwrite on
Windows. The enforcement wiring must clean or uniquify the destination (Roadmap)."""

from __future__ import annotations

from pathlib import Path

_TARGETS = (
    ".claude",
    ".codex",
    ".cursor",
    ".github/hooks",
    ".husky",
    ".mcp.json",
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".clauderc",
)


def neutralize_agent_config(clone_dir: Path) -> list[str]:
    clone_dir = Path(clone_dir)
    moved: list[str] = []
    for rel in _TARGETS:
        p = clone_dir / rel
        if p.exists():
            p.rename(p.with_name(p.name + ".UNTRUSTED"))
            moved.append(rel)
    return moved
