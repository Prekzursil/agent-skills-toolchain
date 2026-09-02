"""Emit one runnable probe script per OS x shell cell."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CELLS = HERE / "cells"

from axes import all_cells  # noqa: E402
from crlf import write_crlf_fixture  # noqa: E402

PY_TEMPLATE = '''#!/usr/bin/env python3
# ASSERTION: cell {cell_id} ({os_name} x {shell}) ships as a runnable probe.
# Absent platforms report NOT-CHECKED, never PASS.
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cell_runtime import main_cell  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main_cell({cell_id!r}, {os_name!r}, {shell!r}))
'''

POSIX_SH = r"""#!/bin/sh
# ASSERTION: Linux x POSIX sh must print a JSON status and exit 0 on this host.
# This is the live RUN cell on a Linux box whose /bin/sh exists.
echo '{"id":"linux__posix-sh","os":"Linux","shell":"POSIX sh","status":"RUN","reason":"host /bin/sh executed this probe"}'
echo SUCCESS:linux-posix-sh
exit 0
"""


def probe_rel(cell_id: str, suffix: str) -> str:
    return f"command-center/p2-wave/probes/BLD-0007/cells/{cell_id}{suffix}"


def emit_all() -> dict[str, str]:
    CELLS.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    for cid, os_name, shell in all_cells():
        if cid == "windows__git-bash-msys":
            dest = CELLS / "windows__git-bash-msys.sh"
            write_crlf_fixture(dest)
            paths[cid] = probe_rel(cid, ".sh")
            continue
        if cid == "linux__posix-sh":
            dest = CELLS / "linux__posix-sh.sh"
            dest.write_bytes(POSIX_SH.encode("utf-8"))
            dest.chmod(0o755)
            paths[cid] = probe_rel(cid, ".sh")
            continue
        dest = CELLS / f"{cid}.py"
        dest.write_text(
            PY_TEMPLATE.format(cell_id=cid, os_name=os_name, shell=shell),
            encoding="utf-8",
        )
        dest.chmod(0o755)
        paths[cid] = probe_rel(cid, ".py")
    return paths


def execute_probe(rel: str) -> dict:
    path = REPO / rel
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if rel.endswith(".py"):
        cmd = [sys.executable, "-B", str(path)]
    else:
        cmd = ["bash", str(path)] if "git-bash" in rel else ["sh", str(path)]
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        timeout=30,
        env=env,
    )
    return {
        "command": cmd,
        "rc": p.returncode,
        "stdout": (p.stdout or b"").decode("utf-8", "replace")[-2000:],
        "stderr": (p.stderr or b"").decode("utf-8", "replace")[-1000:],
    }
