#!/usr/bin/env python3
"""Live experiments: complete uninstall, naive payload-only, scorched-earth."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from lab import (
    DOCUMENTED_USER_DATA,
    HOOK_ID,
    INSTALL_CREATED_USER_DATA,
    MCP_ID,
    PACKAGE_ID,
    TASK_ID,
    UNRELATED_HOOK,
    UNRELATED_MCP,
    UNRELATED_TASK,
    USER_KEEP,
    activate,
    classify_diff,
    install,
    orphan_count,
    package_orphans,
    seed_pre_install,
    snapshot,
    uninstall,
    user_data_survival,
)


def _run_one(mode: str, retain_user_data: bool = True) -> dict[str, Any]:
    tmp = tempfile.TemporaryDirectory(prefix="tst0073-")
    with tmp:
        root = seed_pre_install(Path(tmp.name) / "profile")
        pre = snapshot(root)
        installed = install(root)
        mid = snapshot(root)
        mid_orphans = package_orphans(mid)
        un = uninstall(
            root,
            installed["projection"],
            mode=mode,
            retain_user_data=retain_user_data,
        )
        post = snapshot(root)
        post_orphans = package_orphans(post)
        classified = classify_diff(
            pre["census"],
            post["census"],
            INSTALL_CREATED_USER_DATA,
        )
        survival = user_data_survival(root, pre["census"])
        fired = activate(root)
        unrelated_still = {
            "hooks": UNRELATED_HOOK in (post.get("hooks") or [])
            if mode != "scorched"
            else False,
            "mcp": UNRELATED_MCP in (post.get("mcp") or [])
            if mode != "scorched"
            else False,
            "tasks": UNRELATED_TASK in (post.get("tasks") or [])
            if mode != "scorched"
            else False,
            "user_keep": (root / USER_KEEP).is_file(),
        }
        return {
            "mode": mode,
            "retain_user_data": retain_user_data,
            "package_id": PACKAGE_ID,
            "pre": {
                "hooks": pre["hooks"],
                "mcp": pre["mcp"],
                "tasks": pre["tasks"],
                "settings_keys": pre["settings_keys"],
                "path_count": len(pre["census"]),
            },
            "post_install": {
                "hooks": mid["hooks"],
                "mcp": mid["mcp"],
                "tasks": mid["tasks"],
                "settings_keys": mid["settings_keys"],
                "path_count": len(mid["census"]),
                "package_present": orphan_count(mid_orphans) == 3
                or (
                    HOOK_ID in mid["hooks"]
                    and MCP_ID in mid["mcp"]
                    and TASK_ID in mid["tasks"]
                ),
                "orphans_if_called_now": mid_orphans,
            },
            "uninstall": un,
            "post_uninstall": {
                "hooks": post["hooks"],
                "mcp": post["mcp"],
                "tasks": post["tasks"],
                "settings_keys": post["settings_keys"],
                "path_count": len(post["census"]),
                "orphans": post_orphans,
                "orphan_count": orphan_count(post_orphans),
            },
            "activation_after": fired,
            "package_still_activates": (
                HOOK_ID in fired["hooks"]
                or MCP_ID in fired["mcp"]
                or TASK_ID in fired["tasks"]
            ),
            "detector_saw_install": (
                HOOK_ID in mid["hooks"]
                and MCP_ID in mid["mcp"]
                and TASK_ID in mid["tasks"]
            ),
            "unrelated_still": unrelated_still,
            "diff": classified,
            "user_data": survival,
            "documented_user_data": list(DOCUMENTED_USER_DATA),
            "install_created_user_data": list(INSTALL_CREATED_USER_DATA),
        }


def run_suite() -> dict[str, Any]:
    complete = _run_one("complete", retain_user_data=True)
    naive = _run_one("payload_only", retain_user_data=True)
    scorched = _run_one("scorched", retain_user_data=False)

    tests = {
        "test_no_orphan_hook_registration": (
            complete["post_uninstall"]["orphan_count"] == 0
            and HOOK_ID not in complete["post_uninstall"]["hooks"]
            and complete["detector_saw_install"]
            and naive["post_uninstall"]["orphan_count"] > 0
            and HOOK_ID in naive["post_uninstall"]["hooks"]
        ),
        "test_no_orphan_scheduled_task_or_mcp_entry": (
            MCP_ID not in complete["post_uninstall"]["mcp"]
            and TASK_ID not in complete["post_uninstall"]["tasks"]
            and "astPluginInstalled"
            not in complete["post_uninstall"]["settings_keys"]
            and (
                MCP_ID in naive["post_uninstall"]["mcp"]
                or TASK_ID in naive["post_uninstall"]["tasks"]
            )
            and not complete["package_still_activates"]
            and naive["package_still_activates"]
        ),
        "test_documented_user_data_survives": (
            complete["user_data"]["ok"]
            and complete["unrelated_still"]["user_keep"]
            and complete["unrelated_still"]["hooks"]
            and complete["unrelated_still"]["mcp"]
            and complete["unrelated_still"]["tasks"]
            and not scorched["user_data"]["ok"]
            and not scorched["unrelated_still"]["user_keep"]
        ),
        "profile_diff_only_documented": complete["diff"]["equal_except_documented"],
    }
    return {
        "pass": all(tests.values()),
        "tests": tests,
        "complete": complete,
        "naive_payload_only": naive,
        "scorched": scorched,
    }
