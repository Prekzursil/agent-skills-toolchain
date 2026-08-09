"""Extract an LF-only line range from the spec (bare-CR safe)."""

import sys
from pathlib import Path

p = Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md")
data = p.read_bytes()
lines = data.split(b"\n")
lo = int(sys.argv[1])
hi = int(sys.argv[2])
for i in range(lo, hi + 1):
    if 1 <= i <= len(lines):
        txt = lines[i - 1].decode("utf-8", "replace")
        sys.stdout.write(f"{i}\t{txt}\n")
