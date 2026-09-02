#!/usr/bin/env python3
"""Probe 1: declared vs observed load markers on the repaired plugin tree.

Observed ids come only from the session-start log. A config-file listing is
refused as evidence. Every missing marker is named (empty on the repaired tree).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from hook_load.load_probe import (  # noqa: E402
    DEFAULT_PLUGIN,
    attempt_load,
    compare,
    declared_ids,
    listing_hook_files,
)

ART = REPO / "command-center/receipts/IMP-0460.json"
SENTINEL = "SENTINEL:IMP-0460:HOOKS-LOAD-VERIFIED"


def main() -> int:
    declared = declared_ids(DEFAULT_PLUGIN / "hooks.json")
    if len(declared) < 2:
        print("FAILED:IMP-0460-probe1 declared set too small to discriminate")
        return 1

    listing = listing_hook_files(DEFAULT_PLUGIN)
    try:
        compare(
            declared,
            {"source": "config-listing", "observed_ids": listing},
        )
        print("FAILED:IMP-0460-probe1 listing was accepted as load evidence")
        return 1
    except ValueError as exc:
        print(f"listing_refused={type(exc).__name__}")

    with tempfile.TemporaryDirectory(prefix="imp0460-p1-") as tmp:
        load = attempt_load(DEFAULT_PLUGIN, Path(tmp) / "session.jsonl", "probe1")
        cmp = compare(declared, load)

    print(json.dumps({
        "declared_count": cmp["declared_count"],
        "observed_count": cmp["observed_count"],
        "equal": cmp["equal"],
        "missing_markers": cmp["missing_markers"],
        "load_reason": load["load_reason"],
        "source": load["source"],
        "listing_file_count": len(listing),
    }, sort_keys=True))

    if load["source"] != "session-start-log":
        print("FAILED:IMP-0460-probe1 observed source is not the session log")
        return 1
    if not cmp["equal"]:
        print(
            "FAILED:IMP-0460-probe1 repaired tree observed!=declared "
            f"missing={cmp['missing_markers']}"
        )
        return 1
    if cmp["missing_markers"]:
        print("FAILED:IMP-0460-probe1 missing markers not empty on repaired tree")
        return 1
    if cmp["observed_count"] != len(declared):
        print("FAILED:IMP-0460-probe1 observed_count mismatch")
        return 1
    if len(listing) != len(declared):
        print("FAILED:IMP-0460-probe1 fixture listing/declared cardinality drifted")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0460-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:IMP-0460-probe1 sentinel-absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:IMP-0460-probe1 self-declared {doc.get('state')}")
        return 1
    live = doc.get("declared_vs_observed") or {}
    if int(live.get("declared_count") or -1) != cmp["declared_count"]:
        print("FAILED:IMP-0460-probe1 receipt declared_count drifted")
        return 1
    if int(live.get("observed_count") or -1) != cmp["observed_count"]:
        print("FAILED:IMP-0460-probe1 receipt observed_count drifted")
        return 1
    if live.get("equal") is not True:
        print("FAILED:IMP-0460-probe1 receipt equal is not true")
        return 1
    if "missing_markers" not in live or list(live.get("missing_markers")) != []:
        print("FAILED:IMP-0460-probe1 receipt missing_markers not empty")
        return 1

    print(
        f"declared={cmp['declared_count']} observed={cmp['observed_count']} "
        f"missing={cmp['missing_markers']} equal={cmp['equal']}"
    )
    print("SUCCESS:IMP-0460-probe1 declared-vs-observed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
