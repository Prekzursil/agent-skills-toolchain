#!/usr/bin/env python3
"""Tests for ulysses (Gem B). Runs WITHOUT pytest: `python test_ulysses.py`.

Covers: arm 2 tripwires; HARD trip -> exit 2 + reason (real subprocess wiring);
soft trip -> inject; no trip -> silent; disarm guard; calls_since_test from a
transcript; expiry; and fail-open on a bad store.
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="uly-test-")
os.environ["ULYSSES_DIR"] = _TMP

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import _common as C  # noqa: E402
import arm  # noqa: E402
import enforce  # noqa: E402

# belt-and-suspenders isolation
C.ULY_DIR = Path(_TMP)
C.TRIPWIRES_FILE = Path(_TMP) / "tripwires.json"
C.OVERRIDES_FILE = Path(_TMP) / "overrides.jsonl"

_FAILS = []


def ok(name, cond):
    print(("PASS" if cond else "FAIL") + f": {name}")
    if not cond:
        _FAILS.append(name)


def reset():
    for f in (C.TRIPWIRES_FILE, C.OVERRIDES_FILE):
        try:
            f.unlink()
        except FileNotFoundError:
            pass


def run_enforce(payload: dict):
    """Invoke enforce.py as a real subprocess (proves the exit-code wiring)."""
    env = dict(os.environ)
    env["ULYSSES_DIR"] = _TMP
    p = subprocess.run(
        [sys.executable, str(THIS / "enforce.py")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    return p.returncode, p.stdout, p.stderr


def write_transcript(events) -> str:
    f = Path(tempfile.mkdtemp(prefix="uly-t-")) / "t.jsonl"
    f.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    return str(f)


def edit_ev(path):
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "tu" + os.urandom(3).hex(),
                    "name": "Edit",
                    "input": {"file_path": path},
                }
            ],
        },
    }


def bash_ev(cmd):
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "tu" + os.urandom(3).hex(),
                    "name": "Bash",
                    "input": {"command": cmd},
                }
            ],
        },
    }


def main():
    # ---- 1. arm 2 tripwires ------------------------------------------------
    reset()
    arm.main(["--task", "BC live-mod RE", "--guard-live-game", "--max-edits", "4"])
    store = C.load_tripwires()
    ok("armed store loads", bool(store))
    ok("arm wrote 2 tripwires", store and len(store["predicates"]) == 2)
    ok(
        "one HALT + one ASK",
        store and sorted(p["action"] for p in store["predicates"]) == ["ASK", "HALT"],
    )

    # ---- 2. HARD trip (decide) + real exit-2 subprocess --------------------
    ctx = {
        "tool": "mcp__cheatengine__write_integer",
        "file_path": "",
        "command": "",
        "edit_counts": {},
        "calls_since_test": 0,
        "last_run_failed": False,
        "is_disarm": False,
        "override_active": False,
    }
    v = C.decide(store, ctx)
    ok("decide() HALTs on live-game write", v["verdict"] == "halt")

    rc, out, err = run_enforce(
        {
            "tool_name": "mcp__cheatengine__write_integer",
            "tool_input": {"address": "0x1", "value": 1},
            "cwd": _TMP,
            "transcript_path": "",
        }
    )
    ok("enforce exit code 2 on HARD trip", rc == 2)
    ok("HALT reason on stderr", "HALT" in err and "live" in err.lower())
    ok("HALT writes nothing to stdout", out.strip() == "")

    # ---- 3. SOFT trip (4th edit) -> inject, exit 0 -------------------------
    target = str(Path(_TMP) / "target.py")
    tp = write_transcript([edit_ev(target), edit_ev(target), edit_ev(target)])
    ctx2 = {
        "tool": "Edit",
        "file_path": target,
        "command": "",
        "edit_counts": {C._norm(target): 3},
        "calls_since_test": 0,
        "last_run_failed": False,
        "is_disarm": False,
        "override_active": False,
    }
    ok("decide() ASKs on the 4th edit", C.decide(store, ctx2)["verdict"] == "ask")
    rc, out, err = run_enforce(
        {
            "tool_name": "Edit",
            "tool_input": {"file_path": target},
            "cwd": _TMP,
            "transcript_path": tp,
        }
    )
    ok("enforce exit 0 on soft trip", rc == 0)
    ok(
        "soft trip injects additionalContext",
        '"additionalContext"' in out and "ASK" in out,
    )

    # ---- 4. NO trip -> silent ---------------------------------------------
    fresh = str(Path(_TMP) / "brand_new.py")
    rc, out, err = run_enforce(
        {
            "tool_name": "Edit",
            "tool_input": {"file_path": fresh},
            "cwd": _TMP,
            "transcript_path": "",
        }
    )
    ok("no trip -> exit 0", rc == 0)
    ok(
        "no trip -> silent (no stdout, no block)",
        out.strip() == "" and err.strip() == "",
    )

    # ---- 5. disarm guard ---------------------------------------------------
    dis = {
        "tool": "Write",
        "file_path": str(C.TRIPWIRES_FILE),
        "command": "",
        "edit_counts": {},
        "calls_since_test": 0,
        "last_run_failed": False,
        "is_disarm": True,
        "override_active": False,
    }
    ok("disarm without override -> HALT", C.decide(store, dis)["verdict"] == "halt")
    dis_ovr = dict(dis, override_active=True)
    ok(
        "disarm WITH logged override -> allowed",
        C.decide(store, dis_ovr)["verdict"] == "allow",
    )
    # real subprocess: direct Write to tripwires.json blocked
    rc, out, err = run_enforce(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": str(C.TRIPWIRES_FILE)},
            "cwd": _TMP,
            "transcript_path": "",
        }
    )
    ok(
        "enforce blocks a direct write to tripwires.json",
        rc == 2 and "override" in err.lower(),
    )
    # after a logged override, the same write is allowed
    C.log_override("intentional re-scope")
    rc, out, err = run_enforce(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": str(C.TRIPWIRES_FILE)},
            "cwd": _TMP,
            "transcript_path": "",
        }
    )
    ok("override lets the disarm-edit through", rc == 0)

    # ---- 6. calls_since_test from a transcript ----------------------------
    reset()
    arm.main(["--task", "T", "--max-calls-since-test", "5"])
    store2 = C.load_tripwires()
    # 8 non-test tool calls, no passing test -> calls_since_test = 8 > 5
    ev = [bash_ev("echo hi") for _ in range(8)]
    tp = write_transcript(ev)
    scan = C.scan_transcript(tp)
    ok("scan counts 8 tool calls", scan["tool_calls"] == 8)
    ok("calls_since_test = 8 (never passed)", scan["calls_since_test"] == 8)
    ctx3 = {
        "tool": "Bash",
        "file_path": "",
        "command": "echo go",
        "edit_counts": {},
        "calls_since_test": scan["calls_since_test"],
        "last_run_failed": True,
        "is_disarm": False,
        "override_active": False,
    }
    ok(
        "decide() ASKs after N untested calls",
        C.decide(store2, ctx3)["verdict"] == "ask",
    )
    # now add a PASSING test run near the end -> counter resets
    ev2 = [
        bash_ev("echo a"),
        bash_ev("python -m pytest"),  # this one "passes"
        bash_ev("echo b"),
        bash_ev("echo c"),
    ]
    # attach a passing tool_result for the pytest call
    pytest_id = ev2[1]["message"]["content"][0]["id"]
    ev2.append(
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": pytest_id,
                        "content": "=== 12 passed in 1.2s ===",
                    }
                ],
            },
        }
    )
    scan2 = C.scan_transcript(write_transcript(ev2))
    ok("a passing test resets calls_since_test", scan2["calls_since_test"] <= 2)

    # ---- 7. expiry -> disarmed --------------------------------------------
    reset()
    arm.main(["--task", "E", "--ttl-hours", "1", "--guard-live-game"])
    store_e = C.load_tripwires()
    ok("armed with ttl", bool(store_e))
    store_e["armed_ts"] = time.time() - 2 * 3600  # 2h ago, ttl 1h -> expired
    C.save_tripwires(store_e)
    ok("expired store -> load returns None (disarmed)", C.load_tripwires() is None)
    rc, out, err = run_enforce(
        {
            "tool_name": "mcp__cheatengine__write_integer",
            "tool_input": {},
            "cwd": _TMP,
            "transcript_path": "",
        }
    )
    ok("expired tripwires -> no block (exit 0, silent)", rc == 0 and out.strip() == "")

    # ---- 8. fail-open on a corrupt store ----------------------------------
    reset()
    C.TRIPWIRES_FILE.write_text("{not valid json @@@", encoding="utf-8")
    ok("corrupt store -> load_tripwires None", C.load_tripwires() is None)
    rc, out, err = run_enforce(
        {
            "tool_name": "mcp__cheatengine__write_memory",
            "tool_input": {},
            "cwd": _TMP,
            "transcript_path": "",
        }
    )
    ok("corrupt store -> fail-open (exit 0, no block)", rc == 0 and out.strip() == "")

    # ---- 9. in-process main() fail-open on bad stdin ----------------------
    old_stdin = sys.stdin
    sys.stdin = io.StringIO("not json")
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = enforce.main()
    finally:
        sys.stdin = old_stdin
    ok("enforce.main fail-open on bad stdin", rc == 0)

    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): {_FAILS}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
