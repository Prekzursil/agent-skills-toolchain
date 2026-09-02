#!/usr/bin/env python3
"""Probe 1: three-way AND is not the raw count (both-states + live artifact).

Known-broken naive counter: len(records) (and 'has a license string').
Known-good: qualify_a after collapse. Planted raw=7 must yield qualified=2.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import planted as P  # noqa: E402
import qualify_a as A  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0123-candidate-floor-proof.json"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0123-probe1 {msg}")
    return 1


def naive_raw(records: list[dict]) -> int:
    return len(records)


def naive_license_string(records: list[dict]) -> int:
    n = 0
    for rec in records:
        if rec.get("license") or rec.get("licence") or rec.get("license_file"):
            n += 1
    return n


def main() -> int:
    P.assert_fixture_files(REPO)
    records = P.planted_records()
    expect = P.expected()
    got = A.evaluate(records, REPO)
    raw_naive = naive_raw(records)
    lic_naive = naive_license_string(records)

    if raw_naive != 7:
        return fail(f"planted size {raw_naive} != 7")
    if got["raw_count"] != 7:
        return fail(f"qualifier raw {got['raw_count']} != 7")
    if got["qualified_count"] != 2:
        return fail(f"qualified {got['qualified_count']} != 2")
    ids = sorted(x["id"] for x in got["qualified"])
    if ids != expect["qualified_ids"]:
        return fail(f"qualified ids {ids}")
    if "planted-alias-cmd" not in got["excluded"]["alias"]:
        return fail(f"alias survived {got['excluded']}")
    copy_dropped = (
        "planted-alpha-copy" in got["excluded"]["duplicate"]
        or "planted-alpha-copy" in got["excluded"]["trivial_fork"]
    )
    if not copy_dropped:
        return fail(f"fork/dup survived {got['excluded']}")
    rejected = {x["id"]: x for x in got["failed_three_way_and"]}
    if "planted-license-string-only" not in rejected:
        return fail("licence free-text row counted as fetched")
    if rejected["planted-license-string-only"].get("fetched_licence"):
        return fail("licence string treated as fetched licence")
    if "planted-unclassified" not in rejected:
        return fail("UNKNOWN-NEEDS-PROBE counted as classified")
    if "planted-unresolved-prov" not in rejected:
        return fail("missing provenance path counted as resolved")
    if got["qualified_count"] == raw_naive:
        return fail("qualifier equalled naive raw (no discrimination)")
    if lic_naive >= 6 and got["qualified_count"] == lic_naive:
        return fail("qualifier equalled naive license-string count")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared {st}")
    if "SUCCESS:WFA-0123" not in text:
        return fail("sentinel absent")
    rec_q = (doc.get("both_states") or {}).get("planted_qualified")
    rec_r = (doc.get("both_states") or {}).get("planted_raw")
    if rec_q != got["qualified_count"] or rec_r != 7:
        return fail(f"artifact planted both-states q={rec_q} r={rec_r}")
    if doc.get("qualified_count") is None or doc.get("raw_count") is None:
        return fail("artifact missing raw/qualified")
    if not doc.get("gap_explained"):
        return fail("gap unexplained")
    if int(doc.get("qualified_count", 0)) < 160 and not doc.get("shortfall_route"):
        return fail("shortfall not routed")

    payload = {
        "probe": "probe1-three-way-and-not-raw",
        "unit_id": "WFA-0123",
        "naive_raw": raw_naive,
        "naive_license_string": lic_naive,
        "qualified": got["qualified_count"],
        "qualified_ids": ids,
        "alias_excluded": got["excluded"]["alias"],
        "discriminates": got["qualified_count"] < raw_naive,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"naive_raw={raw_naive} qualified={got['qualified_count']} "
        f"alias={got['excluded']['alias']} copy_dropped={copy_dropped}"
    )
    print("SUCCESS:WFA-0123-probe1 three-way AND is not raw count; planted 7→2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
