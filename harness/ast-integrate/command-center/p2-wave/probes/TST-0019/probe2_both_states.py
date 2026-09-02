#!/usr/bin/env python3
"""Named probe 2: both-states controls, schema, garbage rejection, genuine process.

Mechanically different from probe 1: starts from fixtures + the TST-0013 harness,
then confirms a live genuine decoy survives the guard.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "detector-self-test"))

import scenario as S  # noqa: E402
import session_probe as SP  # noqa: E402
from detector_self_test import run_both_states  # noqa: E402

ART = REPO / "command-center/receipts/TST-0019.json"
SCHEMA = REPO / "command-center/schema/detector-control.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0019-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = list(validator.iter_errors(doc))
    if errs:
        return fail(f"schema {errs[0].message}")
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            return fail(f"schema accepted garbage {list(garbage)[:1]}")
        print(f"garbage_rejected={list(garbage)[:1] or '{}'}")

    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:TST-0019" not in text:
        return fail("sentinel absent")

    t_pid = S.test_probe_excludes_own_pid()
    t_gen = S.test_probe_still_finds_a_genuinely_running_process()
    print(
        f"test_probe_excludes_own_pid ok={t_pid.get('ok')} "
        f"before={t_pid.get('before_probe_pid')} after={t_pid.get('after_probe_pid')}"
    )
    print(
        f"test_probe_still_finds_a_genuinely_running_process ok={t_gen.get('ok')} "
        f"decoy={t_gen.get('decoy_pid')} harness_ok={t_gen.get('harness_ok')}"
    )
    if not t_pid.get("ok"):
        return fail("test_probe_excludes_own_pid")
    if not t_gen.get("ok"):
        return fail("test_probe_still_finds_a_genuinely_running_process")

    dead = SP.load_fixture(S.WIN32_DEAD)
    live = SP.load_fixture(S.WIN32_LIVE)

    def self_detector(mode: str) -> list:
        scan = SP.scan_snapshot(dead, guarded=(mode == "guarded"))
        return [
            m
            for m in scan["matches"]
            if SP.is_self(m, int(scan["probe_pid"]), str(scan.get("probe_start_key") or ""))
        ]

    self_pair = run_both_states(self_detector, "guarded", "unguarded")
    print(
        f"self-match harness silent_on_good={self_pair.silent_on_good} "
        f"fires_on_bad={self_pair.fires_on_bad} ok={self_pair.ok}"
    )
    if not self_pair.ok:
        return fail("self-match both-states harness")

    def presence(snapshot: dict) -> list:
        return SP.scan_snapshot(snapshot, guarded=True)["matches"]

    present_pair = run_both_states(presence, dead, live)
    print(
        f"presence harness silent_on_good={present_pair.silent_on_good} "
        f"fires_on_bad={present_pair.fires_on_bad} ok={present_pair.ok}"
    )
    if not present_pair.ok:
        return fail("presence both-states harness")

    mutant = SP.scan_snapshot(dead, guarded=False)
    if not mutant.get("self_match"):
        return fail("unguarded mutant of dead fixture was silent")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    if tests.get("test_probe_excludes_own_pid", {}).get("result") != "PASS":
        return fail("artifact test_probe_excludes_own_pid not PASS")
    if tests.get("test_probe_still_finds_a_genuinely_running_process", {}).get("result") != "PASS":
        return fail("artifact genuine-process test not PASS")

    print("SUCCESS:TST-0019-probe2 both-states schema genuine-process")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
