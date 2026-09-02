#!/usr/bin/env python3
"""Probe 2: independent clock decay + unreachable is UNKNOWN, never still-fine.

Does not reuse probe 1's archive/relicense assertions. Age is computed by
clock.py, which never inspects license or archived bits.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clock as C  # noqa: E402
import decay as D  # noqa: E402
import live_fetch as LF  # noqa: E402
import registry as R  # noqa: E402

UP = HERE / "fixtures" / "upstream"


def _row(corpus: dict, cid: str) -> dict:
    for item in corpus["candidates"]:
        if item.get("id") == cid:
            return item
    raise KeyError(cid)


def main() -> int:
    now = datetime.now(timezone.utc)
    corpus = R.load_control_corpus()
    aged = D.apply_relative_validated_at(_row(corpus, "ctrl-clock-decay-aged"), now)
    fresh = D.apply_relative_validated_at(
        _row(corpus, "ctrl-adopt-as-is-unchanged"), now
    )
    live_same = LF.load_fixture_live(UP / "unchanged.json")

    interval = D.interval_for(aged)
    clock_aged = C.clock_verdict(aged["adopted"]["validated_at"], interval, now)
    clock_fresh = C.clock_verdict(fresh["adopted"]["validated_at"], interval, now)
    decay_aged = D.revalidate(aged, live_same, now)
    decay_fresh = D.revalidate(fresh, live_same, now)

    print(
        f"clock-aged={clock_aged} decay-aged={decay_aged['verdict']} "
        f"reasons={decay_aged['reasons']} class={decay_aged['new_classification']}"
    )
    print(
        f"clock-fresh={clock_fresh} decay-fresh={decay_fresh['verdict']} "
        f"reasons={decay_fresh['reasons']}"
    )

    aged_ok = (
        clock_aged == "STALE"
        and decay_aged["verdict"] == D.DEMOTE
        and "CLOCK_DECAY" in decay_aged["reasons"]
        and "ARCHIVED" not in decay_aged["reasons"]
        and "RELICENSED" not in decay_aged["reasons"]
        and decay_aged["new_classification"] == D.DEMOTE_CLASS
    )
    fresh_ok = clock_fresh == "FRESH" and decay_fresh["verdict"] == D.KEEP
    if not (aged_ok and fresh_ok):
        print("FAILED:WFA-0159-probe2 clock signal did not discriminate")
        return 1

    # Missing stamp is stale even with identical license/archive/version.
    missing = dict(fresh)
    missing["adopted"] = dict(fresh["adopted"])
    missing["adopted"]["validated_at"] = None
    clock_missing = C.clock_verdict(None, interval, now)
    decay_missing = D.revalidate(missing, live_same, now)
    print(
        f"missing-stamp clock={clock_missing} decay={decay_missing['verdict']} "
        f"reasons={decay_missing['reasons']}"
    )
    if clock_missing != "STALE" or "CLOCK_DECAY" not in decay_missing["reasons"]:
        print("FAILED:WFA-0159-probe2 missing stamp was not STALE")
        return 1

    unreach_c = D.apply_relative_validated_at(
        _row(corpus, "ctrl-unreachable-404"), now
    )
    live_404 = LF.load_fixture_live(UP / "unreachable.json")
    unreach = D.revalidate(unreach_c, live_404, now)
    none_live = D.revalidate(unreach_c, None, now)
    print(
        f"unreachable-404 verdict={unreach['verdict']} reasons={unreach['reasons']} "
        f"class={unreach['new_classification']} note={unreach.get('note')}"
    )
    print(f"unreachable-none verdict={none_live['verdict']} reasons={none_live['reasons']}")
    note = str(unreach.get("note") or "").lower()
    un_ok = (
        unreach["verdict"] == D.UNKNOWN
        and none_live["verdict"] == D.UNKNOWN
        and unreach["new_classification"] == D.DEMOTE_CLASS
        and "UNREACHABLE" in unreach["reasons"]
        and "never still-fine" in note
    )
    if unreach["verdict"] == D.KEEP or none_live["verdict"] == D.KEEP:
        print("FAILED:WFA-0159-probe2 unreachable was treated as still-fine/KEEP")
        return 1
    if not un_ok:
        print("FAILED:WFA-0159-probe2 unreachable was not UNKNOWN")
        return 1

    print("independent-clock-agrees-with-decay-on-age=True")
    print("unreachable=UNKNOWN never-still-fine=True")
    print("SUCCESS:WFA-0159-probe2 clock decay and unreachable UNKNOWN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
