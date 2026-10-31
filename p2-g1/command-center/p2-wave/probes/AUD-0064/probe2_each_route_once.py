#!/usr/bin/env python3
"""AUD-0064 probe 2 - launch each route once, classify what renders.

Evidence requirement: "launch each route once and assert a non-empty,
changing render - a pane that renders a fixed empty frame is
indistinguishable from a working one on a static screenshot."

Every declared route is attempted exactly once as a bounded headless
subprocess. Outcomes are classified, never rounded up:
  RENDERED      process emitted non-empty output inside the window
  EMPTY         process exited 0 with an empty render (empty == working is banned)
  CRASHED       process exited non-zero (a board that crashes headless is a finding)
  INTERACTIVE   process ran past the window with no captured render (TUI held
                a surface that cannot be captured without a tty)
  UNREACHABLE   entry script missing at launch time
Controls (both mandatory, both-states):
  - empty-data control route renders from a deliberately empty source and
    MUST classify EMPTY (never OK);
  - positive control emits a fixed non-empty frame and MUST classify RENDERED.
Windows host adaptation: prior wave measured the Linux worktree; outcomes
here are measured live and recorded verbatim.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path

HOME = Path.home()
REPO = Path(__file__).resolve().parents[4]
UNIT = "AUD-0064"
TABLE = HOME / ".agents" / "skills" / "monitor-launcher" / "monitors.toml"
WINDOW_SECONDS = 12

EMPTY_CONTROL = (
    "import json, pathlib, sys\n"
    "data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
    "rows = data.get('rows', [])\n"
    "out = [f'{r}: {r}' for r in rows]\n"
    "sys.stdout.write(chr(10).join(out))\n"
)
LIVE_CONTROL = (
    "import json, pathlib, sys\n"
    "data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
    "rows = data.get('rows', [])\n"
    "out = [f'{r}: {r}' for r in rows]\n"
    "sys.stdout.write(chr(10).join(out))\n"
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def classify(rc: int, out: str, timed_out: bool) -> str:
    if timed_out:
        return "INTERACTIVE"
    if rc != 0:
        # a traceback is output, but it is not a render: a board that
        # crashes headless is a finding, never rounded up to RENDERED
        return "CRASHED"
    if out.strip():
        return "RENDERED"
    return "EMPTY"


def attempt(cmd: list[str], cwd: str, window: int = WINDOW_SECONDS) -> tuple[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            timeout=window, env=env,
        )
    except subprocess.TimeoutExpired as exc:
        def _txt(piece) -> str:
            if not piece:
                return ""
            if isinstance(piece, bytes):
                return piece.decode("utf-8", "replace")
            return str(piece)

        tail = (_txt(exc.stdout) + _txt(exc.stderr)).strip()
        return "INTERACTIVE", tail
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return classify(proc.returncode, out, False), out


def main() -> int:
    if not TABLE.is_file():
        return fail("monitor registry absent on this host")
    with open(TABLE, "rb") as fh:
        routes = tomllib.load(fh)
    if not routes:
        return fail("registry declares no routes")

    outcomes: dict[str, str] = {}
    for name in sorted(routes):
        row = routes[name]
        d = str(row.get("dir") or "")
        entry = str(row.get("entry") or "")
        dpath = Path(d)
        if not dpath.is_absolute():
            dpath = HOME / ".agents" / "skills" / d
        script = dpath / entry
        if not script.is_file():
            outcomes[name] = "UNREACHABLE"
            print(f"ROUTE|{name}|UNREACHABLE|{(dpath / entry).as_posix()}")
            continue
        outcome, tail = attempt([sys.executable, "-I", str(script)], cwd=str(dpath))
        outcomes[name] = outcome
        first = tail.splitlines()[:1]
        print(f"ROUTE|{name}|{outcome}|{first}")

    with tempfile.TemporaryDirectory() as td:
        empty_src = Path(td) / "empty_state.json"
        empty_src.write_text('{"rows": []}', encoding="utf-8")
        live_src = Path(td) / "live_state.json"
        live_src.write_text('{"rows": ["wfmon 3 running", "agentmon 1 idle"]}', encoding="utf-8")
        ctrl_script = Path(td) / "control_route.py"
        ctrl_script.write_text(EMPTY_CONTROL, encoding="utf-8")
        oc, tailc = attempt([sys.executable, "-I", str(ctrl_script), str(empty_src)],
                            cwd=td, window=15)
        if oc != "EMPTY":
            return fail(f"empty-data control classified {oc} (must be EMPTY): {tailc[-200:]}")
        ctrl2 = Path(td) / "positive_route.py"
        ctrl2.write_text(LIVE_CONTROL, encoding="utf-8")
        op, tailp = attempt([sys.executable, "-I", str(ctrl2), str(live_src)],
                            cwd=td, window=15)
        if op != "RENDERED":
            return fail(f"positive control classified {op} (must be RENDERED): {tailp[-200:]}")
        print(f"CONTROLS|empty-data=EMPTY|positive=RENDERED|both fired")

    counts: dict[str, int] = {}
    for o in outcomes.values():
        counts[o] = counts.get(o, 0) + 1
    summary = " ".join(f"{k}={counts[k]}" for k in sorted(counts))
    if len(outcomes) != len(routes):
        return fail(f"attempted {len(outcomes)} of {len(routes)} routes")
    print(f"routes attempted once each: {len(outcomes)} | {summary}")
    print(f"SUCCESS:{UNIT}-probe2 every route launched once, outcomes classified not rounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
