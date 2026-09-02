#!/usr/bin/env python3
"""Run one probe helper through g1_python and print rc + tail."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
wrapper = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
script = REPO / sys.argv[1]
env = os.environ.copy()
env["PYTHONDONTWRITEBYTECODE"] = "1"
env["AST_INTEGRATE_ROOT"] = str(REPO)
hook_dir = str(REPO / "command-center" / "p2-wave" / "seed-stage")
env["PYTHONPATH"] = os.pathsep.join(
    [
        hook_dir,
        str(REPO),
        str(REPO / "tools"),
        str(REPO / "tools" / "measure-guard"),
        str(REPO / "platform" / "lib"),
        str(REPO / "tools" / "agentspec"),
        env.get("PYTHONPATH", ""),
    ]
)
p = subprocess.run(
    [sys.executable, "-B", str(wrapper), str(script), *sys.argv[2:]],
    cwd=str(REPO),
    capture_output=True,
    text=True,
    timeout=120,
    env=env,
)
text = ((p.stdout or "") + (p.stderr or "")).strip()
print(f"rc={p.returncode}")
print(text[-4000:])
raise SystemExit(p.returncode)
