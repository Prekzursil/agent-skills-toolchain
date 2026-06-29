#!/usr/bin/env python3
r"""open-loops/trigger_match.py — UserPromptSubmit hook (its OWN settings.json entry).

The ACTIVE half of prospective memory: on each human turn, evaluate every stored
trigger's condition against the CURRENT context (cwd / git branch / file-exists /
prompt text / recent files). Any trigger whose condition holds is injected as a
reminder ("you set a reminder: when touching BC, re-assert event_0 — act on it now").

Firing semantics (anti-nag):
  * one-shot triggers (default)  -> surfaced once, then marked fired (written back) so
    they never repeat;
  * recurring triggers           -> re-surface, but throttled to once per RECUR window
    (last_fired_ts), so a long-lived rule does not nag every prompt.

Only CONTEXTUAL triggers fire here (a bare `always` loop is a SessionStart-only standing
reminder handled by resurface.py — firing it on every prompt would be pure noise).

NOT a duplicate of inquisitiveness/prompt-guard (which asks the agent to CLARIFY a vague
prompt) nor semantic-router (which routes to a skill/MCP): this fires user-AUTHORED,
context-gated intentions stored earlier. Inject-only; never blocks. FAIL-OPEN.
Opt-out: OPEN_LOOPS=off or a .disabled file.

Wire spec:
  Event:   UserPromptSubmit   matcher "*"
  Command: python C:/Users/Prekzursil/.claude/hooks/open-loops/trigger_match.py
  Stdout (match): {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                     "additionalContext": "<reminders>"}}
  Stdout (none):  empty.   Exit: always 0.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import _common as C  # noqa: E402


# --------------------------------------------------------------------------- calibrated-silence
# Fail-open shim: a resurfaced open loop is SDT-gated by should_interject(). ANY error
# (gate missing, corrupt ledger, bad input) returns ALLOW — suppression is the dangerous failure.
def _cs_allow(itype, ctx):
    try:
        import sys as _s
        from pathlib import Path as _P
        _s.path.insert(0, str(_P(__file__).resolve().parent.parent / "calibrated-silence"))
        import calibrated_silence as _c
        return _c.should_interject(itype, ctx)[0]
    except Exception:
        return True


def _cs_record(itype, ck, sid):
    try:
        import calibrated_silence as _c
        _c.record_interjection(itype, ck, sid)
    except Exception:
        pass


DISABLED = THIS / ".disabled"
MAX_FIRE = int(os.environ.get("OPEN_LOOPS_MAX_FIRE", "3"))


def _disabled() -> bool:
    return DISABLED.exists() or os.environ.get("OPEN_LOOPS", "").lower() in ("off", "0", "false")


def _recur_ready(t: dict) -> bool:
    try:
        last = float(t.get("fired_ts") or 0)
    except (TypeError, ValueError):
        last = 0.0
    return (C.now() - last) >= C.RECUR_THROTTLE_SEC


def select_and_fire(payload: dict):
    """Return (message_or_None, changed) and mutate `fired`/`fired_ts` on matches.

    `changed` indicates the store must be re-saved. Pure-ish: it returns the new full
    record list to persist via the caller so this stays unit-testable."""
    ctx = C.build_ctx(payload)
    triggers = C.load_triggers(gc=True)
    fired_now: list[dict] = []
    changed = False

    for t in triggers:
        cond = t.get("condition") or {}
        if not C.is_contextual(cond):
            continue  # standing `always` loops are SessionStart-only
        if t.get("fired") and not t.get("recurring"):
            continue  # one-shot already fired
        if t.get("recurring") and not _recur_ready(t):
            continue  # throttled
        if not C.eval_condition(cond, ctx):
            continue
        fired_now.append(t)
        t["fired"] = True
        t["fired_ts"] = C.now()
        changed = True
        if len(fired_now) >= MAX_FIRE:
            break

    if changed:
        C.save_triggers(triggers)
    if not fired_now:
        return None, changed

    lines = ["**[open-loop trigger fired]** You set these reminders earlier and they "
             "match this turn — act on them (or close when done):"]
    for t in fired_now:
        note = C.matched_pred_summary(t.get("condition") or {}, ctx)
        when = time.strftime("%Y-%m-%d", time.localtime(float(t.get("created_ts") or 0)))
        kind = " [recurring]" if t.get("recurring") else ""
        lines.append(f"- ({t['id']}{kind}) {t.get('action', '')}  <- {note}  (set {when})")
    lines.append("Close: `python ~/.claude/hooks/open-loops/add.py --close <id>`")
    return "\n".join(lines), changed


def main() -> int:
    try:
        if _disabled():
            return 0
        payload = C.read_stdin()
        if not str(payload.get("prompt") or "").strip():
            return 0  # no human prompt -> nothing to match
        msg, _ = select_and_fire(payload)
        if msg:
            # CALIBRATED SILENCE: gate the resurface at its emit; fail-open allows on gate error.
            sid = str(payload.get("session_id") or "default")
            if _cs_allow("resurface", {"prompt": payload.get("prompt"), "session_id": sid}):
                C.emit("UserPromptSubmit", msg)
                _cs_record("resurface", "resurface:open-loops", sid)
    except Exception:
        pass  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main())
