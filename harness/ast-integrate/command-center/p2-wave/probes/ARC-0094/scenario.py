#!/usr/bin/env python3
"""Scratch estate for ARC-0094 rollback contract probes.

Layout (exclusive partitions):
  version.json, config/, deploy/  — MUST restore from pre-change backup
  mcp/                            — restore curated enable/disable from backup;
                                    extras not in backup are never deleted
  owner/, userdata/, credentials/ — NEVER destroy: no overwrite of live files,
                                    no delete of extras, restore only if missing
"""
from __future__ import annotations

import json
from pathlib import Path

VERSION_REL = "version.json"
CONFIG_REL = "config/harness.json"
DEPLOY_PLUGIN_REL = "deploy/plugin.json"
DEPLOY_HOOK_REL = "deploy/hooks/hook.pre-tool.json"
MCP_REL = "mcp/enable-disable.json"
OWNER_REL = "owner/notes.md"
OWNER_PLANTED_REL = "owner/planted-owner-file.md"
USERDATA_REL = "userdata/session-notes.md"
CRED_REL = "credentials/store.json"

PREVIOUS_VERSION = {
    "package": "harness-plugin",
    "version": "1.4.2",
    "channel": "stable",
}
UPGRADED_VERSION = {
    "package": "harness-plugin",
    "version": "2.0.0",
    "channel": "canary",
}
PREVIOUS_CONFIG = {
    "interpreter": "python3",
    "strict_unknown_fields": True,
    "windows_bare_sh_forbidden": True,
}
UPGRADED_CONFIG = {
    "interpreter": "python3",
    "strict_unknown_fields": False,
    "windows_bare_sh_forbidden": False,
}
PREVIOUS_PLUGIN = {
    "id": "harness-plugin",
    "hooks": ["hook.pre-tool"],
    "generated": True,
}
UPGRADED_PLUGIN = {
    "id": "harness-plugin",
    "hooks": [],
    "generated": True,
    "upgrade_marker": "v2",
}
PREVIOUS_HOOK = {
    "id": "hook.pre-tool",
    "event": "PreToolUse",
    "command": "python3",
    "script": "hooks/pre_tool.py",
}
UPGRADED_HOOK = {
    "id": "hook.pre-tool",
    "event": "PreToolUse",
    "command": "sh",
    "script": "hooks/pre_tool.sh",
}
CURATED_MCP = {
    "scope": "project",
    "servers": {
        "docs": {"enabled": True, "transport": "stdio"},
        "telemetry": {"enabled": False, "transport": "http"},
        "memory": {"enabled": True, "transport": "stdio"},
    },
}
WIPED_MCP = {
    "scope": "project",
    "servers": {
        "docs": {"enabled": True, "transport": "stdio"},
        "telemetry": {"enabled": True, "transport": "http"},
        "memory": {"enabled": True, "transport": "stdio"},
    },
}
OWNER_NOTES = "# owner-authored notes\nkeep this file; rollback must not destroy it.\n"
USER_NOTES = "# user data\nsession-local notes; not a generated projection.\n"
CREDENTIAL_STORE = {
    "kind": "credential-store-placeholder",
    "injected_environment_only": True,
    "entries": [],
    "note": "fixture contains no secrets; probes must never print live keys",
}

PLANTED_OWNER = (
    "# PLANTED owner-authored file\n"
    "A rollback that tree-syncs to the pre-change backup would DELETE this path "
    "because it is absent from the backup. The contract requires that rollback "
    "to FAIL rather than destroy the file.\n"
)


def _dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, (dict, list)):
        path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        path.write_text(str(obj), encoding="utf-8")


def write_previous_tree(root: Path) -> None:
    """Write the N-1 estate that a pre-change backup must capture."""
    _dump(root / VERSION_REL, PREVIOUS_VERSION)
    _dump(root / CONFIG_REL, PREVIOUS_CONFIG)
    _dump(root / DEPLOY_PLUGIN_REL, PREVIOUS_PLUGIN)
    _dump(root / DEPLOY_HOOK_REL, PREVIOUS_HOOK)
    _dump(root / MCP_REL, CURATED_MCP)
    _dump(root / OWNER_REL, OWNER_NOTES)
    _dump(root / USERDATA_REL, USER_NOTES)
    _dump(root / CRED_REL, CREDENTIAL_STORE)


def apply_upgrade(root: Path) -> None:
    """Mutate restore-targets the way a broken upgrade would.

    Wipes curated MCP enable/disable (telemetry flipped on). Leaves
    owner / user-data / credential files in place.
    """
    _dump(root / VERSION_REL, UPGRADED_VERSION)
    _dump(root / CONFIG_REL, UPGRADED_CONFIG)
    _dump(root / DEPLOY_PLUGIN_REL, UPGRADED_PLUGIN)
    _dump(root / DEPLOY_HOOK_REL, UPGRADED_HOOK)
    extra = root / "deploy" / "upgrade-only.json"
    _dump(extra, {"ephemeral": True, "must_vanish_on_rollback": True})
    _dump(root / MCP_REL, WIPED_MCP)


def plant_owner_file(root: Path) -> Path:
    dest = root / OWNER_PLANTED_REL
    _dump(dest, PLANTED_OWNER)
    return dest


# Probe-facing aliases (same functions, stable names).
write_previous_tree = write_previous_tree
apply_upgrade = apply_upgrade
plant_owner_file = plant_owner_file
