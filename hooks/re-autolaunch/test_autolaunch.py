#!/usr/bin/env python3
"""Tests for re-autolaunch. Runs WITHOUT pytest: `python test_autolaunch.py`.

SAFETY: NEVER launches IDA/Ghidra/BN (the user just hit an OOM). Every run()
path that would spawn is exercised with autolaunch.spawn_launch / brief_wait
monkeypatched to in-memory fakes, so no heavy process is ever started. "up" cases
use a throwaway local TCP listener; "down" cases use a closed free port.
"""
import io
import json
import socket
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autolaunch  # noqa: E402

_FAILS = []


def check(name, cond):
    print(("PASS" if cond else "FAIL") + f": {name}")
    if not cond:
        _FAILS.append(name)


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def listener():
    # backlog must be > the number of unaccepted probe connects we make to it,
    # else a later TCP connect to the same listener is refused (the only reason
    # we never accept() is that probe_ports just needs the handshake to complete).
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(16)
    return s, s.getsockname()[1]


def _spec(key, cfg):
    return cfg["backends"][key]


def main():
    cfg = autolaunch.load_config()

    # ---- 1. backend_for_tool parsing --------------------------------------
    k, s = autolaunch.backend_for_tool("mcp__ghidra-mcp__list_methods", cfg)
    check("maps ghidra-mcp tool", k == "ghidra-mcp" and s and s["tool"] == "ghidra")
    k, s = autolaunch.backend_for_tool("mcp__ida-pro-mcp__list_instances", cfg)
    check("maps ida-pro-mcp tool", k == "ida-pro-mcp" and s and s["tool"] == "ida")
    k, s = autolaunch.backend_for_tool("mcp__binary-ninja-mcp__get_binary_status", cfg)
    check("maps binary-ninja-mcp tool", k == "binary-ninja-mcp" and s and s["tool"] == "bn")
    k, s = autolaunch.backend_for_tool("mcp__frida-mcp__attach", cfg)
    check("non-RE mcp tool -> no backend", k is None and s is None)
    k, s = autolaunch.backend_for_tool("Bash", cfg)
    check("non-mcp tool -> no backend", k is None and s is None)
    k, s = autolaunch.backend_for_tool("", cfg)
    check("empty tool -> no backend", k is None and s is None)

    # ---- 2. probe_ports up/down -------------------------------------------
    lst, p_up = listener()
    try:
        check("listening port probed up", autolaunch.probe_ports([p_up], 1.0) == [p_up])
        p_down = free_port()
        check("closed port probed down", autolaunch.probe_ports([p_down], 0.5) == [])
        check("mixed ports return only up ones",
              autolaunch.probe_ports([p_down, p_up], 1.0) == [p_up])
    finally:
        lst.close()

    # ---- 3. prefer_port / wait_port ---------------------------------------
    ida = _spec("ida-pro-mcp", cfg)
    check("prefer_port picks GUI 13337 when up", autolaunch.prefer_port(ida, [8745, 13337]) == 13337)
    check("prefer_port falls back to first up", autolaunch.prefer_port(ida, [8745]) == 8745)
    check("ida wait_port = headless 8745", autolaunch.wait_port(ida) == 8745)
    check("ghidra wait_port = 8089", autolaunch.wait_port(_spec("ghidra-mcp", cfg)) == 8089)

    # ---- 4. decide() all branches -----------------------------------------
    ghi = _spec("ghidra-mcp", cfg)
    bn = _spec("binary-ninja-mcp", cfg)
    d = autolaunch.decide("ghidra-mcp", ghi, [8089], started_recently=False,
                          free_mb=8000, min_free_mb=2048)
    check("decide up -> noop", d.action == "noop" and d.up_port == 8089)
    d = autolaunch.decide("ghidra-mcp", ghi, [], started_recently=False,
                          free_mb=8000, min_free_mb=2048)
    check("decide down+ram+fresh -> launch", d.action == "launch" and d.wait_port == 8089)
    d = autolaunch.decide("ghidra-mcp", ghi, [], started_recently=True,
                          free_mb=8000, min_free_mb=2048)
    check("decide down+recent-launch -> wait", d.action == "wait")
    d = autolaunch.decide("ghidra-mcp", ghi, [], started_recently=False,
                          free_mb=500, min_free_mb=2048)
    check("decide down+low-ram -> lowram", d.action == "lowram")
    d = autolaunch.decide("binary-ninja-mcp", bn, [], started_recently=False,
                          free_mb=8000, min_free_mb=2048)
    check("decide bn down -> manual", d.action == "manual")
    d = autolaunch.decide("ida-pro-mcp", ida, [13337], started_recently=False,
                          free_mb=8000, min_free_mb=2048)
    check("decide GUI-IDA up -> noop (never duplicate)", d.action == "noop" and d.up_port == 13337)
    # low-ram guard must NOT fire when free_mb is unknown (None) -> fail-open to launch
    d = autolaunch.decide("ghidra-mcp", ghi, [], started_recently=False,
                          free_mb=None, min_free_mb=2048)
    check("decide unknown-ram -> launch (fail-open)", d.action == "launch")

    # ---- 5. build_launch_cmd tokens ---------------------------------------
    cfg2 = {"launcher_python": "PYEXE", "re_launch": "RL"}
    check("launch cmd ghidra (no binary)",
          autolaunch.build_launch_cmd(cfg2, {"tool": "ghidra"}) == ["PYEXE", "RL", "ghidra"])
    check("launch cmd ida (with binary)",
          autolaunch.build_launch_cmd(cfg2, {"tool": "ida", "binary": "B.so"})
          == ["PYEXE", "RL", "ida", "B.so"])
    cmd = autolaunch.build_launch_cmd({"re_launch": "RL"}, {"tool": "ghidra"})
    check("launch cmd defaults python to sys.executable", cmd[0] == sys.executable)

    # ---- 6. run() orchestration with fakes (NO real spawn) ----------------
    orig_state, orig_cfg = autolaunch.STATE_DIR, autolaunch.CONFIG_PATH
    orig_spawn, orig_wait = autolaunch.spawn_launch, autolaunch.brief_wait
    tmp = Path(tempfile.mkdtemp(prefix="re-autolaunch-test-"))
    autolaunch.STATE_DIR = tmp

    calls = {"spawn": 0}

    def fake_spawn(cfg, spec):
        calls["spawn"] += 1
        return True

    def write_cfg(**over):
        c = {
            "re_launch": str(tmp / "re_launch.py"),  # path won't be spawned (fake)
            "launcher_python": "PYEXE",
            "tcp_timeout": 0.4, "brief_wait_seconds": 0.3, "brief_poll_interval": 0.1,
            "up_recheck_seconds": 30, "launch_throttle_seconds": 90,
            "min_free_ram_mb": 0, "deny_while_starting": True, "deny_when_unlaunchable": True,
            "backends": {},
        }
        c.update(over)
        p = tmp / "cfg.json"
        p.write_text(json.dumps(c), encoding="utf-8")
        autolaunch.CONFIG_PATH = p
        return c

    def run_capture(mode, data):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = autolaunch.run(mode, data)
        out = buf.getvalue().strip()
        return rc, (json.loads(out) if out else {})

    try:
        autolaunch.spawn_launch = fake_spawn

        # 6a. UP backend -> silent fast no-op.
        lst, p_up = listener()
        try:
            write_cfg(backends={"x-mcp": {"tool": "x", "launchable": True,
                                          "ports": [p_up], "headless_port": p_up}})
            calls["spawn"] = 0
            rc, out = run_capture("pretool", {"tool_name": "mcp__x-mcp__do", "session_id": "up1"})
            check("run up-backend -> silent no-op", rc == 0 and out == {} and calls["spawn"] == 0)
        finally:
            lst.close()

        # 6b. DOWN + launch + port comes up in brief wait -> allow (additionalContext).
        p_down = free_port()
        write_cfg(backends={"x-mcp": {"tool": "x", "launchable": True,
                                      "ports": [p_down], "headless_port": p_down,
                                      "binary": None}})
        autolaunch.brief_wait = lambda *a, **k: True
        calls["spawn"] = 0
        rc, out = run_capture("pretool", {"tool_name": "mcp__x-mcp__do", "session_id": "dn1"})
        ctx = out.get("hookSpecificOutput", {})
        check("run down+came-up -> spawn + allow/inject (no deny)",
              calls["spawn"] == 1 and ctx.get("additionalContext")
              and "permissionDecision" not in ctx)

        # 6c. DOWN + launch + still starting -> deny (deny_while_starting=True).
        autolaunch.brief_wait = lambda *a, **k: False
        calls["spawn"] = 0
        rc, out = run_capture("pretool", {"tool_name": "mcp__x-mcp__do", "session_id": "dn2"})
        ctx = out.get("hookSpecificOutput", {})
        check("run down+still-starting -> spawn + DENY with retry msg",
              calls["spawn"] == 1 and ctx.get("permissionDecision") == "deny"
              and "retry" in ctx.get("permissionDecisionReason", "").lower())
        st = autolaunch.load_state("dn2")
        check("launch recorded last_launch + starting state",
              st.get("x-mcp", {}).get("last_launch", 0) > 0
              and st["x-mcp"]["last_state"] == "starting")

        # 6d. deny_while_starting=False -> inject only (never deny).
        write_cfg(deny_while_starting=False,
                  backends={"x-mcp": {"tool": "x", "launchable": True,
                                      "ports": [free_port()], "headless_port": free_port()}})
        autolaunch.brief_wait = lambda *a, **k: False
        rc, out = run_capture("pretool", {"tool_name": "mcp__x-mcp__do", "session_id": "dn3"})
        ctx = out.get("hookSpecificOutput", {})
        check("deny_while_starting=False -> inject not deny",
              ctx.get("additionalContext") and "permissionDecision" not in ctx)

        # 6e. BN (not launchable) down -> deny, NO spawn.
        write_cfg(backends={"binary-ninja-mcp": {"tool": "bn", "launchable": False,
                                                 "ports": [free_port()],
                                                 "manual_hint": "open BN GUI on :9009"}})
        calls["spawn"] = 0
        rc, out = run_capture("pretool", {"tool_name": "mcp__binary-ninja-mcp__x", "session_id": "bn1"})
        ctx = out.get("hookSpecificOutput", {})
        check("run BN down -> deny + NO spawn",
              calls["spawn"] == 0 and ctx.get("permissionDecision") == "deny"
              and "bn gui" in ctx.get("permissionDecisionReason", "").lower())

        # 6f. low-RAM guard -> NO spawn, deny with OOM message.
        write_cfg(min_free_ram_mb=10**9,
                  backends={"x-mcp": {"tool": "x", "launchable": True,
                                      "ports": [free_port()], "headless_port": free_port()}})
        calls["spawn"] = 0
        rc, out = run_capture("pretool", {"tool_name": "mcp__x-mcp__do", "session_id": "lr1"})
        ctx = out.get("hookSpecificOutput", {})
        check("low-RAM -> NO spawn + OOM-avoid deny",
              calls["spawn"] == 0 and ctx.get("permissionDecision") == "deny"
              and "oom" in ctx.get("permissionDecisionReason", "").lower())

        # 6g. up-recheck fast-path: recent 'up' -> skip probe entirely (silent).
        write_cfg(backends={"x-mcp": {"tool": "x", "launchable": True, "ports": [1], "headless_port": 1}})
        autolaunch.save_state("fp1", {"x-mcp": {"last_state": "up", "last_check": time.time()}})
        calls["spawn"] = 0
        rc, out = run_capture("pretool", {"tool_name": "mcp__x-mcp__do", "session_id": "fp1"})
        check("recent-up fast-path -> silent, no spawn", rc == 0 and out == {} and calls["spawn"] == 0)

        # 6h. wait-branch: recent launch, port still down -> deny retry (no new spawn).
        write_cfg(backends={"x-mcp": {"tool": "x", "launchable": True,
                                      "ports": [free_port()], "headless_port": free_port()}})
        autolaunch.save_state("w1", {"x-mcp": {"last_launch": time.time(), "last_state": "starting"}})
        calls["spawn"] = 0
        rc, out = run_capture("pretool", {"tool_name": "mcp__x-mcp__do", "session_id": "w1"})
        ctx = out.get("hookSpecificOutput", {})
        check("wait-branch (recent launch, still down) -> deny, no re-spawn",
              calls["spawn"] == 0 and ctx.get("permissionDecision") == "deny")

    finally:
        autolaunch.STATE_DIR, autolaunch.CONFIG_PATH = orig_state, orig_cfg
        autolaunch.spawn_launch, autolaunch.brief_wait = orig_spawn, orig_wait

    # ---- 7. FAIL-OPEN -----------------------------------------------------
    # 7a. malformed stdin -> main() returns 0, emits nothing.
    orig_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO("this is { not json")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = autolaunch.main(["pretool"])
        check("malformed stdin -> fail-open exit 0, silent", rc == 0 and buf.getvalue().strip() == "")
    finally:
        sys.stdin = orig_stdin

    # 7b. an internal exception (decide blows up) -> main still exits 0.
    orig_decide = autolaunch.decide
    orig_cfg2 = autolaunch.CONFIG_PATH
    try:
        def boom(*a, **k):
            raise RuntimeError("simulated internal failure")
        autolaunch.decide = boom
        # point config at the real backends so backend_for_tool resolves and run() proceeds to decide()
        autolaunch.CONFIG_PATH = orig_cfg
        sys.stdin = io.StringIO(json.dumps({"tool_name": "mcp__ghidra-mcp__x", "session_id": "boom"}))
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = autolaunch.main(["pretool"])
        check("internal exception -> fail-open exit 0", rc == 0)
    finally:
        autolaunch.decide = orig_decide
        autolaunch.CONFIG_PATH = orig_cfg2
        sys.stdin = orig_stdin

    # 7c. disabled via env -> immediate 0.
    import os
    os.environ["RE_AUTOLAUNCH"] = "off"
    try:
        check("RE_AUTOLAUNCH=off -> disabled exit 0", autolaunch.main(["pretool"]) == 0)
    finally:
        os.environ.pop("RE_AUTOLAUNCH", None)

    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): {_FAILS}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
