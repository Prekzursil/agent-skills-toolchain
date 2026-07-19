#!/usr/bin/env python3
"""Conformance suite for hooks/_shared/completion.py -- the ONE shared completion predicate (C1).

EVERY case below is a REAL incident from 2026-07-19, not an invented scenario. The predicate exists
because five separate implementations of "is it done?" drifted apart on this box
(dbx_dispatch.py:202, dbx_harvest.py, dbx_batch_runner.py:157, _batch_runner_nb.py:141,
run-wave1.ps1 Test-UnitComplete) and two of them were silently losing work.

The governing rule: a predicate that decides done/present/complete must AND-gate >=2 mechanically
independent signals, and a FAILED DETECTOR must never be reported as an absence.

Run:  python test_completion.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import completion  # noqa: E402

DONE, FAILED, RUNNING, UNKNOWN = "DONE", "FAILED", "RUNNING", "UNKNOWN"


def _artifact(tmp: Path, name: str, body: str) -> str:
    p = tmp / name
    p.write_text(body, encoding="utf-8")
    return str(p)


def build_cases(tmp: Path):
    big = "x" * 2000
    good = _artifact(tmp, "good.md", big + "\nUNIT-COMPLETE: A001\n")
    no_sentinel = _artifact(tmp, "nosent.md", big + "\nthe end\n")
    partial = _artifact(tmp, "partial.md", "y" * 700 + "\nUNIT-COMPLETE: A002\n")  # 512<size<1024
    missing = str(tmp / "does-not-exist.md")

    # --- fixtures that DISCRIMINATE bytes-from-lines -------------------------------------------
    # Every fixture above puts the sentinel on the last line, where "last 600 BYTES" and
    # "last 6 LINES" agree -- so they cannot detect the PowerShell/Python tail drift at all.
    # These two split the readings apart, one in each direction.
    #
    # (a) sentinel + 8 trailing blank lines: inside 600 bytes, OUTSIDE the last 6 lines.
    #     A `Get-Content -Tail 6` gate says FAILED here; the byte gate says DONE. DONE is correct --
    #     trailing whitespace is not a failure, and a producer that flushes newlines would have had
    #     every unit silently rejected.
    trailing_nl = _artifact(tmp, "trailing.md", big + "\nUNIT-COMPLETE: A003\n" + "\n" * 8)
    #
    # (b) sentinel pushed >600 bytes back but still within the last 6 lines (one 900-char line
    #     after it). The byte gate says FAILED, a 6-line gate says DONE. FAILED is correct: the
    #     contract is "the sentinel TERMINATES the artifact", and honouring a sentinel buried under
    #     900 bytes of later output would accept a run that kept writing after claiming completion.
    buried = _artifact(tmp, "buried.md", big + "\nUNIT-COMPLETE: A004\n" + "z" * 900 + "\n")

    return [
        # ---- artifact AND-gate ------------------------------------------------------------
        ("clean success: exit0 + gated artifact", DONE,
         dict(artifact=good, sentinel="UNIT-COMPLETE", exit_code=0)),

        # dbx lesson: exit 0 is NOT proof. A zero exit with no artifact is a severed stream.
        ("severed-stream: exit0 but NO artifact", FAILED,
         dict(artifact=missing, sentinel="UNIT-COMPLETE", exit_code=0)),

        # F036 lesson: codex exited NON-ZERO *after* writing a complete artifact. The deliverable
        # exists and is valid -> DONE. run-wave1 scored this FAILED and under-counted real work.
        ("nonzero exit but artifact is valid", DONE,
         dict(artifact=good, sentinel="UNIT-COMPLETE", exit_code=1)),

        # dbx_harvest bug: its skip test was `size > 512` while the gate was `>=1024 + sentinel`,
        # so a partial counted as "already have it" and blocked re-fetching the good copy.
        ("partial in the 512-1024B window is NOT done", FAILED,
         dict(artifact=partial, sentinel="UNIT-COMPLETE", exit_code=0, min_bytes=1024)),

        # Same case with NO explicit min_bytes -- pins the DEFAULT itself. Found by mutation test:
        # flipping DEFAULT_MIN_BYTES back to dbx_harvest's 512 passed the whole suite because every
        # size case passed min_bytes explicitly. A caller that relies on the default is exactly the
        # one the original bug bit, so the default needs its own test.
        ("partial is NOT done under the DEFAULT gate (no min_bytes passed)", FAILED,
         dict(artifact=partial, sentinel="UNIT-COMPLETE", exit_code=0)),

        ("artifact present but sentinel missing", FAILED,
         dict(artifact=no_sentinel, sentinel="UNIT-COMPLETE", exit_code=0)),

        # ---- the detector-failure rule (the WMI 'Call cancelled' incident) -----------------
        # An empty/failed probe was read as "0 processes" and nearly produced a confident
        # "your MCP fleet emptied" while 672 procs / 58.47 GB were live.
        ("detector itself failed -> UNKNOWN, never FAILED", UNKNOWN,
         dict(artifact=missing, sentinel="UNIT-COMPLETE", detector_ok=False)),

        ("detector failed even with a good artifact -> UNKNOWN", UNKNOWN,
         dict(artifact=good, sentinel="UNIT-COMPLETE", exit_code=0, detector_ok=False)),

        # ---- liveness: DELTA cpu, never cumulative (the memguard incident) -----------------
        # memguard ranked victims by CUMULATIVE cpu, so a server blocked mid-call (near-zero cpu)
        # was killed while one busy 3h ago survived.
        ("alive and burning cpu -> RUNNING", RUNNING,
         dict(artifact=missing, sentinel="UNIT-COMPLETE", pid_alive=True, cpu_delta_s=2.5)),

        ("high CUMULATIVE cpu but zero DELTA is not running", FAILED,
         dict(artifact=missing, sentinel="UNIT-COMPLETE", pid_alive=True, cpu_delta_s=0.0,
              cpu_total_s=1560.0, idle_s=1200, stale_after_s=600)),

        # ---- staleness forces a terminal verdict (the codex-monitor IDLE-forever bug) -------
        # 12 threads sat IDLE indefinitely: husks at 0.2-0.4s cpu across 170-220 MINUTES.
        # A rollout ending in `message` (not `task_complete`) was neither running nor done.
        ("husk: alive but cpu-flat past staleness -> terminal", FAILED,
         dict(artifact=missing, sentinel="UNIT-COMPLETE", pid_alive=True, cpu_delta_s=0.0,
              idle_s=13200, stale_after_s=900)),

        ("fresh and cpu-flat but INSIDE the window -> still RUNNING", RUNNING,
         dict(artifact=missing, sentinel="UNIT-COMPLETE", pid_alive=True, cpu_delta_s=0.0,
              idle_s=30, stale_after_s=900)),

        # ---- process gone --------------------------------------------------------------------
        ("process gone with no artifact -> FAILED", FAILED,
         dict(artifact=missing, sentinel="UNIT-COMPLETE", pid_alive=False)),

        # the codex fan-out: the answer survived in the artifact even though the turn never closed
        ("process gone but artifact valid -> DONE", DONE,
         dict(artifact=good, sentinel="UNIT-COMPLETE", pid_alive=False)),

        # ---- insufficient evidence ------------------------------------------------------------
        # No artifact, no exit code, no liveness, no staleness rule: we do NOT know. Refusing to
        # guess is the whole point -- a single missing signal must not read as failure.
        ("no signals at all -> UNKNOWN", UNKNOWN,
         dict(artifact=None, sentinel="UNIT-COMPLETE")),

        # sentinel not required (some producers only guarantee size)
        ("no sentinel required: size alone gates", DONE,
         dict(artifact=no_sentinel, sentinel=None, exit_code=0)),

        # ---- bytes-vs-lines: the two cases that pin the tail contract -----------------------
        # These exist so test_completion_conformance.py can actually SEE the PowerShell
        # `Get-Content -Tail 6` drift. Without them both readings agree on every fixture and the
        # cross-language harness passes while the implementations disagree.
        ("sentinel + 8 trailing blank lines is still DONE (600 BYTES, not 6 lines)", DONE,
         dict(artifact=trailing_nl, sentinel="UNIT-COMPLETE", exit_code=0)),

        ("sentinel buried >600B back is NOT done (it must TERMINATE the artifact)", FAILED,
         dict(artifact=buried, sentinel="UNIT-COMPLETE", exit_code=0)),
    ]


def main() -> int:
    fails = 0
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for label, want, kwargs in build_cases(tmp):
            try:
                v = completion.classify(**kwargs)
                got = v.state
            except Exception as e:  # a crash is a failure, not an error to hide
                got = f"EXC:{type(e).__name__}:{e}"
            ok = got == want
            if not ok:
                fails += 1
            print(f"  {'OK ' if ok else 'XX '} {label}: got={got} want={want}")
    print(f"\nRESULT: {'ALL PASS' if not fails else str(fails) + ' FAIL'}  ({len(build_cases(Path(tempfile.gettempdir())))} cases)")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
