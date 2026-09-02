#!/usr/bin/env python3
"""Named probe 2: refuse control + silent-misinterpretation detector.

The known-broken fixture is naive-schema-bump: extra v2 keys stripped and
schema_version stamped to 1 so the old loader ACCEPTS it. A load-succeeded
boolean would call that a pass. Field comparison must fire on plugin.version
and discovery_only. The unreadable fixture must be refused with a message
that names JSONDecodeError / unreadable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import state as S  # noqa: E402


def main() -> int:
    rows = {r["id"]: r for r in S.evaluate_all()}

    unreadable = rows["unreadable"]
    if unreadable["old_version_load"]["loaded"]:
        print("FAILED:CNF-0048-probe2 unreadable fixture loaded")
        return 1
    if not unreadable["old_version_load"]["refused"]:
        print("FAILED:CNF-0048-probe2 unreadable not marked refused")
        return 1
    msg = unreadable["old_version_load"]["message"]
    if "JSONDecodeError" not in msg and "unreadable" not in msg.lower():
        print("FAILED:CNF-0048-probe2 refuse message is not actionable:", msg)
        return 1
    if "unreadable.json" not in msg and "fixtures/unreadable" not in msg:
        print("FAILED:CNF-0048-probe2 refuse message does not name the file:", msg)
        return 1

    raw = rows["new-written"]
    if raw["old_version_load"]["loaded"]:
        print("FAILED:CNF-0048-probe2 raw v2 loaded instead of refusing")
        return 1
    if "schema_version" not in raw["old_version_load"]["message"]:
        print("FAILED:CNF-0048-probe2 v2 refuse does not name schema_version")
        print(raw["old_version_load"]["message"])
        return 1

    naive = rows["naive-schema-bump"]
    if not naive["old_version_load"]["loaded"]:
        print("FAILED:CNF-0048-probe2 naive bump did not load; detector has no target")
        print(naive["old_version_load"]["message"])
        return 1
    if naive["meaning_changed_count"] < 1:
        print("FAILED:CNF-0048-probe2 naive bump load-succeeded with no meaning_changed")
        return 1
    changed_paths = {c["path"] for c in naive["field_comparisons"] if c["meaning_changed"]}
    missing = [p for p in S.SEMANTIC_FIELDS if p not in changed_paths]
    if missing:
        print("FAILED:CNF-0048-probe2 semantic fields not flagged:", missing)
        print("changed:", sorted(changed_paths))
        return 1
    version_row = next(
        c
        for c in naive["field_comparisons"]
        if c["path"] == "entries[plugin.harness].version"
    )
    if version_row["intended"] == version_row["loaded"]:
        print("FAILED:CNF-0048-probe2 version meaning was not different")
        return 1
    if naive["outcome"] != "SILENT-MISINTERPRET":
        print("FAILED:CNF-0048-probe2 naive outcome", naive["outcome"])
        return 1

    summary = {
        "naive_loaded": True,
        "naive_meaning_changed": naive["meaning_changed_count"],
        "negative_control_refused": True,
        "pass": True,
        "probe": "probe2-refuse-control",
        "raw_v2_refused": True,
        "unit_id": "CNF-0048",
        "unreadable_message": msg,
    }
    print(json.dumps(summary, sort_keys=True))
    print("unreadable_refused=True naive_misinterpret=True raw_v2_refused=True")
    print("SUCCESS:CNF-0048-probe2 refuse control and meaning-shift detector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
