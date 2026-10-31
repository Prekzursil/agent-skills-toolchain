#!/usr/bin/env python3
"""Probe 2: independent reviewer reproduces both-states + adoption census.

Does not import tools.test_support.selftest. Interprets boolean detector
returns locally, then checks the shared fixture's recorded pair. Census
must discriminate a planted fixture-user from a planted hand-rolled
both_states helper.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.test_support.both_states import (  # noqa: E402
    BothStatesError,
    assert_both_states,
    run_both_states,
)
from tools.test_support.census import census, scan_tree  # noqa: E402

ART = REPO / "command-center/receipts/TST-0328.json"
SENTINEL = "SUCCESS:TST-0328"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0328-probe2 {msg}")
    return 1


def independent_obs(result: object) -> str:
    """Boolean-only interpreter. Does not call tools.test_support.interpret."""
    if result is True:
        return "FIRES"
    if result is False:
        return "SILENT"
    raise TypeError(f"independent reviewer expected bool, got {type(result).__name__}")


def review_silent(_state: object) -> bool:
    return False


def review_always(_state: object) -> bool:
    return True


def review_ok(state: object) -> bool:
    return bool(isinstance(state, dict) and state.get("broken"))


def planted_census() -> dict:
    with tempfile.TemporaryDirectory(prefix="tst-0328-census-") as tmp:
        root = Path(tmp)
        (root / "uses_fixture.py").write_text(
            "from tools.test_support.both_states import assert_both_states\n"
            "\n"
            "def detect(state):\n"
            "    return bool(state)\n",
            encoding="utf-8",
        )
        (root / "hand_rolled.py").write_text(
            "def both_states():\n"
            "    return {'good': True, 'bad': True}\n",
            encoding="utf-8",
        )
        (root / "unrelated.py").write_text(
            "def add(a, b):\n    return a + b\n",
            encoding="utf-8",
        )
        return scan_tree(root, repo=root)


def main() -> int:
    good = {"broken": False, "tag": "reviewer-good"}
    broken = {"broken": True, "tag": "reviewer-broken"}

    ind_good = independent_obs(review_ok(good))
    ind_broken = independent_obs(review_ok(broken))
    rec = run_both_states(
        review_ok, good, broken, detector_id="reviewer-discriminating"
    )
    if rec["known_good"]["observation"] != ind_good:
        return fail("fixture good observation != independent SILENT")
    if rec["known_broken"]["observation"] != ind_broken:
        return fail("fixture broken observation != independent FIRES")
    if not rec.get("valid"):
        return fail("reviewer discriminating detector was not VALID")
    try:
        assert_both_states(review_ok, good, broken, detector_id="reviewer-ok-assert")
    except BothStatesError as exc:
        return fail(f"reviewer discriminating detector raised {exc.reason}")

    silent = run_both_states(
        review_silent, good, broken, detector_id="reviewer-silent"
    )
    if silent.get("reason") != "silent-in-both":
        return fail("reviewer silent detector was not rejected as silent-in-both")
    always = run_both_states(
        review_always, good, broken, detector_id="reviewer-always-on"
    )
    if always.get("reason") != "fires-in-both":
        return fail("reviewer always-on detector was not rejected as fires-in-both")

    planted = planted_census()
    users = set(planted.get("fixture_users") or [])
    hands = set(planted.get("hand_rolled") or [])
    if "uses_fixture.py" not in users:
        return fail("census missed planted fixture user")
    if "hand_rolled.py" not in hands:
        return fail("census missed planted hand-rolled both_states")
    if "uses_fixture.py" in hands:
        return fail("census classified fixture user as hand-rolled")
    if "unrelated.py" in users or "unrelated.py" in hands:
        return fail("census flagged an unrelated file")

    live = census(REPO)
    adoption = live.get("adoption") or {}
    registry = live.get("registry") or {}
    live_scan = live.get("live") or {}
    live_users = list(live_scan.get("fixture_users") or [])
    live_hands = list(live_scan.get("hand_rolled") or [])

    probe1_rel = "command-center/p2-wave/probes/TST-0328/probe1_selftest.py"
    probe2_rel = "command-center/p2-wave/probes/TST-0328/probe2_census_and_reviewer.py"
    if probe1_rel not in live_users or probe2_rel not in live_users:
        return fail("live census did not count TST-0328 probes as fixture users")
    if adoption.get("live_hand_rolled", 0) < 1:
        return fail("live census found zero hand-rolled both-states controls")
    if registry.get("present") is True and not registry.get("parseable"):
        return fail("TEST-REGISTRY.json present but unparseable")

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
    cen = ev.get("census") if isinstance(ev, dict) else None
    if not isinstance(cen, dict) or not cen:
        # schema-conformant receipts carry evidence as a list; the legacy dict
        # sections are preserved verbatim under extensions.evidence_extras
        cen = {}
        for ee in (doc.get("extensions") or {}).get("evidence_extras") or []:
            rec = ee.get("recorded") if isinstance(ee, dict) else None
            if isinstance(rec, dict) and (rec.get("live") is not None or rec.get("registry") is not None):
                cen = rec
                break
    rec_adopt = cen.get("adoption") or {}
    rec_live = cen.get("live") or {}
    rec_users = list(rec_live.get("fixture_users") or [])
    rec_hands = list(rec_live.get("hand_rolled") or [])
    live_user_n = int(adoption.get("live_fixture_users") or 0)
    live_hand_n = int(adoption.get("live_hand_rolled") or 0)
    rec_user_n = rec_adopt.get("live_fixture_users")
    rec_hand_n = rec_adopt.get("live_hand_rolled")
    if rec_user_n != len(rec_users):
        return fail("receipt fixture-user count disagrees with its own list")
    if rec_hand_n != len(rec_hands):
        return fail("receipt hand-rolled count disagrees with its own list")
    if live_user_n != len(live_users):
        return fail("live fixture-user count disagrees with live list")
    if live_hand_n != len(live_hands):
        return fail("live hand-rolled count disagrees with live list")
    phantom_users = sorted(set(rec_users) - set(live_users))
    phantom_hands = sorted(set(rec_hands) - set(live_hands))
    if phantom_users:
        return fail("receipt census lists fixture users that are not live")
    if phantom_hands:
        return fail("receipt census lists hand-rolled files that are not live")
    # Parallel units add *both_states*.py files; a snapshot may lag the live
    # walk. Overstatement is a lie. Growth after the snapshot is not.
    if rec_user_n > live_user_n:
        return fail("receipt census fixture-user count overstated vs live")
    if rec_hand_n > live_hand_n:
        return fail("receipt census hand-rolled count overstated vs live")
    if rec_adopt.get("registry_present") != bool(registry.get("present")):
        return fail("receipt registry_present drifted from live")

    report = {
        "probe": "probe2-census-and-reviewer",
        "unit_id": "TST-0328",
        "reviewer_good": ind_good,
        "reviewer_broken": ind_broken,
        "reviewer_valid": rec.get("valid"),
        "reviewer_silent_reason": silent.get("reason"),
        "reviewer_always_reason": always.get("reason"),
        "planted_fixture_users": sorted(users),
        "planted_hand_rolled": sorted(hands),
        "live_fixture_users": live_users,
        "live_hand_rolled_count": len(live_hands),
        "receipt_live_hand_rolled": rec_hand_n,
        "receipt_live_fixture_users": rec_user_n,
        "registry_present": registry.get("present"),
        "registered_detectors": adoption.get("registered_detectors"),
        "executed_both_states": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        "SUCCESS:TST-0328-probe2 independent both-states recount and adoption census"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
