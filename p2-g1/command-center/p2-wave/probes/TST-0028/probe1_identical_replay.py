#!/usr/bin/env python3
"""TST-0028 probe1: test_identical_build_replays_with_an_empty_diff.

Runs a LIVE record on build-a and replay on byte-identical build-b, then
asserts the semantic artifact_set and decision_trace diffs are both empty
and that the recording's replayability arithmetic matches the receipt.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "TST-0028.json"


def main() -> int:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    checks = []
    red = []

    def check(name, ok, detail):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})
        if not ok:
            red.append(name)

    with tempfile.TemporaryDirectory(prefix="tst0028-probe1-") as tmp:
        doc = harness.run_cycle(Path(tmp), planted=False, comment_only=False)
        check("test_identical_build_replays_with_an_empty_diff",
              doc["artifact_set"]["empty"] is True
              and doc["decision_trace"]["empty"] is True,
              {"artifact_changed": doc["artifact_set"]["changed"],
               "trace_changed": doc["decision_trace"]["changed"]})
        replayability = doc["replayability"]
        check("live-replayability-matches-receipt",
              replayability["denominator_steps"]
              == receipt["replayability"]["denominator_steps"] == 8,
              {"live_denominator": replayability["denominator_steps"],
               "receipt_denominator": receipt["replayability"]["denominator_steps"]})
        live_reasons = set(replayability["blocked_enumerated_by_reason"].values())
        recorded_blocked = {
            entry["step_id"]: entry["reason_class"]
            for entry in receipt["replayability"]["non_replayable_enumerated_by_reason"]
            if entry.get("replayable_without_live_network_or_credentials") is False
        }
        live_norm = {r.casefold() for r in live_reasons}
        rec_norm = {r.casefold() for r in recorded_blocked.values()}
        check("non-replayable-enumerated-by-reason",
              live_norm == {"network", "credential", "gui"}
              and rec_norm == live_norm,
              {"live": sorted(live_norm), "recorded": sorted(rec_norm),
               "raw_live": sorted(live_reasons),
               "raw_recorded": sorted(recorded_blocked.values())})
        check("replayable-fraction-5-of-8",
              replayability["replayable_fraction"] == "5/8",
              {"live": replayability["replayable_fraction"],
               "receipt_answer": receipt["answer"][:60]})
        check("clock-frozen-on-replay",
              doc["replay"]["decision_trace"] == doc["record"]["decision_trace"]
              and any(e["decision"].startswith("clock:")
                      for e in doc["replay"]["decision_trace"]),
              "identical trace under frozen clock from the recording")
        check("network-actually-attempted-in-record",
              next(o["outcome"] for sid, o in doc["record_step_outcomes"].items()
                   if sid == "fetch_external") == "blocked",
              "TEST-NET-1 socket attempted and blocked in the recording")

    nc_ids = [nc.get("id") for nc in receipt.get("negative_controls") or []]
    check("receipt-negative-control-present",
          "NC-comment-only-plant" in nc_ids, nc_ids)
    check("side-by-side-substrate-recorded",
          receipt.get("materialised_builds", {}).get("side_by_side") is True
          and receipt.get("materialised_builds", {}).get("record") == "build-a",
          receipt.get("materialised_builds"))
    check("replayability-percentage-with-reasons-not-bare",
          "62.5%" in str(receipt.get("answer"))
          and receipt["replayability"]["non_replayable_enumerated_by_reason"],
          "answer carries 62.5% + enumerated reasons")

    out = {"probe": "probe1-identical-replay", "unit_id": "TST-0028",
           "pass": not red, "checks": checks, "red": red}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0 if not red else 1


if __name__ == "__main__":
    raise SystemExit(main())
