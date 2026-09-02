#!/usr/bin/env python3
"""Probe 2: launch host after uninstall; record leftover activations."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from common import OUTPUT_REL, UNIT_ID  # noqa: E402
from scenario import run_behavioral  # noqa: E402
from validate_artifact import load_artifact, validate  # noqa: E402


def main() -> int:
    doc, text = load_artifact()
    errors = validate(doc, text)
    if errors:
        print("FAILED:ADV-0047-probe2 artifact " + ";".join(errors[:8]))
        return 1

    with tempfile.TemporaryDirectory(prefix="adv0047-p2-") as tmp_s:
        live = run_behavioral(Path(tmp_s))

    if not live["control_pre_uninstall_all_activate"]:
        print("FAILED:ADV-0047-probe2 detector control: host did not activate while installed")
        return 1
    post = live["post_uninstall"]
    if post["hook_activated"]:
        print("FAILED:ADV-0047-probe2 owned hook still fired after uninstall")
        return 1
    if post["plugin_dir_present"]:
        print("FAILED:ADV-0047-probe2 plugin dir still present")
        return 1
    if not post["mcp_activated"]:
        print("FAILED:ADV-0047-probe2 expected leftover MCP reactivation")
        return 1
    if not post["task_activated"]:
        print("FAILED:ADV-0047-probe2 expected leftover scheduled-task reactivation")
        return 1
    if not post["any_package_activation"]:
        print("FAILED:ADV-0047-probe2 no reactivation recorded")
        return 1

    art = doc.get("behavioral") or {}
    art_post = art.get("post_uninstall") or {}
    for key in ("hook_activated", "mcp_activated", "task_activated"):
        if bool(art_post.get(key)) != bool(post.get(key)):
            print("FAILED:ADV-0047-probe2 artifact mismatch", key, art_post.get(key), post.get(key))
            return 1

    print(
        json.dumps(
            {
                "probe": "probe2-behavioral",
                "unit_id": UNIT_ID,
                "control_pre_uninstall_all_activate": True,
                "post_hook_activated": post["hook_activated"],
                "post_mcp_activated": post["mcp_activated"],
                "post_task_activated": post["task_activated"],
                "any_package_activation": post["any_package_activation"],
                "plugin_dir_present": post["plugin_dir_present"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:ADV-0047-probe2 post-uninstall host activation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
