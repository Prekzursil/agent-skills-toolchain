#!/usr/bin/env python3
"""Disclosed synthetic repo/live trees for ADV-0017.

These are not the Windows live estate. They encode:
  * EOL-only pair (CRLF vs LF, same lines)
  * catalog-pinned live-larger names with live-only lines
  * repo-superset pairs
  * BOTH-UNIQUE pairs (unique lines on both sides) so a one-directional
    sync in EITHER direction would destroy content
  * identical controls
across rules/, hooks/, skills/, agents/, commands/, mcp/.
"""
from __future__ import annotations

from pathlib import Path

from audit_common import CATALOG_PIN_LIVE_LARGER, FIXTURE_LIVE, FIXTURE_REPO

EOL_PATH = "rules/common/hooks.md"
IDENTICAL_PATHS = (
    "rules/common/agents.md",
    "agents/default.md",
)
LIVE_SUPERSET_PATHS = CATALOG_PIN_LIVE_LARGER + ("skills/skill-beta.md",)
REPO_SUPERSET_PATHS = (
    "rules/common/ci-hygiene.md",
    "rules/common/windows-shell.md",
    "skills/skill-alpha.md",
    "mcp/mcp.json",
)
BOTH_UNIQUE_LIVE_AHEAD = "rules/project/both-unique-live-ahead.md"
BOTH_UNIQUE_REPO_AHEAD = "rules/project/both-unique-repo-ahead.md"
BOTH_UNIQUE_HOOKS = "hooks/_dispatch/manifest.json"
BOTH_UNIQUE_CMD = "commands/sync-status.md"


