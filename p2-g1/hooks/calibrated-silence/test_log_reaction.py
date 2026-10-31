#!/usr/bin/env python3
"""Tests for log_reaction.py. Runs WITHOUT pytest: `python test_log_reaction.py`.

Covers the pure reaction classifier (acted via tool / acted via answered question /
annoyed / ignored / nudge-via-memory-write), transcript parsing (skipping tool_result
'user' events), the write-back planner (stale, self-turn guard, session scope, Stop
partial mode), and an end-to-end UserPromptSubmit run via stdin.
"""

import io
import json
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import calibrated_silence as cs  # noqa: E402
import log_reaction as lr  # noqa: E402

_FAILS = []


def ok(name, cond):
    print(("PASS" if cond else "FAIL") + f": {name}")
    if not cond:
        _FAILS.append(name)


def urow(t, ck, reaction="unknown", ts=None, sid="s"):
    return {
        "ts": time.time() if ts is None else ts,
        "type": t,
        "context_key": ck,
        "session_id": sid,
        "surfaced": True,
        "reaction": reaction,
    }


# transcript event builders -------------------------------------------------
def user_ev(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def user_toolresult_ev():
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "content": "out"}],
        },
    }


def asst_tool_ev(name, inp):
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "tool_use", "name": name, "input": inp}],
        },
    }


def transcript(events):
    f = Path(tempfile.mkdtemp(prefix="lr-")) / "t.jsonl"
    f.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    return str(f)


