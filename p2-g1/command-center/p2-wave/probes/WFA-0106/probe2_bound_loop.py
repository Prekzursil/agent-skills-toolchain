#!/usr/bin/env python3
"""Probe 2: escalation bound stops an input that would otherwise loop.

Both-states: a stuck never-adequate scheduler with a tight bound stops;
the same scheduler with the bound lifted hits the safety ceiling.
Adequacy is a function of measurable features, not a self-score.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import progressive as P  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0106-fusion-progressive.json"
UNIT = "WFA-0106"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0106" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")

    loop = P.bound_stops_loop()
    if not loop["bound_enforced"]:
        return fail(f"bound not enforced:{loop}")
    if not loop["would_loop"]:
        return fail("unbounded stuck runner did not consume the safety ceiling")
    if loop["bounded_invocations"] != P.MAX_INVOCATIONS:
        return fail(f"bounded invocations={loop['bounded_invocations']}")
    if loop["bounded_stop_reason"] != "escalation-bound":
        return fail(f"bounded stop_reason={loop['bounded_stop_reason']}")
    if loop["unbounded_invocations"] != P.LOOP_SAFETY:
        return fail(f"unbounded invocations={loop['unbounded_invocations']}")
    strikes = loop["bounded_strikes"]
    if not strikes or max(strikes.values()) < 2:
        return fail("stuck path did not record two strikes on one fingerprint")

    good = P.evaluate(P.compose_progressive())
    if good.verdict != "PASS":
        return fail(f"good-state {good.verdict}:{good.reason}")
    bound_hits = sum(1 for row in good.per_case if row["stop_reason"] == "escalation-bound")
    if bound_hits:
        return fail(f"live corpus hit the bound on {bound_hits} cases")

    pred = P.certified_predicate()
    if pred.self_assessment:
        return fail("certified predicate marked self_assessment")
    feat_uncert = P.AdequacyFeatures(
        n=541,
        rung=0,
        gcd_with_base=1,
        trial_bound=7,
        factor_found=None,
        sqrt_covered=False,
        certified=False,
        certification_rule="gcd==1-uncertified",
        self_assessment=False,
    )
    feat_cert = P.AdequacyFeatures(
        n=9,
        rung=0,
        gcd_with_base=3,
        trial_bound=7,
        factor_found=3,
        sqrt_covered=False,
        certified=True,
        certification_rule="gcd-small-factor",
        self_assessment=False,
    )
    if pred.holds(feat_uncert):
        return fail("predicate held on uncertified features")
    if not pred.holds(feat_cert):
        return fail("predicate missed certified features")
    if "confidence" in pred.spec()["inputs"] or "self_score" in pred.spec()["inputs"]:
        return fail("predicate inputs include a self-score")

    art_bound = (doc.get("escalation_bound") or {})
    if art_bound.get("bound_enforced") is not True:
        return fail("artifact bound_enforced stale")
    if art_bound.get("would_loop") is not True:
        return fail("artifact would_loop stale")

    summary = {
        "probe": "probe2-bound-loop",
        "unit_id": UNIT,
        "pass": True,
        "n": loop["n"],
        "bounded_invocations": loop["bounded_invocations"],
        "unbounded_invocations": loop["unbounded_invocations"],
        "would_loop": loop["would_loop"],
        "bound_enforced": loop["bound_enforced"],
        "corpus_bound_hits": bound_hits,
        "predicate_self_assessment": False,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"loop n={loop['n']} bounded={loop['bounded_invocations']} "
        f"unbounded={loop['unbounded_invocations']} bound_enforced=True"
    )
    print("SUCCESS:WFA-0106-probe2 escalation-bound stops would-loop input (both-states)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
