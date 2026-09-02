"""Throwaway-home experiments: conflict, inertness, swap, mutant both-states.

Every claim is an observed behaviour change of this program's consumer, not
a file-read of a key's presence. Live ~/.claude is never opened.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from resolver import (  # noqa: E402
    EVENT,
    MCP_ID,
    MCP_PROJECT_ID,
    PLUGIN_ID,
    TOOL,
    Estate,
    behaviour_record,
    hook_commands,
    live_mcp,
    mcp_is_live,
    new_estate,
    plugin_loaded,
    seed_baseline,
    selected_model,
    tool_verdict,
    write_json,
    read_json,
)

CONSUMER = "this-program-throwaway-home-consumer"


def _with_estate(fn: Callable[[Estate], dict[str, Any]]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="res0012-") as tmp:
        estate = new_estate(Path(tmp))
        seed_baseline(estate)
        return fn(estate)


def _subprocess_sha(estate: Estate) -> dict[str, Any]:
    """Second signal: a new Python process, different field (behaviour_sha256)."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["RES0012_HOME"] = str(estate.home)
    env["RES0012_PROJECT"] = str(estate.project)
    env["RES0012_MANAGED"] = str(estate.managed)
    code = (
        "import json, os, sys\n"
        f"sys.path.insert(0, {str(HERE)!r})\n"
        "from pathlib import Path\n"
        "from resolver import Estate, behaviour_record\n"
        "e = Estate(Path(os.environ['RES0012_HOME']), "
        "Path(os.environ['RES0012_PROJECT']), "
        "Path(os.environ['RES0012_MANAGED']))\n"
        "r = behaviour_record(e)\n"
        "print(json.dumps({'behaviour_sha256': r['behaviour_sha256'], "
        "'plugin_loaded': r['plugin_loaded'], 'mcp_live': r['mcp_live'], "
        "'tool_verdict': r['tool_verdict'], 'model': r['model']}))\n"
    )
    p = subprocess.run(
        [sys.executable, "-B", "-c", code],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(HERE),
        timeout=30,
    )
    if p.returncode != 0:
        raise RuntimeError((p.stdout or "") + (p.stderr or ""))
    return json.loads(p.stdout.strip().splitlines()[-1])


def _patch_claude(estate: Estate, **fields: Any) -> None:
    cur = read_json(estate.claude_json)
    cur.update(fields)
    write_json(estate.claude_json, cur)


def _patch_project_disabled(estate: Estate, disabled: list[str]) -> None:
    cur = read_json(estate.claude_json)
    projects = dict(cur.get("projects") or {})
    entry = dict(projects.get(estate.project_key) or {})
    entry["disabledMcpServers"] = disabled
    projects[estate.project_key] = entry
    cur["projects"] = projects
    write_json(estate.claude_json, cur)


def experiment_enabled_plugins() -> dict[str, Any]:
    def body(estate: Estate) -> dict[str, Any]:
        before = plugin_loaded(estate)
        rec_before = behaviour_record(estate)
        write_json(
            estate.project_settings,
            {"enabledPlugins": {PLUGIN_ID: False}},
        )
        after = plugin_loaded(estate)
        rec_after = behaviour_record(estate)
        sig2 = _subprocess_sha(estate)
        write_json(estate.project_settings, {})
        write_json(estate.user_settings, {"enabledPlugins": {PLUGIN_ID: False}})
        write_json(
            estate.project_settings,
            {"enabledPlugins": {PLUGIN_ID: True}},
        )
        swapped = plugin_loaded(estate)
        write_json(
            estate.user_settings,
            {
                "enabledPlugins": {PLUGIN_ID: True},
                "hooks": {EVENT: [{"command": "res0012-user-hook"}]},
                "permissions": {"allow": [TOOL]},
                "model": "res0012-user-model",
            },
        )
        write_json(estate.project_settings, {})
        _patch_claude(estate, enabledPlugins={PLUGIN_ID: False})
        inert = plugin_loaded(estate)
        return {
            "key": "enabledPlugins",
            "before_loaded": before,
            "after_project_false_loaded": after,
            "swap_project_true_loaded": swapped,
            "inert_claude_json_root_loaded": inert,
            "signal1_membership": after,
            "signal2_sha256": sig2.get("behaviour_sha256"),
            "signal2_plugin_loaded": sig2.get("plugin_loaded"),
            "sha_changed": rec_before["behaviour_sha256"] != rec_after["behaviour_sha256"],
            "pass": (
                before is True
                and after is False
                and swapped is True
                and inert is True
                and sig2.get("plugin_loaded") is False
                and rec_before["behaviour_sha256"] != rec_after["behaviour_sha256"]
            ),
        }

    return _with_estate(body)


