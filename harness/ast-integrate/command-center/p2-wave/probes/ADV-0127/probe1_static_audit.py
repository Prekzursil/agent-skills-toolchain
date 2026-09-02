#!/usr/bin/env python3
"""Probe 1: static clock-class census of production timestamp writes/comparisons/TTLs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clock_lib as C  # noqa: E402

NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0127-probe1 {msg}")
    return 1


def main() -> int:
    live = C.production_census()
    print(
        json.dumps(
            {
                "probe": live["probe"],
                "unit_id": live["unit_id"],
                "n_rows": live["n_rows"],
                "counts": live["counts"],
                "fingerprint_sha256": live["fingerprint_sha256"],
                "naive_local_present": live["naive_local_present"],
                "utc_aware_present": live["utc_aware_present"],
                "monotonic_present": live["monotonic_present"],
                "close_fromisoformat": live["close_fromisoformat"],
                "production_modules_present": live["production_modules_present"],
                "anchors": live["anchors"],
            },
            indent=1,
            sort_keys=True,
            default=str,
        )
    )
    if live["n_rows"] < 1:
        return fail("census empty")
    if not live["naive_local_present"]:
        return fail("expected naive-local hits (close._now fromisoformat)")
    if not live["utc_aware_present"]:
        return fail("expected utc-aware hits (datetime.now(timezone.utc))")
    if not live["close_fromisoformat"]:
        return fail("did not classify close.py fromisoformat")
    art = C.REPO / C.OUT_REL
    if not art.is_file() or art.stat().st_size < 1024:
        return fail("artifact missing")
    text, doc = C.load_artifact()
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return fail(f"self-declared {doc.get('state')}")
    sentinel = C.catalog_sentinel()
    if sentinel not in text:
        return fail("sentinel-absent")
    errs = C.schema_errors(doc)
    if errs:
        print("\n".join(errs[:12]))
        return fail("schema")
    recorded = (doc.get("static_audit") or {}).get("fingerprint_sha256")
    if recorded != live["fingerprint_sha256"]:
        return fail(f"census fingerprint drift live={live['fingerprint_sha256']} art={recorded}")
    garbage = C.garbage_rejected()
    if any(n < 1 for n in garbage):
        return fail(f"schema accepts garbage {garbage}")
    print(
        f"census rows={live['n_rows']} naive={live['counts'].get('naive-local', 0)} "
        f"utc={live['counts'].get('utc-aware', 0)} monotonic={live['counts'].get('monotonic', 0)}"
    )
    print("SUCCESS:ADV-0127-probe1 static clock-class census, naive fromisoformat classified, artifact matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
