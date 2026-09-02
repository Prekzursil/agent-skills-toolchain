#!/usr/bin/env python3
"""Named probe 1: per-artifact existence in each tree, reported per tree.

A harness that can only emit the union cannot satisfy the control: the
fixture union is 29 while each tree is 17 and 20.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from census import live_census, probe1_payload  # noqa: E402
from common import OUT, UNIT  # noqa: E402


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    live = live_census()
    ctl = live["control"]
    if ctl["count_a"] >= 29 or ctl["count_b"] >= 29:
        return fail("control per-tree count collapsed to 29", ctl)
    if ctl["union_count"] != 29:
        return fail("control union is not 29", ctl)
    if ctl["count_a"] != 17 or ctl["count_b"] != 20:
        return fail("control per-tree counts are not 17/20", ctl)
    if ctl["holds_in_single_tree"]:
        return fail("control claimed a single tree holds 29")

    art_counts = doc.get("per_tree_counts") or {}
    if art_counts.get("harness-restore") != live["per_tree_counts"]["harness-restore"]:
        return fail("artifact harness-restore count != live", art_counts)
    if art_counts.get("repo") != live["per_tree_counts"]["repo"]:
        return fail("artifact repo count != live", art_counts)
    if doc.get("union_count") != live["union_count"]:
        return fail("artifact union_count != live")
    if doc.get("holds_in_single_tree") is True and live["union_count"] < 29:
        return fail("artifact claimed single-tree 29 while live union is below 29")
    if any(int(v) >= 29 for v in art_counts.values()) and live["union_count"] < 29:
        return fail("per-tree count of 29 with live union below 29; union-only harness")

    art_ctl = (doc.get("control") or {}).get("count_a")
    if art_ctl != 17:
        return fail("artifact did not record control per-tree count 17", doc.get("control"))

    payload = probe1_payload(live)
    (HERE / "probe1-per-tree.raw.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:AUD-0067-probe1 per-tree existence counts (not union)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
