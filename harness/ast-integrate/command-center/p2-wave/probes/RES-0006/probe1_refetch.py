#!/usr/bin/env python3
"""Probe 1: tracker re-fetches 50 sources twice at >=24h and matches the artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from catalog import CLASSES  # noqa: E402
from tracker import measure  # noqa: E402

ART = REPO / "command-center/research/RES-0006.json"
SENTINEL = (
    "SUCCESS:RES-0006 in the receipt AND a per-class half-life table "
    "backed by >=2 timestamped snapshots per tracked source"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0006-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "RES-0006":
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    live = measure()
    if live["n_sources"] != 50:
        return fail(f"n_sources={live['n_sources']}")
    if live["n_classes"] != 16 or tuple(CLASSES) != tuple(doc.get("source_classes") or ()):
        return fail("class census")
    if not live["interval_ok"] or live["observation_hours"] < 24:
        return fail(f"interval {live['observation_hours']}")
    if any(len(r["snapshots"]) < 2 for r in live["sources"]):
        return fail("a source has <2 snapshots")

    art_sources = doc.get("sources") or []
    if len(art_sources) != 50:
        return fail(f"artifact sources={len(art_sources)}")
    live_ids = [r["id"] for r in live["sources"]]
    art_ids = [r["id"] for r in art_sources]
    if live_ids != art_ids:
        return fail("source id order mismatch")

    for live_row, art_row in zip(live["sources"], art_sources):
        if live_row["changed"] != art_row.get("changed"):
            return fail(f"changed mismatch {live_row['id']}")
        ls = live_row["snapshots"]
        as_ = art_row.get("snapshots") or []
        if len(as_) < 2:
            return fail(f"artifact snapshots {live_row['id']}")
        if ls[0]["sha256"] != as_[0].get("sha256") or ls[1]["sha256"] != as_[1].get("sha256"):
            return fail(f"sha256 mismatch {live_row['id']}")
        if ls[0]["fetched_at"] != as_[0].get("fetched_at"):
            return fail(f"wave1 timestamp mismatch {live_row['id']}")
        if ls[1]["fetched_at"] != as_[1].get("fetched_at"):
            return fail(f"wave2 timestamp mismatch {live_row['id']}")

    art_table = doc.get("half_life_table") or []
    if len(art_table) != 16:
        return fail(f"half_life_table rows={len(art_table)}")
    for live_row, art_row in zip(live["half_life_table"], art_table):
        if live_row["source_class"] != art_row.get("source_class"):
            return fail("class order")
        if live_row["n_changed"] != art_row.get("n_changed"):
            return fail(f"churn {live_row['source_class']}")
        if live_row["n_sources"] != art_row.get("n_sources"):
            return fail(f"n {live_row['source_class']}")

    tests = {t["id"]: t["result"] for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in ("refetch-50-twice-24h", "archived-tag-zero-churn"):
        if tests.get(tid) != "PASS":
            return fail(f"artifact test {tid}={tests.get(tid)}")

    print(
        "n_sources=50 n_classes=16 n_changed="
        f"{live['n_changed']} interval_h={live['observation_hours']} "
        "min_snapshots=2"
    )
    print("SUCCESS:RES-0006-probe1 refetch-50-twice-24h per-class-churn")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
