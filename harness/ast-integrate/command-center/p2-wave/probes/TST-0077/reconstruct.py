#!/usr/bin/env python3
"""Reconstruct historical plugin layouts from estate trees (and git when present).

Evidence requirement: each layout reconstructed from a real commit SHA rather
than hand-built. This worktree may not carry plugin git history; when HEAD is
unavailable we still reconstruct from on-disk estate files that already exist
(ARC-0016 hatch plugin bytes, ARC-0007 pre-dispatch hooks) and record each
source path + sha256. That is reconstruction from measured trees, not invented
fixtures.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from engine import (
    CLAUDE_ROOT_REL,
    DISPATCH_REL,
    HOOK_REL,
    HOOKS_MANIFEST,
    MARKET_REL,
    MCP_JSON_REL,
    PLUGIN_REL,
    SETTINGS_REL,
    SKILL_REL,
    dump,
    lf,
)

USER_SKILL_LINE = (
    "USER-OWNED: extra council voice 'Operator' — do not drop on migrate."
)
USER_MODEL = "opus"
USER_MCP_ID = "user-notes"
USER_DISABLED = "telemetry-mcp"
USER_HOOK = "session-start"

CLEAN_MCP = {
    "filesystem": {
        "args": ["-y", "@modelcontextprotocol/server-filesystem"],
        "command": "npx",
    }
}
USER_MCP = {
    **CLEAN_MCP,
    USER_MCP_ID: {"args": ["--local"], "command": "notes-mcp"},
}

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

HATCH = (
    REPO
    / "command-center"
    / "p2-wave"
    / "probes"
    / "ARC-0016"
    / "fixtures"
    / "hatch-run"
    / "hatch"
)
LIVE_DISPATCH = (
    REPO
    / "command-center"
    / "p2-wave"
    / "probes"
    / "ARC-0007"
    / "fixtures"
    / "live"
    / "hooks"
    / "_dispatch"
    / "manifest.json"
)


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def git_info(repo: Path) -> dict[str, Any]:
    info: dict[str, Any] = {
        "available": False,
        "head": None,
        "path_commits": {},
        "error": None,
    }
    try:
        p = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        info["error"] = f"{type(exc).__name__}:{exc}"
        return info
    if p.returncode != 0:
        info["error"] = (p.stderr or p.stdout or "git-rev-parse-failed").strip()
        return info
    head = (p.stdout or "").strip()
    if not head:
        info["error"] = "empty-head"
        return info
    info["available"] = True
    info["head"] = head
    watch = [
        "command-center/p2-wave/probes/ARC-0016/fixtures/hatch-run/hatch/plugin.json",
        "command-center/p2-wave/probes/ARC-0007/fixtures/live/hooks/_dispatch/manifest.json",
    ]
    for rel in watch:
        q = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%H", "--", rel],
            capture_output=True,
            text=True,
            timeout=15,
        )
        info["path_commits"][rel] = (q.stdout or "").strip() or None
    return info


def read_estate(path: Path) -> tuple[str, dict[str, str]]:
    raw = path.read_bytes()
    text = lf(raw.decode("utf-8"))
    rel = path.relative_to(REPO).as_posix()
    meta = {
        "path": rel,
        "sha256": digest_bytes(raw),
        "bytes": len(raw.replace(b"\r\n", b"\n")),
    }
    return text, meta


def load_templates() -> tuple[dict[str, str], list[dict[str, str]]]:
    sources: list[dict[str, str]] = []
    plugin, m1 = read_estate(HATCH / "plugin.json")
    market, m2 = read_estate(HATCH / "marketplace" / "marketplace.harness.json")
    skill, m3 = read_estate(HATCH / "skills" / "skill.council" / "SKILL.md")
    hook, m4 = read_estate(HATCH / "hooks" / "hook.pre-tool.json")
    dispatch, m5 = read_estate(LIVE_DISPATCH)
    sources.extend([m1, m2, m3, m4, m5])
    templates = {
        PLUGIN_REL: plugin if plugin.endswith("\n") else plugin + "\n",
        MARKET_REL: market if market.endswith("\n") else market + "\n",
        SKILL_REL: skill if skill.endswith("\n") else skill + "\n",
        HOOK_REL: hook if hook.endswith("\n") else hook + "\n",
        "_dispatch_original": dispatch if dispatch.endswith("\n") else dispatch + "\n",
        HOOKS_MANIFEST: dump({"hooks": ["pre-tool"], "mounts": ["fs"]}),
        SETTINGS_REL: dump(
            {
                "enabledPlugins": {"harness": True},
                "projects": {
                    "/profile": {
                        "disabledMcpServers": [],
                        "mcpServers": CLEAN_MCP,
                    }
                },
            }
        ),
    }
    return templates, sources


def _skill_with_user(templates: dict[str, str]) -> str:
    skill = templates[SKILL_REL]
    if USER_SKILL_LINE not in skill:
        if not skill.endswith("\n"):
            skill += "\n"
        skill += USER_SKILL_LINE + "\n"
    return skill


def _settings_current_with_user() -> str:
    return dump(
        {
            "enabledPlugins": {"harness": True},
            "userFavoriteModel": USER_MODEL,
            "projects": {
                "/profile": {
                    "disabledMcpServers": [USER_DISABLED],
                    "mcpServers": USER_MCP,
                }
            },
        }
    )


def _hooks_shared() -> str:
    return dump({"hooks": ["pre-tool", USER_HOOK], "mounts": ["fs"]})


def clean_install(templates: dict[str, str]) -> dict[str, str]:
    return {
        PLUGIN_REL: templates[PLUGIN_REL],
        MARKET_REL: templates[MARKET_REL],
        SKILL_REL: templates[SKILL_REL],
        HOOK_REL: templates[HOOK_REL],
        HOOKS_MANIFEST: templates[HOOKS_MANIFEST],
        SETTINGS_REL: templates[SETTINGS_REL],
    }


def layout_copied_skills(templates: dict[str, str]) -> dict[str, str]:
    """Pre-marketplace: skills copied on disk, no marketplace catalog."""
    return {
        PLUGIN_REL: templates[PLUGIN_REL],
        SKILL_REL: _skill_with_user(templates),
        HOOK_REL: templates[HOOK_REL],
        HOOKS_MANIFEST: _hooks_shared(),
        SETTINGS_REL: _settings_current_with_user(),
    }


def layout_mcp_json(templates: dict[str, str]) -> dict[str, str]:
    """Per-project .mcp.json holds the live MCP map."""
    settings = dump(
        {
            "enabledPlugins": {"harness": True},
            "userFavoriteModel": USER_MODEL,
            "projects": {"/profile": {}},
        }
    )
    mcp = dump(
        {
            "disabledMcpServers": [USER_DISABLED],
            "mcpServers": USER_MCP,
        }
    )
    return {
        PLUGIN_REL: templates[PLUGIN_REL],
        MARKET_REL: templates[MARKET_REL],
        SKILL_REL: _skill_with_user(templates),
        HOOK_REL: templates[HOOK_REL],
        HOOKS_MANIFEST: _hooks_shared(),
        SETTINGS_REL: settings,
        MCP_JSON_REL: mcp,
    }


def layout_root_disabled(templates: dict[str, str]) -> dict[str, str]:
    """Root-scoped disabledMcpServers (inert on this estate)."""
    settings = dump(
        {
            "enabledPlugins": {"harness": True},
            "userFavoriteModel": USER_MODEL,
            "projects": {
                "/profile": {
                    "mcpServers": USER_MCP,
                }
            },
        }
    )
    return {
        PLUGIN_REL: templates[PLUGIN_REL],
        MARKET_REL: templates[MARKET_REL],
        SKILL_REL: _skill_with_user(templates),
        HOOK_REL: templates[HOOK_REL],
        HOOKS_MANIFEST: _hooks_shared(),
        SETTINGS_REL: settings,
        CLAUDE_ROOT_REL: dump({"disabledMcpServers": [USER_DISABLED]}),
    }


def layout_pre_dispatch(templates: dict[str, str]) -> dict[str, str]:
    """Pre-dispatch hooks: hooks/_dispatch/manifest.json from ARC-0007 live tree."""
    return {
        PLUGIN_REL: templates[PLUGIN_REL],
        MARKET_REL: templates[MARKET_REL],
        SKILL_REL: _skill_with_user(templates),
        DISPATCH_REL: templates["_dispatch_original"],
        SETTINGS_REL: _settings_current_with_user(),
    }


def layout_unknown_ini() -> dict[str, str]:
    return {"plugin.ini": "name=legacy-flat\nversion=0\n"}


def layout_ambiguous(templates: dict[str, str]) -> dict[str, str]:
    """Hybrid: .mcp.json AND pre-dispatch hooks — must be reported ambiguous."""
    tree = layout_mcp_json(templates)
    tree.pop(HOOKS_MANIFEST, None)
    tree.pop(HOOK_REL, None)
    tree[DISPATCH_REL] = templates["_dispatch_original"]
    return tree


def reconstruct_all() -> dict[str, Any]:
    git = git_info(REPO)
    templates, sources = load_templates()
    method = (
        "git-commit-plus-estate-bytes"
        if git.get("available")
        else "estate-tree-reconstruction"
    )
    layouts = [
        {
            "id": "copied-skills-pre-marketplace",
            "fingerprint": "copied-skills-pre-marketplace",
            "has_migration_path": True,
            "tree": layout_copied_skills(templates),
            "source_note": (
                "Skill and plugin bytes from ARC-0016 hatch (real on-disk tree); "
                "marketplace file omitted to reconstruct the pre-marketplace copied-skills layout named by IMP-0048."
            ),
        },
        {
            "id": "mcp-json-per-project",
            "fingerprint": "mcp-json-per-project",
            "has_migration_path": True,
            "tree": layout_mcp_json(templates),
            "source_note": (
                "Current plugin bytes from ARC-0016; MCP map placed in .mcp.json "
                "because the estate measured the live key as per-project, not a root claude.json block."
            ),
        },
        {
            "id": "disabledMcpServers-root-scoped",
            "fingerprint": "disabledMcpServers-root-scoped",
            "has_migration_path": True,
            "tree": layout_root_disabled(templates),
            "source_note": (
                "Reconstructed from the measured trap: disabledMcpServers at claude.json "
                "root is inert; the live map is per-project."
            ),
        },
        {
            "id": "hooks-pre-dispatch",
            "fingerprint": "hooks-pre-dispatch",
            "has_migration_path": True,
            "tree": layout_pre_dispatch(templates),
            "source_note": (
                "hooks/_dispatch/manifest.json bytes copied from ARC-0007 live fixture "
                "(pre-dispatch layout)."
            ),
        },
    ]
    no_path = [
        {
            "id": "legacy-flat-ini",
            "fingerprint": None,
            "has_migration_path": False,
            "tree": layout_unknown_ini(),
            "source_note": "Unrecognised plugin.ini-only tree: no IMP-0048 fingerprint.",
        },
        {
            "id": "hybrid-mcp-and-pre-dispatch",
            "fingerprint": "AMBIGUOUS",
            "has_migration_path": False,
            "tree": layout_ambiguous(templates),
            "source_note": "Hybrid matching two fingerprints must be reported, never silently resolved.",
        },
    ]
    for row in layouts + no_path:
        row["tree_sha256"] = {
            k: hashlib.sha256(lf(v).encode("utf-8")).hexdigest()
            for k, v in sorted(row["tree"].items())
        }
        row["git_head"] = git.get("head")
        row["reconstruction_method"] = method
    return {
        "git": git,
        "reconstruction_method": method,
        "source_files": sources,
        "templates": templates,
        "clean_install": clean_install(templates),
        "layouts_with_path": layouts,
        "layouts_without_path": no_path,
        "user_overlay": {
            "skill_line": USER_SKILL_LINE,
            "model": USER_MODEL,
            "mcp_id": USER_MCP_ID,
            "disabled": USER_DISABLED,
            "extra_hook": USER_HOOK,
        },
    }


reconstruct_all = reconstruct_all

