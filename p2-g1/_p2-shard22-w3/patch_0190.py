#!/usr/bin/env python3
"""Patch TST-0190: pin Git Bash binary (bare 'bash' resolves to WSL when spawned)."""
from pathlib import Path

PROBES = Path(__file__).resolve().parents[1] / "command-center" / "p2-wave" / "probes"
LANE = PROBES / "TST-0190" / "msys_lane.py"
P2 = PROBES / "TST-0190" / "probe2_global_suppression.py"

OLD_LANE = (
    "from __future__ import annotations\n"
    "\n"
    "import json\n"
    "import subprocess\n"
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "HERE = Path(__file__).resolve().parent\n"
    "\n"
    "\n"
    "def run_bash(script: str, timeout: int = 60) -> tuple[int, str]:\n"
    "    p = subprocess.run(\n"
    "        [\"bash\", \"-c\", script], capture_output=True, text=True, timeout=timeout\n"
    "    )\n"
    "    return p.returncode, ((p.stdout or \"\") + (p.stderr or \"\")).strip()\n"
)

NEW_LANE = (
    "from __future__ import annotations\n"
    "\n"
    "import json\n"
    "import os\n"
    "import subprocess\n"
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "HERE = Path(__file__).resolve().parent\n"
    "\n"
    "\n"
    "def git_bash() -> str:\n"
    "    \"\"\"Absolute Git Bash binary. The bare name resolves to WSL bash\n"
    "    (System32) when spawned from a Windows process; WSL cannot see /c/...\n"
    "    paths, which degraded every child call to rc=127.\"\"\"\n"
    "    cand = os.environ.get(\"GITBASH\")\n"
    "    if cand and Path(cand).is_file():\n"
    "        return cand\n"
    "    for c in (\n"
    "        \"C:\" + chr(92) + \"Program Files\" + chr(92) + \"Git\" + chr(92) + \"bin\" + chr(92) + \"bash.exe\",\n"
    "        \"C:\" + chr(92) + \"Program Files\" + chr(92) + \"Git\" + chr(92) + \"usr\" + chr(92) + \"bin\" + chr(92) + \"bash.exe\",\n"
    "        \"C:\" + chr(92) + \"Program Files (x86)\" + chr(92) + \"Git\" + chr(92) + \"bin\" + chr(92) + \"bash.exe\",\n"
    "    ):\n"
    "        if Path(c).is_file():\n"
    "            return c\n"
    "    import shutil\n"
    "    w = shutil.which(\"bash\")\n"
    "    if w and \"git\" in w.lower():\n"
    "        return w\n"
    "    raise RuntimeError(\"Git Bash not found; set GITBASH\")\n"
    "\n"
    "\n"
    "def run_bash(script: str, timeout: int = 60) -> tuple[int, str]:\n"
    "    p = subprocess.run(\n"
    "        [git_bash(), \"-c\", script], capture_output=True, text=True, timeout=timeout\n"
    "    )\n"
    "    return p.returncode, ((p.stdout or \"\") + (p.stderr or \"\")).strip()\n"
)

t = LANE.read_text(encoding="utf-8")
assert OLD_LANE in t, "lane header not found"
t = t.replace(OLD_LANE, NEW_LANE)
LANE.write_text(t, encoding="utf-8", newline="\n")
import ast
ast.parse(t)

t2 = P2.read_text(encoding="utf-8")
t2 = t2.replace(
    "    import subprocess\n\n    tmp",
    "    import subprocess\n\n    BASH = ML.git_bash()\n    tmp",
)
t2 = t2.replace(
    '["bash", "-c",',
    '[BASH, "-c",',
)
P2.write_text(t2, encoding="utf-8", newline="\n")
ast.parse(t2)
print("patched TST-0190 lane + probe2: Git Bash pinned")