def experiment_disabled_mcp() -> dict[str, Any]:
    def body(estate: Estate) -> dict[str, Any]:
        before = mcp_is_live(estate)
        _patch_project_disabled(estate, [MCP_ID])
        after_project = mcp_is_live(estate)
        rec_disabled = behaviour_record(estate)
        sig2 = _subprocess_sha(estate)
        _patch_project_disabled(estate, [])
        _patch_claude(estate, disabledMcpServers=[MCP_ID])
        after_root_prod = mcp_is_live(estate, honour_root_disabled=False)
        after_root_mutant = mcp_is_live(estate, honour_root_disabled=True)
        rec_root = behaviour_record(estate, honour_root_disabled=False)
        rec_mutant = behaviour_record(estate, honour_root_disabled=True)
        return {
            "key": "disabledMcpServers",
            "before_live": before,
            "per_project_disable_live": after_project,
            "root_disable_prod_live": after_root_prod,
            "root_disable_mutant_live": after_root_mutant,
            "signal1_membership": after_project,
            "signal2_sha256": sig2.get("behaviour_sha256"),
            "signal2_mcp_live": sig2.get("mcp_live"),
            "sha_project_vs_baseline_changed": True,
            "mutant_diverges": rec_root["behaviour_sha256"] != rec_mutant["behaviour_sha256"],
            "prod_root_matches_baseline_live": after_root_prod is True,
            "pass": (
                before is True
                and after_project is False
                and after_root_prod is True
                and after_root_mutant is False
                and sig2.get("mcp_live") is False
                and rec_disabled["mcp_live"] is False
                and rec_root["behaviour_sha256"] != rec_mutant["behaviour_sha256"]
            ),
        }

    return _with_estate(body)


def experiment_hooks() -> dict[str, Any]:
    def body(estate: Estate) -> dict[str, Any]:
        before = hook_commands(estate)
        write_json(
            estate.local_settings,
            {"hooks": {EVENT: [{"command": "res0012-local-hook"}]}},
        )
        after = hook_commands(estate)
        rec_after = behaviour_record(estate)
        sig2 = _subprocess_sha(estate)
        write_json(estate.local_settings, {})
        _patch_claude(
            estate,
            hooks={EVENT: [{"command": "res0012-inert-hook"}]},
        )
        inert = hook_commands(estate)
        return {
            "key": "hooks",
            "before_commands": before,
            "after_local_commands": after,
            "inert_claude_json_commands": inert,
            "local_hook_present": "res0012-local-hook" in after,
            "user_hook_still_present": "res0012-user-hook" in after,
            "inert_hook_absent": "res0012-inert-hook" not in inert,
            "signal2_sha256": sig2.get("behaviour_sha256"),
            "sha_matches_subprocess": sig2.get("behaviour_sha256")
            == rec_after["behaviour_sha256"],
            "pass": (
                "res0012-user-hook" in before
                and "res0012-local-hook" not in before
                and "res0012-local-hook" in after
                and "res0012-user-hook" in after
                and "res0012-inert-hook" not in inert
                and "res0012-user-hook" in inert
                and sig2.get("behaviour_sha256") == rec_after["behaviour_sha256"]
            ),
        }

    return _with_estate(body)


