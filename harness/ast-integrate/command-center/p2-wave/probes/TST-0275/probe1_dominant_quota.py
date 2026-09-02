#!/usr/bin/env python3
"""Probe 1: planted dominant persona, quota bounds turns, outcome dominance.

Re-runs the simulator live and checks the catalog tests that turn share is
skewed before quota and bounded after, while surviving-claims share still
exceeds turn share. Also checks same-seed determinism and that the receipt
carries all four share statistics per seat.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0275.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0275-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(doc)
    if "SUCCESS:TST-0275" not in text:
        return fail("sentinel-absent")
    if doc.get("unit_id") != "TST-0275":
        return fail(f"unit_id {doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    live = S.run_unit()
    if not live.get("pass"):
        return fail(f"live unit tests failed {json.dumps(live.get('tests'), sort_keys=True)[:1500]}")

    tests = live["tests"]
    for name in (
        "planted_dominant_pre_quota_skew",
        "post_quota_turn_share_bounded",
        "outcome_dominance_persists_after_turn_cap",
        "four_share_statistics_present",
        "same_seed_determinism",
    ):
        if not tests[name]["pass"]:
            return fail(f"test {name} failed {tests[name]}")

    art_pre = (doc.get("dominant") or {}).get("pre_quota") or {}
    art_post = (doc.get("dominant") or {}).get("post_quota") or {}
    live_pre = live["dominant"]["pre_quota"]
    live_post = live["dominant"]["post_quota"]
    if art_pre.get("transcript_sha256") != live_pre["transcript_sha256"]:
        return fail("artifact pre transcript hash != live")
    if art_post.get("transcript_sha256") != live_post["transcript_sha256"]:
        return fail("artifact post transcript hash != live")
    if art_pre.get("counts") != live_pre["counts"]:
        return fail("artifact pre counts drift")
    if art_post.get("counts") != live_post["counts"]:
        return fail("artifact post counts drift")

    loud = live["loud_seat"]
    post_turns = live_post["shares"][loud]["turns"]
    post_surv = live_post["shares"][loud]["surviving_claims"]
    if post_surv <= post_turns:
        return fail("surviving claims share did not exceed turn share after cap")

    effect = doc.get("effect_size") or {}
    if effect.get("hidden_by_turn_share_only") is not True:
        return fail("artifact does not record that turn-share-only would hide outcome dominance")

    out = {
        "probe": "probe1-dominant-quota",
        "unit_id": "TST-0275",
        "loud": loud,
        "pre_turn_share": live_pre["shares"][loud]["turns"],
        "post_turn_share": post_turns,
        "post_surviving_claims_share": post_surv,
        "pre_sha256": live_pre["transcript_sha256"],
        "post_sha256": live_post["transcript_sha256"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"loud pre_turns={live_pre['counts'][loud]['turns']} "
        f"post_turns={live_post['counts'][loud]['turns']} "
        f"post_surviving={live_post['counts'][loud]['surviving_claims']} "
        f"pre_share={out['pre_turn_share']:.4f} post_share={post_turns:.4f} "
        f"surv_share={post_surv:.4f}"
    )
    print("SUCCESS:TST-0275-probe1 planted-dominant quota-bounds outcome-dominance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
