#!/usr/bin/env python
"""loop-recovery/handler.py — Stop / PreToolUse hook: loop detection + escalation.

Usage (in settings.json hooks):
  python C:/Users/Prekzursil/.claude/hooks/loop-recovery/handler.py --mode stop
  python C:/Users/Prekzursil/.claude/hooks/loop-recovery/handler.py --mode pretooluse

Reads a Claude Code hook event JSON from stdin.  Delegates to verdict.py.

On STALLED (Magentic-One re-plan):
  Injects an additionalContext asking the model to re-derive its assumption
  sheet and propose one concrete next step. Gated through calibrated-silence
  (fail-open = allow). Backed off by a 5-minute cooldown per session.

On LOOPING (Devin stuck-escalation):
  Emits FAILED:<loop_id> + 3 structured options phrased so the model will
  surface them to the user via AskUserQuestion. Backed off per distinct
  loop_id (escalate once, then silent). Gated through calibrated-silence
  (fail-open = allow).

Always exits 0 (fail-open). Opt-out:
  - .disabled file in this directory
  - LOOP_RECOVERY=off environment variable

Anti-re-entry: stop_hook_active flag in stdin → immediate exit 0.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# ── path setup ─────────────────────────────────────────────────────────────────
_HOOK_DIR = Path(__file__).resolve().parent
_CAL_SIL_DIR = str(_HOOK_DIR.parent / "calibrated-silence")

if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))
if _CAL_SIL_DIR not in sys.path:
    sys.path.insert(0, _CAL_SIL_DIR)

import verdict as _v  # noqa: E402 — local module in same directory

# ── tunable defaults ───────────────────────────────────────────────────────────
_DEFAULT_STATE_ROOT = Path.home() / ".claude" / "loop-recovery"
_STALL_COOLDOWN = 300   # seconds — minimum gap between consecutive STALLED injects


# ── opt-out ────────────────────────────────────────────────────────────────────

def _is_disabled() -> bool:
    if os.environ.get("LOOP_RECOVERY", "").strip().lower() in ("off", "0", "false", "no"):
        return True
    if (_HOOK_DIR / ".disabled").exists():
        return True
    return False


# ── calibrated-silence gate ────────────────────────────────────────────────────

def _should_interject(itype: str, session_id: str) -> bool:
    """Return True (allow) — fail-open on any error or missing module."""
    try:
        import calibrated_silence  # noqa: PLC0415
        allow, _ = calibrated_silence.should_interject(itype, {"session_id": str(session_id)})
        return bool(allow)
    except Exception:
        return True


# ── escalation state ───────────────────────────────────────────────────────────

def _state_root() -> Path:
    return Path(os.environ.get("LOOP_RECOVERY_ROOT", str(_DEFAULT_STATE_ROOT)))


def _state_file(session_id: str) -> Path:
    root = _state_root()
    root.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in str(session_id))[:80]
    return root / f"{safe or 'unknown'}.json"


def _load_state(session_id: str) -> dict:
    f = _state_file(session_id)
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(session_id: str, state: dict) -> None:
    try:
        _state_file(session_id).write_text(
            json.dumps(state, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass  # fail-open: state loss is acceptable (just re-escalates once more)


def _already_escalated(loop_id: str, state: dict) -> bool:
    return loop_id in state.get("escalated_loops", {})


def _mark_escalated(loop_id: str, state: dict) -> None:
    state.setdefault("escalated_loops", {})[loop_id] = time.strftime("%Y-%m-%dT%H:%M:%S")


def _stall_cooled_down(state: dict) -> bool:
    last = state.get("last_stall_ts")
    if last is None:
        return True
    try:
        return (time.time() - float(last)) >= _STALL_COOLDOWN
    except Exception:
        return True  # fail-open: broken timestamp → allow inject


def _mark_stall_inject(state: dict) -> None:
    state["last_stall_ts"] = time.time()


# ── output ─────────────────────────────────────────────────────────────────────

def _emit(hook_event_name: str, message: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": hook_event_name,
            "additionalContext": message,
        }
    }))


def _stalled_message(reason: str) -> str:
    return (
        f"Progress has stalled across the last {_v.K} turns ({reason}). "
        "RE-DERIVE the assumption sheet (what is known / what is guessed / "
        "what changed) and propose ONE concrete next step, rather than "
        "continuing the current line."
    )


def _looping_message(loop_id: str, reason: str) -> str:
    lid = loop_id or "unknown"
    return (
        f"FAILED:{lid} — detected a repeating action/failure ({reason}).\n\n"
        "STOP and present these options to the user via AskUserQuestion:\n"
        "1. Try a materially different approach — describe the specific "
        "alternative you would attempt.\n"
        "2. Abandon this line of investigation entirely and ask the user "
        "to re-scope the task.\n"
        "3. Ask the user directly: 'I am stuck on [specific blocker] — "
        "what should I try next?'\n\n"
        "(This is a proven repeated action/failure, not mid-task ambiguity. "
        "Escalating to the user is warranted — do not continue grinding.)"
    )


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    # 1. Parse --mode
    try:
        ap = argparse.ArgumentParser(add_help=False)
        ap.add_argument("--mode", default="stop", choices=["stop", "pretooluse"])
        args, _ = ap.parse_known_args()
        mode = args.mode
    except Exception:
        mode = "stop"

    hook_event_name = "Stop" if mode == "stop" else "PreToolUse"

    # 2. Opt-out
    try:
        if _is_disabled():
            return 0
    except Exception:
        return 0

    # 3. Read stdin
    try:
        raw = sys.stdin.read() or "{}"
        data = json.loads(raw)
    except Exception:
        return 0  # malformed JSON → fail-open

    # 4. Extract fields
    try:
        if data.get("stop_hook_active"):
            return 0  # prevent re-entry from a Stop hook continuation
        session_id = str(data.get("session_id") or "unknown")
        cwd = str(data.get("cwd") or ".")
    except Exception:
        return 0

    # 5. Compute verdict
    try:
        verdict, reason, loop_id = _v.compute_verdict(session_id, cwd)
    except Exception:
        return 0

    if verdict == _v.PROGRESSING:
        return 0

    # 6. Load escalation state
    try:
        state = _load_state(session_id)
    except Exception:
        state = {}

    # 7a. STALLED → soft re-derive inject
    if verdict == _v.STALLED:
        try:
            if not _stall_cooled_down(state):
                return 0
            if not _should_interject("suggestion", session_id):
                return 0
            _emit(hook_event_name, _stalled_message(reason))
            _mark_stall_inject(state)
            _save_state(session_id, state)
        except Exception:
            pass  # fail-open
        return 0

    # 7b. LOOPING → terminal escalation
    if verdict == _v.LOOPING:
        try:
            if loop_id and _already_escalated(loop_id, state):
                return 0  # backoff: this exact loop already escalated
            if not _should_interject("resurface", session_id):
                return 0
            _emit(hook_event_name, _looping_message(loop_id or "unknown", reason))
            if loop_id:
                _mark_escalated(loop_id, state)
                _save_state(session_id, state)
        except Exception:
            pass  # fail-open
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
