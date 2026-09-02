"""Deploy map for AUD-0017, taken from AUD-0018 and the live sync scripts.

Catalog input is "the deploy map from AUD-0018". On this worktree that artifact
and scripts/sync-from-live.ps1 exist. Relative paths are identity-mapped
(Copy-Item -Force / no transform at sync-rules.ps1:67). This module does not
invent extra tree pairs: workflows/ is recorded as unmapped, not folded in.
"""
from __future__ import annotations

from pathlib import Path

COPY_PRIMITIVE = (
    "Copy-Item -Force identity relative path; no transform "
    "(AUD-0018 / sync-rules.ps1:67)"
)

# $Map in scripts/sync-from-live.ps1 (live -> repo), plus the repo -> live
# copiers that AUD-0018 line-read. live_rels are relative to Path.home().
ENTRIES: list[dict] = [
    {
        "kind": "rules",
        "repo_rel": "rules",
        "live_rels": [".claude/rules"],
        "catalog_scripts": ["scripts/sync-from-live.ps1", "scripts/sync-rules.ps1"],
        "direction": "live-to-repo ($Map) and repo-to-live subset (rules/common)",
        "basis": (
            "scripts/sync-from-live.ps1 $Map Label=rules; "
            "scripts/sync-rules.ps1 copies only rules/common/*.md -> "
            "~/.claude/rules/common (non-destructive, no prune)"
        ),
    },
    {
        "kind": "agents",
        "repo_rel": "agents",
        "live_rels": [".claude/agents"],
        "catalog_scripts": ["scripts/sync-from-live.ps1"],
        "direction": "live-to-repo ($Map)",
        "basis": "scripts/sync-from-live.ps1 $Map Label=agents",
    },
    {
        "kind": "commands",
        "repo_rel": "commands",
        "live_rels": [".claude/commands"],
        "catalog_scripts": ["scripts/sync-from-live.ps1"],
        "direction": "live-to-repo ($Map)",
        "basis": "scripts/sync-from-live.ps1 $Map Label=commands",
    },
    {
        "kind": "hooks",
        "repo_rel": "hooks",
        "live_rels": [".claude/hooks"],
        "catalog_scripts": ["scripts/sync-from-live.ps1", "scripts/sync-hooks.ps1"],
        "direction": "live-to-repo ($Map) and repo-to-live (sync-hooks, no prune)",
        "basis": (
            "scripts/sync-from-live.ps1 $Map Label=hooks; "
            "scripts/sync-hooks.ps1 copies repo hooks/ subdirs -> ~/.claude/hooks"
        ),
    },
    {
        "kind": "skills",
        "repo_rel": ".agents/skills",
        "live_rels": [".agents/skills"],
        "catalog_scripts": ["scripts/sync-from-live.ps1"],
        "direction": "live-to-repo ($Map)",
        "basis": (
            "scripts/sync-from-live.ps1 $Map Label=skills: "
            "~/.agents/skills <-> repo .agents/skills"
        ),
    },
    {
        "kind": "skills-compat",
        "repo_rel": "skills",
        "live_rels": [".agents/skills"],
        "catalog_scripts": ["scripts/sync-skills.ps1"],
        "direction": "repo-to-live",
        "basis": (
            "scripts/sync-skills.ps1 copies skill dirs under repo skills/ "
            "(those containing SKILL.md) onto ~/.agents/skills"
        ),
    },
    {
        "kind": "skills-claude-only",
        "repo_rel": "skills-claude-only",
        "live_rels": [".agents/skills"],
        "catalog_scripts": ["scripts/sync-skills.ps1"],
        "direction": "repo-to-live (optional -IncludeClaudeOnly)",
        "basis": (
            "scripts/sync-skills.ps1 -IncludeClaudeOnly adds "
            "repo skills-claude-only/ as a source onto ~/.agents/skills"
        ),
    },
]

LOOSE_FILES: list[dict] = [
    {
        "kind": "loose-codexmon",
        "repo_rel": "tools/monitor/codexmon.ps1",
        "live_rel": ".local/bin/codexmon.ps1",
        "catalog_scripts": ["scripts/sync-from-live.ps1"],
        "basis": "scripts/sync-from-live.ps1 $LooseFiles",
    }
]

# Repo harness trees that exist on this worktree but are not in AUD-0018 $Map.
UNMAPPED_REPO_RELS: list[str] = ["workflows"]


def script_presence(repo: Path) -> dict[str, bool]:
    names = [
        "scripts/sync-rules.ps1",
        "scripts/sync-from-live.ps1",
        "scripts/sync-skills.ps1",
        "scripts/sync-hooks.ps1",
        "command-center/audit/AUD-0018-deploy-script-semantics.json",
    ]
    return {n: (repo / n).is_file() for n in names}


def kind_roots(repo: Path, live_home: Path, fixture: dict | None = None) -> list[dict]:
    """Resolve repo and live directories for each map entry.

    fixture, when set, is {repo: Path, live_home: Path} used instead of host.
    """
    r = Path(fixture["repo"]) if fixture else repo
    h = Path(fixture["live_home"]) if fixture else live_home
    rows = []
    for ent in ENTRIES:
        repo_dir = r / ent["repo_rel"]
        live_dirs = [h / rel for rel in ent["live_rels"]]
        rows.append(
            {
                **ent,
                "repo_dir": str(repo_dir),
                "repo_dir_exists": repo_dir.is_dir(),
                "live_dirs": [
                    {"path": str(p), "exists": p.is_dir()} for p in live_dirs
                ],
            }
        )
    return rows
