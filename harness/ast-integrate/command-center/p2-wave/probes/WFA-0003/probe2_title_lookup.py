#!/usr/bin/env python3
"""Probe 2: reverse-lookup both titles; M-NN 0-identical-titles both-states control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import emit_artifact as E  # noqa: E402
import lib as L  # noqa: E402

ART = REPO / E.OUT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0003-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if E.SENTINEL not in text:
        print("FAILED:WFA-0003-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0003-probe2 self-declared", doc.get("state"))
        return 1

    estate = C.materialize()
    paths = C.five_artifact_paths(estate)
    # Independent of probe 1: rebuild title maps first, then classify intersecting tokens.
    sig_a = L.run_signal_a(paths)
    live_b = L.run_signal_b(paths, sig_a["intersecting"])
    art_b = doc.get("signal_b") or {}
    if live_b["semantic_clash_count"] != art_b.get("semantic_clash_count"):
        print(
            "FAILED:WFA-0003-probe2 clash count drift",
            live_b["semantic_clash_count"],
            art_b.get("semantic_clash_count"),
        )
        return 1
    if live_b["semantic_clash_count"] != 0:
        print("FAILED:WFA-0003-probe2 post-fix semantic clash should be 0")
        return 1

    hist = L.historical_mnn_control(estate)
    print(
        f"pre-fix clashes={hist['semantic_clash_count']} identical={hist['identical_title_count']} "
        f"zero_identical={hist['zero_identical_titles']} "
        f"slice31={hist['published_control_slice']}"
    )
    if not hist["zero_identical_titles"]:
        print("FAILED:WFA-0003-probe2 historical M-NN identical-titles control failed")
        return 1
    slice31 = hist["published_control_slice"]
    if not slice31.get("zero_of_31_identical_titles"):
        print("FAILED:WFA-0003-probe2 0-of-31 identical-titles control failed", slice31)
        return 1

    # Both-states: post-fix silence XOR pre-fix fire.
    if live_b["semantic_clash_count"] == 0 and hist["semantic_clash_count"] > 0:
        both_states = True
    else:
        both_states = False
    print(
        f"both-states postfix_clashes={live_b['semantic_clash_count']} "
        f"prefix_clashes={hist['semantic_clash_count']} xor={both_states}"
    )
    if not both_states:
        print("FAILED:WFA-0003-probe2 both-states control silent-in-both or fire-in-both")
        return 1

    absent_rows = L.absent_class_resolution(estate)
    missing = [
        r["token"]
        for r in absent_rows
        if r["resolve_bare_m_in_doc13"] != "ABSENT"
    ]
    print(f"absent-class n={len(absent_rows)} bare-M-present={missing}")
    if missing:
        print("FAILED:WFA-0003-probe2 required ABSENT ids resolved PRESENT", missing)
        return 1
    mech_missing = [
        r["token"] for r in absent_rows if r["resolve_mech_in_doc13"] != "PRESENT"
    ]
    if mech_missing:
        print("FAILED:WFA-0003-probe2 corresponding MECH cards missing", mech_missing)
        return 1
    art_absent = {r["token"]: r for r in (doc.get("absent_ids") or [])}
    for token in L.ABSENT_CLASS:
        if token not in art_absent:
            print("FAILED:WFA-0003-probe2 artifact omitted ABSENT token", token)
            return 1
        if art_absent[token].get("resolve_bare_m_in_doc13") != "ABSENT":
            print("FAILED:WFA-0003-probe2 artifact ABSENT row stale", token)
            return 1

    pinned = doc.get("pinned_collision_statement") or {}
    log = L.decision_log_facts((estate / "17-DECISION-LOG.md").read_text(encoding="utf-8"))
    if not pinned.get("stale"):
        print("FAILED:WFA-0003-probe2 pinned statement not classified STALE")
        return 1
    if pinned.get("classification") != "STALE":
        print("FAILED:WFA-0003-probe2 classification")
        return 1
    if not log["present_tense_collision_claim"] or not log["zero_mech_tokens"]:
        print("FAILED:WFA-0003-probe2 decision-log fixture drifted")
        return 1
    if "still live" not in (pinned.get("verbatim") or "").lower():
        print("FAILED:WFA-0003-probe2 pinned verbatim missing present-tense claim")
        return 1

    # Titles for a known clash must actually differ.
    sample = next(
        (row for row in hist["clashes"] if row["token"] == "M-16"),
        None,
    )
    if sample is None or len(sample.get("titles") or []) != 2:
        print("FAILED:WFA-0003-probe2 M-16 missing two titles", sample)
        return 1
    print(f"M-16 titles={sample['titles']}")

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe2-title-lookup",
                "postfix_clashes": live_b["semantic_clash_count"],
                "prefix_clashes": hist["semantic_clash_count"],
                "zero_of_31_identical_titles": True,
                "absent_class": list(L.ABSENT_CLASS),
                "pinned_stale": True,
                "unit_id": "WFA-0003",
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0003-probe2 reverse-lookup both-states and ABSENT class")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
