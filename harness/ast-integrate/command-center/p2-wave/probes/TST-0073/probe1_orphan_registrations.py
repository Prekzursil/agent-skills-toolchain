#!/usr/bin/env python3
"""Probe 1: after uninstall, no package hook/MCP/scheduled-task remains registered.

Mechanically: query each registration surface (not infer from a missing payload
folder). Detector control: the same sweep must see the registrations after
install. Negative control: payload-only uninstall leaves the hook/MCP/task
registered and the host would still activate them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lab import HOOK_ID, MCP_ID, TASK_ID  # noqa: E402
from scenario import run_suite  # noqa: E402

ART = REPO / "command-center/receipts/TST-0073.json"
SENTINEL = "SUCCESS:TST-0073"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0073-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0073":
        return fail(f"unit_id={doc.get('unit_id')}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    suite = run_suite()
    complete = suite["complete"]
    naive = suite["naive_payload_only"]
    tests = suite["tests"]

    if not complete["detector_saw_install"]:
        return fail("detector did not see hook/mcp/task after install")
    if complete["post_uninstall"]["orphan_count"] != 0:
        return fail(
            f"complete uninstall left orphans {complete['post_uninstall']['orphans']}"
        )
    if HOOK_ID in complete["post_uninstall"]["hooks"]:
        return fail("orphan hook still registered")
    if MCP_ID in complete["post_uninstall"]["mcp"]:
        return fail("orphan MCP still registered")
    if TASK_ID in complete["post_uninstall"]["tasks"]:
        return fail("orphan scheduled task still registered")
    if complete["package_still_activates"]:
        return fail("host would still activate package registrations")
    if naive["post_uninstall"]["orphan_count"] == 0:
        return fail("payload-only control produced zero orphans (detector vacuous)")
    if HOOK_ID not in naive["post_uninstall"]["hooks"]:
        return fail("payload-only control did not leave the planted hook")
    if not naive["package_still_activates"]:
        return fail("payload-only host activation was silent (control did not fire)")
    if not tests["test_no_orphan_hook_registration"]:
        return fail("test_no_orphan_hook_registration")
    if not tests["test_no_orphan_scheduled_task_or_mcp_entry"]:
        return fail("test_no_orphan_scheduled_task_or_mcp_entry")

    payload = {
        "pass": True,
        "probe": "probe1-orphan-registrations",
        "unit_id": "TST-0073",
        "complete_orphan_count": complete["post_uninstall"]["orphan_count"],
        "complete_hooks": complete["post_uninstall"]["hooks"],
        "complete_mcp": complete["post_uninstall"]["mcp"],
        "complete_tasks": complete["post_uninstall"]["tasks"],
        "naive_orphan_count": naive["post_uninstall"]["orphan_count"],
        "naive_hooks": naive["post_uninstall"]["hooks"],
        "detector_saw_install": True,
        "package_still_activates_complete": complete["package_still_activates"],
        "package_still_activates_naive": naive["package_still_activates"],
        "surfaces_queried": [
            "throwaway-profile/hooks/hooks.json",
            "throwaway-profile/.mcp.json",
            "throwaway-profile/scheduled-tasks/",
            "throwaway-profile/settings.json",
        ],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "complete_orphans=0 naive_orphans="
        f"{naive['post_uninstall']['orphan_count']} "
        "detector_saw_install=True payload_only_still_activates=True"
    )
    print("SUCCESS:TST-0073-probe1 no orphan hook/MCP/scheduled-task after uninstall")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
