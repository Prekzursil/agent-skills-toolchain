"""Reconstructed installer-action inventory for REL-0002.

B07's production installer inventory, command-center/ROLLBACK-MANIFEST.md,
and _USER-PROMPTS.md are absent on this worktree. Rows below are the six
catalog-named mutating surfaces plus the on-tree plugin state journal
from tools/plugin/{install,placement,state,census}.py.
"""
from __future__ import annotations

from typing import Any

CATALOG_TYPES = (
    "write_file",
    "register_hook",
    "add_mcp_entry",
    "edit_settings_key",
    "create_scheduled_task",
    "seed_cache",
)

ON_TREE = [
    "tools/plugin/install.py",
    "tools/plugin/placement.py",
    "tools/plugin/rollback_transaction.py",
    "tools/plugin/census.py",
    "tools/plugin/state.py",
]


def _action(
    *,
    id: str,
    action_type: str,
    target: str,
    capture_preexisting: bool,
    creates: list[str],
    inverse_kind: str,
    completeness: str,
    removes: bool,
    post_inverse_invariant: str,
    residue: str | None = None,
) -> dict[str, Any]:
    inverse: dict[str, Any] = {
        "kind": inverse_kind,
        "target": creates[0],
        "completeness": completeness,
        "removes": removes,
    }
    if residue is not None:
        inverse["residue"] = residue
    return {
        "id": id,
        "action_type": action_type,
        "target": target,
        "capture_preexisting": capture_preexisting,
        "creates": list(creates),
        "post_inverse_invariant": post_inverse_invariant,
        "inverse": inverse,
    }


def build_inventory() -> dict[str, Any]:
    actions = [
        _action(
            id="A-write-plugin-file",
            action_type="write_file",
            target="plugins/demo-plugin/plugin.py",
            capture_preexisting=False,
            creates=["plugins/demo-plugin/plugin.py"],
            inverse_kind="delete_path",
            completeness="total",
            removes=True,
            post_inverse_invariant=(
                "plugins/demo-plugin/plugin.py is absent and no path outside "
                "this action's creates list was unlinked"
            ),
        ),
        _action(
            id="A-register-hook",
            action_type="register_hook",
            target="hooks.json#SessionStart:demo-plugin",
            capture_preexisting=True,
            creates=["hooks.json#SessionStart:demo-plugin"],
            inverse_kind="unregister_hook",
            completeness="partial",
            removes=True,
            residue=(
                "other hook entries already in hooks.json remain byte-identical"
            ),
            post_inverse_invariant=(
                "the SessionStart:demo-plugin entry is gone; pre-install hook "
                "entries are still present"
            ),
        ),
        _action(
            id="A-add-mcp",
            action_type="add_mcp_entry",
            target=".mcp.json#mcpServers.demo-plugin",
            capture_preexisting=True,
            creates=[".mcp.json#mcpServers.demo-plugin"],
            inverse_kind="remove_mcp_entry",
            completeness="partial",
            removes=True,
            residue="other mcpServers keys in .mcp.json remain",
            post_inverse_invariant=(
                "mcpServers.demo-plugin is absent; servers that pre-dated "
                "install remain"
            ),
        ),
        _action(
            id="A-edit-settings",
            action_type="edit_settings_key",
            target=".claude/settings.json#enabledPlugins.demo-plugin",
            capture_preexisting=True,
            creates=[".claude/settings.json#enabledPlugins.demo-plugin"],
            inverse_kind="restore_preimage",
            completeness="partial",
            removes=True,
            residue=(
                "sibling keys in .claude/settings.json, including owner theme "
                "and other enabledPlugins, remain"
            ),
            post_inverse_invariant=(
                "enabledPlugins.demo-plugin is gone because the installer "
                "created it; owner settings that pre-dated install remain"
            ),
        ),
        _action(
            id="A-scheduled-task",
            action_type="create_scheduled_task",
            target="systemd/user/demo-plugin.timer",
            capture_preexisting=False,
            creates=["systemd/user/demo-plugin.timer"],
            inverse_kind="delete_scheduled_task",
            completeness="total",
            removes=True,
            post_inverse_invariant=(
                "the demo-plugin.timer unit the installer created is removed; "
                "no other user timer was touched"
            ),
        ),
        _action(
            id="A-seed-cache",
            action_type="seed_cache",
            target="cache/demo-plugin/seed.json",
            capture_preexisting=False,
            creates=["cache/demo-plugin/seed.json"],
            inverse_kind="purge_seeded_cache",
            completeness="total",
            removes=True,
            post_inverse_invariant=(
                "only the seeded cache/demo-plugin/seed.json blob is purged"
            ),
        ),
        _action(
            id="A-state-journal",
            action_type="write_state_journal",
            target=".plugin-state.json#packages.demo-plugin",
            capture_preexisting=True,
            creates=[".plugin-state.json#packages.demo-plugin"],
            inverse_kind="remove_state_record",
            completeness="partial",
            removes=True,
            residue="records for other packages in .plugin-state.json remain",
            post_inverse_invariant=(
                "the demo-plugin package record is gone; other package records "
                "that pre-dated this install remain"
            ),
        ),
    ]
    creation = []
    seen = set()
    for action in actions:
        for item in action["creates"]:
            if item not in seen:
                seen.add(item)
                creation.append(item)
    predates = [
        "skills/user-authored/my-skill.md",
        "commands/user-hello.md",
        ".claude/settings.json#theme",
        "hooks.json#UserPromptSubmit:owner-hook",
    ]
    return {
        "contract_id": "REL-0002-rollback",
        "schema_version": 1,
        "recorded_creation_set": creation,
        "predated_install_set": predates,
        "actions": actions,
        "inventory_source": {
            "b07_artifact": "ABSENT",
            "rollback_manifest": "ABSENT",
            "user_prompts": "ABSENT",
            "on_tree": list(ON_TREE),
            "catalog_named_action_types": list(CATALOG_TYPES),
        },
    }


def catalog_types_covered(doc: dict[str, Any]) -> list[str]:
    present = {a["action_type"] for a in doc["actions"]}
    return [t for t in CATALOG_TYPES if t in present]
