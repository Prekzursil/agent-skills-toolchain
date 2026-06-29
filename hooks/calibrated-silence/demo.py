#!/usr/bin/env python3
"""CALIBRATED SILENCE — standalone demo of the learning loop (no wiring required).

Proves, against an isolated temp ledger, the four behaviours that matter:
  1. high-ignore history          -> should_interject('suggestion') == False (suppress)
  2. high-acted history           -> should_interject('gem')        == True  (allow)
  3. a borderline type            -> ALLOW with no fatigue ...
                                     ... then SUPPRESS once a fatigue signal is injected
                                         (the criterion visibly rises)
  4. the full record -> react -> learn loop shifts a decision from suppress to allow

Run: `python demo.py`  (exits 0 on success, 1 if any invariant fails).
"""
import sys
import tempfile
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import calibrated_silence as cs   # noqa: E402
import log_reaction as lr         # noqa: E402

FAILS = []


def check(label, cond, detail=""):
    print(f"  [{'OK' if cond else 'XX'}] {label}" + (f"  -- {detail}" if detail else ""))
    if not cond:
        FAILS.append(label)


def fresh_ledger(rows):
    f = Path(tempfile.mkdtemp(prefix="calsil-demo-")) / "interjections.jsonl"
    cs._atomic_write_rows(rows, f)
    return f


def hist(t, acted, ignored, ts):
    return ([{"ts": ts, "type": t, "context_key": "ck", "session_id": "h",
              "surfaced": True, "reaction": "acted"} for _ in range(acted)]
            + [{"ts": ts, "type": t, "context_key": "ck", "session_id": "h",
                "surfaced": True, "reaction": "ignored"} for _ in range(ignored)])


def main():
    old = time.time() - 100_000  # old history -> contributes hit-rate, not density fatigue

    print("\n1) HIGH-IGNORE 'suggestion' (1 acted / 11 ignored) -> should suppress")
    led = fresh_ledger(hist("suggestion", 1, 11, old))
    allow, reason = cs.should_interject("suggestion", {"ledger_path": str(led)})
    check("suggestion suppressed", allow is False, reason)

    print("\n2) HIGH-ACTED 'gem' (9 acted / 1 ignored) -> should allow")
    led = fresh_ledger(hist("gem", 9, 1, old))
    allow, reason = cs.should_interject("gem", {"ledger_path": str(led)})
    check("gem allowed", allow is True, reason)

    print("\n3) BORDERLINE 'route' (6 acted / 6 ignored): allow w/o fatigue, suppress with")
    led = fresh_ledger(hist("route", 6, 6, old))
    allow0, r0 = cs.should_interject("route", {"ledger_path": str(led)})
    allow1, r1 = cs.should_interject("route", {
        "ledger_path": str(led), "correction_rate": 0.9, "prompt": "no fix it"})
    check("route allowed when fresh", allow0 is True, r0)
    check("route suppressed under fatigue", allow1 is False, r1)
    check("fatigue raised the criterion", _crit(r1) > _crit(r0),
          f"crit {_crit(r0):.3f} -> {_crit(r1):.3f}")

    print("\n4) FULL LOOP: record interjections, classify the user's reactions, re-decide")
    led = Path(tempfile.mkdtemp(prefix="calsil-demo-")) / "interjections.jsonl"
    cs.LEDGER_PATH = led
    # Start from a suppress-worthy history for 'route' (mostly ignored).
    cs._atomic_write_rows(hist("route", 0, 6, old), led)
    before, rb = cs.should_interject("route", {"ledger_path": str(led)})
    check("route starts suppressed (6 ignores)", before is False, rb)
    # The agent surfaces 'route' suggestions and the user repeatedly ACTS on them (the
    # skill actually runs). We record each, then the reaction logger classifies them from
    # the EXTERNAL signal (skill:systematic-debugging in the turn's tool-uses). Aged
    # timestamps isolate the pure hit-rate effect from recency/density fatigue, so this
    # shows learning alone flipping the decision. (Recent records would instead trip the
    # density term and stay suppressed -- the anti-fatigue behaviour, demonstrated in #3.)
    for i in range(12):
        cs.record_interjection("route", "skill:systematic-debugging", "live",
                               path=led, now=old + i)
    rows = cs.read_rows(led)
    _rows, n = lr.apply_reactions(rows, "live", "thanks",
                                  {"skill:systematic-debugging"}, now=old + 1000)
    cs._atomic_write_rows(_rows, led)
    p, a, ig = cs.hit_rate("route", cs.read_rows(led))
    after, ra = cs.should_interject("route", {"ledger_path": str(led)})
    check("reactions classified as acted", n == 12, f"{n} rows updated")
    check("route now allowed after acted reactions were learned", after is True,
          f"acted={a} ignored={ig} p={p:.2f} :: {ra}")

    print()
    if FAILS:
        print(f"DEMO FAILED: {FAILS}")
        return 1
    print("DEMO OK — calibrated-silence loop verified end to end.")
    return 0


def _crit(reason):
    import re
    m = re.search(r"crit=([0-9.]+)", reason)
    return float(m.group(1)) if m else -1.0


if __name__ == "__main__":
    sys.exit(main())
