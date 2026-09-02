#!/usr/bin/env python3
"""Probe 2: balanced both-states + independent recount of effect size.

Statistics-mandate reviewer: re-derives the four share statistics from raw
turn events (text-split tokens, unrebutted claim ids) without calling the
simulator's share helper, then reproduces the reported turn-share delta and
point interval from those integer counts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
from recount import counts_equal, effect_from_counts, recount  # noqa: E402

ART = REPO / "command-center/receipts/TST-0275.json"
SIM = REPO / "tools/council/simulate.py"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0275-probe2 {msg}")
    return 1


def _events(spec, cast, enforce: bool):
    sys.path.insert(0, str(REPO))
    from tools.council.simulate import run_council  # noqa: WPS433

    return run_council(spec, cast, enforce_quotas=enforce, seed=S.SEED)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    if not SIM.is_file():
        return fail("tools/council/simulate.py missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:TST-0275" not in json.dumps(doc):
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    live = S.run_unit()
    bal = live["tests"]["both_states_balanced_unperturbed"]
    if not bal.get("pass"):
        return fail(f"balanced both-states failed {bal}")

    art_bal = doc.get("balanced") or {}
    if (art_bal.get("pre_quota") or {}).get("transcript_sha256") != live["balanced"]["pre_quota"][
        "transcript_sha256"
    ]:
        return fail("balanced pre hash drift")
    if (art_bal.get("post_quota") or {}).get("transcript_sha256") != live["balanced"]["post_quota"][
        "transcript_sha256"
    ]:
        return fail("balanced post hash drift")
    if live["balanced"]["pre_quota"]["transcript_sha256"] != live["balanced"]["post_quota"][
        "transcript_sha256"
    ]:
        return fail("balanced quota perturbed the transcript")

    spec = live["spec"]
    seats = list(live["seats"])
    loud = live["loud_seat"]
    pre_run = _events(spec, live["casts"]["dominant"], False)
    post_run = _events(spec, live["casts"]["dominant"], True)
    pre_rc = recount(pre_run["events"], seats)
    post_rc = recount(post_run["events"], seats)
    if not counts_equal(pre_rc["counts"], live["dominant"]["pre_quota"]["counts"]):
        return fail(f"independent pre counts != live {pre_rc['counts']}")
    if not counts_equal(post_rc["counts"], live["dominant"]["post_quota"]["counts"]):
        return fail(f"independent post counts != live {post_rc['counts']}")
    art_pre_counts = (doc.get("dominant") or {}).get("pre_quota", {}).get("counts")
    art_post_counts = (doc.get("dominant") or {}).get("post_quota", {}).get("counts")
    if not counts_equal(pre_rc["counts"], art_pre_counts or {}):
        return fail("independent pre counts != artifact")
    if not counts_equal(post_rc["counts"], art_post_counts or {}):
        return fail("independent post counts != artifact")

    reproduced = effect_from_counts(pre_rc["counts"], post_rc["counts"], loud, seats)
    reported = doc.get("effect_size") or {}
    for key in ("pre", "post", "delta"):
        got = float(reproduced[key])
        want = float(reported.get(key))
        if abs(got - want) > 1e-12:
            return fail(f"effect_size.{key} reproduced={got} artifact={want}")
    art_iv = list(reported.get("interval") or [])
    if art_iv != reproduced["interval"]:
        return fail(f"interval mismatch reproduced={reproduced['interval']} artifact={art_iv}")
    if reproduced["outcome_dominance_persists"] is not True:
        return fail("independent recount did not find outcome dominance")
    if reported.get("interval_method") != "exact-difference-on-seeded-transcript-N1":
        return fail("artifact interval method missing")

    # Token-count honesty: engine token_count must match whitespace split of text.
    for ev in list(pre_run["events"]) + list(post_run["events"]):
        if ev.get("kind") != "turn":
            continue
        n = len(str(ev.get("text") or "").split())
        if int(ev.get("token_count") or -1) != n:
            return fail(f"token_count {ev.get('token_count')} != text split {n}")

    # Four statistics: reporting only turns would hide the surviving-claims hole.
    keys = ("turns", "tokens", "surviving_claims", "cited_evidence")
    for table in (art_pre_counts, art_post_counts):
        for s in seats:
            for k in keys:
                if k not in (table or {}).get(s, {}):
                    return fail(f"artifact missing count {s}.{k}")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS":
        return fail("artifact reviewer verdict is not PASS")
    if reviewer.get("mandate") != "statistics":
        return fail("artifact reviewer mandate is not statistics")

    out = {
        "probe": "probe2-balanced-recount",
        "unit_id": "TST-0275",
        "balanced_unperturbed": True,
        "independent_counts_match": True,
        "reproduced_delta": reproduced["delta"],
        "artifact_delta": reported.get("delta"),
        "interval": reproduced["interval"],
        "outcome_dominance_persists": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"recount delta={reproduced['delta']:.6f} "
        f"interval={reproduced['interval']} "
        f"balanced_identical=True"
    )
    print("SUCCESS:TST-0275-probe2 balanced-both-states independent-recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
