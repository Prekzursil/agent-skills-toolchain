#!/usr/bin/env python3
"""TST-0067 probe2: wrong-scope write detected as inert + detector control.

The project-scope consumer must be observed, never inferred from the
setter's self-read. A root-scope write that the setter self-reads as
successful is INERT for the project consumer; the same write at project
scope is live. Detector control: in the wrong-scope case the setter's
self-read DISAGREES with the consumer observation, so any probe that reads
the setter reports a false green.
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

RECEIPT = REPO / "command-center" / "receipts" / "TST-0067.json"


def main() -> int:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    checks = []
    red = []

    def check(name, ok, detail):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})
        if not ok:
            red.append(name)

    with tempfile.TemporaryDirectory(prefix="tst0067-scope-") as tmp:
        tmp = Path(tmp)
        scopes = harness.ScopedSettings(tmp / "root" / "settings.json",
                                        tmp / "root" / "project" / "settings.json")
        scopes.write_root(harness.ROOT_WRITE)
        setter_saw = scopes.self_read_root()
        consumer = harness.observe_settings_child(scopes.project)
        consumer_value = consumer.get("userspace")
        check("test_a_write_at_the_wrong_scope_is_detected_as_inert",
              setter_saw == harness.ROOT_WRITE
              and consumer_value == harness.OLD
              and consumer_value != harness.ROOT_WRITE,
              {"setter_self_read_root": setter_saw,
               "consumer_scope_value": consumer_value,
               "consumer_pid": consumer.get("consumer_pid")})

        check("test_probe_reads_from_the_consumer_not_from_the_setter",
              setter_saw != consumer_value,
              {"setter": setter_saw, "consumer": consumer_value,
               "disagreement_is_the_detector": True})

        scopes.write_project(harness.PROJECT_WRITE)
        live = harness.observe_settings_child(scopes.project)
        check("correct-scope-write-is-live",
              live.get("userspace") == harness.PROJECT_WRITE,
              {"consumer": live.get("userspace"),
               "setter_self_read_project": scopes.self_read_project()})

    nc_ids = [nc.get("id") for nc in receipt.get("negative_controls") or []]
    check("receipt-false-green-controls-present",
          "setter-self-agreement-false-green-persistent" in nc_ids
          and "setter-self-agreement-false-green-wrong-scope" in nc_ids,
          nc_ids)
    pairs = receipt.get("consumer_observation_pairs") or {}
    wrong = pairs.get("wrong_scope_inert") or {}
    correct = pairs.get("correct_scope_live") or {}
    check("receipt-observation-pairs-match-live-semantics",
          wrong.get("value_written_at_root") == harness.ROOT_WRITE
          and wrong.get("consumer_scope_value") == harness.OLD
          and correct.get("value_written_at_project") == harness.PROJECT_WRITE,
          {"recorded_root_write": wrong.get("value_written_at_root"),
           "recorded_consumer": wrong.get("consumer_scope_value"),
           "recorded_project_write": correct.get("value_written_at_project")})
    check("which-scope-consumers-read-recorded",
          any(c.get("name") == "project-settings-child"
              and "project/settings.json" in str(c.get("reads"))
              for c in receipt.get("which_scope_each_consumer_reads") or []),
          [c.get("name") for c in
           receipt.get("which_scope_each_consumer_reads") or []])
    review = receipt.get("reviewer") or {}
    check("reviewer-derived-flags-consistent",
          isinstance(review.get("derived"), dict)
          and review.get("derived", {}).get("root_write_inert") is True
          and review.get("derived", {}).get("project_write_live") is True,
          review.get("derived"))

    out = {"probe": "probe2-wrong-scope-detector", "unit_id": "TST-0067",
           "pass": not red, "checks": checks, "red": red}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0 if not red else 1


if __name__ == "__main__":
    raise SystemExit(main())
