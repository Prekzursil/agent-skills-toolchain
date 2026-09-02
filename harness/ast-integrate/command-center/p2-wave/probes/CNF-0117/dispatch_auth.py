#!/usr/bin/env python3
"""Execute the live dispatch_cursor.py auth-gate block without starting the supervisor.

The four-line CURSOR_API_KEY check is sliced from the live source and exec'd in
a subprocess so AUTH-FAIL is written to a temp path, never /opt/p2. The key
value is never printed — the child only tests presence via env.get.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import inventory as I

_CHILD = r'''
import os, sys, textwrap
from pathlib import Path
src = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
start = next(i for i, l in enumerate(src) if 'if not os.environ.get("CURSOR_API_KEY"):' in l)
block = textwrap.dedent("\n".join(src[start:start + 4]))
auth_fail = Path(sys.argv[2])
printed = []
ns = {
    "os": os,
    "Path": Path,
    "log": lambda msg: printed.append(str(msg)),
    "AUTH_FAIL": auth_fail,
    "utc_now": lambda: "1970-01-01T00:00:00Z",
}
exec("def _gate():\n" + textwrap.indent(block, "    ") + "\n", ns, ns)
code = ns["_gate"]()
msg = "\n".join(printed)
if auth_fail.is_file():
    msg = (msg + "\n" + auth_fail.read_text(encoding="utf-8")).strip()
sys.stdout.write(msg + "\n")
raise SystemExit(0 if code is None else int(code))
'''


def source_block() -> tuple[int, str]:
    lines = I.DISPATCH.read_text(encoding="utf-8").splitlines()
    start = None
    for i, line in enumerate(lines):
        if 'if not os.environ.get("CURSOR_API_KEY"):' in line:
            start = i
            break
    if start is None:
        raise RuntimeError("dispatch_cursor.py auth gate not found")
    block_lines = lines[start : start + 4]
    if len(block_lines) < 4:
        raise RuntimeError("dispatch_cursor.py auth gate truncated")
    joined = "\n".join(block_lines)
    if "FAILED:no CURSOR_API_KEY" not in joined:
        raise RuntimeError("dispatch_cursor.py auth gate does not name CURSOR_API_KEY")
    if "return 2" not in block_lines[-1]:
        raise RuntimeError("dispatch_cursor.py auth gate does not return 2")
    return start + 1, joined


def run_gate(*, grant: bool) -> tuple[int, str, int]:
    """Return (exit_code, message, source_line). Never prints the key value."""
    line_no, _block = source_block()
    env = os.environ.copy()
    if grant:
        if not env.get("CURSOR_API_KEY"):
            env["CURSOR_API_KEY"] = "cnf-0117-presence-stub-not-a-live-key"
    else:
        env.pop("CURSOR_API_KEY", None)
        env.pop("CURSOR_API_TOKEN", None)
    with tempfile.TemporaryDirectory(prefix="cnf0117-auth-") as tmp:
        auth_fail = Path(tmp) / "AUTH-FAIL"
        script = Path(tmp) / "gate_child.py"
        script.write_text(_CHILD.lstrip() + "\n", encoding="utf-8")
        p = subprocess.run(
            [sys.executable, "-B", str(script), str(I.DISPATCH), str(auth_fail)],
            cwd=str(I.REPO),
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, f"source_line={line_no}\n{text}", line_no
