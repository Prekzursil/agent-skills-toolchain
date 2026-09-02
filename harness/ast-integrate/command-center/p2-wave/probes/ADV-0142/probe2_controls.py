#!/usr/bin/env python3
"""Probe 2: synthetic negative control + join-necessity retest.

Negative control: the same attack against a synthetic artifact set with no
real identifiers must fail. An attacker that 'succeeds' on synthetic data
is pattern-matching, not re-identifying.

Join-necessity: for each successful identification, withhold the named
minimum set and re-run — the join must fail. Both-states: without the
withhold, the join still exists.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

ART = REPO / E.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0142-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if E.completion_sentinel() not in text:
        return fail("catalog sentinel absent")

    neg = E.negative_control()
    if not neg["attacker_failed_to_identify_anyone"]:
        return fail(
            "synthetic set produced joins or identifications: "
            f"joins={neg['successful_join_count']} "
            f"ids={neg['successful_identification_count']}"
        )
    rec_neg = doc.get("negative_control") or {}
    if rec_neg.get("attacker_failed_to_identify_anyone") is not True:
        return fail("artifact negative_control did not record failure-to-identify")
    if not neg["naive_matcher_would_fire"]:
        return fail("naive titlecase matcher silent on synthetic (vacuous control)")

    recorded = doc.get("successful_joins") or []
    if not isinstance(recorded, list):
        return fail("successful_joins missing")

    paths = E.iter_publishable_paths()
    hits = E.extract_paths(paths)
    live_joins = [
        j
        for j in E.joins_from_hits(hits)
        if j["identification_class"] in E.PERSON_OR_MACHINE
    ]
    live_index = {(j["class"], j["token_id"]): j for j in live_joins}

    retested = 0
    for j in recorded:
        key = (j.get("class"), j.get("token_id"))
        live_j = live_index.get(key)
        if live_j is None:
            return fail(f"recorded join vanished on live re-run: {key}")
        withheld = set(j.get("minimum_withhold") or [])
        kept = set(j.get("kept_after_withhold") or [])
        rule = str(j.get("minimum_withhold_rule") or "")
        named_files = set(withheld) | kept
        for loc in j.get("locations") or []:
            if isinstance(loc, dict) and loc.get("path"):
                named_files.add(loc["path"])
        if not kept:
            return fail(f"join {key} names no kept file")
        if int(j.get("minimum_withhold_count") or 0) < 1 and not withheld:
            return fail(f"join {key} names no withhold set")
        if not j.get("retest_after_withhold", {}).get("join_broken"):
            return fail(f"join {key} artifact retest_join_broken is false")

        if live_j["file_count"] < 2:
            return fail(f"join {key} is not live before withhold")

        if rule == "all_except_kept" or j.get("minimum_withhold_truncated") is True:
            remaining_files = {
                h["path"]
                for h in hits
                if h["class"] == key[0]
                and h["token_id"] == key[1]
                and h["path"] in kept
            }
        else:
            remaining_files = {
                h["path"]
                for h in hits
                if h["class"] == key[0]
                and h["token_id"] == key[1]
                and h["path"] in named_files
                and h["path"] not in withheld
            }
        if len(remaining_files) >= 2:
            return fail(
                f"join {key} survived named withhold remaining={len(remaining_files)}"
            )
        retested += 1

    necessity = doc.get("join_necessity") or {}
    if recorded and necessity.get("every_withhold_retest_broke_the_join") is not True:
        return fail("artifact join_necessity flag is not true")

    print(
        json.dumps(
            {
                "probe": "probe2-controls",
                "unit_id": "ADV-0142",
                "pass": True,
                "negative_control_failed_to_identify": True,
                "naive_titlecase_hits": neg["naive_titlecase_hits"],
                "joins_retested": retested,
                "live_join_count": len(live_joins),
            },
            sort_keys=True,
        )
    )
    print(
        f"neg_ok=True naive_titlecase={neg['naive_titlecase_hits']} "
        f"retested={retested} live_joins={len(live_joins)}"
    )
    print("SUCCESS:ADV-0142-probe2 negative control and join-necessity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
