"""Estate fixture trees for IMP-0048 layout fingerprints."""
from __future__ import annotations

import sys
from pathlib import Path
import json as sj


try:
    from .layout_fingerprints import (
        COPIED_SKILLS,
        PER_PROJECT_MCP,
        PRE_DISPATCH_HOOKS,
        ROOT_DISABLED_MCP,
    )
except ImportError:  # script / sys.path=tools/plugin
    from layout_fingerprints import (
        COPIED_SKILLS,
        PER_PROJECT_MCP,
        PRE_DISPATCH_HOOKS,
        ROOT_DISABLED_MCP,
    )


def write_bytes(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, obj: object) -> None:
    write_bytes(path, sj.dumps(obj, indent=2, sort_keys=True) + "\n")


def _base(root: Path) -> Path:
    root = Path(root)
    (root / "home" / ".claude").mkdir(parents=True, exist_ok=True)
    (root / "project").mkdir(parents=True, exist_ok=True)
    return root


def build_copied_skills(root: Path) -> Path:
    """Pre-marketplace: skills copied into ~/.claude/skills, no marketplace."""
    root = _base(root)
    write_bytes(
        root / "home" / ".claude" / "skills" / "skill.council" / "SKILL.md",
        "# council\nCopied into the live skills tree before marketplace mounts.\n",
    )
    write_json(root / "home" / ".claude.json", {"theme": "dark"})
    write_json(root / "home" / ".claude" / "settings.json", {"model": "opus"})
    return root