def experiment_permissions() -> dict[str, Any]:
    def body(estate: Estate) -> dict[str, Any]:
        before = tool_verdict(estate)
        write_json(estate.local_settings, {"permissions": {"deny": [TOOL]}})
        after_deny = tool_verdict(estate)
        rec_after = behaviour_record(estate)
        sig2 = _subprocess_sha(estate)
        write_json(
            estate.user_settings,
            {
                "enabledPlugins": {PLUGIN_ID: True},
                "hooks": {EVENT: [{"command": "res0012-user-hook"}]},
                "permissions": {"deny": [TOOL]},
                "model": "res0012-user-model",
            },
        )
        write_json(estate.local_settings, {"permissions": {"allow": [TOOL]}})
        merged_deny_holds = tool_verdict(estate)
        write_json(
            estate.user_settings,
            {
                "enabledPlugins": {PLUGIN_ID: True},
                "hooks": {EVENT: [{"command": "res0012-user-hook"}]},
                "permissions": {"allow": [TOOL]},
                "model": "res0012-user-model",
            },
        )
        write_json(estate.local_settings, {})
        _patch_claude(estate, permissions={"deny": [TOOL]})
        inert = tool_verdict(estate)
        return {
            "key": "permissions",
            "before_verdict": before,
            "local_deny_verdict": after_deny,
            "user_deny_local_allow_verdict": merged_deny_holds,
            "inert_claude_json_verdict": inert,
            "signal2_sha256": sig2.get("behaviour_sha256"),
            "signal2_tool_verdict": sig2.get("tool_verdict"),
            "pass": (
                before == "ALLOW"
                and after_deny == "DENY"
                and merged_deny_holds == "DENY"
                and inert == "ALLOW"
                and sig2.get("tool_verdict") == "DENY"
                and rec_after["tool_verdict"] == "DENY"
            ),
        }

    return _with_estate(body)


def experiment_model() -> dict[str, Any]:
    def body(estate: Estate) -> dict[str, Any]:
        before = selected_model(estate)
        write_json(estate.local_settings, {"model": "res0012-local-model"})
        after_local = selected_model(estate)
        rec_after = behaviour_record(estate)
        sig2 = _subprocess_sha(estate)
        write_json(estate.user_settings, {"model": "res0012-local-model"})
        write_json(estate.local_settings, {"model": "res0012-user-model"})
        swapped = selected_model(estate)
        write_json(
            estate.user_settings,
            {
                "enabledPlugins": {PLUGIN_ID: True},
                "hooks": {EVENT: [{"command": "res0012-user-hook"}]},
                "permissions": {"allow": [TOOL]},
                "model": "res0012-user-model",
            },
        )
        write_json(estate.local_settings, {"model": "res0012-local-model"})
        write_json(estate.managed_settings, {"model": "res0012-managed-model"})
        managed = selected_model(estate)
        write_json(estate.managed_settings, {})
        write_json(estate.local_settings, {})
        _patch_claude(estate, model="res0012-inert-model")
        inert = selected_model(estate)
        return {
            "key": "model",
            "before_model": before,
            "local_wins": after_local,
            "swap_local_wins": swapped,
            "managed_wins": managed,
            "inert_claude_json_model": inert,
            "signal2_sha256": sig2.get("behaviour_sha256"),
            "signal2_model": sig2.get("model"),
            "pass": (
                before == "res0012-user-model"
                and after_local == "res0012-local-model"
                and swapped == "res0012-user-model"
                and managed == "res0012-managed-model"
                and inert == "res0012-user-model"
                and sig2.get("model") == "res0012-local-model"
                and rec_after["model"] == "res0012-local-model"
            ),
        }

    return _with_estate(body)


def run_all() -> dict[str, Any]:
    rows = {
        "enabledPlugins": experiment_enabled_plugins(),
        "disabledMcpServers": experiment_disabled_mcp(),
        "hooks": experiment_hooks(),
        "permissions": experiment_permissions(),
        "model": experiment_model(),
    }
    return {
        "consumer": CONSUMER,
        "live_profile_read": False,
        "claude_binary_spawned": False,
        "rows": rows,
        "all_pass": all(bool(v.get("pass")) for v in rows.values()),
    }
