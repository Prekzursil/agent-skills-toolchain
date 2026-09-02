#!/usr/bin/env python3
"""Probe 2: inertness control + mutant both-states + subprocess second field."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lab as L  # noqa: E402

OUT = HERE / "probe2-inertness.raw.json"


def main() -> int:
    report = L.run_all()
    rows = report["rows"]
    checks = [
        ("enabledPlugins_claude_json_inert", rows["enabledPlugins"]["inert_claude_json_root_loaded"] is True),
        ("mcp_root_prod_inert", rows["disabledMcpServers"]["root_disable_prod_live"] is True),
        ("mcp_root_mutant_fires", rows["disabledMcpServers"]["root_disable_mutant_live"] is False),
        ("mcp_mutant_sha_diverges", rows["disabledMcpServers"]["mutant_diverges"] is True),
        ("hooks_claude_json_inert", rows["hooks"]["inert_hook_absent"] is True),
        ("permissions_claude_json_inert", rows["permissions"]["inert_claude_json_verdict"] == "ALLOW"),
        ("permissions_merge_deny_holds", rows["permissions"]["user_deny_local_allow_verdict"] == "DENY"),
        ("model_claude_json_inert", rows["model"]["inert_claude_json_model"] == "res0012-user-model"),
        ("model_managed_beats_local", rows["model"]["managed_wins"] == "res0012-managed-model"),
        ("subprocess_sha_hooks", rows["hooks"]["sha_matches_subprocess"] is True),
        ("all_pass", report["all_pass"] is True),
        ("no_live_profile", report["live_profile_read"] is False),
        ("no_claude_binary", report["claude_binary_spawned"] is False),
    ]
    payload = {"probe": "probe2-inertness", "unit_id": "RES-0012", "checks": {}}
    failed = []
    for name, ok in checks:
        payload["checks"][name] = bool(ok)
        print(f"{name}={ok}")
        if not ok:
            failed.append(name)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if failed:
        print(f"FAILED:RES-0012-probe2 {failed}")
        return 1
    print("SUCCESS:RES-0012-probe2 inertness mutant both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
