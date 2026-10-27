#!/usr/bin/env python3
"""CNF-0132 probe1 - planted controls (live, fail-closed).

Runs the rebuilt independence algorithm (graph.py, union-find) over the
rebuilt planted frame and requires the receipt's published planted ranks,
collapse, distribution, and partition property to reproduce exactly.
Structural delivery predicate is asserted first (state, sentinel, bytes).
Rebuilt 2026-10-26 (wave-3 shard 7) after the original probe tree was lost.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import graph  # noqa: E402

OUT = REPO / "command-center/receipts/CNF-0132.json"
FIXTURE = HERE / "fixtures/confirmations.json"
UNIT = "CNF-0132"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def main() -> int:
    fails = []
    checks = []

    def check(ok: bool, label: str, detail: str = "") -> None:
        checks.append({"check": label, "ok": bool(ok), "detail": detail})
        if not ok:
            fails.append(label + (": " + detail if detail else ""))

    # ---- structural delivery predicate ----
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:%s-probe1 artifact unreadable/unparseable: %s" % (UNIT, type(exc).__name__))
        return 1
    if not isinstance(doc, dict):
        print("FAILED:%s-probe1 artifact is not a JSON object" % UNIT)
        return 1
    check(doc.get("unit_id") == UNIT, "unit_id matches catalog unit")
    check(str(doc.get("state", "")).upper() not in NOT_DELIVERING,
          "artifact not self-declared non-delivery", str(doc.get("state")))
    check(OUT.stat().st_size > 0, "artifact non-empty")
    check(OUT.stat().st_size >= int(doc.get("min_bytes_threshold") or 0),
          "artifact above min_bytes_threshold")
    sentinel = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sentinel) and sentinel in text, "sentinel present in artifact text")

    # ---- planted controls: algorithm over the rebuilt frame ----
    if not FIXTURE.is_file():
        check(False, "planted frame exists", str(FIXTURE))
    else:
        frame = graph.load_frame(FIXTURE)
        res = graph.build(frame)
        check(len(frame["records"]) == 8, "frame carries 8 planted records",
              str(len(frame["records"])))
        rec = {c["claim_id"]: c for c in doc["per_claim"]["planted"]}
        for cid in sorted(rec):
            want = rec[cid]
            got = res["per_claim"].get(cid)
            if got is None:
                check(False, "claim rebuilt: " + cid, "missing")
                continue
            check(got["rank"] == want["rank"], "rank matches published: " + cid,
                  "got %s want %s" % (got["rank"], want["rank"]))
            check(got["apparent_n"] == want["apparent_n"],
                  "apparent_n matches published: " + cid)
            check(got["collapsed"] == want["collapsed"],
                  "collapsed matches published: " + cid)
            ws = sorted(want["independent_sets"], key=lambda s: s["component_id"])
            gs = sorted(got["independent_sets"], key=lambda s: s["component_id"])
            if len(ws) != len(gs):
                check(False, "independent-set count matches: " + cid,
                      "%d vs %d" % (len(gs), len(ws)))
                continue
            for w_, g_ in zip(ws, gs):
                check(w_["component_id"] == g_["component_id"],
                      "component id matches: " + cid)
                check(w_["record_ids"] == g_["record_ids"],
                      "component record ids match: " + cid)
                check(w_["shared_upstreams"] == g_["shared_upstreams"],
                      "shared upstreams match: " + cid)
        check(res["rank_distribution"] == doc["rank_distribution"]["planted"],
              "rank distribution matches published planted distribution",
              json.dumps(res["rank_distribution"]))
        check(res["assigned_records"] == res["total_records"] == res["unique_records"] == 8,
              "partition: every record in exactly one node set (8 assigned/8 total/8 unique)")
        collapse = graph.rank1_collapse_report(res, "C-CACHE-COLLAPSE")
        check(collapse["rank"] == 1 and collapse["apparent_n"] == 2,
              "cache collapse reports rank 1 at apparent_n 2")
        check(collapse["shared_upstreams"] == ["cache://shared-blob-9f3c"],
              "cache collapse cites the shared upstream node")

    report = {
        "probe": "probe1-planted-controls",
        "unit_id": UNIT,
        "artifact_bytes": OUT.stat().st_size,
        "checks": checks,
        "fails": fails,
    }
    print(json.dumps(report, indent=1))
    if fails:
        print("FAILED:%s-probe1 %s" % (UNIT, "; ".join(fails)))
        return 1
    print("SUCCESS:%s-probe1 planted controls hold" % UNIT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
