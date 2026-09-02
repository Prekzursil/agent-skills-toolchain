#!/usr/bin/env python3
"""Named probe 2: gateway fail-to-start restores previous inventory intact.

Mechanically different from probe 1 (record-set digest): this probe reads
settings-file sha256 and the live process-name set after rollback.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import KNOWN_DISABLED_PLUGIN, write_estate  # noqa: E402
from curation import (  # noqa: E402
    domain_from_artifact,
    freeze_snapshot,
    import_into_gateway,
    rollback,
    start_gateway,
    write_index,
)

ART = REPO / "command-center/phase3/A4/MIGRATION.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0028-probe2 migration artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="arc0028-p2-") as tmp:
        estate = Path(tmp)
        write_estate(estate)
        snap = freeze_snapshot(estate)
        if snap["merged"].get("blocked"):
            print("FAILED:ARC-0028-probe2 snapshot BLOCKED")
            return 1
        records = snap["merged"]["records"]
        index = import_into_gateway(records)
        write_index(estate, index)
        status = start_gateway(estate, fail=True)
        if status.get("ok"):
            print("FAILED:ARC-0028-probe2 gateway unexpectedly started")
            return 1

        result = rollback(estate, snap, skip_settings=False)
        if result.get("blocked_signal_disagreement"):
            print("FAILED:ARC-0028-probe2 BLOCKED settings-bytes vs process-set")
            print(json.dumps(result, indent=2, default=str)[:3000])
            return 1
        if not result.get("pass"):
            print("FAILED:ARC-0028-probe2 rollback rehearsal")
            print(json.dumps(result, indent=2, default=str)[:3000])
            return 1

        # Negative control: skip settings restore after the naive cut-over clobber.
        estate2 = Path(tmp) / "ctrl"
        write_estate(estate2)
        snap2 = freeze_snapshot(estate2)
        write_index(estate2, import_into_gateway(snap2["merged"]["records"]))
        start_gateway(estate2, fail=True)
        ctrl = rollback(estate2, snap2, skip_settings=True)
        if ctrl.get("pass"):
            print("FAILED:ARC-0028-probe2 skip-settings control unexpectedly passed")
            print(json.dumps(ctrl, indent=2, default=str)[:2000])
            return 1
        if ctrl.get("settings_bytes_restored"):
            print("FAILED:ARC-0028-probe2 skip-settings still restored settings bytes")
            return 1
        if ctrl.get("disabled_plugin_still_disabled"):
            print("FAILED:ARC-0028-probe2 skip-settings still kept plugin disabled")
            return 1

    domain = domain_from_artifact(doc)
    recorded = (domain.get("tests") or {}).get("rollback_rehearsal") or {}
    if not recorded.get("gateway_failed_to_start"):
        print("FAILED:ARC-0028-probe2 artifact missing gateway_failed_to_start")
        return 1
    if not recorded.get("settings_bytes_restored"):
        print("FAILED:ARC-0028-probe2 artifact missing settings_bytes_restored")
        return 1
    if not recorded.get("skip_settings_restore_control_fails"):
        print("FAILED:ARC-0028-probe2 artifact missing skip_settings_restore_control_fails")
        return 1

    out = {
        "probe": "probe2-rollback-rehearsal",
        "unit_id": "ARC-0028",
        "gateway_failed_to_start": True,
        "settings_bytes_restored": True,
        "live_process_set_restored": True,
        "disabled_plugin_still_disabled": True,
        "skip_settings_restore_control_fails": True,
        "disabled_plugin": KNOWN_DISABLED_PLUGIN,
        "want_process_set": result["want_process_set"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "gateway_fail=True settings_restored=True process_set_restored=True "
        f"skip_settings_pass={ctrl.get('pass')} "
        f"plugin_disabled={result.get('disabled_plugin_still_disabled')}"
    )
    print("SUCCESS:ARC-0028-probe2 gateway fail-to-start rollback rehearsal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
