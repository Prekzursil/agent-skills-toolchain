import ast
from pathlib import Path

home = Path.home()
mod = home / "p2-g1" / "tools" / "gitcrypt-worktree" / "gitcrypt_worktree.py"
lines = mod.read_text(encoding="utf-8").splitlines(keepends=True)

# locate the replacement window: from "def _git(args, cwd):" to EOF
start = None
for i, ln in enumerate(lines):
    if ln.startswith("def _git(args, cwd):"):
        start = i
        break
if start is None:
    raise SystemExit("marker 'def _git(args, cwd):' not found")

head = lines[:start]                      # everything up to the helpers
helpers = lines[start:start + 18]         # _git + _staged defs (18 lines)
joined = "".join(helpers)
assert "def _staged(repo)" in joined, "helper window wrong: " + joined[:200]

parts_dir = home / "p2-g1" / "_shard11-w3"
tail = "".join(
    (parts_dir / name).read_text(encoding="utf-8")
    for name in ("tail_a.py", "tail_b1.py", "tail_b2.py", "tail_b3.py")
)

new_src = "".join(head) + joined + ("\n" if not joined.endswith("\n\n") else "") + tail
ast.parse(new_src)  # must parse before we touch the file
mod.write_text(new_src, encoding="utf-8", newline="\n")
print("patched OK, total lines:", new_src.count("\n"))
