#!/usr/bin/env python3
"""Tests for truth-verify. Runs WITHOUT pytest: `python test_truth_verify.py`."""
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import check  # noqa: E402

_FAILS = []


def ok(name, cond):
    print(("PASS" if cond else "FAIL") + f": {name}")
    if not cond:
        _FAILS.append(name)


def transcript(events) -> str:
    f = Path(tempfile.mkdtemp(prefix="tv-")) / "t.jsonl"
    f.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    return str(f)


def human(text="analyze the binary"):
    return {"type": "user", "uuid": "H", "message": {"role": "user",
            "content": [{"type": "text", "text": text}]}}


def assistant_tool(name, inp):
    return {"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "tool_use", "name": name, "input": inp}]}}


def assistant_text(text):
    return {"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "text", "text": text}]}}


def run(tp, stop_active=False):
    buf = io.StringIO()
    old = sys.stdin
    sys.stdin = io.StringIO(json.dumps(
        {"transcript_path": tp, "stop_hook_active": stop_active}))
    try:
        with redirect_stdout(buf):
            check.main()
    finally:
        sys.stdin = old
    return buf.getvalue()


def fired(out):
    return "truth-verify" in out


def main():
    ANCHOR = "The stage-unlock hook is sub_8A3350 and the timer lives at offset 4536."

    # 1. Anchor as fact, no tool this turn -> FIRES.
    tp = transcript([human(), assistant_text(ANCHOR)])
    ok("anchor stated with no verifying tool -> nudge", fired(run(tp)))

    # 2. Anchor + RE MCP call this turn -> silent.
    tp = transcript([human(),
                     assistant_tool("mcp__ida-pro-mcp__decompile", {"addr": "0x8A3350"}),
                     assistant_text(ANCHOR)])
    ok("anchor + ida-pro-mcp call -> silent", not fired(run(tp)))

    # 3. Anchor + Bash objdump this turn -> silent.
    tp = transcript([human(),
                     assistant_tool("Bash", {"command": "objdump -d lib.so | grep 8a3350"}),
                     assistant_text(ANCHOR)])
    ok("anchor + objdump Bash -> silent", not fired(run(tp)))

    # 4. Hedged anchor -> silent.
    tp = transcript([human(), assistant_text(
        "It might be around sub_8A3350 but I need to verify this offset.")])
    ok("hedged anchor -> silent", not fired(run(tp)))

    # 5. No anchor -> silent.
    tp = transcript([human(), assistant_text(
        "I refactored the parser and cleaned up the imports.")])
    ok("no anchor -> silent", not fired(run(tp)))

    # 6. tests/coverage claim WITHOUT anchor (claim-guard's turf) -> silent here.
    tp = transcript([human(), assistant_text(
        "All tests pass and coverage is 100%. The bug is fixed.")])
    ok("tests/coverage claim (claim-guard turf) -> truth-verify silent",
       not fired(run(tp)))

    # 7. stop_hook_active -> silent (anti-loop).
    tp = transcript([human(), assistant_text(ANCHOR)])
    ok("stop_hook_active -> silent", not fired(run(tp, stop_active=True)))

    # 8. Read of the offsets file this turn counts as verification -> silent.
    tp = transcript([human(),
                     assistant_tool("Read", {"file_path": "D:/tools/offsets/en-15.4.1.json"}),
                     assistant_text(ANCHOR)])
    ok("anchor + Read of offsets file -> silent", not fired(run(tp)))

    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): {_FAILS}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
