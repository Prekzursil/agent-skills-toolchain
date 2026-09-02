#!/usr/bin/env python3
"""Five live-tree estate used to prove A3 adopt-in-place packaging.

The Windows live estate (C:/Users/Prekzursil/...) is absent on this host.
Skill, hook, and rule bytes come from the real ARC-0010 generator on this
worktree. Commands, owner overlay, user-data, and MCP enable/disable state
are fixture-only and disclosed as such.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ARC10 = HERE.parent / "ARC-0010"
sys.path.insert(0, str(ARC10))
import generator as G  # noqa: E402

SKILL_REPO = "skills-repo/skill.council/SKILL.md"
SKILL_LIVE = "skills-live/skill.council/SKILL.md"
OWNER_NOTE = "skills-live/skill.council/owner-note.md"
HOOK = "hooks/hook.pre-tool.json"
RULE = "rules/rule.no-secrets.md"
COMMAND = "commands/cmd.catalog-class.md"
USER_DATA = "user-data/session-notes.md"
MCP_STATE = "mcp-state.json"

PRESERVE_RELS = (OWNER_NOTE, USER_DATA, MCP_STATE)
CLAIMED_LIVE_RELS = (SKILL_LIVE, HOOK, RULE, COMMAND)
SOURCE_ONLY_RELS = (SKILL_REPO,)

PKG_SKILL = "pkg.skill.council"
PKG_HOOK = "pkg.hook.pre-tool"
PKG_RULE = "pkg.rule.no-secrets"
PKG_CMD = "pkg.cmd.catalog-class"

CLAIM_MAP = {
    SKILL_LIVE: PKG_SKILL,
    HOOK: PKG_HOOK,
    RULE: PKG_RULE,
    COMMAND: PKG_CMD,
}

SOURCE_MAP = {SKILL_REPO: PKG_SKILL}

LIVE_TREES = (
    {
        "id": "skills-repo",
        "path": "skills-repo/",
        "role": "publishable-source",
        "becomes_package": True,
        "package_ids": [PKG_SKILL],
        "boundary": "one package per skill directory; source bytes are published, not uninstalled from live",
    },
    {
        "id": "skills-live",
        "path": "skills-live/",
        "role": "already-deployed-unpackaged",
        "becomes_package": True,
        "package_ids": [PKG_SKILL],
        "boundary": "SKILL.md is claimed in place; sibling owner-authored files stay unclaimed overlays",
    },
    {
        "id": "hooks",
        "path": "hooks/",
        "role": "already-deployed-unpackaged",
        "becomes_package": True,
        "package_ids": [PKG_HOOK],
        "boundary": "one package per hook json file",
    },
    {
        "id": "rules",
        "path": "rules/",
        "role": "already-deployed-unpackaged",
        "becomes_package": True,
        "package_ids": [PKG_RULE],
        "boundary": "one package per rule markdown file",
    },
    {
        "id": "commands",
        "path": "commands/",
        "role": "already-deployed-unpackaged",
        "becomes_package": True,
        "package_ids": [PKG_CMD],
        "boundary": "one package per command markdown file",
    },
)

COMMAND_BODY = (
    "# cmd.catalog-class\n\n"
    "Discover catalog-class blueprints. Unpackaged live command content;\n"
    "adopted in place as pkg.cmd.catalog-class without a wipe-and-reinstall.\n"
)

OWNER_NOTE_BODY = (
    "# Owner overlay\n\n"
    "Hand-authored note beside the adopted skill. The package must not claim\n"
    "this file. Uninstall must leave it on disk.\n"
)

USER_DATA_BODY = (
    "user session notes (not package content)\n"
    "LIVE-ONLY user data that uninstall must preserve\n"
)

MCP_STATE_OBJ = {
    "schema": "a3-mcp-enablement/v1",
    "curated": True,
    "must_survive_uninstall": True,
    "servers": {
        "hacktricks-mcp-server": {
            "enabled": False,
            "reason": "owner-curated disable",
        },
        "cursor": {"enabled": True},
    },
}

UNCLAIM_WHY = {
    SKILL_REPO: (
        "publishable source tree; claiming it as an installed file would make "
        "uninstall delete the repo copy"
    ),
    OWNER_NOTE: "owner-authored overlay beside a claimed skill; not package payload",
    USER_DATA: "user data; uninstall contract forbids destroying it",
    MCP_STATE: (
        "curated MCP enable/disable state; must never be destroyed by package uninstall"
    ),
}

UNCLAIM_CLASS = {
    SKILL_REPO: "source-not-install",
    OWNER_NOTE: "owner-edit",
    USER_DATA: "user-data",
    MCP_STATE: "mcp-enablement",
}

REAL_TREE = "tools/command-center"
REAL_PKG = "pkg.command-center.tools"


def lf_bytes(data: bytes | str) -> bytes:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return data.replace(b"\r\n", b"\n")


def write_file(root: Path, rel: str, data: bytes | str) -> Path:
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(lf_bytes(data))
    return dest


def generated_payload() -> dict[str, bytes]:
    files = G.generate(G.load_default_registry())
    return {
        "skill": files["skills/skill.council/SKILL.md"],
        "hook": files["hooks/hook.pre-tool.json"],
        "rule": files["rules/rule.no-secrets.md"],
    }


def build_estate(root: Path) -> dict[str, Any]:
    """Write the five live trees plus never-claim overlays under root."""
    payload = generated_payload()
    mapping = {
        SKILL_REPO: payload["skill"],
        SKILL_LIVE: payload["skill"],
        OWNER_NOTE: OWNER_NOTE_BODY,
        HOOK: payload["hook"],
        RULE: payload["rule"],
        COMMAND: COMMAND_BODY,
        USER_DATA: USER_DATA_BODY,
        MCP_STATE: json.dumps(MCP_STATE_OBJ, indent=2, sort_keys=True) + "\n",
    }
    for rel, data in mapping.items():
        write_file(root, rel, data)
    meta = {
        "files": sorted(mapping),
        "claimed_live": list(CLAIMED_LIVE_RELS),
        "preserve": list(PRESERVE_RELS),
        "source_only": list(SOURCE_ONLY_RELS),
        "skill_bytes_match": True,
    }
    (root / "estate-meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    return meta
