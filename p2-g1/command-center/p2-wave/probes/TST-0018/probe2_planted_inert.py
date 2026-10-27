#!/usr/bin/env python3
"""TST-0018 probe2: planted inert detector + known-good two-state control.

test_scanner_flags_a_planted_inert_detector: a stub whose output is
byte-identical on the known-good and known-broken fixture is classified
INERT and named.
test_scanner_does_not_flag_a_known_good_detector: a detector whose output
differs between the two states is never flagged.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RECEIPT = REPO / "command-center" / "receipts" / "TST-0018.json"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scanner  # noqa: E402


def planted_inert_stub(state_fixture):
    """The planted defect: same verdict no matter which fixture it inspects."""
    return {"fired": True, "payload": "FIRED"}


def two_state_valid(state_fixture):
    """The control: output actually depends on the fixture state."""
    if state_fixture["healthy"]:
        return {"fired": True, "payload": "FIRED"}
    return {"fired": False, "payload": "NOT-FIRED"}


def run_detector(fn, good_fixture, broken_fixture):
    return {
        "detector_id": fn.__name__,
        "checked": True,
        "good_output": fn(good_fixture),
        "broken_output": fn(broken_fixture),
    }


def main() -> int:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    checks = []
    red = []

    def check(name, ok, detail):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})
        if not ok:
            red.append(name)

    good_fixture = {"healthy": True}
    broken_fixture = {"healthy": False}

    rows = [
        run_detector(planted_inert_stub, good_fixture, broken_fixture),
        run_detector(two_state_valid, good_fixture, broken_fixture),
    ]
    res = scanner.scan(rows)
    planted = next(v for v in res["verdicts"]
                   if v["detector_id"] == "planted_inert_stub")
    control = next(v for v in res["verdicts"]
                   if v["detector_id"] == "two_state_valid")

    # test_scanner_flags_a_planted_inert_detector
    check("test_scanner_flags_a_planted_inert_detector",
          planted["inert"] is True and planted["verdict"] == "IDENTICAL",
          planted)
    # test_scanner_does_not_flag_a_known_good_detector
    check("test_scanner_does_not_flag_a_known_good_detector",
          control["inert"] is False and control["verdict"] == "DIFFERS",
          control)
    check("inert-is-named-in-the-scan", res["inert"] == ["planted_inert_stub"],
          res["inert"])
    check("all-clean-is-not-claimed", res["all_clean_claim"] is False,
          "one INERT + one VALID is not all clean")

    # cross-check the receipt's recorded negative control contract
    nc = (receipt.get("negative_controls") or [{}])[0]
    check("receipt-negative-control-contract-matches",
          nc.get("id") == "TST-0018-planted-inert-stub"
          and nc.get("fired_on_bad_state") is True
          and nc.get("silent_on_good_state") is True,
          {"id": nc.get("id"), "fired_on_bad_state": nc.get("fired_on_bad_state"),
           "silent_on_good_state": nc.get("silent_on_good_state")})
    # the receipt's own inert naming is the shipped instance of this defect class
    check("receipt-shipped-inert-named",
          receipt.get("inert") == ["plugin/hook_fire_probe.py:filesystem_only_verdict"],
          receipt.get("inert"))

    out = {"probe": "probe2-planted-inert", "unit_id": "TST-0018", "pass": not red,
           "checks": checks, "red": red}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0 if not red else 1


if __name__ == "__main__":
    raise SystemExit(main())
