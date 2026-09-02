#!/usr/bin/env python3
"""Probe 2: event-log cost independence, and reweighting must move a stratum rate.

Reviewer: recompute Pearson r from the raw duration table with an inline formula
(not by calling convenience_bias.pearson_r).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import convenience_bias as CB  # noqa: E402
from event_costs import extract_costs, record_self_report_seconds  # noqa: E402

ART = HERE.parents[3] / "command-center" / "receipts" / "CNF-0144.json"
REPO = HERE.parents[3]


def inline_pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n != len(ys) or n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = dx = dy = 0.0
    for x, y in zip(xs, ys):
        vx = x - mx
        vy = y - my
        num += vx * vy
        dx += vx * vx
        dy += vy * vy
    if dx <= 0.0 or dy <= 0.0:
        return None
    return num / math.sqrt(dx * dy)


def snippet_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNF-0144-probe2 snippet missing in {rel}")
    return text[:idx].count("\n") + 1


def main() -> int:
    rows = CB.ensure_fixtures()
    records = CB.load_json(CB.RECORDS_PATH)
    costs_a = extract_costs(CB.EVENTS_PATH, records)
    flipped = []
    for rec in records:
        copy = dict(rec)
        copy["self_reported_seconds"] = 10**9
        copy["duration_seconds"] = 10**9
        copy["self_reported_tool_count"] = 10**6
        flipped.append(copy)
    costs_b = extract_costs(CB.EVENTS_PATH, flipped)
    if set(costs_a) != set(costs_b):
        print("FAILED:CNF-0144-probe2 cost keys changed after self-report mutation")
        return 1
    for cid in costs_a:
        if costs_a[cid].wall_clock_seconds != costs_b[cid].wall_clock_seconds:
            print(f"FAILED:CNF-0144-probe2 wall_clock mutated for {cid}")
            return 1
        if costs_a[cid].tool_count != costs_b[cid].tool_count:
            print(f"FAILED:CNF-0144-probe2 tool_count mutated for {cid}")
            return 1

    mismatches = 0
    for r in rows:
        sr = r.self_reported_seconds
        if sr is None or r.wall_clock_seconds is None:
            print("FAILED:CNF-0144-probe2 missing cost or self-report")
            return 1
        if abs(sr - r.wall_clock_seconds) < 1e-9:
            mismatches += 1  # they should NOT match
    if mismatches:
        print("FAILED:CNF-0144-probe2 self-report equals event cost; control is inert")
        return 1
    event_order = [
        r.claim_id
        for r in sorted(rows, key=lambda x: x.wall_clock_seconds or 0.0)
    ]
    self_order = [
        r.claim_id
        for r in sorted(rows, key=lambda x: x.self_reported_seconds or 0.0)
    ]
    if event_order == self_order:
        print("FAILED:CNF-0144-probe2 self-report ranking matches event ranking")
        return 1

    # Missing completion events must not fall back to self-report duration.
    orphan_events = CB.FIXTURES / "orphan-events.jsonl"
    orphan_events.write_text(
        json.dumps(
            {
                "event": "dispatch",
                "claim_id": "CLM-ORPHAN",
                "ts": "2026-08-01T00:00:00Z",
                "substrate": "local-parallel",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    orphan_records = [
        {
            "claim_id": "CLM-ORPHAN",
            "self_reported_seconds": 12345.0,
            "duration_seconds": 12345.0,
            "verdict": "CONFIRMED",
        }
    ]
    orphan_costs = extract_costs(orphan_events, orphan_records)
    oc = orphan_costs.get("CLM-ORPHAN")
    if oc is None or oc.wall_clock_seconds is not None:
        print("FAILED:CNF-0144-probe2 missing completion fell back to self-report")
        return 1
    if record_self_report_seconds(orphan_records[0]) != 12345.0:
        print("FAILED:CNF-0144-probe2 control helper did not see self-report")
        return 1

    planted = CB.drop_expensive_completions(rows)
    moved = CB.reweighting_moves_a_stratum(planted, min_abs=0.01)
    if moved["inert"] or not moved["moved"]:
        print("FAILED:CNF-0144-probe2 reweighting inert on planted sample")
        print(json.dumps(moved, sort_keys=True, default=str)[:2000])
        return 1

    src = "command-center/p2-wave/probes/CNF-0144/event_costs.py"
    line_ignore = snippet_line(src, "del records  # duration independence")
    line_load = snippet_line(src, "def load_event_costs(")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:CNF-0144-probe2 self-declared {doc.get('state')}")
            return 1
        table = doc.get("correlation", {}).get("duration_table") or doc.get(
            "duration_table"
        )
        if not table:
            print("FAILED:CNF-0144-probe2 duration table missing from artifact")
            return 1
        xs = [float(row["wall_clock_seconds"]) for row in table]
        ys = [float(row["inclusion"]) for row in table]
        live_r = inline_pearson(xs, ys)
        published = doc.get("correlation", {}).get("pearson", {}).get("r")
        if live_r is None or published is None:
            print("FAILED:CNF-0144-probe2 missing r")
            return 1
        if abs(live_r - float(published)) > 1e-12:
            print(
                f"FAILED:CNF-0144-probe2 reviewer r {live_r} != published {published}"
            )
            return 1
        tests = {t.get("id"): t for t in doc.get("tests") or [] if isinstance(t, dict)}
        for tid in ("cost-independence", "reweighting-noninert"):
            if tests.get(tid, {}).get("result") != "PASS":
                print(f"FAILED:CNF-0144-probe2 artifact test {tid} not PASS")
                return 1
        src_cost = (doc.get("cost_measurement") or {}).get("source")
        if src_cost != "event-log":
            print(f"FAILED:CNF-0144-probe2 cost source {src_cost}")
            return 1
        reviewer_r = live_r
    else:
        reviewer_r = None

    out = {
        "probe": "probe2-independence-and-reweight",
        "unit_id": "CNF-0144",
        "self_report_ignored": True,
        "ranking_diverges": True,
        "orphan_no_fallback": True,
        "reweighting_inert": False,
        "moved_strata": moved["moved"],
        "event_costs_ignore_line": f"{src}:{line_ignore}",
        "event_costs_load_line": f"{src}:{line_load}",
        "reviewer_inline_pearson": reviewer_r,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True, default=str))
    print(
        f"independence_ok=True reweight_moved={len(moved['moved'])} "
        f"reviewer_r={reviewer_r}"
    )
    print("SUCCESS:CNF-0144-probe2 cost independence and reweighting")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
