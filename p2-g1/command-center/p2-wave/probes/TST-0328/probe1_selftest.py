#!/usr/bin/env python3
"""Probe 1: the fixture rejects silent-in-both and always-on detectors.

Also accepts a discriminating detector (SILENT then FIRES) and records
both observations. A fixture that cannot fail is the same bug one level up.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.test_support.both_states import (  # noqa: E402
    FIRES,
    SILENT,
    BothStatesError,
    assert_both_states,
    run_both_states,
)
from tools.test_support.selftest import run_selftest  # noqa: E402

ART = REPO / "command-center/receipts/TST-0328.json"
SENTINEL = "SUCCESS:TST-0328"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0328-probe1 {msg}")
    return 1


def local_silent(_state: object) -> bool:
    """Deliberately silent detector constructed in this probe, not selftest.py."""
    return False


def local_always(_state: object) -> bool:
    return True


def local_ok(state: object) -> bool:
    return bool(isinstance(state, dict) and state.get("broken"))


def main() -> int:
    live = run_selftest()
    print(
        json.dumps(
            {
                "probe": "probe1-selftest",
                "unit_id": "TST-0328",
                "silent_in_both_rejected": live["silent_in_both_rejected"],
                "always_on_rejected": live["always_on_rejected"],
                "inverted_rejected": live["inverted_rejected"],
                "discriminating_accepted": live["discriminating_accepted"],
                "discriminating_known_good": live["discriminating"]["known_good"],
                "discriminating_known_broken": live["discriminating"]["known_broken"],
            },
            sort_keys=True,
        )
    )
    if not live["pass"]:
        return fail("package selftest did not pass")
    if not live["silent_in_both_rejected"]:
        return fail("silent detector was not rejected")
    if not live["always_on_rejected"]:
        return fail("always-on detector was not rejected")
    if live["discriminating"]["known_good"] != SILENT:
        return fail("discriminating detector was not SILENT on known-good")
    if live["discriminating"]["known_broken"] != FIRES:
        return fail("discriminating detector did not FIRE on known-broken")

    good = {"broken": False}
    broken = {"broken": True}
    silent_rec = run_both_states(
        local_silent, good, broken, detector_id="probe1-local-silent"
    )
    if silent_rec.get("reason") != "silent-in-both" or silent_rec.get("valid"):
        return fail("probe-local silent detector was not classified silent-in-both")
    try:
        assert_both_states(local_silent, good, broken, detector_id="probe1-local-silent-assert")
    except BothStatesError as exc:
        if exc.reason != "silent-in-both":
            return fail(f"assert reason for silent was {exc.reason!r}")
    else:
        return fail("assert_both_states did not raise on a silent detector")

    always_rec = run_both_states(
        local_always, good, broken, detector_id="probe1-local-always-on"
    )
    if always_rec.get("reason") != "fires-in-both" or always_rec.get("valid"):
        return fail("probe-local always-on detector was not classified fires-in-both")
    try:
        assert_both_states(local_always, good, broken, detector_id="probe1-local-always-assert")
    except BothStatesError as exc:
        if exc.reason != "fires-in-both":
            return fail(f"assert reason for always-on was {exc.reason!r}")
    else:
        return fail("assert_both_states did not raise on an always-on detector")

    ok_rec = assert_both_states(local_ok, good, broken, detector_id="probe1-local-ok")
    if ok_rec["known_good"]["observation"] != SILENT:
        return fail("local discriminating detector was not SILENT on good")
    if ok_rec["known_broken"]["observation"] != FIRES:
        return fail("local discriminating detector did not FIRE on broken")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    ev = doc.get("evidence") or {}
    st = ev.get("selftest") if isinstance(ev, dict) else None
    if not isinstance(st, dict) or not st:
        # schema-conformant receipts carry evidence as a list; the legacy dict
        # sections are preserved verbatim under extensions.evidence_extras
        st = {}
        for ee in (doc.get("extensions") or {}).get("evidence_extras") or []:
            rec = ee.get("recorded") if isinstance(ee, dict) else None
            if isinstance(rec, dict) and (rec.get("silent_in_both_rejected") is not None
                                          or rec.get("always_on_rejected") is not None):
                st = rec
                break
    if st.get("silent_in_both_rejected") is not True:
        return fail("receipt selftest.silent_in_both_rejected is not true")
    if st.get("always_on_rejected") is not True:
        return fail("receipt selftest.always_on_rejected is not true")
    if st.get("discriminating_accepted") is not True:
        return fail("receipt selftest.discriminating_accepted is not true")
    obs = doc.get("both_states_observations") or []
    if not isinstance(obs, list) or len(obs) < 2:
        return fail("receipt did not record both-states observations")
    print("SUCCESS:TST-0328-probe1 silent and always-on rejected; discriminating recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
