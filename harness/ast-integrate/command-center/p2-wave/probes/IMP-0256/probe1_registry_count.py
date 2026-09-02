#!/usr/bin/env python3
"""Probe 1: computed registry count is 87 phase-7 + 9 delegated = 96.

Also: unique ids, distinct delegated fingerprints, every delegated entry
emits a CouncilSpec that hands off to phase-7A (compile + delegate).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from blueprint_library.compiler import compile_council_spec, delegated_fingerprints
from blueprint_library.delegate import delegate_to_phase7a
from blueprint_library.inventory import DELEGATED_IDS, PHASE7_RECORDS
from blueprint_library.registry import library_counts, load_library


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0256-probe1 {msg}")
    return 1


def main() -> int:
    entries = load_library()
    counts = library_counts(entries)
    print(
        json.dumps(
            {
                "phase7": counts["phase7"],
                "delegated": counts["delegated"],
                "total": counts["total"],
                "unique_ids": counts["unique_ids"],
                "inventory_phase7_tuple": len(PHASE7_RECORDS),
                "inventory_delegated_tuple": len(DELEGATED_IDS),
            },
            sort_keys=True,
        )
    )
    if counts["phase7"] != 87:
        return fail(f"phase7 count {counts['phase7']} != 87")
    if counts["delegated"] != 9:
        return fail(f"delegated count {counts['delegated']} != 9")
    if counts["total"] != 96:
        return fail(f"total {counts['total']} != 96")
    if counts["unique_ids"] != 96:
        return fail(f"unique_ids {counts['unique_ids']} != 96 (duplicate id)")
    if counts["phase7"] + counts["delegated"] != counts["total"]:
        return fail("phase7+delegated != total")
    if len(PHASE7_RECORDS) != 87 or len(DELEGATED_IDS) != 9:
        return fail("inventory tuple lengths drifted from registry lists")

    fps = delegated_fingerprints()
    if set(fps) != set(DELEGATED_IDS):
        return fail("fingerprint key set != delegated ids")
    if len(set(fps.values())) != 9:
        return fail(f"fingerprint collisions among delegated: {fps}")

    for protocol_id in DELEGATED_IDS:
        spec = compile_council_spec(protocol_id, {"seed": "probe1"})
        if spec.get("deliberation_implemented_here") is not False:
            return fail(f"{protocol_id} claims local deliberation")
        runtime = (spec.get("delegate_to") or {}).get("runtime")
        if runtime != "phase-7A":
            return fail(f"{protocol_id} delegate_to.runtime={runtime!r}")
        if spec.get("protocol_id") != protocol_id:
            return fail(f"{protocol_id} spec protocol_id mismatch")
        packet = delegate_to_phase7a(spec)
        if packet.get("kind") != "phase7a-handoff":
            return fail(f"{protocol_id} handoff kind {packet.get('kind')!r}")
        if packet.get("spec_protocol_id") != protocol_id:
            return fail(f"{protocol_id} handoff protocol mismatch")
        print(
            f"delegated {protocol_id} compile_ok=True "
            f"runtime_present={packet.get('runtime_present')} "
            f"status={packet.get('status')}"
        )

    print(
        f"computed phase7={counts['phase7']} delegated={counts['delegated']} "
        f"total={counts['total']} fingerprints_unique=9"
    )
    print("SUCCESS:IMP-0256-probe1 registry 87+9=96 and nine CouncilSpec handoffs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
