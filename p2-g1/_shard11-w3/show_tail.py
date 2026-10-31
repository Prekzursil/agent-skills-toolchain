from pathlib import Path
p = Path.home() / "p2-g1" / "tools" / "gitcrypt-worktree" / "gitcrypt_worktree.py"
lines = p.read_text(encoding="utf-8").splitlines()
for i, ln in enumerate(lines[1424:1516], 1425):
    print(f"{i}: {ln}")
