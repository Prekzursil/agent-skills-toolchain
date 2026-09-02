"""Shared IMP-0133 probe helpers. Fixture token is fake; never a live secret."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOKEN = "ghp_IMP0133FixtureLeakTok000000000000001"
VIOLATION = "param-credential-literal"

sys.path.insert(0, str(REPO / "tools" / "agentspec"))


def independent_grep_hits(path: Path, token: str) -> int:
    """Count via /usr/bin/grep -F, not the Python detector under test."""
    grep = Path("/usr/bin/grep")
    if not grep.is_file():
        grep = Path("/bin/grep")
    proc = subprocess.run(
        [str(grep), "-o", "-F", token, str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 1:
        return 0
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or f"grep exit {proc.returncode}")
    return sum(1 for line in proc.stdout.splitlines() if line == token)
