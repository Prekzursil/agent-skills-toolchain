#!/usr/bin/env python3
r"""Tests for bg-registry. Runs WITHOUT pytest: `python test_bg_registry.py`.

Proves the registry trio actually FIRES (orphan alert) and actually STAYS SILENT
(live pid / present artifact / current-session / already-done / deduped) by DIRECT
invocation of register/done_marker/reconcile main() with sample stdin.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

# Isolate the registry to a throwaway dir BEFORE the modules cache any path.
_TMP = Path(tempfile.mkdtemp(prefix="bgreg-"))
os.environ["BG_REGISTRY_DIR"] = str(_TMP)
os.environ["BG_REGISTRY_MIN_AGE_SEC"] = "0"

import _common as C  # noqa: E402
import register  # noqa: E402
import done_marker  # noqa: E402
import reconcile  # noqa: E402

# Force every module's view of the registry to the temp dir + no grace window.
C.BG_DIR = _TMP
C.SEEN_FILE = _TMP / ".reconciled.json"
reconcile.GRACE = 0

_FAILS = []


def ok(name, cond):
    print(("PASS" if cond else "FAIL") + f": {name}")
    if not cond:
        _FAILS.append(name)


def _reset():
    for p in list(_TMP.glob("*.ndjson")) + [C.SEEN_FILE]:
        try:
            p.unlink()
        except OSError:
            pass


def _invoke(mod, stdin_obj):
    buf = io.StringIO()
    old = sys.stdin
    sys.stdin = io.StringIO(json.dumps(stdin_obj))
    try:
        with redirect_stdout(buf):
            # register.main takes argv (hook path = no flags); the others take none.
            mod.main([]) if mod is register else mod.main()
    finally:
        sys.stdin = old
    return buf.getvalue()


def _records(sid):
    return list(C.read_records(C.registry_file(sid)))


def _dead_pid() -> int:
    """A pid that is guaranteed dead: spawn a no-op child and reap it."""
    p = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.exit(0)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    p.wait()
    return p.pid


def fired(out):
    return "ORPHANED BACKGROUND WORK" in out


def main():  # noqa: C901
    # --- liveness primitive sanity (the foundation of the whole check) ---
    ok("pid_alive(self) is True", C.pid_alive(os.getpid()) is True)
    ok("pid_alive(dead) is not True", C.pid_alive(_dead_pid()) is not True)

    # --- register: hook mode (PreToolUse Task) ---
    _reset()
    _invoke(
        register,
        {
            "session_id": "S1",
            "tool_name": "Task",
            "tool_input": {
                "subagent_type": "code-reviewer",
                "description": "review",
                "prompt": "do the thing",
            },
        },
    )
    recs = _records("S1")
    ok(
        "register(Task) wrote one running record",
        len(recs) == 1 and recs[0]["status"] == "running" and recs[0]["kind"] == "Task",
    )
    ok("register(Task) marked sync=True", recs[0].get("sync") is True)

    # --- register: CLI mode (background launcher) ---
    _reset()
    out = _invoke_cli(
        [
            "--kind",
            "background",
            "--id",
            "lr-1",
            "--pid",
            "4242",
            "--artifact",
            str(_TMP / "out.log"),
            "--cmd",
            "jest --coverage",
            "--session",
            "S2",
        ]
    )
    recs = _records("S2")
    ok(
        "register CLI wrote record + SUCCESS marker",
        "SUCCESS:bg-registry" in out and len(recs) == 1 and recs[0]["pid"] == 4242,
    )
    ok("register CLI background sync=False", recs[0].get("sync") is False)

    # --- done_marker: synchronous Task closes on turn end ---
    _reset()
    C.append_record(
        "S3",
        {
            "id": "t1",
            "kind": "Task",
            "sync": True,
            "status": "running",
            "started_ts": C.now(),
            "session": "S3",
        },
    )
    _invoke(done_marker, {"session_id": "S3"})
    eff = C.fold(_records("S3"))
    ok("done_marker closes sync Task -> done", eff["t1"]["status"] == "done")

    # --- done_marker: background with present artifact -> done ---
    _reset()
    art = _TMP / "done-art.txt"
    art.write_text("result", encoding="utf-8")
    C.append_record(
        "S4",
        {
            "id": "b1",
            "kind": "background",
            "sync": False,
            "status": "running",
            "expected_artifact": str(art),
            "pid": _dead_pid(),
            "started_ts": C.now(),
            "session": "S4",
        },
    )
    _invoke(done_marker, {"session_id": "S4"})
    ok(
        "done_marker closes background w/ artifact -> done",
        C.fold(_records("S4"))["b1"]["status"] == "done",
    )

    # --- done_marker: background, no artifact, async -> stays running ---
    _reset()
    C.append_record(
        "S5",
        {
            "id": "b2",
            "kind": "background",
            "sync": False,
            "status": "running",
            "expected_artifact": str(_TMP / "nope.log"),
            "pid": 999999,
            "started_ts": C.now(),
            "session": "S5",
        },
    )
    _invoke(done_marker, {"session_id": "S5"})
    ok(
        "done_marker leaves incomplete background running",
        C.fold(_records("S5"))["b2"]["status"] == "running",
    )

    # === reconcile: the headline behavior ===
    # (a) dead pid + missing artifact (prior session) -> ALERT
    _reset()
    C.append_record(
        "PRIOR",
        {
            "id": "orph-1",
            "kind": "background",
            "sync": False,
            "status": "running",
            "pid": _dead_pid(),
            "expected_artifact": str(_TMP / "never.log"),
            "started_ts": C.now() - 3600,
            "session": "PRIOR",
        },
    )
    out = _invoke(reconcile, {"session_id": "CUR"})
    ok("reconcile alerts on dead-pid + missing-artifact orphan", fired(out))
    ok(
        "reconcile alert names the id + 'resume or discard'",
        "orph-1" in out and "resume or discard" in out,
    )

    # (b) live pid -> silent
    _reset()
    C.append_record(
        "PRIOR",
        {
            "id": "live-1",
            "kind": "background",
            "sync": False,
            "status": "running",
            "pid": os.getpid(),
            "expected_artifact": str(_TMP / "never.log"),
            "started_ts": C.now() - 3600,
            "session": "PRIOR",
        },
    )
    ok(
        "reconcile silent when pid is alive",
        not fired(_invoke(reconcile, {"session_id": "CUR"})),
    )

    # (c) present artifact -> silent (even with a dead pid)
    _reset()
    art2 = _TMP / "present.log"
    art2.write_text("output produced", encoding="utf-8")
    C.append_record(
        "PRIOR",
        {
            "id": "done-art",
            "kind": "background",
            "sync": False,
            "status": "running",
            "pid": _dead_pid(),
            "expected_artifact": str(art2),
            "started_ts": C.now() - 3600,
            "session": "PRIOR",
        },
    )
    ok(
        "reconcile silent when artifact present",
        not fired(_invoke(reconcile, {"session_id": "CUR"})),
    )

    # (d) current-session record -> silent (in-flight guard)
    _reset()
    C.append_record(
        "CUR",
        {
            "id": "inflight",
            "kind": "background",
            "sync": False,
            "status": "running",
            "pid": _dead_pid(),
            "expected_artifact": str(_TMP / "never.log"),
            "started_ts": C.now() - 3600,
            "session": "CUR",
        },
    )
    ok(
        "reconcile silent for current-session in-flight work",
        not fired(_invoke(reconcile, {"session_id": "CUR"})),
    )

    # (e) already-done record -> silent
    _reset()
    C.append_record(
        "PRIOR",
        {
            "id": "fin",
            "kind": "Task",
            "sync": True,
            "status": "running",
            "started_ts": C.now() - 3600,
            "session": "PRIOR",
        },
    )
    C.append_record("PRIOR", {"id": "fin", "status": "done", "done_ts": C.now()})
    ok(
        "reconcile silent for already-done record",
        not fired(_invoke(reconcile, {"session_id": "CUR"})),
    )

    # (f) dedup: alerts once, silent on the second SessionStart
    _reset()
    C.append_record(
        "PRIOR",
        {
            "id": "orph-dup",
            "kind": "background",
            "sync": False,
            "status": "running",
            "pid": _dead_pid(),
            "expected_artifact": str(_TMP / "never.log"),
            "started_ts": C.now() - 3600,
            "session": "PRIOR",
        },
    )
    first = _invoke(reconcile, {"session_id": "CUR"})
    second = _invoke(reconcile, {"session_id": "CUR2"})
    ok("reconcile fires once then dedups", fired(first) and not fired(second))

    # (g) FAIL-OPEN: garbage stdin never raises / never alerts
    _reset()
    bad = io.StringIO()
    old = sys.stdin
    sys.stdin = io.StringIO("}{ not json")
    try:
        with redirect_stdout(bad):
            rc = reconcile.main()
    finally:
        sys.stdin = old
    ok(
        "reconcile fail-open on bad stdin (rc 0, silent)",
        rc == 0 and not fired(bad.getvalue()),
    )

    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): {_FAILS}")
        return 1
    print("ALL PASS")
    return 0


def _invoke_cli(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        register.main(argv)
    return buf.getvalue()


if __name__ == "__main__":
    sys.exit(main())
