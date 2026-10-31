#!/usr/bin/env python3
"""Tests for open-loops (Gem A). Runs WITHOUT pytest: `python test_open_loops.py`.

Isolates the store + the event-ledger root into a temp dir via env (set BEFORE import).
"""

import os
import sys
import tempfile
import time
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="ol-test-")
os.environ["OPEN_LOOPS_DIR"] = _TMP
os.environ["EVENT_LEDGER_ROOT"] = os.path.join(_TMP, "ledger")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402
import resurface  # noqa: E402
import trigger_match  # noqa: E402
import add  # noqa: E402

# belt-and-suspenders: point the store at the temp dir even if env timing slipped
C.OL_DIR = Path(_TMP)
C.TRIGGERS_FILE = Path(_TMP) / "triggers.jsonl"

_FAILS = []


def ok(name, cond):
    print(("PASS" if cond else "FAIL") + f": {name}")
    if not cond:
        _FAILS.append(name)


def reset():
    try:
        C.TRIGGERS_FILE.unlink()
    except FileNotFoundError:
        pass


def main():
    # ---- 1. plain-language parse + store round-trip -------------------------
    reset()
    add.main(["when cwd under D:\\WSA or a BC path -> re-assert event_0 after restart"])
    t = C.load_triggers()
    ok("plain-language add stored 1 trigger", len(t) == 1)
    cond = t[0]["condition"] if t else {}
    ok("parsed condition has predicates", bool(cond.get("preds")))
    ok(
        "parsed a cwd_glob from the path token",
        any(p["type"] == "cwd_glob" for p in cond.get("preds", [])),
    )
    ok("action parsed after the arrow", "event_0" in (t[0]["action"] if t else ""))

    # ---- 2. resurface FIRES when cwd matches -------------------------------
    msg = resurface.build_message({"cwd": "D:/WSA/battlecats", "source": "startup"})
    ok("resurface surfaces the matching loop", bool(msg) and "event_0" in msg)

    # ---- 3. resurface SILENT when nothing matches --------------------------
    reset()
    msg = resurface.build_message({"cwd": "C:/unrelated/proj", "source": "startup"})
    ok("resurface silent with no loops + empty ledger", msg is None)

    # ---- 4. explicit predicates + branch match (monkeypatched branch) ------
    reset()
    add.main(
        [
            "--branch",
            "feat/*",
            "--prompt-regex",
            r"\bPR\b|pull request",
            "--mode",
            "all",
            "--action",
            "re-read .coverage-thresholds.json",
        ]
    )
    t = C.load_triggers()
    ok("explicit add stored with mode=all", t and t[0]["condition"]["mode"] == "all")
    _orig_branch = C.git_branch
    C.git_branch = lambda cwd: "feat/trainer-gui-p2c"
    try:
        # condition is ALL: branch feat/* AND prompt has PR -> both hold -> fires
        m, changed = trigger_match.select_and_fire(
            {"cwd": _TMP, "prompt": "let's open a PR now", "transcript_path": ""}
        )
        ok(
            "trigger_match fires when branch+prompt both match",
            bool(m) and "coverage" in m,
        )
        ok("one-shot marked fired (write-back)", changed)
        # second turn -> already fired (one-shot) -> silent
        m2, _ = trigger_match.select_and_fire(
            {"cwd": _TMP, "prompt": "let's open a PR now", "transcript_path": ""}
        )
        ok("one-shot does not re-fire", m2 is None)
    finally:
        C.git_branch = _orig_branch

    # ---- 5. non-matching trigger is SILENT ---------------------------------
    reset()
    add.main(["--cwd-glob", "*nonexistent-marker*", "--action", "do X"])
    m, _ = trigger_match.select_and_fire(
        {"cwd": "C:/somewhere/else", "prompt": "hello", "transcript_path": ""}
    )
    ok("non-matching trigger stays silent", m is None)

    # ---- 6. standing `always` loop does NOT fire on prompt, DOES resurface --
    reset()
    add.main(["just remember to clean up the temp daemons"])  # no '->' -> always loop
    t = C.load_triggers()
    ok(
        "no-arrow text -> always standing loop",
        t and t[0]["condition"]["preds"][0]["type"] == "always",
    )
    m, _ = trigger_match.select_and_fire(
        {"cwd": _TMP, "prompt": "anything", "transcript_path": ""}
    )
    ok("always loop is NOT fired on every prompt (anti-nag)", m is None)
    msg = resurface.build_message({"cwd": _TMP, "source": "startup"})
    ok("always loop IS surfaced at SessionStart", bool(msg) and "temp daemons" in msg)

    # ---- 7. expired (ttl) is GC'd -----------------------------------------
    reset()
    old = C.make_trigger(
        {"mode": "any", "preds": [{"type": "always"}]}, "stale loop", ttl_days=1
    )
    old["created_ts"] = time.time() - 5 * 86400  # 5 days ago, ttl 1 day -> expired
    C.append_trigger(old)
    fresh = C.make_trigger(
        {"mode": "any", "preds": [{"type": "always"}]}, "live loop", ttl_days=0
    )  # never expires
    C.append_trigger(fresh)
    survived = C.load_triggers(gc=True)
    ok(
        "expired trigger GC'd, fresh kept",
        len(survived) == 1 and survived[0]["action"] == "live loop",
    )
    # the GC rewrote the file -> only 1 line remains on disk
    on_disk = [
        ln
        for ln in C.TRIGGERS_FILE.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    ok("GC rewrote the store (expired removed from disk)", len(on_disk) == 1)

    # ---- 8. --close flips fired -------------------------------------------
    reset()
    add.main(["--cwd-glob", "*x*", "--action", "closeme"])
    tid = C.load_triggers()[0]["id"]
    add.main(["--close", tid])
    ok("--close marks the loop fired", C.load_triggers()[0]["fired"] is True)

    # ---- 9. dispatcher-style main([]) emits JSON on stdout -----------------
    reset()
    add.main(["--cwd-glob", "*wsa*", "--action", "dispatch-check"])
    import io
    import json
    from contextlib import redirect_stdout

    buf = io.StringIO()
    old_stdin = sys.stdin
    sys.stdin = io.StringIO(json.dumps({"cwd": "D:/WSA", "source": "startup"}))
    try:
        with redirect_stdout(buf):
            resurface.main([])
    finally:
        sys.stdin = old_stdin
    out = buf.getvalue()
    parsed_ok = False
    for line in out.splitlines():
        try:
            o = json.loads(line)
            if o.get("hookSpecificOutput", {}).get("additionalContext"):
                parsed_ok = True
        except Exception:
            pass
    ok("resurface.main emits valid hookSpecificOutput JSON", parsed_ok)

    # ---- 10. fail-open on a corrupt store ----------------------------------
    reset()
    C.TRIGGERS_FILE.write_text("{ this is not json\n@@@\n", encoding="utf-8")
    ok("corrupt store -> load_triggers returns [] (fail-open)", C.load_triggers() == [])
    ok(
        "corrupt store -> resurface does not crash",
        resurface.build_message({"cwd": _TMP, "source": "startup"}) is None,
    )

    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): {_FAILS}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
