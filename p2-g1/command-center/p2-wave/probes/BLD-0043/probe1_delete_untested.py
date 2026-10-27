#!/usr/bin/env python3
"""BLD-0043 probe1 - structural + sentinel delivery predicate (live, fail-closed).

Checks the live join (9 catalog floors, 67 tests, 0 structural mappings, all 9 floors untested), the synthetic fixture corpus (11 mappings across the three accepted channels, comment-only unmapped), and the three controls.
Recreated 2026-10-25 (wave-2 shard 7) after the original probe tree was lost.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = REPO / "command-center/receipts/BLD-0043.json"
UNIT = "BLD-0043"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def main() -> int:
    fails = []
    notes = []

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(label + (": " + detail if detail else ""))

    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:%s-probe1 artifact unreadable/unparseable: %s" % (UNIT, type(exc).__name__))
        return 1
    if not isinstance(doc, dict):
        print("FAILED:%s-probe1 artifact is not a JSON object" % UNIT)
        return 1

    check(doc.get("unit_id") == UNIT, "unit_id mismatch", str(doc.get("unit_id")))
    check(str(doc.get("state", "")).upper() not in NOT_DELIVERING,
          "self-declared non-delivery", str(doc.get("state")))
    check(OUT.stat().st_size > 0, "artifact empty")
    minb = int(doc.get("min_bytes_threshold") or 0)
    check(OUT.stat().st_size >= minb, "below min_bytes_threshold",
          "%s < %s" % (OUT.stat().st_size, minb))
    sentinel = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sentinel) and sentinel in text, "sentinel absent from artifact text")

    reqs = doc.get("requirements") or []
    untested = doc.get("untested_requirements") or []
    live = doc.get("live") or {}
    fx = doc.get("fixture_corpus") or {}
    check(len(reqs) == 9, "requirement rows != 9", str(len(reqs)))
    want = {"REQ-CC0024-F0%d" % i for i in range(1, 10)}
    got = {str(r.get("id")) for r in reqs}
    check(got == want, "requirement ids drift", str(sorted(got ^ want)))
    check(int(live.get("requirement_count", -1)) == 9, "live.requirement_count != 9", str(live.get("requirement_count")))
    check(int(live.get("test_count", -1)) == 67, "live.test_count != 67", str(live.get("test_count")))
    check(int(live.get("mapping_count", -1)) == 0, "live.mapping_count != 0", str(live.get("mapping_count")))
    check(int(live.get("untested_count", -1)) == 9, "live.untested_count != 9", str(live.get("untested_count")))
    check(int(live.get("orphan_count", -1)) == 67, "live.orphan_count != 67", str(live.get("orphan_count")))
    check(len(untested) == 9, "untested rows != 9", str(len(untested)))
    check(all(u.get("id") in want and str(u.get("reason", "")).strip() for u in untested),
          "untested rows lack id-in-reqs or reason")
    mappings = fx.get("mappings") or []
    check(int(fx.get("mapping_count", -1)) == len(mappings) == 11,
          "fixture mapping_count/rows != 11", "%s/%d" % (fx.get("mapping_count"), len(mappings)))
    vocab = {"test-id", "marker", "registry-entry"}
    check(all(str(m.get("channel")) in vocab for m in mappings), "fixture channel outside accepted vocabulary")
    co = fx.get("comment_only") or []
    check(len(co) == 1 and "unmapped" in str(co[0].get("reason", "")),
          "comment-only fixture row missing/unmapped-reason")
    check(int(fx.get("orphan_count", -1)) == 2, "fixture orphan_count != 2", str(fx.get("orphan_count")))
    cls = {str(o.get("classification")) for o in fx.get("orphan_tests") or []}
    check(cls <= {"promote", "retire"} and cls, "fixture orphan classes outside promote/retire", str(cls))
    ctrls = doc.get("controls") or []
    check(len(ctrls) == 3 and all(c.get("pass") is True for c in ctrls),
          "controls != 3 rows or non-passing", str([(c.get("id"), c.get("pass")) for c in ctrls]))
    for name in ("fixtures/mapped_tests.py", "fixtures/comment_only.py"):
        check((HERE / name).is_file(), "fixture file missing", name)

    report = {
        "probe": "probe1-delivery-predicate",
        "unit_id": UNIT,
        "artifact_bytes": OUT.stat().st_size,
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1))
    if fails:
        print("FAILED:%s-probe1 %s" % (UNIT, "; ".join(fails)))
        return 1
    print("SUCCESS:%s-probe1 delivery predicate holds" % UNIT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
