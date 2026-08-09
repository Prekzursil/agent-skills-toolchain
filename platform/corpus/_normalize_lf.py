"""Normalise every authored .py in this directory to pure LF.

Files written through Python's text mode on Windows pick up CRLF; files written by the agent
Write tool are LF.  The mixture matters because git stores the LF form and CI checks THAT out,
so a formatter verdict measured on CRLF worktree bytes is measured on the wrong bytes
(rules/common/windows-shell.md 8b, ledger-proven: ruff reported "already formatted" locally and
"would reformat" in CI for the same commit).
"""

import pathlib

root = pathlib.Path(__file__).resolve().parent
changed = []
for p in sorted(root.rglob("*.py")):
    if "__pycache__" in p.parts:
        continue
    raw = p.read_bytes()
    crlf = raw.count(b"\r\n")
    if crlf:
        p.write_bytes(raw.replace(b"\r\n", b"\n"))
        changed.append((p.relative_to(root).as_posix(), crlf))

for name, n in changed:
    print(f"  normalised {name}  ({n} CRLF -> LF)")
remaining = {
    p.relative_to(root).as_posix(): p.read_bytes().count(b"\r\n")
    for p in sorted(root.rglob("*.py"))
    if "__pycache__" not in p.parts and p.read_bytes().count(b"\r\n")
}
print(f"files normalised: {len(changed)}")
print(f"files still holding CRLF: {remaining}")
print("SUCCESS:normalize-lf" if not remaining else "FAILED:normalize-lf residual CRLF")
