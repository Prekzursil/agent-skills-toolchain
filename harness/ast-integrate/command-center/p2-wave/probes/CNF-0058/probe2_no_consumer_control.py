#!/usr/bin/env python3
"""CNF-0058 probe 2: a path with no consumer is identified, not assumed safe.

Independent re-derive from fixture trees (detector control). Does not read the
confirmation artifact conclusion first.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import layout as L  # noqa: E402
import scenario as S  # noqa: E402


def main() -> int:
    paths = S.materialize()
    result = L.analyze(paths["before"], paths["after"], paths["consumers"])
    xref = {row["path"]: row for row in result["consumer_cross_reference"]}
    if S.NO_CONSUMER_ADDED not in xref:
        print(f"FAILED:CNF-0058-probe2 added path {S.NO_CONSUMER_ADDED} not in changed-path list")
        print(json.dumps(sorted(xref), indent=2))
        return 1
    row = xref[S.NO_CONSUMER_ADDED]
    if row.get("consumer_finding") != "no-consumer":
        print("FAILED:CNF-0058-probe2 unreferenced path was not identified as no-consumer")
        print(json.dumps(row, indent=2, sort_keys=True))
        return 1
    if row.get("assumed_safe") is not False:
        print("FAILED:CNF-0058-probe2 unreferenced path was assumed safe")
        print(json.dumps(row, indent=2, sort_keys=True))
        return 1
    if row.get("consumers"):
        print("FAILED:CNF-0058-probe2 control path unexpectedly has consumers")
        print(json.dumps(row, indent=2, sort_keys=True))
        return 1
    if not row.get("explicit_no_consumer"):
        print("FAILED:CNF-0058-probe2 missing explicit_no_consumer flag")
        return 1

    orphans = {o["path"]: o for o in result.get("unreferenced_inventory") or []}
    if S.NO_CONSUMER_ORPHAN not in orphans:
        print(f"FAILED:CNF-0058-probe2 stable orphan {S.NO_CONSUMER_ORPHAN} missing from inventory")
        return 1
    orphan = orphans[S.NO_CONSUMER_ORPHAN]
    if orphan.get("assumed_safe") is not False or orphan.get("consumer_finding") != "no-consumer":
        print("FAILED:CNF-0058-probe2 stable orphan assumed safe")
        print(json.dumps(orphan, indent=2, sort_keys=True))
        return 1

    unclassified = result.get("incomplete_classifications") or []
    if unclassified:
        print(f"FAILED:CNF-0058-probe2 unclassified changed paths {unclassified}")
        return 1
    if not result.get("every_changed_path_classified"):
        print("FAILED:CNF-0058-probe2 every_changed_path_classified is false")
        return 1

    payload = {
        "pass": True,
        "probe": "probe2-no-consumer-control",
        "unit_id": S.UNIT_ID,
        "added_unreferenced": S.NO_CONSUMER_ADDED,
        "stable_orphan": S.NO_CONSUMER_ORPHAN,
        "consumer_finding": row["consumer_finding"],
        "assumed_safe": False,
        "explicit_no_consumer": True,
        "changed_paths": result["delta"]["changed_paths"],
        "unreferenced_count": len(orphans),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"no_consumer={S.NO_CONSUMER_ADDED} assumed_safe=False "
        f"orphan={S.NO_CONSUMER_ORPHAN}"
    )
    print("SUCCESS:CNF-0058-probe2 no-consumer control identified not assumed-safe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
