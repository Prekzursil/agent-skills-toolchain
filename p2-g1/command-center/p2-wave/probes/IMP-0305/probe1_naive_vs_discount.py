#!/usr/bin/env python3
"""Probe 1: same inputs, naive vs correlation-discounted pooling.

Both-states:
  FIRE  — fully-correlated clones, naive independent-evidence pooling is
          near-certain (overconfidence manufactured).
  SILENT — the same clones with the correlation discount stay at the
           single-voice credence, not near-certain.

A second mechanism (hand logit recomputation) must agree with bayes.py.
Undeclared independence (missing vendor+context, no declared_rho) must
raise. Per-run threshold override must be refused.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.vote.bayes import (  # noqa: E402
    PerRunThresholdTuneError,
    UndeclaredIndependenceError,
    clone_both_states,
    clone_panel,
    independent_panel,
    is_near_certain,
    load_near_certain_spec,
    logit,
    n_effective,
    pool,
    pool_with_and_without_discount,
    sigmoid,
)

ART = REPO / "command-center/receipts/IMP-0305.json"
SENTINEL = "SUCCESS:IMP-0305"
CLONE_P = 0.80
N = 8


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0305-probe1 {msg}")
    return 1


def _hand_naive(credence: float, n: int) -> float:
    return sigmoid(n * logit(credence))


def _hand_discounted(credence: float, n: int, rho: float) -> float:
    return sigmoid(n_effective(n, rho) * logit(credence))


def main() -> int:
    spec = load_near_certain_spec()
    refused = False
    try:
        load_near_certain_spec(override=0.5)
    except PerRunThresholdTuneError:
        refused = True
    print(f"threshold_override_refused={refused} threshold={spec['threshold']}")
    if not refused:
        return _fail("per-run threshold override was accepted")
    if spec["threshold"] != 0.99 or spec["id"] != "imp-0305-near-certain-v1":
        return _fail(f"unexpected spec {spec}")

    undeclared_fired = False
    try:
        pool([{"participant_id": "x", "credence": 0.8}], discount=True)
    except UndeclaredIndependenceError:
        undeclared_fired = True
    print(f"undeclared_independence_fired={undeclared_fired}")
    if not undeclared_fired:
        return _fail("missing vendor+context did not refuse pooling")

    clones = clone_panel(CLONE_P, N)
    both = pool_with_and_without_discount(clones)
    naive = both["naive"]
    disc = both["discounted"]
    hand_n = _hand_naive(CLONE_P, N)
    hand_d = _hand_discounted(CLONE_P, N, 1.0)

    print(
        json.dumps(
            {
                "probe": "probe1-naive-vs-discount",
                "clone_credence": CLONE_P,
                "n": N,
                "naive_pooled": naive["pooled_credence"],
                "discounted_pooled": disc["pooled_credence"],
                "hand_naive": hand_n,
                "hand_discounted": hand_d,
                "naive_n_eff": naive["n_effective"],
                "discounted_n_eff": disc["n_effective"],
                "roster_rho": disc["rho_measured_roster"],
                "naive_near_certain": naive["near_certain"],
                "discounted_near_certain": disc["near_certain"],
                "void": disc["independence_assumption_void"],
            },
            indent=1,
            sort_keys=True,
        )
    )

    if not both["same_inputs"] or not both["same_n"]:
        return _fail("naive and discounted did not share inputs")
    if abs(naive["pooled_credence"] - hand_n) > 1e-12:
        return _fail("naive disagrees with hand logit product")
    if abs(disc["pooled_credence"] - hand_d) > 1e-12:
        return _fail("discount disagrees with hand n_eff shrink")
    if abs(disc["pooled_credence"] - CLONE_P) > 1e-12:
        return _fail("rho=1 discounted pool is not the single-voice credence")
    if abs(disc["n_effective"] - 1.0) > 1e-12:
        return _fail(f"rho=1 n_eff={disc['n_effective']} not 1")
    if abs(naive["n_effective"] - float(N)) > 1e-12:
        return _fail(f"naive n_eff={naive['n_effective']} not {N}")
    if not naive["near_certain"]:
        return _fail("naive clone panel was not near-certain (FIRE expected)")
    if disc["near_certain"]:
        return _fail("discounted clone panel was near-certain (SILENT expected)")
    if not disc["independence_assumption_void"]:
        return _fail("clone roster did not void independence")
    if naive["assumption"] != "naive-independent-evidence":
        return _fail("naive path did not declare independent-evidence")
    if disc["assumption"] != "exchangeable-with-rho":
        return _fail("discount path did not declare exchangeable-with-rho")
    if disc["rho_measured_roster"] != 1.0:
        return _fail(f"clone roster rho={disc['rho_measured_roster']}")

    # Known-good: eight distinct vendor+context voices, same credence.
    # Independence is not void; discount matches naive (rho=0).
    ind = pool_with_and_without_discount(independent_panel(CLONE_P, N))
    print(
        f"independent_rho={ind['discounted']['rho_measured_roster']} "
        f"naive={ind['naive']['pooled_credence']} "
        f"disc={ind['discounted']['pooled_credence']} "
        f"void={ind['discounted']['independence_assumption_void']}"
    )
    if ind["discounted"]["rho_measured_roster"] != 0.0:
        return _fail("distinct-vendor roster rho was not 0")
    if ind["discounted"]["independence_assumption_void"]:
        return _fail("distinct-vendor panel wrongly voided independence")
    if abs(ind["naive"]["pooled_credence"] - ind["discounted"]["pooled_credence"]) > 1e-12:
        return _fail("rho=0 discount diverged from naive")
    if abs(ind["naive"]["pooled_credence"] - hand_n) > 1e-12:
        return _fail("independent naive is not the n-fold log-odds product")

    ctrl = clone_both_states(CLONE_P, N)
    if not ctrl["negative_control_naive_is_near_certain"]:
        return _fail("negative-control naive not near-certain")
    if not ctrl["negative_control_discounted_not_near_certain"]:
        return _fail("negative-control discounted WAS near-certain")

    planted_bad = is_near_certain(naive["pooled_credence"], spec)
    known_good = not is_near_certain(disc["pooled_credence"], spec)
    print(f"planted_bad_fires={planted_bad} known_good_silent={known_good}")
    if not planted_bad or not known_good:
        return _fail("both-states detector failed")

    if not ART.is_file():
        return _fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return _fail("sentinel-absent")
    if doc.get("unit_id") != "IMP-0305":
        return _fail(f"unit_id={doc.get('unit_id')}")
    rec_naive = float(doc["same_inputs"]["naive_pooled"])
    rec_disc = float(doc["same_inputs"]["discounted_pooled"])
    if abs(rec_naive - naive["pooled_credence"]) > 1e-12:
        return _fail("receipt naive_pooled stale vs live")
    if abs(rec_disc - disc["pooled_credence"]) > 1e-12:
        return _fail("receipt discounted_pooled stale vs live")
    if "low" in str(doc.get("same_inputs", {})).lower() and "pooled" not in str(doc.get("same_inputs")):
        return _fail("receipt used an adjective instead of a number")

    print(
        "SUCCESS:IMP-0305-probe1 naive-overconfident discounted-silent "
        f"naive={naive['pooled_credence']:.12f} discounted={disc['pooled_credence']:.12f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
