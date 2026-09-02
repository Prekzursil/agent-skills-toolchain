#!/usr/bin/env python3
"""Named probe 1: live five-way differ vs receipt, plus detector controls.

Known-present must stay silent. Deleting one manifest id must grow the
disagreeing-id set by exactly that id. Live pairwise counts/digests must match
the artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import controls as C  # noqa: E402
import differ as D  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0169.json"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:CNF-0169-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, default=str)[:3000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0169":
        return fail("unit_id", doc.get("unit_id"))
    text = json.dumps(doc)
    if "SUCCESS:CNF-0169" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail("self-declared", doc.get("state"))
    if doc.get("report_kind") != "evidence-integrity":
        return fail("report_kind", doc.get("report_kind"))

    ctrls = C.assert_controls()
    present = next(r for r in ctrls["controls"] if r["id"] == "known-present")
    broken = next(r for r in ctrls["controls"] if r["id"] == "known-broken-delete-manifest")
    if not present["silent_on_good_state"]:
        return fail("known-present not silent", present)
    if not broken["fired_on_bad_state"]:
        return fail("known-broken did not fire", broken)
    if not broken["exactly_one_id_difference"]:
        return fail("known-broken did not grow by one id", broken)

    live = D.load_live(REPO)
    art_pairs = doc.get("pairwise_differences") or []
    live_pairs = live["pairwise_differences"]
    if len(art_pairs) != 10 or len(live_pairs) != 10:
        return fail("pair count", {"art": len(art_pairs), "live": len(live_pairs)})
    mismatch = []
    for art, now in zip(art_pairs, live_pairs):
        if art.get("pair") != now["pair"]:
            mismatch.append(("pair", art.get("pair"), now["pair"]))
            continue
        for side in ("left_minus_right", "right_minus_left"):
            a, b = art.get(side) or {}, now[side]
            if a.get("count") != b["count"] or a.get("digest") != b["digest"]:
                mismatch.append((now["pair"], side, a.get("count"), b["count"]))
    if mismatch:
        return fail("live/artifact pairwise mismatch", mismatch[:8])

    for name in D.SOURCES:
        art_src = (doc.get("sources") or {}).get(name) or {}
        live_src = live["sources"][name]
        if art_src.get("present") != live_src["present"]:
            return fail(f"source present drift {name}", { "art": art_src, "live": live_src })
        if art_src.get("id_count") != live_src["id_count"]:
            return fail(f"source id_count drift {name}", {"art": art_src, "live": live_src})

    if doc.get("five_way_agree") is True:
        return fail("five_way_agree true on this divergent tree")
    if live["five_way_agree"] is True:
        return fail("live five_way_agree true on this divergent tree")
    if live["five_way_agree"] != doc.get("five_way_agree"):
        return fail("five_way_agree drift")

    # Absent claim/test registries must be empty membership, not skipped.
    if live["sources"]["claims"]["present"] is False and live["sources"]["claims"]["id_count"] != 0:
        return fail("absent claims not empty")
    if live["sources"]["tests"]["present"] is False and live["sources"]["tests"]["id_count"] != 0:
        return fail("absent tests not empty")

    payload = {
        "pass": True,
        "probe": "probe1-live-controls",
        "unit_id": "CNF-0169",
        "pair_count": 10,
        "five_way_agree": live["five_way_agree"],
        "source_counts": {n: live["sources"][n]["id_count"] for n in D.SOURCES},
        "known_present_silent": True,
        "known_broken_fired": True,
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:CNF-0169-probe1 live differ detector-controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
