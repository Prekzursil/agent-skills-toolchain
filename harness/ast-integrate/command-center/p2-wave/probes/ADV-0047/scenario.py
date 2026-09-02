"""Three-point snapshot differential and post-uninstall behavioural probe."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common import PACKAGE_ID, TASK_ID
from lifecycle import (
    Profile,
    classify_residue,
    install_package,
    launch_host,
    snapshot,
    uninstall_package,
)


def _redact(paths: list[str]) -> list[str]:
    return list(paths)


def run_three_point(tmp: Path) -> dict[str, Any]:
    profile = Profile(tmp / "profile")
    profile.materialize_empty()
    pre = snapshot(profile)
    installed = install_package(profile)
    post_i = snapshot(profile)
    uninstalled = uninstall_package(profile, purge_user_data=False)
    post_u = snapshot(profile)
    classified = classify_residue(pre, post_i, post_u, profile)
    native = uninstalled["native_registry"]
    return {
        "probe": "probe1-snapshot-diff",
        "pre_file_count": len(pre["files"]),
        "post_install_file_count": len(post_i["files"]),
        "post_uninstall_file_count": len(post_u["files"]),
        "install": {"ok": installed["ok"], "owned_prefixes": installed["owned_prefixes"]},
        "uninstall": {
            "ok": uninstalled["ok"],
            "contract": uninstalled["contract"],
            "purge_user_data": uninstalled["purge_user_data"],
            "user_data_deleted": uninstalled["user_data_deleted"],
            "native_registry": native,
        },
        "differential": {
            "install_created_count": classified["install_created_count"],
            "install_created_files": _redact(classified["install_created_files"]),
            "removed_files": _redact(classified["removed_files"]),
            "residue_files": _redact(classified["residue_files"]),
            "intentional_retention": _redact(classified["intentional_retention"]),
            "unintentional_residue": _redact(classified["unintentional_residue"]),
            "privacy_relevant": _redact(classified["privacy_relevant"]),
            "registry_created": classified["registry_created"],
            "registry_residue": classified["registry_residue"],
            "tasks_created": classified["tasks_created"],
            "tasks_residue": classified["tasks_residue"],
            "mcp_created": classified["mcp_created"],
            "mcp_residue": classified["mcp_residue"],
            "user_data_kept": classified["user_data_kept"],
            "user_data_byte_identical": classified["user_data_byte_identical"],
            "user_data_deleted": classified["user_data_deleted"],
            "control_install_created_nonempty": classified["control_install_created_nonempty"],
        },
        "scopes": {
            "files": True,
            "registry_analog": True,
            "scheduled_tasks": True,
            "mcp": True,
            "native_windows_registry": bool(native.get("available")),
        },
    }


def run_behavioral(tmp: Path) -> dict[str, Any]:
    profile = Profile(tmp / "profile")
    profile.materialize_empty()
    install_package(profile)
    before = launch_host(profile)
    before_act = before.get("activations") or {}
    uninstall_package(profile, purge_user_data=False)
    after = launch_host(profile)
    after_act = after.get("activations") or {}
    pre_hook = bool((before_act.get("hook") or {}).get("activated"))
    pre_mcp = bool((before_act.get("mcp") or {}).get("activated"))
    pre_task = bool((before_act.get("task") or {}).get("activated"))
    post_hook = bool((after_act.get("hook") or {}).get("activated"))
    post_mcp = bool((after_act.get("mcp") or {}).get("activated"))
    post_task = bool((after_act.get("task") or {}).get("activated"))
    control_detector = pre_hook and pre_mcp and pre_task
    return {
        "probe": "probe2-behavioral",
        "control_pre_uninstall_all_activate": control_detector,
        "pre_uninstall": {
            "exit_code": before["exit_code"],
            "hook_activated": pre_hook,
            "mcp_activated": pre_mcp,
            "task_activated": pre_task,
            "plugin_dir_present": bool(before_act.get("plugin_dir_present")),
        },
        "post_uninstall": {
            "exit_code": after["exit_code"],
            "hook_activated": post_hook,
            "mcp_activated": post_mcp,
            "task_activated": post_task,
            "plugin_dir_present": bool(after_act.get("plugin_dir_present")),
            "any_package_activation": bool(after_act.get("any_package_activation")),
            "mcp_id": PACKAGE_ID,
            "task_id": TASK_ID,
        },
        "reactivation": {
            "hooks": post_hook,
            "mcp": post_mcp,
            "scheduled_task": post_task,
        },
        "host_exit_pre": before["exit_code"],
        "host_exit_post": after["exit_code"],
    }
