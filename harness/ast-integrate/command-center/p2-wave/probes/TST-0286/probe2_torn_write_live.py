#!/usr/bin/env python3
"""Probe 2: torn-write resume fails loudly; live-model field boundary.

Torn-write: a child is SIGKILL'd mid-persist. Resume must raise TornWriteError
and must not rebuild a transcript from the half-written log.

Live-model arm: two live-mode runs diverge on the full event blob and match
on the stripped canonical transcript. Named fields are classified.

Independent reviewer path on this Linux worker: re-compute the three hashes
under /bin/sh (not the parent python process). pwsh7 / Git Bash are probed
and recorded; they are NOT-CHECKED when absent rather than faked.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import store as ST  # noqa: E402
import simulate as S  # noqa: E402
from store import TornWriteError  # noqa: E402

OUT = HERE / "probe2-torn-write-live.json"
SEED = S.DEFAULT_SEED


def _torn_write_trial(tmp: Path) -> dict:
    log_path = tmp / "torn.clog"
    proc = subprocess.Popen(
        [sys.executable, "-B", str(HERE / "store.py"), "--slow-append", str(log_path)],
        cwd=str(HERE),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # 60s not 6s: under memory pressure on the measurement host, the child
    # python process can take >6s just to start. The trial still requires the
    # prefix to appear and the resume to fail loudly; only the wait is longer.
    deadline = time.time() + 60.0
    saw = False
    size_at_kill = 0
    magic = len(ST.MAGIC)
    while time.time() < deadline:
        if log_path.is_file():
            size_at_kill = log_path.stat().st_size
            if size_at_kill >= magic + 24:
                saw = True
                break
        time.sleep(0.02)
    if not saw:
        proc.kill()
        proc.wait(timeout=5)
        return {
            "killed": False,
            "reason": "child-never-wrote-prefix",
            "pid": proc.pid,
            "size": size_at_kill,
            "fired_on_bad_state": False,
            "silent_on_good_state": False,
        }
    os.kill(proc.pid, signal.SIGKILL)
    proc.wait(timeout=5)
    size_after = log_path.stat().st_size if log_path.is_file() else 0
    full_min = magic + 8 + 32 + 8192
    truncated = 0 < size_after < full_min
    torn_error = None
    fired = False
    resumed_anyway = False
    try:
        S.resume(log_path)
        resumed_anyway = True
    except TornWriteError as exc:
        fired = True
        torn_error = str(exc)
    except Exception as exc:  # noqa: BLE001
        torn_error = f"{type(exc).__name__}:{exc}"
        fired = "torn-write" in torn_error or "truncated" in torn_error.lower()
    good_path = tmp / "clean.clog"
    S.pause_at(SEED, S.PAUSE_AFTER, good_path)
    clean_resume = S.resume(good_path)
    silent_on_good = any(e.get("kind") == "run_completed" for e in clean_resume)
    return {
        "killed": True,
        "pid": proc.pid,
        "size_at_kill": size_at_kill,
        "size_after": size_after,
        "full_record_min": full_min,
        "truncated": truncated,
        "fired_on_bad_state": fired and truncated and not resumed_anyway,
        "silent_on_good_state": silent_on_good,
        "resumed_anyway": resumed_anyway,
        "torn_error": torn_error,
        "clean_resume_decision": next(
            (e["decision"] for e in reversed(clean_resume) if e.get("kind") == "run_completed"),
            None,
        ),
    }


def _live_boundary(tmp: Path) -> dict:
    a_path = tmp / "live-a.clog"
    b_path = tmp / "live-b.clog"
    a = S.run_uninterrupted(SEED, a_path, mode="live", noise_source="live-a")
    time.sleep(0.01)
    b = S.run_uninterrupted(SEED, b_path, mode="live", noise_source="live-b")
    canon_a = S.transcript_sha256(a)
    canon_b = S.transcript_sha256(b)
    raw_a = ST.encode_log(a)
    raw_b = ST.encode_log(b)
    raw_ha = __import__("hashlib").sha256(raw_a).hexdigest()
    raw_hb = __import__("hashlib").sha256(raw_b).hexdigest()
    live_present = any(k in ev for ev in a for k in S.LIVE_FIELDS)
    scripted_path = tmp / "scripted.clog"
    scripted = S.run_uninterrupted(SEED, scripted_path, mode="scripted")
    scripted_hash = S.transcript_sha256(scripted)
    live_vs_scripted_field = S.first_divergence(scripted, a)
    return {
        "canonical_sha256_a": canon_a,
        "canonical_sha256_b": canon_b,
        "canonical_match": canon_a == canon_b,
        "raw_log_sha256_a": raw_ha,
        "raw_log_sha256_b": raw_hb,
        "raw_logs_diverge": raw_ha != raw_hb,
        "scripted_canonical_sha256": scripted_hash,
        "live_canonical_matches_scripted": canon_a == scripted_hash,
        "live_vs_scripted_named_field": live_vs_scripted_field,
        "live_vs_scripted_only_mode": live_vs_scripted_field == "canonical_events[0].mode",
        "live_fields_recorded": live_present,
        "guaranteed_reproducible_fields": list(S.REPRODUCIBLE_FIELDS),
        "recorded_but_not_reproducible_fields": list(S.LIVE_FIELDS),
        "live_field_samples": {
            k: next((e.get(k) for e in a if k in e), None) for k in S.LIVE_FIELDS
        },
    }


def _second_shell() -> dict:
    script = (
        "import sys, tempfile; from pathlib import Path; "
        f"sys.path.insert(0, {str(HERE)!r}); import simulate as S; "
        "tmp=Path(tempfile.mkdtemp(prefix='tst-0286-sh-')); "
        f"seed={SEED!r}; k=S.PAUSE_AFTER; "
        "u=S.run_uninterrupted(seed, tmp/'u.clog'); "
        "S.pause_at(seed, k, tmp/'p.clog'); r=S.resume(tmp/'p.clog'); "
        "q=S.replay_from_log(tmp/'p.clog'); "
        "print(S.transcript_sha256(u)); print(S.transcript_sha256(r)); "
        "print(S.transcript_sha256(q))"
    )
    sh = shutil.which("sh") or "/bin/sh"
    proc = subprocess.run(
        [sh, "-c", f"{sys.executable} -B -c {script!r}"],
        cwd=str(HERE.parent.parent.parent.parent),
        capture_output=True,
        text=True,
        timeout=60,
    )
    lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    hashes = [ln for ln in lines if len(ln) == 64]
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    git_bash = None
    for candidate in (
        "/usr/bin/bash",
        "/bin/bash",
        "/mnt/c/Program Files/Git/bin/bash.exe",
    ):
        if Path(candidate).is_file():
            git_bash = candidate
            break
    return {
        "shell": sh,
        "exit_code": proc.returncode,
        "hashes": hashes,
        "hashes_equal": len(hashes) == 3 and hashes[0] == hashes[1] == hashes[2],
        "stderr_tail": (proc.stderr or "")[-400:],
        "windows": {
            "pwsh": pwsh,
            "git_bash": git_bash if (git_bash and "Git" in git_bash) else None,
            "status": "NOT-CHECKED",
            "reason": "Linux worker; pwsh7 and Git Bash are not the second substrate here. /bin/sh re-run is the independent shell on this host.",
        },
    }


def evaluate() -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="tst-0286-p2-"))
    torn = _torn_write_trial(tmp)
    live = _live_boundary(tmp)
    shell = _second_shell()
    ok = (
        torn.get("fired_on_bad_state") is True
        and torn.get("silent_on_good_state") is True
        and torn.get("truncated") is True
        and live.get("canonical_match") is True
        and live.get("raw_logs_diverge") is True
        and live.get("live_vs_scripted_only_mode") is True
        and live.get("live_fields_recorded") is True
        and shell.get("hashes_equal") is True
        and shell.get("exit_code") == 0
    )
    return {
        "pass": ok,
        "torn_write": torn,
        "live_model_arm": live,
        "second_shell": shell,
        "tmp": str(tmp),
    }


def main() -> int:
    result = evaluate()
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    torn = result["torn_write"]
    live = result["live_model_arm"]
    print(f"torn_truncated={torn.get('truncated')} fired={torn.get('fired_on_bad_state')} silent_good={torn.get('silent_on_good_state')}")
    print(f"torn_error={torn.get('torn_error')}")
    print(f"live_canonical_match={live.get('canonical_match')} raw_diverge={live.get('raw_logs_diverge')}")
    print(f"live_vs_scripted_field={live.get('live_vs_scripted_named_field')} only_mode={live.get('live_vs_scripted_only_mode')}")
    print(f"second_shell_equal={result['second_shell'].get('hashes_equal')} rc={result['second_shell'].get('exit_code')}")
    if not result["pass"]:
        print("FAILED:TST-0286-probe2 torn-write or live-model boundary")
        return 1
    print("SUCCESS:TST-0286-probe2 torn-write live-boundary second-shell")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
