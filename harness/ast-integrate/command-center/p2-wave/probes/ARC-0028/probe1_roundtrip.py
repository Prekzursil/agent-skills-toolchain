#!/usr/bin/env python3
"""Named probe 1: export curation, import to gateway, re-export equals original set.

Signal 1: sha256 of canonical record JSON.
Signal 2: sorted (id, split, effective_enabled, live_active) tuples.
Disagreement is BLOCKED, not a picked winner.

Also proves a drop-disabled importer fails (negative control).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    EXPOSED_INACTIVE_MCP,
    KNOWN_DISABLED_MCP,
    KNOWN_DISABLED_PLUGIN,
    write_estate,
)
from curation import (  # noqa: E402
    diff_records,
    domain_from_artifact,
    expected_invariants,
    export_from_gateway,
    freeze_snapshot,
    import_into_gateway,
    merge_records,
    snapshot_live,
    snapshot_settings,
)

ART = REPO / "command-center/phase3/A4/MIGRATION.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0028-probe1 migration artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if doc.get("unit_id") != "ARC-0028":
        print("FAILED:ARC-0028-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:ARC-0028" not in blob:
        print("FAILED:ARC-0028-probe1 sentinel absent")
        return 1

    with tempfile.TemporaryDirectory(prefix="arc0028-p1-") as tmp:
        estate = Path(tmp)
        write_estate(estate)
        snap = freeze_snapshot(estate)
        merged = snap["merged"]
        if merged.get("blocked"):
            print("FAILED:ARC-0028-probe1 snapshot BLOCKED")
            print(json.dumps(merged.get("disagreements"), indent=2)[:2000])
            return 1
        records = merged["records"]
        inv = expected_invariants(records)
        if not all(inv.values()):
            print("FAILED:ARC-0028-probe1 invariants")
            print(json.dumps(inv, indent=2))
            return 1

        index = import_into_gateway(records, drop_never_activate=False)
        exported = export_from_gateway(index)
        diff = diff_records(records, exported)
        if diff.get("blocked_signal_disagreement"):
            print("FAILED:ARC-0028-probe1 BLOCKED digest vs tuple disagreement")
            print(json.dumps(diff, indent=2, default=str)[:2000])
            return 1
        if not diff.get("equal"):
            print("FAILED:ARC-0028-probe1 round-trip set mismatch")
            print(json.dumps(diff, indent=2, default=str)[:3000])
            return 1

        dropped = import_into_gateway(records, drop_never_activate=True)
        dropped_export = export_from_gateway(dropped)
        drop_diff = diff_records(records, dropped_export)
        if drop_diff.get("equal"):
            print("FAILED:ARC-0028-probe1 drop-disabled control did not fail")
            return 1
        if f"plugin:{KNOWN_DISABLED_PLUGIN}" not in drop_diff.get("missing", []):
            print("FAILED:ARC-0028-probe1 drop-disabled did not drop plugin:agentbridge")
            print(drop_diff.get("missing"))
            return 1

        # Re-merge from the two live sources independently of freeze.records
        merged2 = merge_records(snapshot_settings(estate), snapshot_live(estate))
        if merged2["records_sha256"] != merged["records_sha256"]:
            print("FAILED:ARC-0028-probe1 two snapshot reads disagree")
            print(merged["records_sha256"], merged2["records_sha256"])
            return 1

    domain = domain_from_artifact(doc)
    recorded = {r["id"]: r for r in (domain.get("sample") or []) if isinstance(r, dict) and r.get("id")}
    if len(recorded) < 5:
        print(f"FAILED:ARC-0028-probe1 artifact sample {len(recorded)}")
        return 1
    for rec in records:
        got = recorded.get(rec["id"])
        if not got:
            print(f"FAILED:ARC-0028-probe1 artifact missing sample {rec['id']}")
            return 1
        if got.get("split") != rec["split"]:
            print(f"FAILED:ARC-0028-probe1 split drift {rec['id']}")
            return 1
        if bool(got.get("effective_enabled")) != rec["effective_enabled"]:
            print(f"FAILED:ARC-0028-probe1 enabled drift {rec['id']}")
            return 1
        if bool(got.get("live_active")) != rec["live_active"]:
            print(f"FAILED:ARC-0028-probe1 live_active drift {rec['id']}")
            return 1

    tests = (domain.get("tests") or {}).get("round_trip_fidelity") or {}
    if not tests.get("drop_disabled_control_fails"):
        print("FAILED:ARC-0028-probe1 artifact missing drop_disabled_control_fails")
        return 1
    if tests.get("records_checked") != len(records):
        print("FAILED:ARC-0028-probe1 records_checked drift", tests.get("records_checked"), len(records))
        return 1

    out = {
        "probe": "probe1-roundtrip",
        "unit_id": "ARC-0028",
        "records_checked": len(records),
        "set_equal": True,
        "disabled_plugin_preserved": True,
        "exposed_inactive_preserved": True,
        "drop_disabled_control_fails": True,
        "disabled_ids": [f"plugin:{KNOWN_DISABLED_PLUGIN}", f"mcp:{KNOWN_DISABLED_MCP}"],
        "exposed_inactive": [f"mcp:{EXPOSED_INACTIVE_MCP}"],
        "before_sha256": diff["before_sha256"],
        "after_sha256": diff["after_sha256"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"records={len(records)} equal=True "
        f"drop_missing={drop_diff.get('missing')} "
        f"invariants={inv}"
    )
    print("SUCCESS:ARC-0028-probe1 round-trip set equality and refuse-drop-disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
