#!/usr/bin/env python3
"""Probe 2: independent OSV purl re-query of the known-vulnerable fixture."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scanner import query_osv  # noqa: E402
from scanner_reviewer import query_osv_purl  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0053-probe2 {msg}")
    return 1


def main() -> int:
    author = query_osv("lodash", "npm", "4.17.20")
    if not author.get("ok") or not author.get("ids"):
        return fail(
            "author OSV NOT-CHECKED "
            f"endpoint={author.get('endpoint')} errors={author.get('errors')}"
        )
    reviewer = query_osv_purl()
    if not reviewer.get("ok") or not reviewer.get("finding_ids"):
        return fail(
            "reviewer OSV NOT-CHECKED "
            f"endpoint={reviewer.get('endpoint')} errors={reviewer.get('errors')}"
        )
    print(
        "reviewer "
        + json.dumps(
            {
                "finding_count": reviewer["finding_count"],
                "finding_ids": reviewer["finding_ids"],
                "live": reviewer["live"],
                "method": reviewer["method"],
                "status": reviewer["status"],
            },
            sort_keys=True,
        )
    )
    overlap = sorted(set(author["ids"]) & set(reviewer["finding_ids"]))
    print(f"overlap={overlap}")
    if not overlap:
        return fail("author and purl reviewer share no GHSA ids")
    if reviewer.get("method") != "purl":
        return fail("reviewer did not use purl")
    if not reviewer.get("live"):
        return fail("reviewer not live")
    print("SUCCESS:BLD-0053-probe2 independent scanner re-query")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
