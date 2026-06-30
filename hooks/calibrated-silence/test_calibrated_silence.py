#!/usr/bin/env python3
"""Tests for calibrated_silence.py. Runs WITHOUT pytest: `python test_calibrated_silence.py`.

Covers the SDT math (cold-start allow, high-ignore suppress, high-acted allow, value
weighting, fatigue raises the bar / flips a borderline case), fail-open on a corrupt
ledger, the kill-switch, Wilson smoothing, and record/read round-trips.
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import calibrated_silence as cs  # noqa: E402

_FAILS = []
OLD = time.time() - 100_000  # outside the density window -> no accidental fatigue


def ok(name, cond):
    print(("PASS" if cond else "FAIL") + f": {name}")
    if not cond:
        _FAILS.append(name)


def row(t, reaction="unknown", ts=None, sid="hist", surfaced=True, ck="ck"):
    return {
        "ts": OLD if ts is None else ts,
        "type": t,
        "context_key": ck,
        "session_id": sid,
        "surfaced": surfaced,
        "reaction": reaction,
    }


def many(t, acted, ignored, **kw):
    return [row(t, "acted", **kw) for _ in range(acted)] + [
        row(t, "ignored", **kw) for _ in range(ignored)
    ]


def mk_ledger(rows):
    f = Path(tempfile.mkdtemp(prefix="calsil-")) / "interjections.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return f


def decide(itype, rows, **ctx):
    p = mk_ledger(rows)
    ctx["ledger_path"] = str(p)
    return cs.should_interject(itype, ctx)


def main():
    os.environ.pop("CALIBRATED_SILENCE", None)  # ensure not globally disabled

    # 1. Cold start: empty ledger -> ALLOW (don't suppress before learning).
    allow, reason = decide("suggestion", [])
    ok("empty ledger -> allow (cold-start)", allow and "cold-start" in reason)

    # 2. Low n (< MIN_SAMPLES) even if all-ignored -> still ALLOW.
    allow, _ = decide("suggestion", many("suggestion", 0, 3))
    ok("n<MIN all-ignored -> allow (cold-start)", allow)

    # 3. High-ignore, enough samples -> SUPPRESS (the gate CAN say no).
    allow, reason = decide("suggestion", many("suggestion", 1, 11))
    ok("high-ignore suggestion -> suppress", allow is False and "suppress" in reason)

    # 4. High-acted -> ALLOW.
    allow, _ = decide("gem", many("gem", 9, 1))
    ok("high-acted gem -> allow", allow)

    # 5. Borderline 50/50 with NO fatigue -> ALLOW.
    allow_base, rbase = decide("route", many("route", 6, 6))
    ok("route 6/6 no-fatigue -> allow", allow_base)

    # 6. Same borderline + injected fatigue -> SUPPRESS (fatigue raises the bar / FLIP).
    allow_fat, rfat = decide(
        "route", many("route", 6, 6), correction_rate=0.9, prompt="no fix it"
    )
    ok("route 6/6 + fatigue -> suppress (flip)", allow_fat is False)
    ok("fatigue raised the criterion vs baseline", _crit(rfat) > _crit(rbase))

    # 7. Value weighting: at the SAME smoothed hit-rate a high-value 'gem' clears the bar
    #    while a low-value 'nudge' does not.
    allow_gem, _ = decide("gem", many("gem", 5, 6))
    allow_nudge, _ = decide("nudge", many("nudge", 5, 6))
    ok(
        "value weighting: gem allows where nudge suppresses",
        allow_gem and (allow_nudge is False),
    )

    # 8. Density fatigue: many recent surfaced interjections THIS session raise the bar.
    now = time.time()
    hist = many("route", 6, 6)  # old learning history
    dense = [
        row("route", "unknown", ts=now - 10, sid="S", surfaced=True) for _ in range(4)
    ]
    allow_dense, rdense = decide("route", hist + dense, session_id="S", now=now)
    ok(
        "recent density -> suppress borderline",
        allow_dense is False and "dens=" in rdense,
    )

    # 9. Late hour adds fatigue (probe fatigue_bump directly for determinism).
    late = time.mktime((2026, 6, 29, 3, 0, 0, 0, 0, -1))
    bump_late, det_late = cs.fatigue_bump("route", {"now": late}, [])
    bump_day, _ = cs.fatigue_bump(
        "route", {"now": time.mktime((2026, 6, 29, 14, 0, 0, 0, 0, -1))}, []
    )
    ok("late hour raises fatigue", bump_late > bump_day and "late=" in det_late)

    # 10. Fatigue is clamped to FATIGUE_MAX (never total silence).
    bump_max, _ = cs.fatigue_bump(
        "route", {"correction_rate": 1.0, "prompt": "no", "now": late}, []
    )
    ok("fatigue clamped to FATIGUE_MAX", bump_max <= cs.FATIGUE_MAX + 1e-9)

    # 11. A high-value high-hit interjection still punches through MAX fatigue.
    allow_punch, _ = decide(
        "gem", many("gem", 18, 2), correction_rate=1.0, prompt="no", now=late
    )
    ok("high-EV gem survives max fatigue", allow_punch)

    # 12. Fail-open: a read error returns ALLOW (suppression is the dangerous failure).
    orig = cs.read_rows
    try:
        cs.read_rows = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        allow, reason = cs.should_interject("suggestion", {})
        ok("read error -> allow (fail-open)", allow and "fail-open" in reason)
    finally:
        cs.read_rows = orig

    # 13. Corrupt ledger lines are skipped, not fatal.
    f = Path(tempfile.mkdtemp(prefix="calsil-")) / "interjections.jsonl"
    f.write_text(
        "{not json\n" + json.dumps(row("gem", "acted")) + "\ngarbage]]",
        encoding="utf-8",
    )
    parsed = cs.read_rows(f)
    ok("corrupt lines skipped, valid kept", len(parsed) == 1)
    allow, _ = cs.should_interject("gem", {"ledger_path": str(f)})
    ok("corrupt-but-parseable ledger -> no crash", allow in (True, False))

    # 14. Fully-garbage ledger -> reads as empty -> cold-start allow.
    f2 = Path(tempfile.mkdtemp(prefix="calsil-")) / "interjections.jsonl"
    f2.write_text("@@@@\n####\n", encoding="utf-8")
    allow, reason = cs.should_interject("suggestion", {"ledger_path": str(f2)})
    ok("garbage ledger -> allow (empty=cold-start)", allow)

    # 15. Kill-switch forces ALLOW regardless of a suppress-worthy ledger.
    os.environ["CALIBRATED_SILENCE"] = "off"
    try:
        allow, reason = decide("suggestion", many("suggestion", 0, 20))
        ok(
            "kill-switch CALIBRATED_SILENCE=off -> allow",
            allow and "disabled" in reason,
        )
    finally:
        os.environ.pop("CALIBRATED_SILENCE", None)

    # 16. Wilson center: neutral at n=0, pulls a low-n estimate toward 0.5, exact at high n.
    ok("wilson(0,0)=0.5", abs(cs.wilson_center(0, 0) - 0.5) < 1e-9)
    ok("wilson low-n pulled toward 0.5", cs.wilson_center(0, 2) > 0.10)
    ok("wilson high-n near raw rate", abs(cs.wilson_center(80, 100) - 0.8) < 0.05)
    ok(
        "wilson monotonic in successes",
        cs.wilson_center(8, 10) > cs.wilson_center(2, 10),
    )

    # 17. record_interjection round-trips and feeds counts_by_type.
    led = Path(tempfile.mkdtemp(prefix="calsil-")) / "interjections.jsonl"
    ok("record append #1", cs.record_interjection("route", "skill:x", "s1", path=led))
    ok("record append #2", cs.record_interjection("route", "mcp:y", "s1", path=led))
    rows = cs.read_rows(led)
    ok("two rows recorded", len(rows) == 2 and rows[0]["reaction"] == "unknown")
    cbt = cs.counts_by_type(rows)
    ok("counts_by_type counts unknowns", cbt["route"]["unknown"] == 2)

    # 18. hit_rate reflects the ledger.
    p, a, i = cs.hit_rate("gem", many("gem", 7, 3))
    ok("hit_rate acted/ignored", a == 7 and i == 3 and p > 0.5)

    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): {_FAILS}")
        return 1
    print("ALL PASS")
    return 0


def _crit(reason):
    """Pull the criterion float out of a should_interject reason string for comparison."""
    import re

    m = re.search(r"crit=([0-9.]+)", reason)
    return float(m.group(1)) if m else -1.0


if __name__ == "__main__":
    sys.exit(main())
