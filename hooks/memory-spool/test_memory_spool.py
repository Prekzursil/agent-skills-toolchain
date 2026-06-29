#!/usr/bin/env python3
r"""Tests for memory-spool. Runs WITHOUT pytest: `python test_memory_spool.py`.

Proves: PreToolUse spools the payload; a FAILED tool_response keeps the spool + alerts;
a SUCCESS tool_response clears it silently; SessionStart surfaces unflushed entries once.
All by DIRECT invocation with sample stdin.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

_TMP = Path(tempfile.mkdtemp(prefix="memspool-"))
os.environ["MEMORY_SPOOL_DIR"] = str(_TMP)

import _common as C  # noqa: E402
import spool  # noqa: E402
import flush_check  # noqa: E402

C.SPOOL_DIR = _TMP
C.REPORTED_FILE = _TMP / ".reported.json"

_FAILS = []


def ok(name, cond):
    print(("PASS" if cond else "FAIL") + f": {name}")
    if not cond:
        _FAILS.append(name)


def _reset():
    for p in list(_TMP.glob("*")):
        try:
            p.unlink()
        except OSError:
            pass


def _spool_count():
    return len(C.list_spools())


def _write_note_stdin(title, content="body", session="s1", response=None, with_resp=False):
    ti = {"title": title, "content": content, "folder": "notes"}
    d = {"session_id": session, "tool_name": "mcp__basic-memory__write_note",
         "tool_input": ti}
    if with_resp:
        d["tool_response"] = response
    return d


def _invoke(mod, stdin_obj, argv=None):
    buf = io.StringIO()
    old = sys.stdin
    sys.stdin = io.StringIO(json.dumps(stdin_obj))
    try:
        with redirect_stdout(buf):
            if argv is not None:
                mod.main(argv)
            else:
                mod.main()
    finally:
        sys.stdin = old
    return buf.getvalue()


def fired(out):
    return "memory-spool" in out


def main():  # noqa: C901
    # --- response_ok classifier (the load-bearing success/fail signal) ---
    ok("response_ok: empty string -> fail", C.response_ok("") is False)
    ok("response_ok: None -> fail", C.response_ok(None) is False)
    ok("response_ok: isError dict -> fail",
       C.response_ok({"isError": True, "content": [{"text": "down"}]}) is False)
    ok("response_ok: error dict -> fail", C.response_ok({"error": "connection refused"}) is False)
    ok("response_ok: real note result -> ok",
       C.response_ok({"isError": False, "content": [{"type": "text", "text": "# Saved\npermalink: notes/x"}]}) is True)
    ok("response_ok: non-empty string -> ok", C.response_ok("Created note notes/x") is True)

    # --- 1. PreToolUse spools the payload ---
    _reset()
    _invoke(spool, _write_note_stdin("Alpha decision"))
    ok("spool.py wrote one spool entry", _spool_count() == 1)
    rec = C.load_json(C.list_spools()[0])
    ok("spool entry captured title + payload",
       rec.get("title") == "Alpha decision" and rec.get("payload", {}).get("content") == "body"
       and rec.get("status") == "pending")

    # --- 2. PostToolUse FAILED response -> keep spool + alert ---
    out = _invoke(flush_check, _write_note_stdin("Alpha decision", with_resp=True,
                  response={"isError": True, "content": [{"type": "text", "text": "basic-memory not connected"}]}),
                  argv=["posttool"])
    ok("failed write keeps the spool", _spool_count() == 1)
    ok("failed write injects a loud alert", fired(out) and "NOT persisted" in out)
    ok("failed entry marked failed", C.load_json(C.list_spools()[0]).get("status") == "failed")

    # --- 3. PostToolUse SUCCESS response -> clear spool, silent ---
    _reset()
    _invoke(spool, _write_note_stdin("Beta decision"))
    ok("re-spool for success case", _spool_count() == 1)
    out = _invoke(flush_check, _write_note_stdin("Beta decision", with_resp=True,
                  response={"isError": False, "content": [{"type": "text", "text": "# Beta\npermalink: notes/beta"}]}),
                  argv=["posttool"])
    ok("successful write clears the spool", _spool_count() == 0)
    ok("successful write is silent", not fired(out))

    # --- 4. SessionStart surfaces unflushed entries (the killed-mid-write case) ---
    _reset()
    _invoke(spool, _write_note_stdin("Gamma never-confirmed"))  # Post never ran (session died)
    out = _invoke(flush_check, {"session_id": "s2", "hook_event_name": "SessionStart"},
                  argv=["sessionstart"])
    ok("SessionStart surfaces unflushed spool", fired(out) and "never confirmed saved" in out
       and "Gamma never-confirmed" in out)

    # --- 5. SessionStart dedups (fires once) ---
    out2 = _invoke(flush_check, {"session_id": "s3", "hook_event_name": "SessionStart"},
                   argv=["sessionstart"])
    ok("SessionStart dedups after first report", not fired(out2))

    # --- 6. SessionStart with empty spool -> silent ---
    _reset()
    out = _invoke(flush_check, {"session_id": "s4"}, argv=["sessionstart"])
    ok("SessionStart silent when spool empty", not fired(out))

    # --- 7. edit_note is also spooled ---
    _reset()
    _invoke(spool, {"session_id": "s5", "tool_name": "mcp__basic-memory__edit_note",
                    "tool_input": {"identifier": "notes/x", "operation": "append", "content": "more"}})
    ok("edit_note is spooled too", _spool_count() == 1)

    # --- 8. non-memory tool is ignored ---
    _reset()
    _invoke(spool, {"session_id": "s6", "tool_name": "Bash", "tool_input": {"command": "ls"}})
    ok("non-memory tool not spooled", _spool_count() == 0)

    # --- 8b. tool_use_id fallback clears the spool even if Post payload drifts ---
    _reset()
    _invoke(spool, {"session_id": "s7", "tool_use_id": "tu-123",
                    "tool_name": "mcp__basic-memory__write_note",
                    "tool_input": {"title": "Delta", "content": "orig"}})
    ok("spool stored with tool_use_id", _spool_count() == 1)
    out = _invoke(flush_check, {"session_id": "s7", "tool_use_id": "tu-123",
                  "tool_name": "mcp__basic-memory__write_note",
                  "tool_input": {"title": "Delta", "content": "DRIFTED-payload"},  # hash won't match
                  "tool_response": {"isError": False, "content": [{"text": "permalink: notes/delta"}]}},
                  argv=["posttool"])
    ok("uid fallback clears spool despite payload drift", _spool_count() == 0 and not fired(out))

    # --- 9. FAIL-OPEN on garbage stdin ---
    _reset()
    old = sys.stdin
    sys.stdin = io.StringIO("not json {{{")
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = flush_check.main(["sessionstart"])
    finally:
        sys.stdin = old
    ok("flush_check fail-open on bad stdin", rc == 0 and not fired(buf.getvalue()))

    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): {_FAILS}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
