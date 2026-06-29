#!/usr/bin/env python3
"""Tests for persist-nudge. Runs WITHOUT pytest: `python test_nudge.py`."""
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import nudge  # noqa: E402

_FAILS = []


def ok(name, cond):
    print(("PASS" if cond else "FAIL") + f": {name}")
    if not cond:
        _FAILS.append(name)


def edit_ev(n):
    return {"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "tool_use", "name": "Edit",
                         "input": {"file_path": f"f{n}.py"}}]}}


def bash_ev(cmd):
    return {"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "tool_use", "name": "Bash",
                         "input": {"command": cmd}}]}}


def bm_write_ev():
    return {"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "tool_use", "name": "mcp__basic-memory__write_note",
                         "input": {"title": "x"}}]}}


def transcript(events) -> str:
    f = Path(tempfile.mkdtemp(prefix="pn-")) / "t.jsonl"
    f.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    return str(f)


def run(tp, sid, stop_active=False):
    buf = io.StringIO()
    old = sys.stdin
    sys.stdin = io.StringIO(json.dumps(
        {"transcript_path": tp, "session_id": sid, "stop_hook_active": stop_active}))
    try:
        with redirect_stdout(buf):
            nudge.main()
    finally:
        sys.stdin = old
    return buf.getvalue()


def fired(out):
    return "persist-nudge" in out


def main():
    # isolate the once-per-session marker store
    nudge.SEEN_DIR = Path(tempfile.mkdtemp(prefix="pn-seen-"))

    # 1. 6 edits, no persist -> fires.
    tp = transcript([edit_ev(i) for i in range(6)])
    ok("6 edits, nothing saved -> nudge", fired(run(tp, "s1")))

    # 2. 1 commit, no persist -> fires.
    tp = transcript([edit_ev(0), bash_ev("git commit -m wip")])
    ok("1 commit, nothing saved -> nudge", fired(run(tp, "s2")))

    # 3. 6 edits + basic-memory write_note -> silent.
    tp = transcript([edit_ev(i) for i in range(6)] + [bm_write_ev()])
    ok("edits + basic-memory write_note -> silent", not fired(run(tp, "s3")))

    # 4. 6 edits + note.py Bash -> silent.
    tp = transcript([edit_ev(i) for i in range(6)] +
                    [bash_ev("python ~/.claude/hooks/event-ledger/note.py --kind decision x")])
    ok("edits + note.py -> silent", not fired(run(tp, "s4")))

    # 5. below threshold (3 edits, no commit) -> silent.
    tp = transcript([edit_ev(i) for i in range(3)])
    ok("3 edits, no commit -> silent (below threshold)", not fired(run(tp, "s5")))

    # 6. once-per-session dedup.
    tp = transcript([edit_ev(i) for i in range(6)])
    first = run(tp, "s6")
    second = run(tp, "s6")
    ok("fires once then deduped", fired(first) and not fired(second))

    # 7. stop_hook_active -> silent.
    tp = transcript([edit_ev(i) for i in range(6)])
    ok("stop_hook_active -> silent", not fired(run(tp, "s7", stop_active=True)))

    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): {_FAILS}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
