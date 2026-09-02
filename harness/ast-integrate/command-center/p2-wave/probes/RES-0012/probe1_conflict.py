#!/usr/bin/env python3
"""Probe 1: conflicting values at two scopes; observe which behaviour wins."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lab as L  # noqa: E402

OUT = HERE / "probe1-conflict.raw.json"


def main() -> int:
    report = L.run_all()
    rows = report["rows"]
    checks = [
        ("enabledPlugins_project_unloads", rows["enabledPlugins"]["after_project_false_loaded"] is False),
        ("enabledPlugins_was_loaded", rows["enabledPlugins"]["before_loaded"] is True),
        ("enabledPlugins_swap_reloads", rows["enabledPlugins"]["swap_project_true_loaded"] is True),
        ("mcp_per_project_unloads", rows["disabledMcpServers"]["per_project_disable_live"] is False),
        ("mcp_was_live", rows["disabledMcpServers"]["before_live"] is True),
        ("hooks_local_added", rows["hooks"]["local_hook_present"] is True),
        ("hooks_user_kept", rows["hooks"]["user_hook_still_present"] is True),
        ("permissions_local_deny", rows["permissions"]["local_deny_verdict"] == "DENY"),
        ("permissions_was_allow", rows["permissions"]["before_verdict"] == "ALLOW"),
        ("model_local_wins", rows["model"]["local_wins"] == "res0012-local-model"),
        ("model_swap_tracks_scope", rows["model"]["swap_local_wins"] == "res0012-user-model"),
        ("all_pass", report["all_pass"] is True),
        ("no_live_profile", report["live_profile_read"] is False),
    ]
    payload = {"probe": "probe1-conflict", "unit_id": "RES-0012", "checks": {}}
    failed = []
    for name, ok in checks:
        payload["checks"][name] = bool(ok)
        print(f"{name}={ok}")
        if not ok:
            failed.append(name)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if failed:
        print(f"FAILED:RES-0012-probe1 {failed}")
        return 1
    print("SUCCESS:RES-0012-probe1 conflict behaviour deltas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
