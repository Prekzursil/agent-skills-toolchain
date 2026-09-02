#!/usr/bin/env python3
"""Probe 2: both withdrawal halves, named-clock exposure window, fresh-profile re-run."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from clock import CLOCK_SOURCE  # noqa: E402
from drill import INJECTED_PROPAGATION_S, PAYLOAD, run_drill  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:REL-0023-probe2 {msg}")
    return 1


def check_window(window: dict, label: str) -> str | None:
    if window.get("clock_source") != CLOCK_SOURCE:
        return f"{label} clock_source {window.get('clock_source')}"
    merge_ns = window["merge_ns"]
    reflect_ns = window["reflect_ns"]
    delay_ns = window["delay_ns"]
    if not isinstance(merge_ns, int) or not isinstance(reflect_ns, int):
        return f"{label} clock samples are not integers"
    if delay_ns != reflect_ns - merge_ns:
        return f"{label} delay_ns is not reflect_ns-merge_ns"
    if delay_ns <= 0:
        return f"{label} non-positive delay"
    delay_s = window["delay_seconds"]
    if abs(delay_s - delay_ns / 1_000_000_000) > 1e-12:
        return f"{label} delay_seconds does not match delay_ns"
    if delay_s < INJECTED_PROPAGATION_S * 0.5:
        return f"{label} delay shorter than injected propagation"
    during = window["during_window_fresh"]
    if during.get("version") != "1.1.0":
        return f"{label} during-window fresh did not still get 1.1.0 ({during})"
    if during.get("executed") != PAYLOAD["1.1.0"]:
        return f"{label} during-window did not execute withdrawn bytes"
    after = window["after_reflect_fresh"]
    if after.get("version") == "1.1.0":
        return f"{label} after-reflect fresh still resolved 1.1.0"
    if after.get("version") != "1.0.0":
        return f"{label} after-reflect expected 1.0.0 got {after.get('version')}"
    if after.get("executed") == PAYLOAD["1.1.0"]:
        return f"{label} after-reflect executed withdrawn bytes"
    if after.get("executed") != PAYLOAD["1.0.0"]:
        return f"{label} after-reflect did not execute 1.0.0 bytes"
    refuse = window["refuse_move_after"]
    if refuse.get("action") != "REFUSE_MOVE":
        return f"{label} post-reflect move was not refused"
    if not window.get("direct_index_write_refused"):
        return f"{label} direct public-index write was not refused"
    text = window.get("protects_already_installed") or ""
    if "KEEP_RUNNING_UNAWARE" not in text:
        return f"{label} missing already-installed finding"
    if "private-registry" not in text and "private registry" not in text:
        return f"{label} missing which-half statement"
    if "revert PR" not in text and "revert pull request" not in text.lower():
        return f"{label} missing public-half statement"
    return None


def main() -> int:
    first = run_drill()
    err = check_window(first["exposure_window"], "run-1")
    if err:
        return fail(err)

    # Reviewer requirement: re-execute on a freshly created profile from the
    # same commands. A second run_drill() is a new temp profile, not a re-read.
    second = run_drill()
    err = check_window(second["exposure_window"], "run-2")
    if err:
        return fail(err)
    if first["root"] == second["root"]:
        return fail("second run reused the first profile")
    if first["isolation"]["profile"] == second["isolation"]["profile"]:
        return fail("second run reused the first canary profile")

    w = second["exposure_window"]
    print(
        json.dumps(
            {
                "probe": "probe2-exposure-window",
                "unit_id": "REL-0023",
                "pass": True,
                "clock_source": w["clock_source"],
                "delay_seconds": w["delay_seconds"],
                "delay_ns": w["delay_ns"],
                "direct_index_write_refused": w["direct_index_write_refused"],
                "during_window_version": w["during_window_fresh"]["version"],
                "after_reflect_version": w["after_reflect_fresh"]["version"],
                "fresh_profiles": [first["root"], second["root"]],
            },
            sort_keys=True,
        )
    )
    print(
        f"SUCCESS:REL-0023-probe2 exposure window "
        f"{w['delay_seconds']:.6f}s on {w['clock_source']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
