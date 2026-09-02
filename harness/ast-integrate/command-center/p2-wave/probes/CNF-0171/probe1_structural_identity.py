#!/usr/bin/env python3
"""Probe 1 (primary): import-graph + object identity at the six declared sites.

Both-states: the live tree binds one judge object at all six sites.
Known-broken: a vendored copy of the reducer at a fake site must be DIVERGENT.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import identity as I  # noqa: E402


def main() -> int:
    live = I.resolve_declared_sites()
    shared = I.all_shared(live)
    object_ids = [row.get("object_id") for row in live]
    origins = [row.get("resolved_import_path") for row in live]

    with tempfile.TemporaryDirectory(prefix="cnf0171-vendor-") as tmp:
        broken = I.vendor_copy_control(Path(tmp))

    ok = bool(shared and broken.get("fired"))
    payload = {
        "probe": "probe1-structural-identity",
        "unit_id": "CNF-0171",
        "pass": ok,
        "primary_signal": "import-graph-and-object-identity",
        "declared_sites": list(I.DECLARED_SITE_IDS),
        "live_all_shared": shared,
        "live_object_ids": object_ids,
        "live_unique_object_ids": len(set(object_ids)),
        "live_resolved_import_paths": origins,
        "live_rows": live,
        "known_broken_vendored_copy": {
            "fired": broken.get("fired"),
            "ast_fingerprint_matches_library": broken.get("ast_fingerprint_matches_library"),
            "vendored_judge_is_library": broken.get("vendored_judge_is_library"),
            "identity_status": (broken.get("row") or {}).get("identity_status"),
            "same_object_as_library": (broken.get("row") or {})
            .get("bound_judge", {})
            .get("same_object_as_library"),
            "co_filename": (broken.get("row") or {}).get("bound_judge", {}).get("co_filename"),
            "note": broken.get("note"),
        },
        "library_symbol": I.SHARED_SYMBOL,
        "library_origin": I.rel(I.library_origin()),
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if not shared:
        print("FAILED:CNF-0171-probe1 live declared sites are not one judge object")
        return 1
    if not broken.get("fired"):
        print("FAILED:CNF-0171-probe1 vendored-copy control did not fire")
        return 1
    print(f"live_shared=True unique_objects=1 vendored_copy_fired=True sites={len(live)}")
    print("SUCCESS:CNF-0171-probe1 structural identity and vendored-copy control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
