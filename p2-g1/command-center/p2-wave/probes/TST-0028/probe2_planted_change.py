#!/usr/bin/env python3
"""TST-0028 probe2: test_a_planted_behaviour_change_shows_up_in_the_diff.

Runs the LIVE planted cycle (record accept-v1, replay build-c carrying
accept-v2) and asserts both semantic diffs are non-empty, then runs the
comment-only control (build-d) and asserts the diffs stay empty: a comment
without behaviour change must not fire the detector.
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

    with tempfile.TemporaryDirectory(prefix="tst0028-probe2-") as tmp:
        planted = harness.run_cycle(Path(tmp) / "p", planted=True)
        changed_paths = [c["path"] for c in planted["artifact_set"]["changed"]]
        check("test_a_planted_behaviour_change_shows_up_in_the_diff",
              planted["artifact_set"]["empty"] is False
              and planted["decision_trace"]["empty"] is False,
              {"artifact_changed": changed_paths,
               "trace_changed": len(planted["decision_trace"]["changed"])})
        check("planted-changes-digest-and-report",
              "digest.txt" in changed_paths and "report.json" in changed_paths,
              changed_paths)
        check("planned-marker-actually-carried",
              planted["replay"]["plan_marker"] == "accept-v2"
              and planted["record"]["plan_marker"] == "accept-v1",
              {"record": planted["record"]["plan_marker"],
               "replay": planted["replay"]["plan_marker"]})
        comment = harness.run_cycle(Path(tmp) / "c", comment_only=True)
        check("comment-only-control-does-not-fire",
              comment["artifact_set"]["empty"] is True
              and comment["decision_trace"]["empty"] is True,
              "comment-only source edit produces an empty diff")

    # receipt cross-checks
    nc = next(nc for nc in receipt.get("negative_controls") or []
              if nc.get("id") == "NC-comment-only-plant")
    check("receipt-negative-control-contract-matches",
          nc.get("observed_comment_only_empty") is True
          and nc.get("observed_planted_non_empty") is True
          and nc.get("fired_on_bad_state") is True
          and nc.get("silent_on_good_state") is True,
          {"id": nc.get("id"), "fired_on_bad_state": nc.get("fired_on_bad_state"),
           "silent_on_good_state": nc.get("silent_on_good_state")})
    tests_live = receipt.get("tests_live") or {}
    check("receipt-tests-live-shapes-match-live",
          tests_live.get("identical_replay", {}).get("empty") is True
          and tests_live.get("planted_behaviour_change", {}).get("empty") is False
          and tests_live.get("comment_only_control", {}).get("empty") is True,
          {k: v.get("empty") for k, v in tests_live.items()})
    check("replayability-answer-non-bare",
          "62.5%" in str(receipt.get("answer"))
          and "network" in str(receipt.get("answer"))
          and "credential" in str(receipt.get("answer")),
          "answer enumerates the non-replayable reasons")

    out = {"probe": "probe2-planted-change", "unit_id": "TST-0028",
           "pass": not red, "checks": checks, "red": red}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0 if not red else 1


if __name__ == "__main__":
    raise SystemExit(main())
