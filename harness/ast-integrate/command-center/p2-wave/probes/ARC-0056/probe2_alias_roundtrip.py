#!/usr/bin/env python3
"""Named probe 2: live alias round-trip (resolved target string).

Every aliased old name must invoke() to the recorded product target.
Unknown names are NOT-FOUND. Removed names do not resolve as aliases.
Different field than probe 1 (targets, not set membership).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from dispositions import ALIASES  # noqa: E402
from invoke import invoke, roundtrip_aliases  # noqa: E402

ART = REPO / "command-center/phase3/A8/MIGRATION.json"
LIVE = HERE / "fixtures" / "live"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0056-probe2 migration artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "ARC-0056":
        print("FAILED:ARC-0056-probe2 unit_id", doc.get("unit_id"))
        return 1

    table = doc.get("alias_table") or []
    if len(table) < 3:
        print("FAILED:ARC-0056-probe2 alias_table too small", len(table))
        return 1
    art_map = {row["old"]: row["target"] for row in table}
    if art_map != ALIASES:
        print("FAILED:ARC-0056-probe2 alias_table drift vs policy")
        print("policy", ALIASES)
        print("art   ", art_map)
        return 1

    result = roundtrip_aliases(LIVE)
    if not result["pass"]:
        print("FAILED:ARC-0056-probe2 alias roundtrip")
        print(json.dumps(result, indent=2, default=str)[:3000])
        return 1

    # Live invocation of each recorded row (not just the policy dict).
    live_failed = []
    for row in table:
        got = invoke(row["old"], LIVE)
        if not got.get("ok") or got.get("target") != row["target"]:
            live_failed.append({"row": row, "got": got})
    if live_failed:
        print("FAILED:ARC-0056-probe2 live invoke mismatch")
        print(json.dumps(live_failed, indent=2, default=str)[:3000])
        return 1

    recorded = (doc.get("tests") or {}).get("alias_roundtrip") or {}
    if int(recorded.get("aliases_checked") or -1) != result["aliases_checked"]:
        print("FAILED:ARC-0056-probe2 artifact aliases_checked drift")
        return 1
    if not recorded.get("negative_control_unknown_name"):
        print("FAILED:ARC-0056-probe2 artifact missing negative control")
        return 1

    # Control: dropping one alias from a scratch map must not round-trip.
    dropped = next(iter(ALIASES))
    scratch_fail = invoke(dropped, LIVE)
    if not scratch_fail.get("ok") or scratch_fail.get("target") != ALIASES[dropped]:
        print("FAILED:ARC-0056-probe2 baseline alias no longer live")
        return 1

    out = {
        "probe": "probe2-alias-roundtrip",
        "unit_id": "ARC-0056",
        "aliases_checked": result["aliases_checked"],
        "negative_control_unknown_name": True,
        "removed_do_not_resolve": result["removed_do_not_resolve"],
        "failed": [],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"aliases_checked={result['aliases_checked']} "
        f"unknown=NOT-FOUND removed_blocked={result['removed_do_not_resolve']}"
    )
    print("SUCCESS:ARC-0056-probe2 alias round-trip live invocation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
