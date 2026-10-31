"""BUILD-R1: report and strip CR bytes from a file, in place, preserving content.

windows-shell.md section 3: an agent-written .sh carries CRLF, Git Bash tolerates it and real
WSL bash does NOT ("then\\r" parses as a command). Measure the CR count before and after
rather than assuming the editor did the right thing.
"""

from __future__ import annotations

import sys
from pathlib import Path

for arg in sys.argv[1:]:
    p = Path(arg)
    raw = p.read_bytes()
    before = raw.count(b"\r")
    if before:
        p.write_bytes(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
    after = p.read_bytes().count(b"\r")
    print(f"{p.name}: CR before={before} after={after}")
