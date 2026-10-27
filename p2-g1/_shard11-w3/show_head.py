import sys
from pathlib import Path
p = Path.home() / "p2-g1" / "tools" / "gitcrypt-worktree" / "gitcrypt_worktree.py"
lines = p.read_text(encoding="utf-8").splitlines()
print(f"total lines: {len(lines)}")
for i, ln in enumerate(lines[:60], 1):
    print(f"{i}: {ln}")
