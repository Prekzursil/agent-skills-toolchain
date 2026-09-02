#!/usr/bin/env python3
"""Named probe 1: per-class freshness windows and the age histogram.

Loads the recorded-council fixture, stamps every anchor, and answers:
how many anchors at decision time are older than their class window?
A planted mixed set must show a non-zero stale count. Fresh twins of the
same class stay admitted. The binding gate refuses the whole decision
while any stale anchor remains unrevalidated.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.evidence.freshness import (  # noqa: E402
    FRESH,
    STALE,
    admit_for_binding,
    age_histogram,
    bind_on_fresh_anchors,
    is_stale,
    load_recorded_council,
    window_for,
)

FIXTURE = HERE / "fixtures" / "recorded-council.json"
SOURCES = HERE / "fixtures" / "sources"
EXPECTED_STALE = {
    "A-LIVE-STALE",
    "A-MEAS-STALE",
    "A-DOC-STALE",
    "A-ANEC-STALE",
}
EXPECTED_FRESH = {
    "A-LIVE-FRESH",
    "A-EXEC-FRESH",
    "A-PEER-FRESH",
    "A-ARCH-FRESH",
}


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0257-probe1 {msg}")
    return 1


def main() -> int:
    recorded = load_recorded_council(FIXTURE, sources_root=SOURCES)
    now = recorded["decision_at"]
    anchors = recorded["anchors"]
    if len(anchors) != 8:
        return fail(f"expected 8 anchors, got {len(anchors)}")

    hist = age_histogram(anchors, now)
    stale_ids = set(hist["stale_ids"])
    fresh_ids = set(hist["fresh_ids"])
    if stale_ids != EXPECTED_STALE:
        return fail(f"stale_ids={sorted(stale_ids)} want {sorted(EXPECTED_STALE)}")
    if fresh_ids != EXPECTED_FRESH:
        return fail(f"fresh_ids={sorted(fresh_ids)} want {sorted(EXPECTED_FRESH)}")
    if hist["n_stale"] != 4 or hist["n_fresh"] != 4:
        return fail(f"histogram n_stale={hist['n_stale']} n_fresh={hist['n_fresh']}")

    # Per-class window enforcement: same age, different class => different verdict.
    live_stale = next(a for a in anchors if a["anchor_id"] == "A-LIVE-STALE")
    live_fresh = next(a for a in anchors if a["anchor_id"] == "A-LIVE-FRESH")
    if window_for("live-url") != 3600.0:
        return fail(f"live-url window {window_for('live-url')}")
    if window_for("documentation") == window_for("live-url"):
        return fail("documentation window collapsed onto live-url")
    if not is_stale(live_stale, now):
        return fail("A-LIVE-STALE was not stale at decision time")
    if is_stale(live_fresh, now):
        return fail("A-LIVE-FRESH was stale (class window not applied)")
    # documentation 10d stale, peer-reviewed 30d still fresh
    doc = next(a for a in anchors if a["anchor_id"] == "A-DOC-STALE")
    peer = next(a for a in anchors if a["anchor_id"] == "A-PEER-FRESH")
    if not is_stale(doc, now) or is_stale(peer, now):
        return fail("documentation/peer-reviewed windows mixed")

    decision = bind_on_fresh_anchors(anchors, now, require_all_fresh=True)
    if decision["binding"] is True:
        return fail("binding allowed while 4 stale anchors were unrevalidated")
    if set(decision["stale_excluded"]) != EXPECTED_STALE:
        return fail(f"stale_excluded={decision['stale_excluded']}")
    if set(decision["supporting_anchor_ids"]) != EXPECTED_FRESH:
        return fail(f"supporting={decision['supporting_anchor_ids']}")
    for aid in EXPECTED_STALE:
        if aid in decision["supporting_anchor_ids"]:
            return fail(f"stale {aid} carried the binding decision")

    # Known-good twin: restamp A-LIVE-STALE as_of=now and it must admit.
    restamped = dict(live_stale)
    restamped["as_of_unix"] = now
    restamped["as_of"] = live_fresh["as_of"]
    if admit_for_binding(restamped, now)["freshness"] != FRESH:
        return fail("restamped stale twin did not become FRESH")
    if admit_for_binding(live_stale, now)["freshness"] != STALE:
        return fail("original stale twin did not stay STALE")

    payload = {
        "probe": "probe1-class-windows",
        "unit_id": "IMP-0257",
        "council_id": recorded["council_id"],
        "decision_at": now,
        "n_anchors": hist["n_anchors"],
        "n_stale": hist["n_stale"],
        "n_fresh": hist["n_fresh"],
        "stale_ids": hist["stale_ids"],
        "fresh_ids": hist["fresh_ids"],
        "age_bins": hist["age_bins"],
        "by_class": {
            k: {"n": v["n"], "n_stale": v["n_stale"], "n_fresh": v["n_fresh"], "window_s": v["window_s"]}
            for k, v in hist["by_class"].items()
        },
        "binding": decision["binding"],
        "refuse_reason": decision["refuse_reason"],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"n_stale={hist['n_stale']} n_fresh={hist['n_fresh']} "
        f"binding={decision['binding']} refused={decision['refuse_reason']}"
    )
    print("SUCCESS:IMP-0257-probe1 class-window histogram and binding refusal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