def main():
    # ---- pure dismissal / substantive ------------------------------------
    ok("dismissal: 'no'", lr.is_dismissal("no"))
    ok("dismissal: 'stop'", lr.is_dismissal("Stop."))
    ok("dismissal: 'no thanks'", lr.is_dismissal("no thanks"))
    ok("dismissal: 'skip it'", lr.is_dismissal("skip it"))
    ok(
        "not dismissal: long negative",
        not lr.is_dismissal(
            "no, actually I think we should refactor the whole auth module instead"
        ),
    )
    ok("not dismissal: agreement", not lr.is_dismissal("yes please do that"))
    ok(
        "substantive: real answer",
        lr.is_substantive("yes the auth module specifically please"),
    )
    ok("not substantive: 'ok'", not lr.is_substantive("ok"))
    ok("not substantive: dismissal", not lr.is_substantive("no"))

    # ---- pure classify ---------------------------------------------------
    ok(
        "acted via skill tool",
        lr.classify(
            "suggestion",
            "skill:systematic-debugging",
            "ok",
            {"skill:systematic-debugging"},
        )
        == "acted",
    )
    ok(
        "acted via name-only context_key match",
        lr.classify(
            "route", "systematic-debugging", "k", {"skill:systematic-debugging"}
        )
        == "acted",
    )
    ok(
        "acted via answered question",
        lr.classify(
            "question",
            "clarify:goal",
            "yes I mean the auth refactor specifically",
            set(),
        )
        == "acted",
    )
    ok(
        "annoyed via terse dismissal",
        lr.classify("suggestion", "skill:foo", "no thanks", set()) == "annoyed",
    )
    ok(
        "ignored: substantive but no tool, not a question",
        lr.classify(
            "suggestion",
            "skill:foo",
            "let me think about the architecture later today",
            set(),
        )
        == "ignored",
    )
    ok(
        "ignored: silence, no tool",
        lr.classify("route", "mcp:tooluniverse", "ok", set()) == "ignored",
    )
    ok(
        "nudge acted via memory write",
        lr.classify("nudge", "persist:durable", "thanks", {"memory:write"}) == "acted",
    )
    ok(
        "nudge acted via basic-memory mcp",
        lr.classify("nudge", "persist:durable", "k", {"mcp:basic-memory"}) == "acted",
    )
    ok(
        "tool match beats dismissal (user acted then grumbled)",
        lr.classify("suggestion", "skill:foo", "no", {"skill:foo"}) == "acted",
    )

    # ---- transcript parsing ----------------------------------------------
    last_text, keys = lr.turn_signals(
        transcript(
            [
                user_ev("first prompt here please"),
                asst_tool_ev(
                    "Read", {"file_path": "a.py"}
                ),  # before last user -> excluded
                user_toolresult_ev(),  # tool result, NOT a user turn
                user_ev("second prompt turn T"),
                asst_tool_ev("Skill", {"skill": "systematic-debugging"}),
            ]
        )
    )
    ok("turn_signals last user text", last_text == "second prompt turn T")
    ok(
        "turn_signals tool keys = post-last-user only",
        "skill:systematic-debugging" in keys and "Read" not in str(keys),
    )
    # memory-write synthetic key from a note.py bash
    _t, keys2 = lr.turn_signals(
        transcript(
            [
                user_ev("save this please now"),
                asst_tool_ev(
                    "Bash",
                    {
                        "command": "python ~/.claude/hooks/event-ledger/note.py --kind decision x"
                    },
                ),
            ]
        )
    )
    ok("note.py bash -> memory:write key", "memory:write" in keys2)

    # ---- apply_reactions (pure, deterministic now) -----------------------
    t0 = 1_000_000.0
    rows = [urow("route", "skill:systematic-debugging", ts=t0 - 100, sid="s")]
    rows, n = lr.apply_reactions(
        rows, "s", "ok", {"skill:systematic-debugging"}, now=t0
    )
    ok("apply: acted via tool", rows[0]["reaction"] == "acted" and n == 1)

    rows = [urow("suggestion", "skill:foo", ts=t0 - 100, sid="s")]
    lr.apply_reactions(rows, "s", "no thanks", set(), now=t0)
    ok("apply: annoyed via dismissal", rows[0]["reaction"] == "annoyed")

    rows = [urow("suggestion", "skill:foo", ts=t0 - 100, sid="s")]
    lr.apply_reactions(
        rows, "s", "let us go look at something else entirely now", set(), now=t0
    )
    ok(
        "apply: ignored (substantive, no tool, not question)",
        rows[0]["reaction"] == "ignored",
    )

    rows = [urow("question", "clarify:goal", ts=t0 - 100, sid="s")]
    lr.apply_reactions(
        rows, "s", "yes refactor the auth module specifically please", set(), now=t0
    )
    ok("apply: question answered -> acted", rows[0]["reaction"] == "acted")

    # self-turn guard: a row recorded THIS turn (ts ~ now) is left unknown
    rows = [urow("route", "skill:x", ts=t0, sid="s")]
    lr.apply_reactions(rows, "s", "no", set(), now=t0)
    ok("apply: self-turn row left unknown", rows[0]["reaction"] == "unknown")

    # stale unknown (older than REACTION_WINDOW) with no tool -> ignored
    rows = [urow("suggestion", "skill:foo", ts=t0 - 5000, sid="s")]
    lr.apply_reactions(rows, "s", "totally unrelated new request here", set(), now=t0)
    ok("apply: stale unknown -> ignored", rows[0]["reaction"] == "ignored")
    # stale but the tool was eventually used -> acted
    rows = [urow("suggestion", "skill:foo", ts=t0 - 5000, sid="s")]
    lr.apply_reactions(rows, "s", "x", {"skill:foo"}, now=t0)
    ok("apply: stale + tool used -> acted", rows[0]["reaction"] == "acted")

    # session scoping: other session untouched
    rows = [urow("route", "skill:x", ts=t0 - 100, sid="other")]
    lr.apply_reactions(rows, "s", "no", set(), now=t0)
    ok("apply: other-session row untouched", rows[0]["reaction"] == "unknown")

    # Stop partial mode: acted via tool credited; non-acted stays unknown (not punished)
    rows = [urow("route", "skill:x", ts=t0 - 100, sid="s")]
    lr.apply_reactions(rows, "s", "", {"skill:x"}, stop_mode=True, now=t0)
    ok("stop-mode: acted credited", rows[0]["reaction"] == "acted")
    rows = [urow("route", "skill:x", ts=t0 - 100, sid="s")]
    lr.apply_reactions(rows, "s", "no", set(), stop_mode=True, now=t0)
    ok(
        "stop-mode: non-acted stays unknown (not premature ignored)",
        rows[0]["reaction"] == "unknown",
    )

    # ---- end-to-end main() via stdin (UserPromptSubmit path) -------------
    led = Path(tempfile.mkdtemp(prefix="lr-led-")) / "interjections.jsonl"
    cs.LEDGER_PATH = led
    cs.record_interjection(
        "suggestion",
        "skill:systematic-debugging",
        "sess",
        path=led,
        now=time.time() - 120,
    )
    tp = transcript(
        [
            user_ev("the previous prompt"),
            asst_tool_ev("Skill", {"skill": "systematic-debugging"}),
        ]
    )
    _run_main({"session_id": "sess", "transcript_path": tp, "prompt": "great, thanks"})
    reacted = cs.read_rows(led)[0]["reaction"]
    ok(
        "e2e: UserPromptSubmit classifies prior interjection as acted",
        reacted == "acted",
    )

    # opt-out: CALSIL_REACTION=off makes main() a no-op
    import os

    led2 = Path(tempfile.mkdtemp(prefix="lr-led-")) / "interjections.jsonl"
    cs.LEDGER_PATH = led2
    cs.record_interjection(
        "suggestion", "skill:foo", "sess2", path=led2, now=time.time() - 120
    )
    os.environ["CALSIL_REACTION"] = "off"
    try:
        _run_main(
            {
                "session_id": "sess2",
                "transcript_path": transcript([user_ev("x")]),
                "prompt": "no",
            }
        )
    finally:
        os.environ.pop("CALSIL_REACTION", None)
    ok(
        "e2e: opt-out leaves ledger unchanged",
        cs.read_rows(led2)[0]["reaction"] == "unknown",
    )

    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): {_FAILS}")
        return 1
    print("ALL PASS")
    return 0


def _run_main(stdin_obj):
    buf = io.StringIO()
    old = sys.stdin
    sys.stdin = io.StringIO(json.dumps(stdin_obj))
    try:
        with redirect_stdout(buf):
            lr.main()
    finally:
        sys.stdin = old
    return buf.getvalue()


if __name__ == "__main__":
    sys.exit(main())
