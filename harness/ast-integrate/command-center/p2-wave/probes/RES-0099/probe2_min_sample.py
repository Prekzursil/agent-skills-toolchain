#!/usr/bin/env python3
"""Probe 2: minimum sample below which no FP/FN rate may be quoted.

Control: n=10 labelled known-good with 0 fires MUST be RATE-NOT-QUOTED (quoting
0% would be an overclaim; rule-of-three upper is 30%). n=30 known-good plus
>=5 known-bad MAY be quoted, with a Wilson interval, not a bare percentage.

The artifact must state the same floor. A mutant floor of 1 must not pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import coverage as C  # noqa: E402

ART_REL = "command-center/research/RES-0099.json"
SENTINEL = (
    "SUCCESS:RES-0099 in the receipt AND a field-coverage report against "
    "real existing events plus a stated minimum-sample threshold"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0099-probe2 {msg}")
    return 1


def main() -> int:
    path = REPO / ART_REL
    if not path.is_file():
        return fail("artifact missing")
    art = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(art, ensure_ascii=True)
    if SENTINEL not in text:
        return fail("catalog sentinel absent")

    floor = art.get("minimum_sample") or art.get("min_sample") or {}
    n_min = int(floor.get("min_labelled_n") or 0)
    k_min = int(floor.get("min_per_class") or 0)
    if n_min != C.MIN_LABELLED_N:
        return fail(f"min_labelled_n artifact={n_min} live={C.MIN_LABELLED_N}")
    if k_min != C.MIN_PER_CLASS:
        return fail(f"min_per_class artifact={k_min} live={C.MIN_PER_CLASS}")
    if n_min < 2:
        return fail("mutant floor n=1 would let any rate be quoted")
    if "rule-of-three" not in str(floor.get("why") or "").lower().replace(" ", ""):
        # allow "rule of three" / "rule-of-three"
        why = str(floor.get("why") or "").lower()
        if "rule of three" not in why and "rule-of-three" not in why:
            return fail("minimum-sample why does not cite rule of three")

    # Broken state: too small, or missing the complementary class.
    small = C.quote_rate(k=0, n=10, n_complement=0, kind="fp")
    if small["quoted"] is not False or small["status"] != "RATE-NOT-QUOTED":
        return fail(f"n=10 control quoted a rate: {small}")
    missing_bad = C.quote_rate(k=0, n=30, n_complement=0, kind="fp")
    if missing_bad["quoted"] is not False:
        return fail("n=30 with 0 known-bad quoted FP; FN is unmeasurable")

    # Good state: enough known-good AND enough known-bad.
    ok_fp = C.quote_rate(k=0, n=30, n_complement=5, kind="fp")
    if ok_fp["quoted"] is not True:
        return fail(f"n=30+5 control refused a quote it should allow: {ok_fp}")
    if abs(float(ok_fp["point"]) - 0.0) > 1e-12:
        return fail(f"0/30 point {ok_fp['point']}")
    if float(ok_fp["wilson95_hi"]) <= 0.05:
        return fail("Wilson upper too tight for 0/30; interval is the point of quoting")
    ok_fn = C.quote_rate(k=0, n=30, n_complement=30, kind="fn")
    if ok_fn["quoted"] is not True:
        return fail(f"FN 0/30 with complement 30 should quote: {ok_fn}")

    if small["status"] == ok_fp["status"]:
        return fail("min-sample detector silent in both states")

    live_art_status = (art.get("rate_quote") or art.get("rate_quote") or {}).get("status")
    if live_art_status not in {"RATE-NOT-QUOTED", "NOT-QUOTED"}:
        return fail(f"artifact must not quote a live rate from unlabelled events: {live_art_status}")

    print(
        json.dumps(
            {
                "probe": "probe2_min_sample",
                "min_labelled_n": n_min,
                "min_per_class": k_min,
                "small_n10_quoted": small["quoted"],
                "missing_known_bad_quoted": missing_bad["quoted"],
                "ok_fp_quoted": ok_fp["quoted"],
                "ok_fp_wilson95_hi": ok_fp["wilson95_hi"],
                "ok_fn_quoted": ok_fn["quoted"],
                "rule_of_three_at_min": C.rule_of_three_upper(n_min),
            },
            sort_keys=True,
        )
    )
    print(
        f"floor n>={n_min} per_class>={k_min} "
        f"n10_quoted={small['quoted']} n30c5_quoted={ok_fp['quoted']}"
    )
    print("SUCCESS:RES-0099-probe2 minimum-sample floor both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
