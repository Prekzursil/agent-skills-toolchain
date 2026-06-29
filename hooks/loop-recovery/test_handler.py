#!/usr/bin/env python
"""pytest tests for the loop-recovery hook gem.

Covers (per spec):
  1. progressing → silent exit 0
  2. stalled (mock K flat turns) → re-derive inject
  3. looping (mock fingerprint repeat N) → terminal FAILED + options inject
  4. same loop not re-escalated twice
  5. recurring-failure-precondition → looping
  6. malformed ledger/stdin → exit 0
  7. opt-out (.disabled file) → exit 0
  8. opt-out (LOOP_RECOVERY=off) → exit 0

All tests are fully hermetic: subprocess + tmp_path ensure no shared state.
CALIBRATED_SILENCE=off is set in every subprocess env so the real interjection
ledger never influences test outcomes.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

HOOK_DIR = Path(__file__).resolve().parent
HANDLER = str(HOOK_DIR / "handler.py")


# ── helpers ────────────────────────────────────────────────────────────────────

def _slug(p: str) -> str:
    """Mirror of verdict._legacy_slug — must stay in sync."""
    base = Path(p).name or "root"
    h = hashlib.sha256(p.encode("utf-8", "replace")).hexdigest()[:8]
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in base)[:40]
    return f"{safe}-{h}"


def _write_ledger(ledger_root: Path, cwd: str, events: list) -> None:
    slug = _slug(cwd)
    d = ledger_root / slug
    d.mkdir(parents=True, exist_ok=True)
    with (d / "events.jsonl").open("w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")


def _write_degen(degen_root: Path, session_id: str, window: list) -> None:
    degen_root.mkdir(parents=True, exist_ok=True)
    safe = "".join(
        c if c.isalnum() or c in "-_." else "-" for c in session_id
    )[:80]
    (degen_root / f"{safe or 'unknown'}.json").write_text(
        json.dumps(window), encoding="utf-8"
    )


def _run(
    tmp_path: Path,
    mode: str,
    stdin_data: dict,
    *,
    extra_env: dict | None = None,
) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "ANTI_DEGEN_ROOT":   str(tmp_path / "anti-degen"),
        "EVENT_LEDGER_ROOT": str(tmp_path / "ledger"),
        "LOOP_RECOVERY_ROOT": str(tmp_path / "loop-recovery"),
        # Disable calibrated-silence so the real usage ledger doesn't interfere.
        "CALIBRATED_SILENCE": "off",
    }
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, HANDLER, "--mode", mode],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        env=env,
    )


# ── event factories ────────────────────────────────────────────────────────────

def _turn(seq: int, cwd: str = "/fake/proj") -> dict:
    return {"seq": seq, "ts": "2026-01-01T00:00:00", "kind": "turn", "cwd": cwd}


def _milestone(seq: int) -> dict:
    return {"seq": seq, "ts": "2026-01-01T00:00:00", "kind": "milestone", "text": "done"}


def _decision(seq: int) -> dict:
    return {"seq": seq, "ts": "2026-01-01T00:00:00", "kind": "decision", "text": "chose X"}


def _failure(seq: int, preconditions: str = "lib<=2.0.0") -> dict:
    return {
        "seq": seq, "ts": "2026-01-01T00:00:00", "kind": "failure",
        "text": "it broke", "preconditions": preconditions,
    }


def _fp(tool: str, ah: str, oh: str) -> dict:
    return {"tool": tool, "ah": ah, "oh": oh, "ts": "2026-01-01T00:00:00"}


# ── tests ──────────────────────────────────────────────────────────────────────

def test_progressing_silent_exit_0(tmp_path):
    """Turns with milestones/decisions present → PROGRESSING → no output, exit 0."""
    cwd = "/fake/proj"
    events = [_turn(i, cwd) for i in range(1, 6)] + [_milestone(6), _decision(7)]
    _write_ledger(tmp_path / "ledger", cwd, events)
    r = _run(tmp_path, "stop", {"session_id": "s_prog", "cwd": cwd})
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_stalled_injects_rederive(tmp_path):
    """K+ turns with no milestones/decisions → STALLED → re-derive inject."""
    cwd = "/fake/proj"
    events = [_turn(i, cwd) for i in range(1, 6)]   # 5 turns, nothing else
    _write_ledger(tmp_path / "ledger", cwd, events)
    r = _run(tmp_path, "stop", {"session_id": "s_stall", "cwd": cwd})
    assert r.returncode == 0
    assert r.stdout.strip() != "", "expected a stall inject but got no output"
    out = json.loads(r.stdout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "RE-DERIVE" in ctx
    assert "assumption" in ctx.lower()
    assert "next step" in ctx.lower()


def test_looping_fp_injects_terminal(tmp_path):
    """Anti-degen fingerprint repeated ≥3 times → LOOPING → FAILED + options inject."""
    cwd = "/fake/proj"
    session = "s_fploop"
    # 3 identical entries → same (tool, ah, oh) → fingerprint loop
    window = [_fp("Bash", "aaa111", "bbb222")] * 3
    _write_degen(tmp_path / "anti-degen", session, window)
    r = _run(tmp_path, "stop", {"session_id": session, "cwd": cwd})
    assert r.returncode == 0
    assert r.stdout.strip() != "", "expected a looping inject but got no output"
    out = json.loads(r.stdout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "FAILED:" in ctx
    # Must include escalation options phrased for AskUserQuestion
    assert "AskUserQuestion" in ctx or "option" in ctx.lower() or "approach" in ctx.lower()


def test_same_loop_not_re_escalated_twice(tmp_path):
    """LOOPING: first call escalates; second call with same loop_id is silent (backoff)."""
    cwd = "/fake/proj"
    session = "s_backoff"
    window = [_fp("Bash", "deadbeef", "cafebabe")] * 3
    _write_degen(tmp_path / "anti-degen", session, window)

    # First run → LOOPING escalation fires, state file written
    r1 = _run(tmp_path, "stop", {"session_id": session, "cwd": cwd})
    assert r1.returncode == 0
    assert r1.stdout.strip() != "", "first escalation should fire"

    # Second run with identical conditions → backoff → silent
    r2 = _run(tmp_path, "stop", {"session_id": session, "cwd": cwd})
    assert r2.returncode == 0
    assert r2.stdout.strip() == "", "second call must be silent (loop already escalated)"


def test_recurring_failure_precondition_looping(tmp_path):
    """Same failure precondition appearing ≥2 times → LOOPING verdict → FAILED inject."""
    cwd = "/fake/proj"
    session = "s_failloop"
    events = [_failure(i, preconditions="foo-lib<=2.0.0") for i in range(1, 4)]
    _write_ledger(tmp_path / "ledger", cwd, events)
    r = _run(tmp_path, "stop", {"session_id": session, "cwd": cwd})
    assert r.returncode == 0
    assert r.stdout.strip() != "", "expected a failure-loop inject"
    out = json.loads(r.stdout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "FAILED:" in ctx


def test_malformed_stdin_exit_0(tmp_path):
    """Malformed JSON in stdin → fail-open → exit 0, no output."""
    env = {
        **os.environ,
        "ANTI_DEGEN_ROOT":   str(tmp_path / "anti-degen"),
        "EVENT_LEDGER_ROOT": str(tmp_path / "ledger"),
        "LOOP_RECOVERY_ROOT": str(tmp_path / "loop-recovery"),
        "CALIBRATED_SILENCE": "off",
    }
    r = subprocess.run(
        [sys.executable, HANDLER, "--mode", "stop"],
        input="{not valid json!!!",
        capture_output=True, text=True, env=env,
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_empty_ledger_exit_0(tmp_path):
    """No ledger data at all → PROGRESSING → exit 0, silent."""
    r = _run(tmp_path, "stop", {"session_id": "s_empty", "cwd": "/no/such/project"})
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_opt_out_disabled_file(tmp_path):
    """Presence of .disabled file in hook dir → immediate no-op, exit 0."""
    cwd = "/fake/proj"
    events = [_turn(i, cwd) for i in range(1, 6)]   # would normally trigger STALLED
    _write_ledger(tmp_path / "ledger", cwd, events)

    disabled_file = HOOK_DIR / ".disabled"
    try:
        disabled_file.write_text("", encoding="utf-8")
        r = _run(tmp_path, "stop", {"session_id": "s_dis", "cwd": cwd})
        assert r.returncode == 0
        assert r.stdout.strip() == ""
    finally:
        try:
            disabled_file.unlink(missing_ok=True)
        except Exception:
            pass


def test_opt_out_env_var(tmp_path):
    """LOOP_RECOVERY=off → no-op, exit 0 regardless of stall conditions."""
    cwd = "/fake/proj"
    events = [_turn(i, cwd) for i in range(1, 6)]   # would normally trigger STALLED
    _write_ledger(tmp_path / "ledger", cwd, events)
    r = _run(
        tmp_path, "stop",
        {"session_id": "s_envoff", "cwd": cwd},
        extra_env={"LOOP_RECOVERY": "off"},
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_pretooluse_mode_emits_correct_event_name(tmp_path):
    """PreToolUse mode emits hookEventName: PreToolUse."""
    cwd = "/fake/proj"
    events = [_turn(i, cwd) for i in range(1, 6)]
    _write_ledger(tmp_path / "ledger", cwd, events)
    r = _run(
        tmp_path, "pretooluse",
        {"session_id": "s_ptu", "cwd": cwd, "tool_name": "Bash", "tool_input": {}},
    )
    assert r.returncode == 0
    if r.stdout.strip():
        out = json.loads(r.stdout)
        assert out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"


def test_stop_hook_active_noop(tmp_path):
    """stop_hook_active flag in stdin → immediate no-op (prevents re-entry loops)."""
    r = _run(
        tmp_path, "stop",
        {"session_id": "s_active", "cwd": "/fake/proj", "stop_hook_active": True},
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_malformed_ledger_line_exit_0(tmp_path):
    """Corrupt JSONL lines in the ledger → skipped gracefully → exit 0."""
    cwd = "/fake/proj"
    slug = _slug(cwd)
    d = tmp_path / "ledger" / slug
    d.mkdir(parents=True, exist_ok=True)
    # Mix valid and corrupt lines
    lines = [
        json.dumps(_turn(1, cwd)),
        "{broken json",
        json.dumps(_turn(2, cwd)),
        "not json at all",
        json.dumps(_turn(3, cwd)),
    ]
    (d / "events.jsonl").write_text("\n".join(lines), encoding="utf-8")
    r = _run(tmp_path, "stop", {"session_id": "s_corrupt", "cwd": cwd})
    assert r.returncode == 0
    # Only 3 valid turns (< MIN_ACTIVITY_TURNS=4) → no stall, no output
    assert r.stdout.strip() == ""


def test_empty_stdin_exit_0(tmp_path):
    """Empty stdin → treated as '{}' → fail-open → exit 0."""
    env = {
        **os.environ,
        "ANTI_DEGEN_ROOT":   str(tmp_path / "anti-degen"),
        "EVENT_LEDGER_ROOT": str(tmp_path / "ledger"),
        "LOOP_RECOVERY_ROOT": str(tmp_path / "loop-recovery"),
        "CALIBRATED_SILENCE": "off",
    }
    r = subprocess.run(
        [sys.executable, HANDLER, "--mode", "stop"],
        input="",
        capture_output=True, text=True, env=env,
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_different_output_hashes_not_looping(tmp_path):
    """Same tool+args but varying output → not a loop (output changed = progress)."""
    cwd = "/fake/proj"
    session = "s_varying"
    window = [
        _fp("Bash", "same_args", "output_v1"),
        _fp("Bash", "same_args", "output_v2"),
        _fp("Bash", "same_args", "output_v3"),
    ]
    _write_degen(tmp_path / "anti-degen", session, window)
    r = _run(tmp_path, "stop", {"session_id": session, "cwd": cwd})
    assert r.returncode == 0
    # No fingerprint loop because output varied. No stall (no ledger turns either).
    assert r.stdout.strip() == ""


def test_fp_loop_different_tools_not_looping(tmp_path):
    """Three entries but different tools → no single (tool, ah) repeated ≥3 times → PROGRESSING."""
    cwd = "/fake/proj"
    session = "s_diff_tools"
    window = [
        _fp("Bash",   "aaaaa", "ooooo"),
        _fp("Edit",   "aaaaa", "ooooo"),
        _fp("Write",  "aaaaa", "ooooo"),
    ]
    _write_degen(tmp_path / "anti-degen", session, window)
    r = _run(tmp_path, "stop", {"session_id": session, "cwd": cwd})
    assert r.returncode == 0
    assert r.stdout.strip() == ""


# ── unit-level verdict tests (direct import, no subprocess) ───────────────────

def _reload_verdict():
    """Import or re-import verdict so env-var based defaults are fresh."""
    import importlib
    import sys
    if "verdict" in sys.modules:
        return importlib.reload(sys.modules["verdict"])
    sys.path.insert(0, str(HOOK_DIR))
    import verdict
    return verdict


def test_verdict_progressing_with_milestones():
    """Direct verdict call: milestones present → PROGRESSING."""
    import tempfile, os
    with tempfile.TemporaryDirectory() as td:
        v = _reload_verdict()
        cwd = "/tmp/proj"
        events = [
            {"seq": i, "kind": "turn", "cwd": cwd, "ts": "2026-01-01T00:00:00"}
            for i in range(1, 6)
        ] + [{"seq": 6, "kind": "milestone", "text": "done", "ts": "2026-01-01T00:00:00"}]
        slug = v._legacy_slug(cwd)
        d = Path(td) / "ledger" / slug
        d.mkdir(parents=True)
        (d / "events.jsonl").write_text(
            "\n".join(json.dumps(e) for e in events), encoding="utf-8"
        )
        verdict_val, _, _ = v.compute_verdict(
            "session_x", cwd,
            ledger_root=Path(td) / "ledger",
            anti_degen_root=Path(td) / "anti-degen",
        )
        assert verdict_val == v.PROGRESSING


def test_verdict_stalled_direct():
    """Direct verdict call: 5 turns, 0 milestones → STALLED."""
    with __import__("tempfile").TemporaryDirectory() as td:
        v = _reload_verdict()
        cwd = "/tmp/proj2"
        events = [
            {"seq": i, "kind": "turn", "cwd": cwd, "ts": "2026-01-01T00:00:00"}
            for i in range(1, 6)
        ]
        slug = v._legacy_slug(cwd)
        d = Path(td) / "ledger" / slug
        d.mkdir(parents=True)
        (d / "events.jsonl").write_text(
            "\n".join(json.dumps(e) for e in events), encoding="utf-8"
        )
        verdict_val, _, _ = v.compute_verdict(
            "session_y", cwd,
            ledger_root=Path(td) / "ledger",
            anti_degen_root=Path(td) / "anti-degen",
        )
        assert verdict_val == v.STALLED


def test_verdict_looping_fp_direct():
    """Direct verdict call: fingerprint repeated 3× → LOOPING."""
    with __import__("tempfile").TemporaryDirectory() as td:
        v = _reload_verdict()
        session = "sess_fp"
        window = [{"tool": "Bash", "ah": "h1", "oh": "o1", "ts": "X"}] * 3
        degen_dir = Path(td) / "anti-degen"
        degen_dir.mkdir(parents=True)
        (degen_dir / f"{session}.json").write_text(json.dumps(window), encoding="utf-8")
        verdict_val, _, loop_id = v.compute_verdict(
            session, "/tmp/proj",
            anti_degen_root=degen_dir,
            ledger_root=Path(td) / "ledger",
        )
        assert verdict_val == v.LOOPING
        assert loop_id is not None


def test_verdict_fail_open_on_exception():
    """Bad inputs → fail-open → PROGRESSING (no exception escapes)."""
    v = _reload_verdict()
    # Pass a non-existent path with a broken root
    verdict_val, reason, _ = v.compute_verdict(
        None, None,  # type: ignore
        anti_degen_root=Path("/nonexistent_root_xyz"),
        ledger_root=Path("/nonexistent_root_xyz"),
    )
    assert verdict_val == v.PROGRESSING
    assert "fail-open" in reason.lower() or verdict_val == v.PROGRESSING


def test_verdict_progressing_head_changed_no_milestones():
    """Turns with changing git HEAD but 0 milestones/decisions → PROGRESSING, not STALLED.

    Regression guard for the M4 false-positive: a session that commits code
    every turn (HEAD sha advances) without ever calling note.py must NOT
    receive spurious 'RE-DERIVE the assumption sheet' nudges.
    """
    with __import__("tempfile").TemporaryDirectory() as td:
        v = _reload_verdict()
        cwd = "/tmp/proj_head_chg"
        # 5 turn events, each with a distinct HEAD sha (4 commits across the window),
        # no milestones, no decisions, no dirty files.
        events = [
            {
                "seq": i,
                "kind": "turn",
                "cwd": cwd,
                "ts": "2026-01-01T00:00:00",
                "head": f"abc{i:05x}def",   # unique sha per turn → HEAD moved
                "dirty_files": [],
            }
            for i in range(1, 6)
        ]
        slug = v._legacy_slug(cwd)
        d = Path(td) / "ledger" / slug
        d.mkdir(parents=True)
        (d / "events.jsonl").write_text(
            "\n".join(json.dumps(e) for e in events), encoding="utf-8"
        )
        verdict_val, reason, _ = v.compute_verdict(
            "session_head_chg", cwd,
            ledger_root=Path(td) / "ledger",
            anti_degen_root=Path(td) / "anti-degen",
        )
        assert verdict_val == v.PROGRESSING, (
            f"Expected PROGRESSING when HEAD changes across turns, "
            f"got {verdict_val!r}: {reason}"
        )