def _write(path: Path, body: str, *, crlf: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = body if body.endswith("\n") else body + "\n"
    if crlf:
        data = text.replace("\n", "\r\n").encode("utf-8")
        path.write_bytes(data)
    else:
        path.write_bytes(text.encode("utf-8"))


def write_fixture_trees() -> dict:
    """Idempotent: same relative paths, same bytes every run."""
    repo, live = FIXTURE_REPO, FIXTURE_LIVE
    for root in (repo, live):
        if root.exists():
            for p in root.rglob("*"):
                if p.is_file():
                    p.unlink()

    ident_agents = "# agents\nidentical body both trees\n"
    _write(repo / "rules/common/agents.md", ident_agents)
    _write(live / "rules/common/agents.md", ident_agents)
    ident_default = "# default agent\nshared identical policy\n"
    _write(repo / "agents/default.md", ident_default)
    _write(live / "agents/default.md", ident_default)

    eol = "# hooks\nsame content; line endings are the only difference\n"
    _write(repo / EOL_PATH, eol, crlf=False)
    _write(live / EOL_PATH, eol, crlf=True)

    owner_shared = (
        "# Owner ops authorization\n"
        "H1. Do not mutate git history.\n"
        "H2. Do not print secrets.\n"
        "H3. Fail closed on missing evidence.\n"
    )
    owner_live = owner_shared + (
        "LIVE-ONLY owner-ops-authorization policy line — fixture, not Windows estate. #1\n"
        "LIVE-ONLY owner-ops-authorization policy line — fixture, not Windows estate. #2\n"
        "LIVE-ONLY owner-ops-authorization policy line — fixture, not Windows estate. #3\n"
        "LIVE-ONLY owner-ops-authorization policy line — fixture, not Windows estate. #4\n"
        "LIVE-ONLY owner-ops-authorization policy line — fixture, not Windows estate. #5\n"
        "LIVE-ONLY owner-ops-authorization policy line — fixture, not Windows estate. #6\n"
        "LIVE-ONLY owner-ops-authorization policy line — fixture, not Windows estate. #7\n"
        "LIVE-ONLY owner-ops-authorization policy line — fixture, not Windows estate. #8\n"
        "LIVE-ONLY owner-ops-authorization policy line — fixture, not Windows estate. #9\n"
        "LIVE-ONLY owner-ops-authorization policy line — fixture, not Windows estate. #10\n"
        "LIVE-ONLY owner-ops-authorization policy line — fixture, not Windows estate. #11\n"
        "LIVE-ONLY owner-ops-authorization policy line — fixture, not Windows estate. #12\n"
        "LIVE-ONLY owner-ops-authorization policy line — fixture, not Windows estate. #13\n"
    )
    _write(repo / "rules/common/owner-ops-authorization.md", owner_shared)
    _write(live / "rules/common/owner-ops-authorization.md", owner_live)

    perf_shared = (
        "# Performance\nPrefer incremental scans.\nAvoid full-tree reread on each probe.\n"
    )
    perf_live = perf_shared + (
        "LIVE-ONLY performance policy line — fixture, not Windows estate. #1\n"
        "LIVE-ONLY performance policy line — fixture, not Windows estate. #2\n"
        "LIVE-ONLY performance policy line — fixture, not Windows estate. #3\n"
    )
    _write(repo / "rules/common/performance.md", perf_shared)
    _write(live / "rules/common/performance.md", perf_live)

    sec_shared = "# Security\nNo wildcard tool grants.\nRe-validate declarations after edit.\n"
    sec_live = sec_shared + (
        "LIVE-ONLY security policy line — fixture, not Windows estate. #1\n"
        "LIVE-ONLY security policy line — fixture, not Windows estate. #2\n"
    )
    _write(repo / "rules/common/security.md", sec_shared)
    _write(live / "rules/common/security.md", sec_live)

    skill_beta_shared = "# skill-beta\nshared skill body\n"
    _write(repo / "skills/skill-beta.md", skill_beta_shared)
    _write(
        live / "skills/skill-beta.md",
        skill_beta_shared + "LIVE-ONLY skill-beta remainder\n",
    )

    ci_live = "# CI hygiene\nRequire both-states controls.\n"
    ci_repo = ci_live + (
        "REPO-ONLY: fail on stub sentinels.\n"
        "REPO-ONLY extra ci-hygiene line\n"
    )
    _write(live / "rules/common/ci-hygiene.md", ci_live)
    _write(repo / "rules/common/ci-hygiene.md", ci_repo)

    win_live = "# windows-shell\nshared powershell notes\n"
    _write(live / "rules/common/windows-shell.md", win_live)
    _write(
        repo / "rules/common/windows-shell.md",
        win_live + "REPO-ONLY windows-shell remainder\n",
    )

    skill_alpha_live = "# skill-alpha\nshared skill body\n"
    _write(live / "skills/skill-alpha.md", skill_alpha_live)
    _write(
        repo / "skills/skill-alpha.md",
        skill_alpha_live + "REPO-ONLY skill-alpha remainder\n",
    )

    mcp_live = '{\n  "servers": ["fs"]\n}\n'
    mcp_repo = '{\n  "servers": ["fs"],\n  "repo_only": true\n}\n'
    _write(live / "mcp/mcp.json", mcp_live)
    _write(repo / "mcp/mcp.json", mcp_repo)

    both_live_ahead_shared = (
        "# both-unique live-ahead\nSHARED line A\nSHARED line B\n"
    )
    _write(
        repo / BOTH_UNIQUE_LIVE_AHEAD,
        both_live_ahead_shared + "REPO-ONLY unique line for both-unique-live-ahead\n",
    )
    _write(
        live / BOTH_UNIQUE_LIVE_AHEAD,
        both_live_ahead_shared
        + "LIVE-ONLY unique line for both-unique-live-ahead #1\n"
        + "LIVE-ONLY unique line for both-unique-live-ahead #2\n"
        + "LIVE-ONLY unique line for both-unique-live-ahead #3\n",
    )

    both_repo_ahead_shared = "# both-unique repo-ahead\nSHARED line C\n"
    _write(
        live / BOTH_UNIQUE_REPO_AHEAD,
        both_repo_ahead_shared + "LIVE-ONLY unique line for both-unique-repo-ahead\n",
    )
    _write(
        repo / BOTH_UNIQUE_REPO_AHEAD,
        both_repo_ahead_shared
        + "REPO-ONLY unique line for both-unique-repo-ahead #1\n"
        + "REPO-ONLY unique line for both-unique-repo-ahead #2\n"
        + "REPO-ONLY unique line for both-unique-repo-ahead #3\n",
    )

    hooks_shared = '{\n  "hooks": ["pre-tool", "post-tool"],\n'
    _write(
        repo / BOTH_UNIQUE_HOOKS,
        hooks_shared + '  "mounts": ["fs"],\n  "repo_only_key": true\n}\n',
    )
    _write(
        live / BOTH_UNIQUE_HOOKS,
        hooks_shared + '  "mounts": ["fs", "mcp-extra"],\n  "live_only_key": true\n}\n',
    )

    cmd_shared = "# sync-status\nmeasurement-only; do not invoke sync\n"
    _write(
        repo / BOTH_UNIQUE_CMD,
        cmd_shared + "REPO-ONLY command note\n",
    )
    _write(
        live / BOTH_UNIQUE_CMD,
        cmd_shared + "LIVE-ONLY command note\n",
    )

    n_repo = sum(1 for p in repo.rglob("*") if p.is_file())
    n_live = sum(1 for p in live.rglob("*") if p.is_file())
    return {
        "repo_root": str(repo),
        "live_root": str(live),
        "repo_files": n_repo,
        "live_files": n_live,
        "eol_path": EOL_PATH,
        "both_unique_paths": [
            BOTH_UNIQUE_LIVE_AHEAD,
            BOTH_UNIQUE_REPO_AHEAD,
            BOTH_UNIQUE_HOOKS,
            BOTH_UNIQUE_CMD,
        ],
        "live_superset_paths": list(LIVE_SUPERSET_PATHS),
        "repo_superset_paths": list(REPO_SUPERSET_PATHS),
        "identical_paths": list(IDENTICAL_PATHS),
        "disclosed_synthetic": True,
        "not_windows_live_estate": True,
    }


def fixture_roots() -> tuple[Path, Path]:
    return FIXTURE_REPO, FIXTURE_LIVE
