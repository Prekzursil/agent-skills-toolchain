#!/usr/bin/env python3
r"""CALIBRATED SILENCE — reaction logger (UserPromptSubmit primary; Stop fallback).

Closes the learning loop for calibrated_silence.py: it classifies how the user ACTUALLY
reacted to the prior turn's interjection(s) and writes that reaction back to the ledger,
so should_interject()'s hit-rate is learned from EXTERNAL behavior, never self-judgment.

The reaction signal (the user's next-turn behavior):
  acted    - the suggested skill/tool/agent got invoked this turn, OR (for a 'question'
             interjection) the user's next prompt is a substantive answer, OR (for a
             'nudge') durable memory actually got written.
  annoyed  - the user's next prompt is a terse dismissal ("no", "stop", "skip it").
  ignored  - none of the above: the user moved on without engaging.
  unknown  - not yet resolvable (left for a later turn).

TWO ENTRY MODES (auto-detected from stdin):
  * UserPromptSubmit (PRIMARY, full classification): the NEW prompt is the reaction.
    The transcript's tool-uses since the last user message are this-prior-turn's agent
    actions. Resolves acted / annoyed / ignored.
  * Stop (FALLBACK, partial): no verbal reaction exists yet (it arrives next turn), so
    this only UPGRADES unknown -> acted when a matching tool was used this turn; it never
    marks ignored/annoyed (that would prematurely punish an interjection the user has not
    yet had a turn to react to).

Self-reference guard: rows recorded in THIS same turn (ts within SELF_EPSILON of now) are
skipped, so the logger never classifies a fresh interjection as its own reaction regardless
of hook ordering. Inject-nothing, exit 0, FAIL-OPEN. Opt-out: CALSIL_REACTION=off or a
`.disabled` file in this directory.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import calibrated_silence as cs  # noqa: E402

DISABLED = THIS / ".disabled"
REACTION_WINDOW = int(os.environ.get("CALSIL_REACTION_WINDOW", "1800"))  # stale cutoff (s)
SELF_EPSILON = float(os.environ.get("CALSIL_SELF_EPSILON", "2.0"))       # this-turn guard (s)
SUBSTANTIVE_WORDS = int(os.environ.get("CALSIL_SUBSTANTIVE_WORDS", "5"))

# Terse dismissal vocabulary (an EXTERNAL pushback signal).
_DISMISS_TOKENS = frozenset((
    "no", "nope", "nah", "stop", "dont", "skip", "cancel", "nvm", "ignore", "wrong", "quiet",
))
_DISMISS_PHRASES = frozenset((
    "no thanks", "no thank you", "not now", "not right now", "no need", "never mind",
    "forget it", "leave it", "drop it", "maybe later", "skip it", "stop it", "shut up",
))

_GIT_NOTE = re.compile(r"note\.py|write_note|basic[-_]memory[^\n]*(write|note)", re.IGNORECASE)
_BM_WRITE = re.compile(r"mcp__basic-memory__(write_note|edit_note|create)", re.IGNORECASE)


# --------------------------------------------------------------------------- pure classifier
def _norm(text) -> str:
    return re.sub(r"[^a-z0-9'\s]", " ", str(text or "").lower()).replace("'", "")


def is_dismissal(text) -> bool:
    """Terse pushback -> the user is annoyed by the interjection."""
    norm = _norm(text)
    words = norm.split()
    if not words or len(words) > 6:
        return False
    if words[0] in _DISMISS_TOKENS:
        return True
    return norm.strip() in _DISMISS_PHRASES


def is_substantive(text) -> bool:
    """A real, on-topic reply (engagement) rather than a one-word brush-off."""
    if is_dismissal(text):
        return False
    return len(str(text or "").split()) >= SUBSTANTIVE_WORDS


def _acted_via_tools(itype, context_key, tool_keys) -> bool:
    """True if a tool/skill/agent matching this interjection's target was invoked.

    `tool_keys` is a set of 'kind:name' strings (observe.py convention) plus the synthetic
    'memory:write' when durable memory was written this turn. `context_key` SHOULD carry the
    actionable target as 'kind:name' (e.g. 'skill:systematic-debugging', 'mcp:tooluniverse')
    when the interjection routes to a specific tool.
    """
    if not tool_keys:
        return False
    ck = str(context_key or "").strip().lower()
    if ck and ck in tool_keys:
        return True
    name = ck.split(":")[-1]
    if name and any(name == k.split(":")[-1] or name in k for k in tool_keys):
        return True
    # a persistence nudge is "acted on" when durable memory actually got written
    if str(itype) == "nudge" or ck.startswith("persist"):
        if any(k.startswith("mcp:basic-memory") or k == "memory:write" for k in tool_keys):
            return True
    return False


def classify(itype, context_key, reaction_text, tool_keys) -> str:
    """Pure reaction classifier. Returns 'acted' | 'annoyed' | 'ignored'."""
    if _acted_via_tools(itype, context_key, tool_keys):
        return "acted"
    if str(itype) == "question" and is_substantive(reaction_text):
        return "acted"
    if is_dismissal(reaction_text):
        return "annoyed"
    return "ignored"


# --------------------------------------------------------------------------- transcript parse
def _iter_events(transcript_path):
    p = Path(transcript_path)
    if not p.exists():
        return
    with p.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def _user_text(ev):
    """Real user-turn text, or None. A user event whose content is only tool_result
    blocks is a tool reply, NOT user speech -> None (so it is not mistaken for a turn)."""
    if not isinstance(ev, dict) or ev.get("type") != "user":
        return None
    msg = ev.get("message") or {}
    content = msg.get("content")
    if content is None:
        content = ev.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [b.get("text", "") for b in content
                 if isinstance(b, dict) and b.get("type") == "text"]
        joined = " ".join(t for t in texts if t).strip()
        return joined or None
    return None


def _tool_uses(ev):
    msg = ev.get("message") or {}
    content = msg.get("content")
    if content is None:
        content = ev.get("content")
    if not isinstance(content, list):
        return
    for b in content:
        if isinstance(b, dict) and b.get("type") == "tool_use":
            yield str(b.get("name") or ""), b.get("input") or {}


def _keys_for(tool_name, tool_input):
    """Map a tool invocation to candidate 'kind:name' keys (observe.py convention) plus
    a synthetic 'memory:write' when this invocation persists durable memory."""
    keys = []
    tn = str(tool_name or "")
    ti = tool_input if isinstance(tool_input, dict) else {}
    if tn == "Skill":
        s = str(ti.get("skill") or ti.get("name") or "").strip()
        if s:
            keys.append(f"skill:{s}".lower())
            if ":" in s:
                keys.append(f"skill:{s.split(':')[-1]}".lower())
    elif tn == "Task":
        a = str(ti.get("subagent_type") or "").strip()
        if a:
            keys.append(f"agent:{a}".lower())
            if ":" in a:
                keys.append(f"agent:{a.split(':')[-1]}".lower())
    elif tn.startswith("mcp__"):
        parts = tn.split("__")
        if len(parts) >= 2 and parts[1]:
            keys.append(f"mcp:{parts[1]}".lower())
        if _BM_WRITE.search(tn):
            keys.append("memory:write")
    elif tn in ("SlashCommand",) or tn.startswith("/"):
        c = (tn.lstrip("/") if tn != "SlashCommand" else str(ti.get("command") or "")).strip().lstrip("/")
        if c:
            keys.append(f"command:{c.split()[0]}".lower())
    elif tn in ("Bash", "PowerShell"):
        cmd = str(ti.get("command") or "")
        if _GIT_NOTE.search(cmd):
            keys.append("memory:write")
    return keys


def turn_signals(transcript_path):
    """Return (last_user_text, tool_keys) where tool_keys are the agent's tool invocations
    since the last real user message (i.e. the prior turn's agent actions)."""
    events = list(_iter_events(transcript_path))
    last_idx = -1
    last_text = ""
    for i, ev in enumerate(events):
        t = _user_text(ev)
        if t is not None:
            last_idx = i
            last_text = t
    tool_keys = set()
    for ev in events[last_idx + 1:]:
        for name, inp in _tool_uses(ev):
            for k in _keys_for(name, inp):
                tool_keys.add(k)
    return last_text, tool_keys


# --------------------------------------------------------------------------- write-back
def apply_reactions(rows, session_id, reaction_text, tool_keys, *, stop_mode=False, now=None):
    """Pure write-back planner. Mutates and returns `rows` with newly-resolved reactions.

    stop_mode=True only upgrades unknown -> acted via tools (never ignored/annoyed), because
    at Stop the user has not yet had a turn to react. Returns (rows, n_changed).
    """
    now = time.time() if now is None else float(now)
    sid = str(session_id or "default")
    changed = 0
    for row in rows:
        try:
            if str(row.get("reaction")) != "unknown":
                continue
            if str(row.get("session_id")) != sid:
                continue
            ts = float(row.get("ts", 0))
            if ts > now - SELF_EPSILON:   # recorded this same turn -> not a reaction yet
                continue
            itype = str(row.get("type") or "")
            ckey = str(row.get("context_key") or "")
            if stop_mode:
                if _acted_via_tools(itype, ckey, tool_keys):
                    row["reaction"] = "acted"
                    changed += 1
                continue
            if now - ts > REACTION_WINDOW:   # stale and never engaged
                if _acted_via_tools(itype, ckey, tool_keys):
                    row["reaction"] = "acted"
                else:
                    row["reaction"] = "ignored"
                changed += 1
                continue
            row["reaction"] = classify(itype, ckey, reaction_text, tool_keys)
            changed += 1
        except Exception:
            continue
    return rows, changed


def main() -> int:
    try:
        if DISABLED.exists() or os.environ.get("CALSIL_REACTION", "").strip().lower() in ("off", "0", "false"):
            return 0
        try:
            data = json.loads(sys.stdin.read() or "{}")
        except Exception:
            return 0
        if data.get("stop_hook_active"):
            return 0
        sid = data.get("session_id") or "default"
        transcript = str(data.get("transcript_path") or "")
        has_prompt = "prompt" in data and data.get("prompt") is not None

        last_text, tool_keys = turn_signals(transcript) if transcript else ("", set())
        # UserPromptSubmit: the NEW prompt is the reaction. Stop: no reaction yet.
        if has_prompt:
            reaction_text = str(data.get("prompt") or "")
            stop_mode = False
        else:
            reaction_text = last_text  # used only for the rare manual call; stop_mode ignores it
            stop_mode = True

        rows = cs.read_rows()
        if not rows:
            return 0
        rows, changed = apply_reactions(rows, sid, reaction_text, tool_keys, stop_mode=stop_mode)
        if changed:
            cs._atomic_write_rows(rows)
    except Exception:
        pass  # fail-open: a logger must never crash a session
    return 0


if __name__ == "__main__":
    sys.exit(main())
