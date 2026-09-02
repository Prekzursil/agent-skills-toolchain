#!/usr/bin/env python3
"""Probe 2: wrong-scope write is inert; detector control vs setter-self-read.

Independent re-derive: this probe re-runs the live child and compares writer
value to consumer value. It does not accept the receipt's verdict field as
input to that comparison.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0067-probe2 {msg}")
    return 1


def main() -> int:
    doc = S.require_receipt()
    scope = S.measure_wrong_scope_inert()
    control = S.measure_detector_control()
    print(
        json.dumps(
            {
                "probe": "probe2-wrong-scope-detector",
                "unit_id": "TST-0067",
                "scope": scope,
                "detector_control": control,
            },
            sort_keys=True,
        )
    )
    if not scope["pass"]:
        return fail("wrong-scope measurement did not pass")
    if not control["pass"]:
        return fail("detector-control measurement did not pass")
    inert = scope["wrong_scope_inert"]
    live = scope["correct_scope_live"]
    if inert["consumer_scope_value"] == S.ROOT_WRITE:
        return fail("project consumer observed the root-scope write")
    if inert["consumer_scope_value"] != S.OLD:
        return fail(f"expected OLD after root write, got {inert['consumer_scope_value']!r}")
    if live["consumer_scope_value"] != S.PROJECT_WRITE:
        return fail("project consumer did not observe the project-scope write")
    if not control["persistent_setter_false_green"]:
        return fail("setter-only check did not false-green the persistent miss")
    if not control["scope_setter_false_green"]:
        return fail("setter-only check did not false-green the root-scope write")
    if not control["session_consumer_true_green"]:
        return fail("consumer check failed the in-session injection")
    if not control["project_consumer_true_green"]:
        return fail("consumer check failed the project-scope write")

    rec_inert = ((doc.get("consumer_observation_pairs") or {}).get("wrong_scope_inert") or {})
    if rec_inert.get("consumer_scope_value") != inert["consumer_scope_value"]:
        return fail("receipt inert consumer value does not match live re-run")
    rec_live = ((doc.get("consumer_observation_pairs") or {}).get("correct_scope_live") or {})
    if rec_live.get("consumer_scope_value") != live["consumer_scope_value"]:
        return fail("receipt project consumer value does not match live re-run")

    derived_inert = rec_inert.get("value_written_at_root") != rec_inert.get(
        "consumer_scope_value"
    )
    if not derived_inert:
        return fail("re-derive: receipt root write was not inert vs consumer")

    print(
        f"root_written={inert['value_written_at_root']!r} "
        f"project_consumer_after_root={inert['consumer_scope_value']!r} "
        f"project_consumer_after_project={live['consumer_scope_value']!r} "
        f"setter_false_green_persistent={control['persistent_setter_false_green']} "
        f"setter_false_green_scope={control['scope_setter_false_green']}"
    )
    print("SUCCESS:TST-0067-probe2 wrong-scope inert; setter-self-read is not evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
