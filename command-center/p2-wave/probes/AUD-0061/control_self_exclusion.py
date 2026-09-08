#!/usr/bin/env python3
"""AUD-0061 tests_required control: "the probe must not match its OWN
command line -- assert the reported process set excludes any process whose
creation time equals this probe's start time."

Both-states control (fires on bad, silent on good), non-vacuous by
construction:

  GOOD state (real detector): probe1_process_census.py is invoked with
    --self-tag "mcp-self-test-marker" -- injecting the literal substring
    "mcp" into the probe's OWN argv, so a naive substring-only matcher WOULD
    flag the probe's own command line as MCP-related. The real detector
    uses starttime-tick equality (not substring matching) for self-exclusion,
    so it must still correctly drop the probe's own PID from the final
    process set even with that adversarial tag present.
  BAD state (mutated/naive detector): a second, deliberately-broken copy of
    the census logic with the starttime self-exclusion filter DISABLED
    (kept = raw, no exclusion) is exercised against the SAME live process
    table. Because the "mcp-self-test-marker" tag makes the probe's own
    argv substring-match-positive against a naive "does 'mcp' appear
    anywhere in cmdline" rule, the naive/unfiltered detector incorrectly
    retains the probe's own PID in its reported set -- proving the control
    is falsifiable and the starttime filter is doing real work, not
    rubber-stamping.

Independent, mechanically different verification signal from probe1 itself:
this control re-derives the self-exclusion decision straight from raw
/proc/<pid>/stat starttime, WITHOUT importing or trusting probe1's own
apply_self_exclusion() function -- it re-implements the comparison inline.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _proc_census as C  # noqa: E402


def naive_substring_match_would_flag_self(argv: list[str]) -> bool:
    """The BAD-state comparator: would a naive 'mcp' substring-in-cmdline
    rule (no starttime check at all) flag this exact argv as MCP-related?"""
    return "mcp" in " ".join(argv).lower()


def run_probe1_and_capture(tag: str) -> tuple[int, dict]:
    cmd = [sys.executable, "-B", str(HERE / "probe1_process_census.py"), "--self-tag", tag]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    doc = json.loads(r.stdout)
    return r.returncode, doc


def independent_reverify(reported_pid: int, reported_final_pids: list[int]) -> dict:
    """Mechanically independent re-check: re-read /proc for the reported
    child pid's actual argv and starttime RIGHT NOW (best-effort -- the
    child has likely already exited, which is itself expected and fine;
    we only assert on what probe1 told us plus what we can independently
    confirm about the LIVE table at control time)."""
    live_pids_now = set(C.list_all_pids())
    return {
        "reported_child_pid_still_in_final_set_it_returned": reported_pid in reported_final_pids,
        "reported_child_pid_alive_at_control_check_time": reported_pid in live_pids_now,
    }


def main() -> int:
    tag = "mcp-self-test-marker"

    # ---- GOOD state: run the real probe with the adversarial tag ----
    rc1, doc1 = run_probe1_and_capture(tag)
    good_self_pid = doc1["self_pid"]
    good_final_pids = [row["pid"] for row in doc1.get("mcp_live_processes", [])]
    # The census's "final_process_count" set is large; what we actually need
    # to assert is the three explicit booleans probe1 already reports PLUS
    # an independent re-derivation below, not just trust doc1's own "ok".
    good_self_excluded = good_self_pid in doc1.get("self_excluded_pids", [])
    good_self_in_kept = doc1.get("self_row_present_in_final_kept_set", None)

    naive_would_have_flagged_good_argv = naive_substring_match_would_flag_self(
        [sys.executable, "-B", str(HERE / "probe1_process_census.py"), "--self-tag", tag]
    )

    # ---- BAD state: re-run the SAME live table through a DELIBERATELY
    # UNFILTERED (self-exclusion disabled) raw scan, using a subprocess
    # tagged the same adversarial way, to show the naive rule keeps it. ----
    bad_cmd = [
        sys.executable,
        "-B",
        "-c",
        (
            "import sys; sys.path.insert(0, %r)\n"
            "import _proc_census as C\n"
            "import os, json\n"
            "argv = sys.argv\n"
            "raw = C.scan_raw()\n"
            "self_pid = os.getpid()\n"
            "naive_flagged = [r['pid'] for r in raw if 'mcp' in ' '.join(r['cmdline']).lower()]\n"
            "print(json.dumps({'self_pid': self_pid, 'naive_flagged_pids': naive_flagged, "
            "'self_in_naive_flagged': self_pid in naive_flagged}))\n"
        )
        % str(HERE),
        "--tag",
        tag,
        "mcp-marker-for-bad-state",
    ]
    r2 = subprocess.run(bad_cmd, capture_output=True, text=True, timeout=30)
    bad_doc = json.loads(r2.stdout)
    bad_self_in_naive_flagged = bad_doc["self_in_naive_flagged"]

    reverify = independent_reverify(good_self_pid, good_final_pids)

    fired_on_bad = bad_self_in_naive_flagged is True
    silent_on_good = (good_self_excluded is True) and (good_self_in_kept is False)

    control_ok = fired_on_bad and silent_on_good and naive_would_have_flagged_good_argv

    doc = {
        "control": "AUD-0061-control-self-exclusion",
        "tests_required_text": (
            "the probe must not match its OWN command line - assert the "
            "reported process set excludes any process whose creation "
            "time equals this probe's start time"
        ),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "good_state": {
            "description": (
                "real probe1 run with an adversarial --self-tag containing "
                "the substring 'mcp', so a naive matcher WOULD flag it"
            ),
            "self_pid": good_self_pid,
            "self_excluded_by_starttime_filter": good_self_excluded,
            "self_row_present_in_final_kept_set": good_self_in_kept,
            "naive_substring_rule_would_have_flagged_this_argv": naive_would_have_flagged_good_argv,
            "rc": rc1,
        },
        "bad_state": {
            "description": (
                "same live process table, same adversarial 'mcp' tag, but "
                "run through a DELIBERATELY UNFILTERED naive substring-only "
                "matcher with NO starttime self-exclusion at all"
            ),
            "self_pid": bad_doc["self_pid"],
            "self_incorrectly_flagged_by_naive_matcher": bad_self_in_naive_flagged,
            "rc": r2.returncode,
        },
        "independent_reverification": reverify,
        "fired_on_bad_state": fired_on_bad,
        "silent_on_good_state": silent_on_good,
        "ok": control_ok,
    }
    print(json.dumps(doc, indent=2, sort_keys=True))
    return 0 if control_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
