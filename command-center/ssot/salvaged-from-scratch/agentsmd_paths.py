"""Independent AGENTS.md path-claim sweep with a BOTH-STATES detector control.

The audit said "every AGENTS.md one I opened is use-vs-mention" -- a partial check
stated as a full conclusion. Resolve ALL of them and print each unresolved one with
its full line so the mention/dependency call is made on the FIELD, not the document.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path("C:/Users/Prekzursil/source/ast-integrate")
AGENTS = ROOT / "AGENTS.md"

tracked = set(subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.splitlines())
tracked_dirs = set()
for t in tracked:
    parts = t.split("/")
    for i in range(1, len(parts)):
        tracked_dirs.add("/".join(parts[:i]))

lines = AGENTS.read_text(encoding="utf-8").splitlines()

# backtick-quoted tokens that look like repo paths
PATHISH = re.compile(r"`([A-Za-z0-9_./-]+(?:/[A-Za-z0-9_./-]*)*)`")


def resolves(tok: str) -> bool:
    t = tok.rstrip("/")
    if not t:
        return False
    return (t in tracked or t in tracked_dirs
            or (ROOT / t).exists())


# ---- DETECTOR CONTROL (both states) --------------------------------------
ctl_real = "AGENTS.md"
ctl_fake = "docs/__definitely_not_here__/NOPE.md"
assert resolves(ctl_real), "CONTROL FAILED: a real path read as unresolved"
assert not resolves(ctl_fake), "CONTROL FAILED: a fabricated path read as resolved"
assert resolves("tools/lib"), "CONTROL FAILED: a real DIRECTORY read as unresolved"
print(f"[CONTROL] real={resolves(ctl_real)} fake={resolves(ctl_fake)} dir={resolves('tools/lib')} -> OK")

seen, unresolved = set(), []
for n, line in enumerate(lines, 1):
    for tok in PATHISH.findall(line):
        if "/" not in tok and not tok.endswith(".md"):
            continue          # bare words like `main`, `pytest` are not path claims
        if tok in seen:
            continue
        seen.add(tok)
        if not resolves(tok):
            unresolved.append((n, tok, line.strip()))

print(f"[SWEEP] distinct path-ish tokens = {len(seen)} · unresolved = {len(unresolved)}")
for n, tok, line in unresolved:
    print(f"\n  AGENTS.md:{n}  TOKEN={tok!r}")
    print(f"     LINE: {line[:300]}")

print(f"\nSUCCESS:advver-agentsmd-paths total={len(seen)} unresolved={len(unresolved)}")
sys.exit(0)