def build_mcp_json(root: Path) -> Path:
    """Per-project .mcp.json holds the live mcpServers map."""
    root = _base(root)
    write_json(
        root / "project" / ".mcp.json",
        {"mcpServers": {"fs": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem"]}}},
    )
    write_json(root / "home" / ".claude.json", {"numStartups": 3})
    write_json(
        root / "home" / ".claude" / "hooks" / "_dispatch" / "manifest.json",
        {"hooks": ["session-start"]},
    )
    return root


def build_root_disabled(root: Path) -> Path:
    """disabledMcpServers at ~/.claude.json ROOT (inert on this estate)."""
    root = _base(root)
    write_json(
        root / "home" / ".claude.json",
        {"disabledMcpServers": ["legacy-server"], "numStartups": 1},
    )
    write_json(
        root / "home" / ".claude" / "hooks" / "_dispatch" / "manifest.json",
        {"hooks": ["session-start"]},
    )
    return root


def build_pre_dispatch(root: Path) -> Path:
    """Standalone hook files, no hooks/_dispatch/manifest.json."""
    root = _base(root)
    write_json(
        root / "home" / ".claude" / "hooks" / "pre-tool.json",
        {"type": "command", "command": "python3 hooks/pre-tool.py"},
    )
    write_json(root / "home" / ".claude.json", {"numStartups": 2})
    write_json(root / "home" / ".claude" / "settings.json", {"model": "opus"})
    return root


def build_current(root: Path) -> Path:
    """Current layout: must match zero legacy fingerprints."""
    root = _base(root)
    write_json(
        root / "home" / ".claude.json",
        {
            "projects": {
                "/tmp/ast-integrate": {"disabledMcpServers": ["opt-out-here"]}
            }
        },
    )
    write_json(
        root / "home" / ".claude" / "settings.json",
        {"enabledPlugins": {"ast-integrate@local-market": True}},
    )
    write_bytes(
        root / "home" / ".claude" / "skills" / "skill.council" / "SKILL.md",
        "# council\nDeployed from marketplace; not a pre-marketplace copy.\n",
    )
    write_json(
        root / "home" / ".claude" / "hooks" / "_dispatch" / "manifest.json",
        {"hooks": ["pre-tool", "session-start"]},
    )
    write_json(
        root / "home" / ".claude" / "hooks" / "pre-tool.json",
        {"type": "command", "command": "python3 hooks/pre-tool.py"},
    )
    write_json(
        root / "project" / ".claude-plugin" / "marketplace.json",
        {"name": "local-market", "plugins": [{"name": "ast-integrate", "source": "./"}]},
    )
    write_json(
        root / "project" / ".claude-plugin" / "plugin.json",
        {"name": "ast-integrate", "version": "0.0.0"},
    )
    write_json(root / "project" / ".mcp.json", {"note": "stub leftover, not live"})
    write_json(
        root / "home" / ".mcp.json",
        {"mcpServers": {"wrong-file": {"command": "echo"}}},
    )
    return root


def build_hybrid_copied_and_root_disabled(root: Path) -> Path:
    """Reviewer hybrid: two fingerprints, must be AMBIGUOUS."""
    root = _base(root)
    write_bytes(
        root / "home" / ".claude" / "skills" / "skill.council" / "SKILL.md",
        "# council\nCopied skills plus root-scoped disable map.\n",
    )
    write_json(
        root / "home" / ".claude.json",
        {"disabledMcpServers": ["hybrid-server"]},
    )
    write_json(root / "home" / ".claude" / "settings.json", {"model": "opus"})
    return root


def build_marker_only_claude_json(root: Path) -> Path:
    """Shared marker ~/.claude.json, live key is per-project (current)."""
    root = _base(root)
    write_json(
        root / "home" / ".claude.json",
        {"projects": {"/tmp/p": {"disabledMcpServers": ["only-here"]}}},
    )
    write_json(
        root / "home" / ".claude" / "hooks" / "_dispatch" / "manifest.json",
        {"hooks": ["session-start"]},
    )
    return root


def build_marker_only_skills(root: Path) -> Path:
    """SKILL.md exists but marketplace + enabledPlugins say current."""
    root = _base(root)
    write_bytes(
        root / "home" / ".claude" / "skills" / "skill.council" / "SKILL.md",
        "# council\n",
    )
    write_json(
        root / "home" / ".claude" / "settings.json",
        {"enabledPlugins": {"ast-integrate@local-market": True}},
    )
    write_json(
        root / "project" / ".claude-plugin" / "marketplace.json",
        {"name": "local-market", "plugins": []},
    )
    write_json(root / "home" / ".claude.json", {"numStartups": 1})
    write_json(
        root / "home" / ".claude" / "hooks" / "_dispatch" / "manifest.json",
        {"hooks": ["session-start"]},
    )
    return root


def build_marker_only_mcp(root: Path) -> Path:
    """project/.mcp.json exists without a live mcpServers map."""
    root = _base(root)
    write_json(root / "project" / ".mcp.json", {})
    write_json(root / "home" / ".claude.json", {"numStartups": 1})
    write_json(
        root / "home" / ".claude" / "hooks" / "_dispatch" / "manifest.json",
        {"hooks": ["session-start"]},
    )
    return root


def build_home_mcp_wrong_file(root: Path) -> Path:
    """Right key, wrong file: mcpServers in home/.mcp.json only."""
    root = _base(root)
    write_json(
        root / "home" / ".mcp.json",
        {"mcpServers": {"wrong-file": {"command": "echo"}}},
    )
    write_json(root / "home" / ".claude.json", {"numStartups": 1})
    write_json(
        root / "home" / ".claude" / "hooks" / "_dispatch" / "manifest.json",
        {"hooks": ["session-start"]},
    )
    return root


def build_marker_only_hooks(root: Path) -> Path:
    """Hook files exist AND dispatch manifest (current, not pre-dispatch)."""
    root = _base(root)
    write_json(
        root / "home" / ".claude" / "hooks" / "pre-tool.json",
        {"type": "command"},
    )
    write_json(
        root / "home" / ".claude" / "hooks" / "_dispatch" / "manifest.json",
        {"hooks": ["pre-tool"]},
    )
    write_json(root / "home" / ".claude.json", {"numStartups": 1})
    return root


def build_version_spoof_copied_skills(root: Path) -> Path:
    """Legacy copied-skills tree that claims layoutVersion=current."""
    root = build_copied_skills(root)
    write_json(
        root / "home" / ".claude.json",
        {"layoutVersion": "current", "pluginVersion": "9.9.9", "theme": "dark"},
    )
    return root


HISTORICAL_BUILDERS = {
    COPIED_SKILLS: build_copied_skills,
    PER_PROJECT_MCP: build_mcp_json,
    ROOT_DISABLED_MCP: build_root_disabled,
    PRE_DISPATCH_HOOKS: build_pre_dispatch,
}


def materialize_all(dest: Path) -> dict[str, Path]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    mapping = {
        "copied-skills": build_copied_skills,
        "mcp-json": build_mcp_json,
        "root-disabled": build_root_disabled,
        "pre-dispatch": build_pre_dispatch,
        "current": build_current,
        "hybrid-ambiguous": build_hybrid_copied_and_root_disabled,
        "marker-only-claude-json": build_marker_only_claude_json,
        "marker-only-skills": build_marker_only_skills,
        "marker-only-mcp": build_marker_only_mcp,
        "home-mcp-wrong-file": build_home_mcp_wrong_file,
        "marker-only-hooks": build_marker_only_hooks,
        "version-spoof-copied-skills": build_version_spoof_copied_skills,
    }
    for name, builder in mapping.items():
        out[name] = builder(dest / name)
    return out
