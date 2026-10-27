#!/usr/bin/env python3
"""TST-0032 probe2: test_green_claim_is_blocked_when_a_quarantined_test_is_in_the_path.

Rebuilds the planted suite, recomputes the ledger from raw outcomes (not
from probe1's summary), then asserts the green-claim gate blocks when a
quarantined test is in the path and allows when only DETERMINISTIC tests
are in the path. Known-present run first.
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

    order = [name for name, _ in scenario.build_suite()]
    fp = ledger.worktree_fingerprint(
        [REPO / "command-center" / "lib" / "flake_quarantine" / "ledger.py",
         HERE / "scenario.py", HERE / "probe1_planted_coin_flip.py",
         HERE / "probe2_green_claim_blocked.py"])
    adapted = IndexedSuite(scenario.build_suite())
    built = ledger.measure([(n, f) for n, f in adapted.items()], n=20,
                           fingerprint=fp, order=order,
                           hypothesis="probe2 rebuilds the suite and recomputes from raw outcomes")
    rows = built["rows"]
    recomputed = ledger.independent_ratios(rows)
    ledger_doc = {
        "quarantined": [k for k, v in recomputed.items() if v["quarantined"]],
        "rows": rows,
    }
    check("probe2-rebuilds-and-recomputes-from-raw-outcomes",
          ledger_doc["quarantined"] == scenario.EXPECTED_QUARANTINED
          and receipt["flake_ledger"]["quarantined_named"] == ledger_doc["quarantined"],
          {"live": ledger_doc["quarantined"],
           "recorded": receipt["flake_ledger"]["quarantined_named"]})

    bad = ledger.suite_green_claim(
        claimed_green=True, tests_in_path=["planted.coin_flip"],
        ledger=ledger_doc)
    check("test_green_claim_is_blocked_when_a_quarantined_test_is_in_the_path",
          bad["blocked"] is True and bad["allowed"] is False
          and "quarantined-in-path" in bad["blocked_by"]
          and "planted.coin_flip" in bad["quarantined_in_path"],
          {"blocked": bad["blocked"], "blocked_by": bad["blocked_by"],
           "quarantined_in_path": bad["quarantined_in_path"]})

    good = ledger.suite_green_claim(
        claimed_green=True, tests_in_path=["planted.always_pass"],
        ledger=ledger_doc)
    check("deterministic-path-allows-green",
          good["blocked"] is False and good["allowed"] is True,
          {"blocked": good["blocked"], "allowed": good["allowed"]})
    check("quarantine-still-named-in-report",
          good["quarantine_still_in_report"] is True,
          "the gate stays visible even when the path is clean")

    broken_in = ledger.suite_green_claim(
        claimed_green=True, tests_in_path=["planted.always_fail"],
        ledger=ledger_doc)
    check("broken-in-path-also-blocks",
          broken_in["blocked"] is True and "broken-in-path" in broken_in["blocked_by"],
          {"blocked_by": broken_in["blocked_by"]})

    nc_ids = [nc.get("id") for nc in receipt.get("negative_controls") or []]
    check("receipt-negative-controls-present",
          "quarantined-in-path-blocks-green" in nc_ids
          and "always-pass-not-quarantined" in nc_ids, nc_ids)
    nc = next(nc for nc in receipt.get("negative_controls") or []
              if nc.get("id") == "quarantined-in-path-blocks-green")
    check("receipt-both-states-recorded",
          nc.get("fired_on_bad_state") is True
          and nc.get("silent_on_good_state") is True
          and "blocked=True" in str(nc.get("bad_state_output"))
          and "blocked=False" in str(nc.get("good_state_output")),
          {"bad": str(nc.get("bad_state_output"))[:70],
           "good": str(nc.get("good_state_output"))[:40]})
    check("receipt-known-present-run-first",
          nc.get("known_present_run_first") is True,
          "control ordering recorded")
    check("no-retry-masking-policy",
          receipt["flake_ledger"].get("retry_policy", "").startswith("NO retry"),
          str(receipt["flake_ledger"].get("retry_policy"))[:70])
    check("min-n-recorded", receipt["flake_ledger"].get("min_n") == 20
          and receipt["flake_ledger"].get("n") == 20,
          {"min_n": receipt["flake_ledger"].get("min_n"),
           "n": receipt["flake_ledger"].get("n")})

    out = {"probe": "probe2-green-claim-blocked", "unit_id": "TST-0032",
           "pass": not red, "checks": checks, "red": red}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0 if not red else 1


if __name__ == "__main__":
    raise SystemExit(main())
