#!/usr/bin/env python3
"""TST-0032 probe1: test_ledger_detects_a_planted_coin_flip_test.

Runs the ledger's N=20 same-order repetitions over the planted suite, then
independently recomputes classification from the raw outcome rows. Asserts
the coin flip is FLAKY and quarantined-named, always_pass is NOT quarantined,
n=19 is refused, and same-fingerprint retry without a changed hypothesis is
refused (retry WITH hypothesis is accepted).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario  # noqa: E402

sys.path.insert(0, str(REPO / "command-center" / "lib"))
from flake_quarantine import ledger  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "TST-0032.json"


class IndexedSuite:
    """Adapter so each repetition knows its index (seeded draws advance)."""

    def __init__(self, suite):
        self.suite = suite
        self.counters = {name: 0 for name, _ in suite}

    def items(self):
        out = []
        for name, fn in self.suite:
            counter = {"i": 0}

            def call(fn=fn, counter=counter):
                idx = counter["i"]
                counter["i"] += 1
                fn(idx)

            out.append((name, call))
        return out


def main() -> int:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    checks = []
    red = []

    def check(name, ok, detail):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})
        if not ok:
            red.append(name)

    suite = scenario.build_suite()
    order = [name for name, _ in suite]
    fp = ledger.worktree_fingerprint(
        [REPO / "command-center" / "lib" / "flake_quarantine" / "ledger.py",
         HERE / "scenario.py", HERE / "probe1_planted_coin_flip.py",
         HERE / "probe2_green_claim_blocked.py"])
    adapted = IndexedSuite(suite)
    items = [(name, fn) for name, fn in adapted.items()]
    result = ledger.measure(items, n=20, fingerprint=fp, order=order)

    classes = {r["id"]: r["class"] for r in result["rows"]}
    ratios = {r["id"]: r["pass_ratio"] for r in result["rows"]}
    check("test_ledger_detects_a_planted_coin_flip_test",
          classes["planted.coin_flip"] == "FLAKY"
          and "planted.coin_flip" in result["quarantined_named"],
          {"class": classes["planted.coin_flip"],
           "quarantined_named": result["quarantined_named"]})
    check("always-pass-deterministic-not-quarantined",
          classes["planted.always_pass"] == "DETERMINISTIC"
          and "planted.always_pass" not in result["quarantined"],
          classes["planted.always_pass"])
    check("rare-flake-named", classes["planted.rare_flake"] == "FLAKY"
          and "planted.rare_flake" in result["quarantined_named"],
          classes["planted.rare_flake"])
    check("always-fail-broken-not-quarantined",
          classes["planted.always_fail"] == "BROKEN"
          and "planted.always_fail" not in result["quarantined"],
          "BROKEN is reported, not hidden in quarantine")
    check("live-ratios-match-recorded",
          ratios == scenario.EXPECTED_RATIOS
          and ratios == receipt["measured_flake_rate"]["per_test_pass_ratio"],
          {"live": ratios,
           "recorded": receipt["measured_flake_rate"]["per_test_pass_ratio"]})
    check("same-order-same-sha", result["order"] == order
          and result["sha"] == fp["sha"],
          {"n": result["n"], "sha_prefix": result["sha"][:12]})

    recompute = ledger.independent_ratios(result["rows"])
    check("independent-recompute-agrees",
          {k: v["class"] for k, v in recompute.items()} == classes
          and {k: v["quarantined"] for k, v in recompute.items()}
          == {k: k in scenario.EXPECTED_QUARANTINED for k in classes},
          {k: recompute[k]["class"] for k in recompute})
    check("receipt-independent-recompute-matches",
          receipt["flake_ledger"]["independent_recompute"]["planted.coin_flip"]["class"] == "FLAKY"
          and receipt["flake_ledger"]["independent_recompute"]["planted.coin_flip"]["quarantined"] is True
          and receipt["flake_ledger"]["independent_recompute"]["planted.always_pass"]["quarantined"] is False,
          "receipt recompute block agrees with live recompute")

    refused = False
    try:
        ledger.measure(scenario.build_suite(), n=19, fingerprint=fp)
    except ledger.InsufficientRepetitionsError:
        refused = True
    check("n19-refused", refused, "MIN_N=20; n=19 raises InsufficientRepetitionsError")

    retry_refused = False
    prior = {"sha": fp["sha"], "order": order, "n": 20}
    try:
        ledger.measure(scenario.build_suite(), n=20, fingerprint=fp,
                       order=order, prior=prior)
    except ledger.RetryWithoutHypothesisError:
        retry_refused = True
    check("same-fingerprint-retry-without-hypothesis-refused",
          retry_refused, "identical (sha, order, n) raises")
    accepted = ledger.measure(
        scenario.build_suite(), n=20, fingerprint=fp, order=order, prior=prior,
        hypothesis="probe1 re-run under changed hypothesis: re-verify FLAKY classes")
    check("retry-with-changed-hypothesis-accepted",
          accepted["hypothesis"] is not None,
          str(accepted["hypothesis"])[:60])

    out = {"probe": "probe1-planted-coin-flip", "unit_id": "TST-0032",
           "pass": not red, "checks": checks, "red": red}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0 if not red else 1


if __name__ == "__main__":
    raise SystemExit(main())
