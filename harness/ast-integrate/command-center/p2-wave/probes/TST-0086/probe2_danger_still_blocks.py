#!/usr/bin/env python3
"""Probe 2: genuinely dangerous operations still exit 2 (both-states pair).

Independent of probe 1's inject path: this re-runs live no-force-push/hook.py
against a real `git push --force` proposal (inspect-only, never executed) and
a safe `ls -la`. A non-dangerous advisory rewrite must not become a block.
Swallowing exit 2 must fail this probe. Estate dispatcher is inject-only and
must still exit 0 when a consolidated check returns 2.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0086.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0086-probe2 {msg}")
    return 1


def as_int(value, default=None):
    if value is None:
        return default
    return int(value)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:TST-0086" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    census = S.estate_census()
    if census.get("estate_inputs_present") is not True:
        return fail("estate dispatcher/settings/no-force-push missing")

    live = E.danger_both_states()
    broken = live.get("known_broken") or {}
    good = live.get("known_good") or {}
    advisory = live.get("advisory_nonzero_does_not_block") or {}
    injected = live.get("injected_exception_on_danger_hook") or {}
    mutant = live.get("mutant_swallows_exit_2") or {}
    disarmed = live.get("dispatch_disarmed_block") or {}

    print(
        f"danger_exit={broken.get('exit_code')} blocked_by={broken.get('blocked_by')} "
        f"fired={broken.get('danger_hook_fired')} pre={broken.get('pre_tool_ran')}"
    )
    print(f"safe_exit={good.get('exit_code')} blocked={good.get('blocked')}")
    print(
        f"advisory_exit={advisory.get('exit_code')} "
        f"pre_tool_process={advisory.get('pre_tool_process_exit')}"
    )
    print(
        f"inject_on_danger_exit={injected.get('exit_code')} "
        f"continued={injected.get('session_continued')}"
    )
    print(
        f"mutant_swallow_exit={mutant.get('exit_code')} "
        f"would_pass={mutant.get('would_pass_danger_test')}"
    )
    print(
        f"dispatch_rc2_session={disarmed.get('session_exit')} "
        f"note={disarmed.get('note_visible')}"
    )

    if not live.get("pass"):
        return fail("live danger both-states did not pass")
    if as_int(broken.get("exit_code")) != 2:
        return fail("dangerous operation did not exit 2")
    if broken.get("blocked_by") != "hooks/no-force-push/hook.py":
        return fail("block was not attributed to no-force-push")
    if not broken.get("danger_hook_fired"):
        return fail("danger hook body did not fire on live payload")
    if as_int(good.get("exit_code")) != 0:
        return fail("safe operation did not exit 0")
    if good.get("blocked") is True:
        return fail("safe operation blocked")
    if as_int(advisory.get("exit_code")) != 0:
        return fail("advisory rewrite was promoted to a session block")
    if as_int(injected.get("exit_code")) != 0:
        return fail("exception on danger hook did not fail open")
    if mutant.get("would_pass_danger_test") is True:
        return fail("swallow-exit-2 mutant would still pass; detector is vacuous")
    if as_int(disarmed.get("session_exit")) != 0:
        return fail("estate dispatcher propagated exit 2 (it is inject-only)")
    if disarmed.get("note_visible") is not True:
        return fail("disarmed block request was silent on dispatcher stdout")

    pair = doc.get("danger_pair") or doc.get("both_states") or {}
    rec_broken = pair.get("known_broken") or {}
    rec_good = pair.get("known_good") or {}
    if as_int(rec_broken.get("exit_code")) != 2:
        return fail("artifact known_broken exit_code is not 2")
    if as_int(rec_good.get("exit_code")) != 0:
        return fail("artifact known_good exit_code is not 0")
    if doc.get("both_states", {}).get("discriminates") is not True:
        return fail("artifact both_states.discriminates is not true")

    scope = doc.get("scope") or {}
    measured = list(scope.get("measured") or [])
    if "hooks/_dispatch/dispatch.py" not in measured:
        return fail("artifact did not measure estate dispatcher")
    if "hooks/no-force-push/hook.py" not in measured:
        return fail("artifact did not measure no-force-push")
    denied = list(scope.get("does_not_claim") or [])
    if "estate hooks/_dispatch/dispatch.py was measured" in denied:
        return fail("artifact denies measuring the estate dispatcher")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    t2 = tests.get("test_dangerous_operation_still_exits_two")
    if not t2 or t2.get("result") != "PASS":
        return fail("artifact test_dangerous_operation_still_exits_two not PASS")

    out = {
        "probe": "probe2-danger-still-blocks",
        "unit_id": "TST-0086",
        "danger_exit": 2,
        "safe_exit": 0,
        "advisory_does_not_block": True,
        "inject_fail_open": True,
        "mutant_caught": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:TST-0086-probe2 dangerous operation still exits 2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
