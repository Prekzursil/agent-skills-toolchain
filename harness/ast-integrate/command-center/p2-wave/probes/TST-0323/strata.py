#!/usr/bin/env python3
"""2×2 partition: oracle_type × platform_verdict.

A platform that is accurate on passes and wrong on failures is a specific
bias; an unstratified sample averages it away.
"""
from __future__ import annotations

ORACLE_TYPES = ("deterministic", "judged")
VERDICTS = ("fail", "pass")
STRATA = tuple(f"{o}:{v}" for o in ORACLE_TYPES for v in VERDICTS)


def stratum_id(oracle_type: str, platform_verdict: str) -> str:
    return f"{oracle_type}:{platform_verdict}"


def row_stratum(row: dict) -> str:
    return stratum_id(str(row["oracle_type"]), str(row["platform_verdict"]))


def partition(rows: list[dict]) -> dict:
    buckets: dict[str, list[dict]] = {s: [] for s in STRATA}
    unmatched: list[str] = []
    seen: set[str] = set()
    dupes: list[str] = []
    for row in rows:
        cid = str(row.get("case_id") or "")
        if cid in seen:
            dupes.append(cid)
        seen.add(cid)
        sid = row_stratum(row)
        if sid not in buckets:
            unmatched.append(cid or sid)
            continue
        buckets[sid].append(row)
    counts = {s: len(buckets[s]) for s in STRATA}
    total = sum(counts.values())
    return {
        "ok": (
            not unmatched
            and not dupes
            and total == len(rows)
            and all(s in STRATA for s in counts)
        ),
        "buckets": buckets,
        "counts": counts,
        "dupes": dupes,
        "intersections_empty": True,
        "n": len(rows),
        "sum_equals_n": total == len(rows),
        "unmatched": unmatched,
    }
