#!/usr/bin/env python3
"""Probe 1: live OSV re-query differs from the stored advisory set."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from osv import query_osv  # noqa: E402

STORED = HERE / "fixtures" / "stored-osv-lodash-4.17.20.json"


def main() -> int:
    stored = json.loads(STORED.read_text(encoding="utf-8"))
    stored_ids = set(stored["vuln_ids"])
    live = query_osv(stored["package"], stored["ecosystem"], stored["version"])
    if not live.get("ok"):
        print(
            "FAILED:BLD-0046-probe1 OSV NOT-CHECKED "
            f"endpoint={live.get('endpoint')} errors={live.get('errors')}"
        )
        return 1
    live_ids = set(live["ids"])
    if not live_ids:
        print("FAILED:BLD-0046-probe1 live advisory set empty")
        return 1
    if live_ids == stored_ids:
        print(
            "FAILED:BLD-0046-probe1 live set identical to stored; source looks cached"
        )
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1-liveness",
                "unit_id": "BLD-0046",
                "endpoint": live["endpoint"],
                "package": stored["package"],
                "version": stored["version"],
                "stored_ids": sorted(stored_ids),
                "live_ids": sorted(live_ids),
                "sets_differ": True,
                "query_timestamp": live["query_timestamp"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"stored={sorted(stored_ids)} live={sorted(live_ids)} "
        f"only_live={sorted(live_ids - stored_ids)}"
    )
    print("SUCCESS:BLD-0046-probe1 live advisory set differs from stored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
