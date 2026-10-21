#!/usr/bin/env python
"""PostToolUse hook — result-aware anti-degeneration fingerprint.

WHY: agents sometimes get stuck calling the same tool with the same arguments and
getting the same output, looping without making progress. A naive input-hash debounce
breaks legitimate polling tools (server_health, git status) whose args are identical by
design. The fix is a RESULT-AWARE fingerprint: (tool_name, args_hash, output_hash). If
we see >=3 occurrences of the same (tool, args) pair AND all of them produced the SAME
output, there is no progress and we inject a warning. If the output ever changes, that
is evidence the call is doing something — no warning.

Storage: ~/.claude/anti-degen/<session_id>.json
Sliding window: last WINDOW_SIZE (tool_name, args_hash, output_hash) triples, oldest dropped.

This hook is RECORD-ONLY + INJECT-only (exit 0, never exit 1/2). Fail-open: any error
in the body writes nothing, prints nothing, and exits 0 so it can never crash a session.

Stdin (PostToolUse): JSON object with keys:
  session_id    str
  tool_name     str
  tool_input    dict | any   (the args passed to the tool)
  tool_response str | dict   (the tool's output; also try tool_output as fallback)
  cwd           str
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

# ── configuration ────────────────────────────────────────────────────────────
WINDOW_SIZE = 8  # how many recent triples to retain per session
REPEAT_THRESHOLD = 3  # how many same-(tool,args,output) hits before warning
ROOT = Path(
    os.environ.get("ANTI_DEGEN_ROOT", str(Path.home() / ".claude" / "anti-degen"))
)

# ── helpers ───────────────────────────────────────────────────────────────────


def _sha(text: str) -> str:
    """64-hex sha256 digest (non-crypto use; sha256 chosen per CWE-327 guidance)."""
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def _args_hash(tool_input) -> str:
    """Normalize tool_input to a stable string before hashing.

    Normalization: sort dict keys recursively so that {a:1,b:2} and {b:2,a:1}
    produce the same hash. Non-dict inputs are JSON-encoded as-is.
    """
    try:
        normalized = json.dumps(
            tool_input,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=repr,
        )
    except Exception:
        normalized = repr(tool_input)
    return _sha(normalized)


def _output_hash(tool_response) -> str:
    """Hash the text of the tool's output."""
    if isinstance(tool_response, str):
        text = tool_response
    else:
        try:
            text = json.dumps(
                tool_response,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                default=repr,
            )
        except Exception:
            text = repr(tool_response)
    return _sha(text)


def _session_file(session_id: str) -> Path:
    ROOT.mkdir(parents=True, exist_ok=True)
    # sanitize session_id to a safe filename component
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in str(session_id))[
        :80
    ]
    return ROOT / f"{safe or 'unknown'}.json"


def _load_window(session_id: str) -> list:
    """Load the sliding-window list for this session. Returns [] on any error."""
    f = _session_file(session_id)
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save_window(session_id: str, window: list) -> None:
    """Persist the window list. Silently ignored on error."""
    try:
        _session_file(session_id).write_text(
            json.dumps(window, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass


def _check_and_update(session_id: str, tool_name: str, args_h: str, out_h) -> bool:
    """Record the new triple and return True iff the warning should fire.

    Returns True only when:
      - the same (tool_name, args_h) pair has appeared >=REPEAT_THRESHOLD times in
        the current window AND every one of those appearances has out_h == out_h
        (i.e. the output has NEVER changed for this tool+args combination).

    A single differing output_hash means progress happened → return False.
    An absent output (out_h is None, recorded when the host sent no result key)
    is UNVERIFIABLE, not identical — any None in the matching window suppresses
    the warning (absent = unverifiable = allow, the SubagentStop doctrine).
    """
    window = _load_window(session_id)

    # append the new triple
    window.append(
        {
            "tool": tool_name,
            "ah": args_h,
            "oh": out_h,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
    )

    # keep only the last WINDOW_SIZE entries
    if len(window) > WINDOW_SIZE:
        window = window[-WINDOW_SIZE:]

    _save_window(session_id, window)

    # count occurrences of (tool, args_h) in the window
    matches = [
        e for e in window if e.get("tool") == tool_name and e.get("ah") == args_h
    ]
    if len(matches) < REPEAT_THRESHOLD:
        return False

    # any unobserved output in the matches -> "identical output" is unverifiable
    if any(e.get("oh") is None for e in matches):
        return False

    # all matching entries must share the SAME output_hash — any variation = progress
    output_hashes = {e.get("oh") for e in matches}
    if len(output_hashes) > 1:
        return False  # output changed at least once → not stuck

    return True  # same tool, same args, same output, >=3 times → stuck


# ── main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    try:
        raw = sys.stdin.read() or "{}"
        data = json.loads(raw)
    except Exception:
        return 0  # fail-open: malformed input → do nothing

    try:
        session_id = str(data.get("session_id") or "unknown")
        tool_name = str(data.get("tool_name") or "")
        tool_input = data.get("tool_input") or {}
        # PostToolUse uses "tool_response"; some schemas use "tool_output".
        # grok absent-field class (2026-10-21): grok sends NO result key on most
        # PostToolUse events. An absent response must NOT hash to the same
        # ""-digest as every other absent response — that made any 3x identical
        # call read as "identical output" when no output was ever seen. Absent =
        # unverifiable: record oh=None and let _check_and_update refuse to fire
        # on unobserved outputs (observed empties keep their old semantics).
        tool_response = data.get("tool_response")
        if tool_response is None:
            tool_response = data.get("tool_output")
        response_present = tool_response is not None

        args_h = _args_hash(tool_input)
        out_h = _output_hash(tool_response) if response_present else None

        should_warn = _check_and_update(session_id, tool_name, args_h, out_h)

        if should_warn:
            msg = (
                f"You have repeated the '{tool_name}' action {REPEAT_THRESHOLD} or more times "
                f"with identical arguments AND identical output — no change in result. "
                f"Stop, summarize what is blocking you, and either try a materially "
                f"different approach or ask the user."
            )
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PostToolUse",
                            "additionalContext": msg,
                        }
                    }
                )
            )

    except Exception:
        pass  # fail-open: any logic error → exit 0, do nothing

    return 0


if __name__ == "__main__":
    sys.exit(main())
