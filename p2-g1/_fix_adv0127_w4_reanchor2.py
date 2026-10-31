#!/usr/bin/env python3
"""ADV-0127 wave-4 re-anchor, part 2: probe2 + emit_artifact expectations.

probe2: require the retry_backoff block to be an honest disclosed
NOT-CHECKED (anchor removed from live tree) instead of asserting
clock_independent=True from a function that no longer exists.
emit_artifact: freshness target re-anchored on vi.freshness, retry target
NOT-CHECKED, headline + evidence aligned with the live tree, win32 TZ-shift
evidence verdict keyed on the observed world.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
P2 = HERE / "command-center" / "p2-wave" / "probes" / "ADV-0127" / "probe2_behavioral.py"
EM = HERE / "command-center" / "p2-wave" / "probes" / "ADV-0127" / "emit_artifact.py"

# ---- probe2 ----
src = P2.read_text(encoding="utf-8")
old = '''    if not live["retry_backoff"]["clock_independent"]:
        return fail("retry backoff unexpectedly clock-dependent")'''
new = '''    rb = live["retry_backoff"]
    if (
        rb.get("status") != "NOT-CHECKED"
        or rb.get("clock_independent") is not None
        or not rb.get("reason")
    ):
        return fail("retry_backoff not an honest disclosed NOT-CHECKED")'''
assert old in src, "probe2 retry assertion anchor missing"
src = src.replace(old, new, 1)
P2.write_text(src, encoding="utf-8", newline="\n")
print("probe2_behavioral.py patched OK")

# ---- emit_artifact ----
src = EM.read_text(encoding="utf-8")

old = '''        "(never-expiring defer). vuln_ingestion.parse_iso_z accepts naive strings; "
        "with_retry is sleep-based and clock-independent. platform cache/leases modules "
        "and PowerShell are absent (NOT-CHECKED), not invented."'''
new = '''        "(never-expiring defer). The live freshness gate vi.freshness compares naive "
        "strptime parses - a backward step flips it conservatively to STALE; the prior "
        "parse_iso_z/with_retry anchors were removed from the live tree by concurrent "
        "fleet work (2026-10-26) and retry backoff is recorded NOT-CHECKED. platform "
        "cache/leases modules and PowerShell are absent (NOT-CHECKED), not invented."'''
assert old in src, "emit headline anchor missing"
src = src.replace(old, new, 1)

old = '''        verdict(
            "TARGET-FRESHNESS-CHECKS",
            "close._now / parse_iso_z accept naive ISO; iso_z(naive) follows the process TZ.",
            "CONFIRMED" if live["freshness"]["iso_z_naive_shifts_with_tz"] else "REFUTED",
        ),'''
new = '''        verdict(
            "TARGET-FRESHNESS-CHECKS",
            "Live freshness gate vi.freshness compares naive strptime parses "
            "(naive-local class; cannot represent zone-aware time); a backward step "
            "flips it conservatively to STALE rather than silently fresh.",
            "CONFIRMED"
            if (
                live["freshness"]["parse_is_naive"]
                and live["freshness"]["beyond_window_flips_stale"]
                and live["freshness"]["backward_step_flips_stale"]
            )
            else "REFUTED",
        ),'''
assert old in src, "emit freshness target anchor missing"
src = src.replace(old, new, 1)

old = '''        verdict(
            "TARGET-RETRY-BACKOFF",
            "Retry backoff compares wall-clock instants (vulnerable to skew).",
            "REFUTED" if live["retry_backoff"]["clock_independent"] else "CONFIRMED",
        ),'''
new = '''        verdict(
            "TARGET-RETRY-BACKOFF",
            "Retry backoff compares wall-clock instants (vulnerable to skew); "
            "with_retry/SourceUnreachable were removed from the live tree by "
            "concurrent fleet work (2026-10-26), so the class is disclosed "
            "NOT-CHECKED.",
            "NOT-CHECKED",
        ),'''
assert old in src, "emit retry target anchor missing"
src = src.replace(old, new, 1)

old = '''            {
                "kind": "test-run",
                "verdict": "CONFIRMED",
                "claim": "Naive ISO stamps shift 5h when process TZ moves UTC → America/New_York.",
                "path": "tools/command-center/close.py",
                "detail": live["timezone_change"]["naive"],
            },'''
new = '''            {
                "kind": "test-run",
                "verdict": (
                    "CONFIRMED"
                    if live["tz_shift_world"]["naive_shifted"]
                    else "REFUTED"
                ),
                "claim": "Naive ISO stamps shift 5h when process TZ moves UTC → America/New_York (unrepresentable on win32; world disclosed in tz_shift_world).",
                "path": "tools/command-center/close.py",
                "detail": {
                    "naive": live["timezone_change"]["naive"],
                    "tz_shift_world": live["tz_shift_world"],
                },
            },
            {
                "kind": "test-run",
                "verdict": "CONFIRMED",
                "claim": "vi.freshness (live gate) is a naive strptime compare; beyond-window and backward-step both return STALE conservatively.",
                "path": "tools/marketplace/vuln_ingestion.py",
                "detail": {
                    "beyond_window": live["freshness"]["beyond_window_verdict"],
                    "backward_step": live["freshness"]["backward_step_verdict"],
                    "tz_invariant": live["freshness"]["verdict_tz_invariant_under_tz_change"],
                },
            },'''
assert old in src, "emit evidence anchor missing"
src = src.replace(old, new, 1)

old = '''        "honesty": {
            "production_absent": ['''
new = '''        "honesty": {
            "vi_anchor_drift_2026_10_26": (
                "parse_iso_z/iso_z/with_retry removed from the live tree by "
                "concurrent fleet work; freshness re-anchored on the live "
                "vi.freshness gate; retry_backoff disclosed NOT-CHECKED"
            ),
            "production_absent": ['''
assert old in src, "emit honesty anchor missing"
src = src.replace(old, new, 1)

EM.write_text(src, encoding="utf-8", newline="\n")
print("emit_artifact.py patched OK")
