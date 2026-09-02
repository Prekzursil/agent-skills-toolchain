#!/usr/bin/env python3
"""Named probe 1: enumerate allow/deny per settings scope and merge.

This is the config-read model. It does not test hook matchers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    catalog_tool_policy,
    fixture_merge_scopes,
    live_permission_scopes,
    merge_allow_deny,
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0080-probe1 {msg}")
    return 1


def main() -> int:
    live = live_permission_scopes()
    if len(live) < 6:
        return fail(f"expected 6 live scopes, got {len(live)}")
    missing_names = [r["scope"] for r in live if not r.get("scope")]
    if missing_names:
        return fail("scope id missing")

    live_existing = [r for r in live if r.get("exists")]
    live_merged = merge_allow_deny(live)

    fixtures = fixture_merge_scopes()
    for row in fixtures:
        if not row.get("exists") or not row.get("parse_ok"):
            return fail(f"fixture unreadable {row.get('path')}: {row.get('error')}")
    fx_merged = merge_allow_deny(fixtures)
    expected_allow = {
        "Bash(git *)",
        "Bash(echo *)",
        "Bash(grep *)",
        "Bash(rm *)",
        "Bash(python *)",
        "Bash(find *)",
    }
    expected_deny = {"Bash(curl *)", "Bash(rm *)"}
    expected_effective = {
        "Bash(git *)",
        "Bash(echo *)",
        "Bash(grep *)",
        "Bash(python *)",
        "Bash(find *)",
    }
    got_allow = set(fx_merged["allow_union"])
    got_deny = set(fx_merged["deny_union"])
    got_eff = set(fx_merged["effective_allow"])
    if got_allow != expected_allow:
        return fail(f"fixture allow union {sorted(got_allow)} != {sorted(expected_allow)}")
    if got_deny != expected_deny:
        return fail(f"fixture deny union {sorted(got_deny)} != {sorted(expected_deny)}")
    if got_eff != expected_effective:
        return fail(
            f"fixture effective {sorted(got_eff)} != {sorted(expected_effective)} "
            "(deny must win for Bash(rm *))"
        )
    if "Bash(rm *)" in got_eff:
        return fail("Bash(rm *) survived local deny; merge is broken")

    cursor = next((r for r in live if r["scope"] == "user-cursor"), None)
    if cursor is None:
        return fail("user-cursor scope absent from enumerator")
    if cursor.get("exists") and cursor.get("parse_ok"):
        if "Shell(ls)" not in (cursor.get("allow") or []):
            return fail("live user-cursor allow list did not contain Shell(ls)")
        if "Shell(ls)" not in live_merged["effective_allow"] and "Shell(ls)" not in (
            live_merged["deny_union"]
        ):
            return fail("live Shell(ls) dropped from effective merge without a deny")

    policy = catalog_tool_policy()
    if not policy.get("exists") or not policy.get("allow"):
        return fail("catalog tool_policy allow list unreadable")

    payload = {
        "probe": "probe1-allow-merge",
        "unit_id": "AUD-0080",
        "pass": True,
        "live_scopes": [
            {
                "scope": r["scope"],
                "path": r["path"],
                "exists": r["exists"],
                "parse_ok": r["parse_ok"],
                "allow": r.get("allow") or [],
                "deny": r.get("deny") or [],
                "bytes": r.get("bytes") or 0,
                "error": r.get("error"),
            }
            for r in live
        ],
        "live_existing_count": len(live_existing),
        "live_merged": live_merged,
        "fixture_scopes": fixtures,
        "fixture_merged": fx_merged,
        "catalog_tool_policy_related": {
            "path": policy["path"],
            "allow_count": len(policy.get("allow") or []),
            "deny_count": len(policy.get("deny") or []),
            "default": policy.get("default"),
            "merged_into_live": False,
            "note": policy.get("note"),
        },
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "live_existing="
        f"{len(live_existing)} live_allow={len(live_merged['allow_union'])} "
        f"live_effective={len(live_merged['effective_allow'])} "
        f"fixture_effective={len(fx_merged['effective_allow'])}"
    )
    print("SUCCESS:AUD-0080-probe1 per-scope allow entries and deny-wins merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
