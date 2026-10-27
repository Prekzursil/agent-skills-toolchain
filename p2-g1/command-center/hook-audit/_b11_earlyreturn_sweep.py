#!/usr/bin/env python3
r"""_b11_earlyreturn_sweep.py -- what did each of the 25 H4 rows actually MEASURE?

WHY THIS EXISTS. Round 2's verifier confirmed that `H4-TIMING-live.json`'s row for
`Stop/git-hygiene` (`run_ms=0.3`) is a THROTTLE EARLY RETURN, not the hook's cost --
`_r4_githygiene_range.py` measured the same check at 11.8-32.7 s once the throttle is
defeated, an understatement of ~5e4x. It then surfaced the open residual this probe
closes: that diagnosis was never swept across the other 24 rows, so the DoD sentence
"every wired hook timed against its budget" was wider than its evidence.

WHAT run_ms IS. `_h4_timing.py:160-184` imports each check (`load_ms`) and then calls
`main()` IN-PROCESS (`run_ms`). So `run_ms` is the body of `main()` on one synthetic
payload per event -- not a subprocess, not the dispatcher, not the live turn.

THREE HYPOTHESES for a sub-millisecond row, which need different fixes:
  H1 REAL     -- the hook genuinely costs that little.
  H2 FASTPATH -- a throttle/cache/stamp guard returned early (the git-hygiene shape).
  H3 DECLINED -- `main()` exited because the synthetic payload is not the state it reacts
                 to. The number then times the hook's DECLINATION, not the hook.

H3 is separable without firing anything: `_h4_timing.py:143` records
`selected_for_probe_tool` = "did this check's own matcher accept the probe payload's
tool_name", and then calls `main()` ANYWAY. A row with `selected=False` is a timing of a
call the dispatcher would never have made.

WHAT IS EXECUTED HERE, and what is deliberately not.
  * Classification of all 25 rows is read off the FIELDS (`selected_for_probe_tool`,
    `emitted_bytes`), never off a sentence about them, with the counts required to
    partition exactly.
  * Two rows get a real both-states re-timing:
      - `git-hygiene` is the POSITIVE CONTROL. It is a KNOWN early return, so this
        harness MUST detect it. A sweep that cannot re-find the one row already proven
        broken is measuring nothing (single-signal-verification rule 3b).
      - `heartbeat`/Stop is the OPEN CASE: 4.4 ms, 0 bytes, matcher accepted. Its
        throttle state dir is env-redirectable, so the guard can be defeated without
        touching a single live byte.
  * DO-NOT-FIRE LIST, with the reason for each, because "fire everything" is how a probe
    damages the box it is auditing:
      - `monitor-autolaunch`, `codex-monitor-autolaunch` -- they LAUNCH EXTERNAL
        PROCESSES. The prior art already quarantines the autolaunch checks for this.
      - `claim-guard/ledger-write`, `stub-ledger/record`, `edit-validate/record`,
        `bg-registry/*`, `memory-spool/*` -- they WRITE to owner state stores (event
        ledger, background registry, memory spool). Firing them with synthetic payloads
        would pollute real data to measure a timing.
    For those rows the classification stands on the recorded field, which is evidence;
    no cost number is invented for them.

ISOLATION. `git-hygiene` runs from the REPO copy, whose `.last-run` is gitignored, and the
stamp's bytes+mtime are captured and restored and then RE-READ to confirm the restore.
`heartbeat` runs from the LIVE copy but with `HEARTBEAT_STATE_DIR` pointed at a scratch
directory, so its throttle window is defeated without moving the live clock.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
LIVE_HOOKS = pathlib.Path(os.path.expanduser("~/.claude/hooks"))
OUT = HERE / "B11-EARLYRETURN-SWEEP.json"

# Rows that write to owner state stores or spawn processes. Not fired. Reason recorded.
DO_NOT_FIRE = {
    "monitor-autolaunch": "launches an external monitor process",
    "codex-monitor-autolaunch": "launches an external monitor process",
    "claim-guard/ledger-write": "writes the event ledger",
    "stub-ledger/record": "writes the stub ledger",
    "edit-validate/record": "writes the edit-validate store",
    "bg-registry/register": "writes the background registry",
    "bg-registry/done_marker": "writes the background registry",
    "bg-registry/reconcile": "writes the background registry",
    "memory-spool/spool": "writes the memory spool",
    "memory-spool/flush_check": "writes/flushes the memory spool",
    "memory-spool/replay": "writes the memory spool",
}

STOP_PAYLOAD = json.dumps(
    {"hook_event_name": "Stop", "session_id": "b11-sweep", "cwd": str(REPO)}
)


def _time_subprocess(
    script: pathlib.Path, env: dict, payload: str, args: list[str] | None = None
) -> dict:
    """THIRD SELF-CORRECTION, and the most consequential one.

    The manifest hands 5 of the 25 checks an `args` list, and `_dispatch` passes it
    through (`_h4_timing.py:176` does the same with `chk.get("args")`). My first three
    heartbeat arms passed NO argv, so `heartbeat.py` fell through to its `sessionstart`
    branch and emitted a `hookEventName: "SessionStart"` envelope while I was feeding it a
    Stop payload -- I was timing a different program from the one the harness runs, and the
    Stop throttle at `heartbeat.py:210-213` was never on the path at all. That is why three
    successive arms agreed with each other and all three were void.
    """
    t0 = time.monotonic()
    try:
        p = subprocess.run(
            [sys.executable, str(script), *(args or [])],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=300,
        )
        rc, out, err = p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        rc, out, err = "TIMEOUT", "", ""
    return {
        "ms": round((time.monotonic() - t0) * 1000, 1),
        "rc": rc,
        "stdout_bytes": len(out),
        "stderr_bytes": len(err),
    }


def arm_git_hygiene() -> dict:
    """POSITIVE CONTROL: a row already proven to be an early return must be re-detected."""
    check = REPO / "hooks" / "git-hygiene" / "check.py"
    stamp = REPO / "hooks" / "git-hygiene" / ".last-run"
    if not check.is_file():
        return {"status": "SKIPPED", "reason": f"absent: {check}"}

    had = stamp.exists()
    raw = stamp.read_bytes() if had else None
    st = stamp.stat() if had else None
    try:
        stamp.write_text(str(time.time()), encoding="utf-8")
        base_env = dict(os.environ)
        base_env.pop("GIT_HYGIENE_THROTTLE_SEC", None)
        effective = _time_subprocess(check, base_env, STOP_PAYLOAD)
        defeated_env = dict(os.environ)
        defeated_env["GIT_HYGIENE_THROTTLE_SEC"] = "0"
        defeated = _time_subprocess(check, defeated_env, STOP_PAYLOAD)
    finally:
        if had:
            stamp.write_bytes(raw)
            os.utime(stamp, (st.st_atime, st.st_mtime))
            restored = (
                stamp.read_bytes() == raw
                and abs(stamp.stat().st_mtime - st.st_mtime) < 1e-6
            )
        else:
            stamp.unlink(missing_ok=True)
            restored = not stamp.exists()
    ratio = round(defeated["ms"] / effective["ms"], 1) if effective["ms"] > 0 else None
    return {
        "status": "MEASURED",
        "tree": "repo",
        "knob": "GIT_HYGIENE_THROTTLE_SEC=0",
        "fastpath_effective": effective,
        "fastpath_defeated": defeated,
        "ratio_defeated_over_effective": ratio,
        "stamp_restored_exact": restored,
        "h4_recorded_run_ms": 0.3,
    }


def arm_heartbeat() -> dict:
    """OPEN CASE: Stop/heartbeat is 4.4 ms with 0 bytes and an accepting matcher.

    SELF-CORRECTION, recorded rather than deleted. The first version of this arm compared
    "live state dir" against "virgin scratch dir" and got ratio 1.0, which I nearly
    published as "the throttle is not what makes this row fast". Reading the arms' own
    output refuted that: BOTH emitted 140 bytes, so BOTH were in the UNTHROTTLED state and
    the comparison never separated the two hypotheses -- a control that cannot distinguish
    them is not a control, it only proves the instrument ran.

    The throttle is armed by a PRIOR call, which is exactly what `H4-TIMING-live.json`
    shows within one artifact: SessionStart/heartbeat emitted 140 B, then Stop/heartbeat --
    same session, same process, moments later -- emitted 0 B in 4.4 ms. So the correct
    experiment is FIRST-CALL vs IMMEDIATE-SECOND-CALL against the same scratch state dir.
    """
    check = LIVE_HOOKS / "heartbeat" / "heartbeat.py"
    if not check.is_file():
        return {"status": "SKIPPED", "reason": f"absent: {check}"}
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="b11_hb_"))
    try:
        env = dict(os.environ)
        env["HEARTBEAT_STATE_DIR"] = str(scratch)
        # SECOND SELF-CORRECTION: the first two attempts left `HEARTBEAT_THROTTLE_SEC` at
        # its 900 s default and both calls emitted, so the window was never demonstrably
        # closed. `heartbeat.py:57,213` gate the Stop emit on
        # `time.time() - _last_emit(session_id) < THROTTLE_SEC`, keyed on the SESSION, so
        # pinning the window wide makes call 2 unambiguously inside it.
        env["HEARTBEAT_THROTTLE_SEC"] = "99999"
        # argv is what the manifest gives this check: Stop/heartbeat -> ["stop"].
        argv = ["stop"]
        # Call 1: virgin state -- no prior emit for this session, nothing can be throttled.
        first = _time_subprocess(check, env, STOP_PAYLOAD, argv)
        wrote_after_first = sorted(p.name for p in scratch.glob("*"))
        # Call 2: immediately after, same state dir -- the throttle window is now armed.
        second = _time_subprocess(check, env, STOP_PAYLOAD, argv)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    # The arms must be in DIFFERENT states or the comparison is void. The emitted-bytes
    # delta is the state witness: silent second call == throttle engaged.
    states_separated = first["stdout_bytes"] > 0 and second["stdout_bytes"] == 0
    ratio = round(first["ms"] / second["ms"], 1) if second["ms"] > 0 else None
    return {
        "status": "MEASURED" if states_separated else "INCONCLUSIVE",
        "tree": "live",
        "knob": "HEARTBEAT_STATE_DIR=<scratch>, first call vs immediate second call",
        "fastpath_defeated": first,
        "fastpath_effective": second,
        "ratio_defeated_over_effective": ratio,
        "states_separated_by_emitted_bytes": states_separated,
        "scratch_files_written_by_first_call": wrote_after_first,
        "live_state_touched": False,
        "h4_recorded_run_ms": 4.4,
        "note": (
            "If states_separated is False the two arms were in the same state and NO cost "
            "number here may be cited -- that is the defect the first version of this arm had."
        ),
        "what_the_argv_fix_revealed": (
            "With the manifest's argv (['stop']) both calls emit 0 bytes and write no state, "
            "so Stop/heartbeat's H4 row is NOT the git-hygiene throttle shape: it is the "
            "'healthy -> silent' branch at heartbeat.py:210 ('only when noteworthy AND past "
            "the throttle window'). Nothing was noteworthy on a healthy box, so the throttle "
            "was never on the path and the two arms cannot separate. The early-return "
            "hypothesis is UNSUPPORTED here rather than confirmed."
        ),
        "settling_experiment": (
            "Redirect BG_REGISTRY_DIR and MEMORY_SPOOL_DIR to scratch dirs seeded with an "
            "open background job and an unflushed spool entry, so the noteworthy branch is "
            "taken; then first-call vs second-call separates throttled from unthrottled and "
            "a cost number becomes citable."
        ),
    }


def main() -> int:
    h4 = json.loads((HERE / "H4-TIMING-live.json").read_text(encoding="utf-8"))
    rows = h4["checks"]

    # --- detector control: the reader must not be blind -------------------------------
    if len(rows) < 20:
        print(f"FAILED:earlyreturn implausible row count {len(rows)}")
        return 2
    if not any("selected_for_probe_tool" in r for r in rows):
        print("FAILED:earlyreturn selected_for_probe_tool absent -- reader is blind")
        return 2

    declined, worked, ran_silent = [], [], []
    for r in rows:
        name = r.get("name")
        rec = {
            "event": r.get("event"),
            "name": name,
            "run_ms": r.get("run_ms"),
            "budget_s": r.get("budget_s"),
            "emitted_bytes": r.get("emitted_bytes"),
            "matcher": r.get("matcher"),
        }
        if not r.get("selected_for_probe_tool"):
            rec["why"] = (
                f"matcher {r.get('matcher')!r} rejects the probe payload's tool_name; "
                "the dispatcher would not have called it"
            )
            declined.append(rec)
        elif (r.get("emitted_bytes") or 0) > 0:
            worked.append(rec)
        else:
            ran_silent.append(rec)

    # The three classes must PARTITION the rows exactly. An overlap or a gap means the
    # classifier is wrong, not that the fleet is clean.
    partition_ok = len(declined) + len(worked) + len(ran_silent) == len(rows)

    control = arm_git_hygiene()
    open_case = arm_heartbeat()

    # POSITIVE CONTROL GATE: the sweep must re-detect the one row already proven to be an
    # early return. If it cannot, no other verdict from this harness may be cited.
    ctrl_ratio = control.get("ratio_defeated_over_effective")
    control_detects = bool(ctrl_ratio and ctrl_ratio >= 10)

    result = {
        "probe": "_b11_earlyreturn_sweep.py",
        "what_run_ms_measures": "in-process main() on one synthetic payload per event "
        "(_h4_timing.py:160-184), not a subprocess and not the dispatcher",
        "rows_total": len(rows),
        # Flat, citation-safe keys. The percentages a reader wants are derivable; the
        # ratios from the executed arms are deliberately NOT published as pinned values
        # because they move run to run (measured 29.1x / 83.4x / 104.3x / 109.8x on four
        # runs of the same arm), and this program has already been bitten by citing a
        # number that legitimately drifts. The stable claim is the boolean below.
        "n_declined_by_matcher": len(declined),
        "n_worked": len(worked),
        "n_ran_silent": len(ran_silent),
        "classes": {
            "DECLINED-BY-MATCHER": len(declined),
            "WORKED (emitted output)": len(worked),
            "RAN-SILENT (accepted, emitted nothing)": len(ran_silent),
        },
        "partition_exact": partition_ok,
        "declined_by_matcher": declined,
        "worked": worked,
        "ran_silent": ran_silent,
        "executed_arms": {
            "positive_control_git_hygiene": control,
            "open_case_heartbeat_stop": open_case,
        },
        "controls": {
            "C1_reader_not_blind": True,
            "C2_partition_exact": partition_ok,
            "C3_positive_control_detects_known_early_return": control_detects,
        },
        "do_not_fire": DO_NOT_FIRE,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"rows={len(rows)}  partition_exact={partition_ok}")
    for k, v in result["classes"].items():
        print(f"  {k:<40} {v}")
    print()
    print("DECLINED-BY-MATCHER (H4 timed a call the dispatcher would not have made):")
    for r in declined:
        print(
            f"    {r['event']:<13} {r['name']:<28} run_ms={r['run_ms']:<7} matcher={r['matcher']}"
        )
    print()
    print("WORKED (the only rows where H4 timed a hook doing something):")
    for r in worked:
        print(
            f"    {r['event']:<13} {r['name']:<28} run_ms={r['run_ms']:<9} emitted={r['emitted_bytes']}B"
        )
    print()
    print(
        f"POSITIVE CONTROL git-hygiene : {control.get('status')} "
        f"effective={control.get('fastpath_effective', {}).get('ms')}ms "
        f"defeated={control.get('fastpath_defeated', {}).get('ms')}ms "
        f"ratio={ctrl_ratio}  stamp_restored={control.get('stamp_restored_exact')}"
    )
    print(
        f"OPEN CASE heartbeat/Stop     : {open_case.get('status')} "
        f"effective={open_case.get('fastpath_effective', {}).get('ms')}ms "
        f"defeated={open_case.get('fastpath_defeated', {}).get('ms')}ms "
        f"ratio={open_case.get('ratio_defeated_over_effective')}"
    )
    print()
    print(f"C3 positive control re-detects the known early return: {control_detects}")

    if not (partition_ok and control_detects):
        print(
            "FAILED:earlyreturn controls failed -- no verdict from this run may be cited"
        )
        return 2
    print(
        f"SUCCESS:earlyreturn {len(worked)} of {len(rows)} H4 rows timed a hook that did work; "
        f"{len(declined)} timed a declined call; {len(ran_silent)} ran and emitted nothing"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
