#!/usr/bin/env python
"""Tests for the TMS auto-retraction system. Run WITHOUT pytest:

    python test_tms.py

Covers: the cascade (retract a premise -> dependents flip OUT), explain reasons,
source-drift recheck (+ restore), cycle/unknown-premise rejection, the CLI
end-to-end, and the stale_anchor PreToolUse hook (soft inject / hard exit-2 /
silent-when-IN / fail-open / throttle).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import tms_core as tms  # noqa: E402

CLI = THIS / "tms.py"
HOOK = THIS / "stale_anchor.py"
_FAILS: list[str] = []


def ok(name: str, cond: bool) -> None:
    print(("PASS" if cond else "FAIL") + f": {name}")
    if not cond:
        _FAILS.append(name)


def newdb() -> str:
    d = tempfile.mkdtemp(prefix="tms-test-")
    p = os.path.join(d, "beliefs.db")
    os.environ["TMS_DB"] = p
    return p


def raises(fn) -> bool:
    try:
        fn()
        return False
    except Exception:
        return True


def run_cli(db: str, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["TMS_DB"] = db
    return subprocess.run(
        [sys.executable, str(CLI), *args], capture_output=True, text=True, env=env
    )


def run_hook(db: str, payload: dict) -> tuple[int, str, str]:
    env = dict(os.environ)
    env["TMS_DB"] = db
    p = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    return p.returncode, p.stdout, p.stderr


def chain(conn) -> None:
    """base(IN) <- off_render(premise base) <- finding(premise off_render)."""
    tms.assert_node(conn, "base", "image base 0x400000", "address")
    tms.assert_node(
        conn,
        "off_render",
        "getGlobal render fn at 0x4F1E20",
        "offset",
        premises=["base"],
    )
    tms.assert_node(
        conn,
        "finding",
        "patch target at 0x4F1E20 (getGlobal)",
        "fact",
        premises=["off_render"],
    )


def st(conn, nid: str) -> str:
    return tms.get_node(conn, nid)["status"]


# --------------------------------------------------------------------------- #
def test_cascade() -> None:
    newdb()
    conn = tms.connect()
    chain(conn)
    ok(
        "cascade: all IN initially",
        all(st(conn, x) == "IN" for x in ("base", "off_render", "finding")),
    )

    flips = tms.retract_node(conn, "base")
    ok("cascade: retract base -> base OUT", st(conn, "base") == "OUT")
    ok("cascade: offset flips OUT", st(conn, "off_render") == "OUT")
    ok("cascade: finding flips OUT (transitive)", st(conn, "finding") == "OUT")
    ok("cascade: flips report dependents", "off_render" in flips and "finding" in flips)

    ok(
        "explain: base reason = retracted",
        "retracted" in tms.get_node(conn, "base")["reason"],
    )
    ok(
        "explain: offset reason names premise base",
        "premise" in tms.get_node(conn, "off_render")["reason"].lower()
        and "base" in tms.get_node(conn, "off_render")["reason"],
    )
    ok(
        "explain: finding root cause traces to base",
        ("base", "explicitly retracted") in tms.root_causes(conn, "finding"),
    )

    tms.assert_node(conn, "base", "image base 0x400000", "address")
    ok(
        "cascade: re-assert base restores all IN",
        all(st(conn, x) == "IN" for x in ("base", "off_render", "finding")),
    )

    # an independently-retracted dependent stays OUT even when its premise is IN
    tms.retract_node(conn, "finding")
    ok(
        "cascade: explicitly-retracted finding stays OUT while base IN",
        st(conn, "base") == "IN"
        and st(conn, "off_render") == "IN"
        and st(conn, "finding") == "OUT",
    )


def test_drift() -> None:
    p = newdb()
    src = os.path.join(os.path.dirname(p), "lib.bin")
    Path(src).write_bytes(b"\x90\x90 original bytes")
    conn = tms.connect()
    tms.assert_node(
        conn, "fn", "scan match getCheck at 0x1234abcd", "address", source=src
    )
    tms.assert_node(
        conn, "patch", "nop the integrity check in fn", "fact", premises=["fn"]
    )
    ok(
        "drift: IN before any change",
        st(conn, "fn") == "IN" and st(conn, "patch") == "IN",
    )

    drift, _ = tms.recheck(conn)
    ok("drift: recheck is a no-op when unchanged", not drift and st(conn, "fn") == "IN")

    Path(src).write_bytes(b"\xcc changed bytes -- recompiled")
    drift, _ = tms.recheck(conn)
    ok("drift: recheck flags fn drifted", drift.get("fn") is True)
    ok(
        "drift: fn + dependent patch now OUT",
        st(conn, "fn") == "OUT" and st(conn, "patch") == "OUT",
    )
    ok(
        "drift: explain mentions sha drift",
        "drift" in tms.get_node(conn, "fn")["reason"],
    )

    Path(src).write_bytes(b"\x90\x90 original bytes")  # restore exact bytes
    tms.recheck(conn)
    ok(
        "drift: restoring the file recovers IN (bidirectional)",
        st(conn, "fn") == "IN" and st(conn, "patch") == "IN",
    )


def test_guards() -> None:
    newdb()
    conn = tms.connect()
    tms.assert_node(conn, "a", "A", "fact")
    tms.assert_node(conn, "b", "B", "fact", premises=["a"])
    ok(
        "guard: cycle assert rejected",
        raises(lambda: tms.assert_node(conn, "a", "A2", "fact", premises=["b"])),
    )
    ok(
        "guard: unknown premise rejected",
        raises(lambda: tms.assert_node(conn, "c", "C", "fact", premises=["ghost"])),
    )
    ok(
        "guard: bad kind rejected",
        raises(lambda: tms.assert_node(conn, "d", "D", "banana")),
    )
    ok(
        "guard: retract missing node rejected",
        raises(lambda: tms.retract_node(conn, "ghost")),
    )


def test_cli() -> None:
    p = newdb()
    r = run_cli(
        p, "assert", "base", "--statement", "image base 0x400000", "--kind", "address"
    )
    ok("cli: assert base rc0", r.returncode == 0 and "asserted" in r.stdout)
    run_cli(
        p,
        "assert",
        "off",
        "--statement",
        "offset 0x4F1E20",
        "--kind",
        "offset",
        "--premises",
        "base",
    )
    run_cli(
        p,
        "assert",
        "find",
        "--statement",
        "finding render hook",
        "--kind",
        "fact",
        "--premises",
        "off",
    )

    r = run_cli(p, "retract", "base")
    ok(
        "cli: retract base cascades to off+find",
        r.returncode == 0 and "off" in r.stdout and "find" in r.stdout,
    )

    r = run_cli(p, "status", "--out-only", "--json")
    ids = {n["id"] for n in json.loads(r.stdout)}
    ok("cli: status --out-only lists all 3 OUT", ids == {"base", "off", "find"})

    r = run_cli(p, "explain", "off", "--json")
    ej = json.loads(r.stdout)
    ok(
        "cli: explain off OUT + root cause base",
        ej["status"] == "OUT" and any(c["id"] == "base" for c in ej["root_causes"]),
    )

    r = run_cli(p, "trace", "find", "--json")
    tj = json.loads(r.stdout)
    ok(
        "cli: trace find closure includes base+off",
        set(tj["ancestors"]) >= {"base", "off"},
    )

    r = run_cli(p, "explain", "ghost")
    ok(
        "cli: explain missing node -> rc1 + stderr",
        r.returncode == 1 and "no such node" in r.stderr,
    )


def test_hook() -> None:
    # silent when everything IN
    p = newdb()
    conn = tms.connect()
    chain(conn)
    rc, out, err = run_hook(
        p,
        {
            "tool_name": "mcp__cheatengine__read_memory",
            "tool_input": {"address": "0x4F1E20"},
        },
    )
    ok(
        "hook: silent when all IN (read)",
        rc == 0 and out.strip() == "" and err.strip() == "",
    )
    rc, out, err = run_hook(
        p,
        {
            "tool_name": "mcp__cheatengine__write_memory",
            "tool_input": {"address": "0x4F1E20", "value": 0},
        },
    )
    ok(
        "hook: silent when all IN (write)",
        rc == 0 and out.strip() == "" and err.strip() == "",
    )

    # retract base -> off_render + finding OUT
    tms.retract_node(conn, "base")

    rc, out, err = run_hook(
        p,
        {
            "tool_name": "mcp__cheatengine__read_memory",
            "tool_input": {"address": "0x4F1E20"},
        },
    )
    ok(
        "hook: SOFT inject on OUT offset (read, non-write)",
        rc == 0 and "STALE ANCHOR" in out,
    )
    inj = json.loads(out)["hookSpecificOutput"]
    ok(
        "hook: soft uses additionalContext (exit 0)",
        "additionalContext" in inj and "BLOCKED" not in inj["additionalContext"],
    )

    rc, out, err = run_hook(
        p,
        {
            "tool_name": "mcp__cheatengine__write_memory",
            "tool_input": {"address": "0x4F1E20", "value": 0},
        },
    )
    ok(
        "hook: HARD exit-2 on write/patch to OUT offset",
        rc == 2 and "STALE ANCHOR (BLOCKED)" in err,
    )

    rc, out, err = run_hook(
        p,
        {
            "tool_name": "mcp__binary-ninja-mcp__patch_bytes",
            "tool_input": {"address": "0x4F1E20", "bytes": "9090"},
        },
    )
    ok(
        "hook: HARD exit-2 on binja patch_bytes to OUT offset",
        rc == 2 and "BLOCKED" in err,
    )

    # an unrelated address must NOT trip the gate
    rc, out, err = run_hook(
        p,
        {
            "tool_name": "mcp__cheatengine__write_memory",
            "tool_input": {"address": "0xDEAD00", "value": 0},
        },
    )
    ok(
        "hook: silent on a write to an unrelated (non-OUT) address",
        rc == 0 and out.strip() == "" and err.strip() == "",
    )


def test_hook_frida_and_version() -> None:
    # frida script that WRITES to an OUT offset -> hard
    p = newdb()
    conn = tms.connect()
    chain(conn)
    tms.retract_node(conn, "base")
    script = "var p = ptr('0x4F1E20'); Memory.patchCode(p, 4, function(w){ w.writeByteArray([0x90,0x90]); });"
    rc, out, err = run_hook(
        p,
        {
            "tool_name": "mcp__frida-mcp__execute_in_session",
            "tool_input": {"script": script},
        },
    )
    ok("hook: HARD on frida script writing to OUT offset", rc == 2 and "BLOCKED" in err)

    # frida script that only READS the OUT offset -> soft
    rscript = "var p = ptr('0x4F1E20'); console.log(p.readByteArray(8));"
    rc, out, err = run_hook(
        p,
        {
            "tool_name": "mcp__frida-mcp__execute_in_session",
            "tool_input": {"script": rscript},
        },
    )
    ok(
        "hook: SOFT on frida script only reading OUT offset",
        rc == 0 and "STALE ANCHOR" in out,
    )

    # version-kind soft match
    pv = newdb()
    cv = tms.connect()
    tms.assert_node(cv, "ver", "game version 15.4.1 (EN) offsets valid", "version")
    tms.retract_node(cv, "ver")
    rc, out, err = run_hook(
        pv,
        {
            "tool_name": "mcp__ghidra-mcp__list_methods",
            "tool_input": {"note": "offsets for 15.4.1 build"},
        },
    )
    ok("hook: SOFT match on OUT version token", rc == 0 and "STALE ANCHOR" in out)


def test_hook_failopen_and_throttle() -> None:
    # missing db -> fail-open silent
    missing = os.path.join(tempfile.mkdtemp(prefix="tms-test-"), "nope.db")
    rc, out, err = run_hook(
        missing,
        {
            "tool_name": "mcp__cheatengine__write_memory",
            "tool_input": {"address": "0x4F1E20"},
        },
    )
    ok(
        "hook: fail-open on missing db",
        rc == 0 and out.strip() == "" and err.strip() == "",
    )

    # corrupt db -> fail-open silent
    cp = newdb()
    Path(cp).write_bytes(b"this is definitely not an sqlite database " * 4)
    rc, out, err = run_hook(
        cp,
        {
            "tool_name": "mcp__cheatengine__write_memory",
            "tool_input": {"address": "0x4F1E20"},
        },
    )
    ok(
        "hook: fail-open on corrupt db",
        rc == 0 and out.strip() == "" and err.strip() == "",
    )

    # throttle: identical soft call deduped within window
    p = newdb()
    conn = tms.connect()
    chain(conn)
    tms.retract_node(conn, "base")
    payload = {
        "tool_name": "mcp__ghidra-mcp__decompile_function_by_address",
        "tool_input": {"address": "0x4F1E20"},
    }
    rc1, out1, _ = run_hook(p, payload)
    rc2, out2, _ = run_hook(p, payload)
    ok("throttle: first soft injects", rc1 == 0 and "STALE ANCHOR" in out1)
    ok("throttle: second identical soft suppressed", rc2 == 0 and out2.strip() == "")


def main() -> int:
    for fn in (
        test_cascade,
        test_drift,
        test_guards,
        test_cli,
        test_hook,
        test_hook_frida_and_version,
        test_hook_failopen_and_throttle,
    ):
        fn()
    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): {_FAILS}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
