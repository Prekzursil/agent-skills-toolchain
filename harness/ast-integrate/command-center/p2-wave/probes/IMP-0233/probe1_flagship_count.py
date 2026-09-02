#!/usr/bin/env python3
"""Probe 1: flagship count is computed from the registry and equals 40.

Both-states: live registry computes 40; a planted extra flagship computes 41
and fails the gate; a demoted flagship computes 39 and fails the gate.
The integer 40 is the spec floor compared to the count, not the count itself.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center" / "lib"
sys.path.insert(0, str(LIB))

from flagship_e2e_contract.contract import SPEC_FLAGSHIP_COUNT, flagship_count_ok  # noqa: E402
from flagship_e2e_contract.registry import (  # noqa: E402
    all_ids,
    compute_flagship_count,
    load_registry,
    plant_extra_flagship,
    plant_missing_flagship,
)

RAW = HERE / "probe1-flagship-count.raw.json"


def main() -> int:
    doc = load_registry()
    ids = all_ids(doc)
    live = compute_flagship_count(doc)
    extra = compute_flagship_count(plant_extra_flagship(doc))
    missing = compute_flagship_count(plant_missing_flagship(doc))

    unique = len(set(ids))
    n_entries = len(doc.get("entries") or [])
    live_ok = flagship_count_ok(live)
    extra_rejected = extra != SPEC_FLAGSHIP_COUNT and not flagship_count_ok(extra)
    missing_rejected = missing != SPEC_FLAGSHIP_COUNT and not flagship_count_ok(missing)

    claimed = doc.get("library_size")
    if claimed != n_entries:
        print("FAILED:IMP-0233-probe1 library_size is not the entry list length")
        return 1

    out = {
        "both_states": True,
        "entries": n_entries,
        "extra_flagship_count": extra,
        "extra_rejected": extra_rejected,
        "live_count": live,
        "live_ok": live_ok,
        "missing_flagship_count": missing,
        "missing_rejected": missing_rejected,
        "pass": bool(
            live_ok
            and extra_rejected
            and missing_rejected
            and unique == 96
            and n_entries == 96
            and live == 40
            and extra == 41
            and missing == 39
        ),
        "spec_floor": SPEC_FLAGSHIP_COUNT,
        "unique_ids": unique,
    }
    RAW.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"live={live} extra={extra} missing={missing} unique={unique} "
        f"entries={n_entries} live_ok={live_ok} extra_rejected={extra_rejected} "
        f"missing_rejected={missing_rejected}"
    )
    if not out["pass"]:
        print("FAILED:IMP-0233-probe1 computed flagship count gate")
        return 1
    print("SUCCESS:IMP-0233-probe1 computed flagship count == 40 with both-states mutants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
