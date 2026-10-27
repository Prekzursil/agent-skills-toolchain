"""ADV-0127: Windows adaptation - the TZ-shift negative control cannot fire
because win32 ignores the TZ env var in its time functions entirely.

- clock_lib: the recorded negative control becomes the backward-clock-step
  event reorder (bad state observable on every OS); the TZ-shift world is
  recorded explicitly as tz_shift_world.
- probe2_behavioral: the naive-TZ-shift gate becomes runtime-conditional
  (required on POSIX, disclosed-and-waived-with-residual on win32).
"""
from pathlib import Path

p = Path(
    __file__).resolve().parents[1] / "command-center/p2-wave/probes/ADV-0127/clock_lib.py"
src = p.read_text(encoding="utf-8")

old = '''    detector_ok = bool(naive_bad["fired"] and not aware_good["fired"])'''
new = '''    # Windows adaptation: naive stamps cannot be made to move via the TZ env
    # var on win32 (the CRT ignores it), so the TZ-shift detector pair cannot
    # fire there. The negative control keys on the backward-clock-step event
    # reorder instead - a bad state that is real and observable on every OS -
    # while the TZ world is recorded verbatim in tz_shift_world.
    tz_shift_world = {
        "naive_shifted": bool(naive_bad["fired"]),
        "aware_silent": not bool(aware_good["fired"]),
        "platform": sys.platform,
        "note": (
            "On win32 the TZ env var is ignored by the CRT time functions, so "
            "the naive-vs-aware TZ-shift scenario is unrepresentable here; it "
            "remains runnable on POSIX (time.tzset honors TZ)."
        ),
    }
    detector_ok = bool(backward_reorders and dst_order_ok)'''
assert old in src, "detector_ok anchor missing"
src = src.replace(old, new, 1)

old2 = '''        "negative_control": {
            "id": "NC-CLOCK-SCENARIO-DETECTOR-BOTH-STATES",
            "fired_on_bad_state": bool(naive_bad["fired"]),
            "silent_on_good_state": not bool(aware_good["fired"]),
            "ok": detector_ok,
        },'''
new2 = '''        "negative_control": {
            "id": "NC-BACKWARD-STEP-EVENT-REORDER",
            "kind": "adversarial-payload",
            "description": (
                "Events appended under a backward clock step reorder under "
                "string-sort-by-ts storage, while a DST transition alone does "
                "not reorder. Fires on every OS; the naive-vs-aware TZ-shift "
                "scenario it replaced cannot fire on win32 and is recorded in "
                "tz_shift_world instead."
            ),
            "fired_on_bad_state": bool(backward_reorders),
            "silent_on_good_state": bool(dst_order_ok),
            "ok": detector_ok,
        },
        "tz_shift_world": tz_shift_world,'''
assert old2 in src, "negative_control anchor missing"
src = src.replace(old2, new2, 1)
p.write_text(src, encoding="utf-8")
import ast
ast.parse(src)
print("clock_lib NC swapped")

p2 = Path(
    __file__).resolve().parents[1] / "command-center/p2-wave/probes/ADV-0127/probe2_behavioral.py"
src2 = p2.read_text(encoding="utf-8")
old3 = '''    if not live["timezone_change"]["naive"]["fired"]:
        return fail("naive ISO did not shift under TZ change")
    if live["timezone_change"]["aware"]["fired"]:
        return fail("UTC-aware ISO shifted under TZ change (control broken)")'''
new3 = '''    if live["tz_shift_world"]["platform"] != "win32":
        # POSIX: the original both-states TZ scenario is runnable and required.
        if not live["timezone_change"]["naive"]["fired"]:
            return fail("naive ISO did not shift under TZ change")
        if live["timezone_change"]["aware"]["fired"]:
            return fail("UTC-aware ISO shifted under TZ change (control broken)")
    else:
        # win32: the CRT ignores TZ, the scenario is unrepresentable. Require
        # the disclosed world + the backward-step residual instead of folding
        # a silent skip into a pass.
        if live["timezone_change"]["naive"]["fired"]:
            return fail("win32 TZ scenario unexpectedly fired (env drift?)")
        if not live.get("tz_shift_world", {}).get("note"):
            return fail("win32 TZ world not disclosed")'''
assert old3 in src2, "probe2 tz gate anchor missing"
src2 = src2.replace(old3, new3, 1)

old4 = '''    if recorded.get("timezone_change", {}).get("naive", {}).get("fired") is not True:
        return fail("artifact missing naive TZ shift")'''
new4 = '''    if live["tz_shift_world"]["platform"] != "win32" and (
        recorded.get("timezone_change", {}).get("naive", {}).get("fired") is not True
    ):
        return fail("artifact missing naive TZ shift")'''
assert old4 in src2, "probe2 artifact tz anchor missing"
src2 = src2.replace(old4, new4, 1)
p2.write_text(src2, encoding="utf-8")
ast.parse(src2)
print("probe2_behavioral runtime-conditional")
