"""Independent dead-path sweep over the files this lane OWNS and TOUCHED.

Scope: docs/roadmap.md (edited by 84bf3a33) + CLAUDE.md + AGENTS.md + README.md.
Extracts (a) markdown link targets and (b) backticked repo-relative paths, then
resolves each against git ls-files AND the filesystem.

Detector controls (both must hold or the run aborts):
  C1 a fabricated path must read ABSENT
  C2 a known-present path must read PRESENT
  C3 the extractor must find > 0 candidates in each file (an empty extraction
     is a broken regex, not a clean doc)
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path("C:/Users/Prekzursil/source/ast-integrate")

tracked = set(
    subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                   text=True, check=True).stdout.splitlines()
)
tracked_dirs = set()
for f in tracked:
    parts = f.split("/")
    for i in range(1, len(parts)):
        tracked_dirs.add("/".join(parts[:i]))

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
TICK = re.compile(r"`([^`\n]+)`")
PATHISH = re.compile(r"^[A-Za-z0-9_.\-/]+$")


def exists(rel: str) -> bool:
    rel = rel.rstrip("/")
    if rel in tracked or rel in tracked_dirs:
        return True
    return (ROOT / rel).exists()


def candidates(doc: Path):
    text = doc.read_text(encoding="utf-8")
    out = []
    for m in LINK.finditer(text):
        t = m.group(1)
        if t.startswith(("http://", "https://", "#", "mailto:")):
            continue
        out.append(("link", t))
    for m in TICK.finditer(text):
        t = m.group(1)
        if not PATHISH.match(t):
            continue
        if "/" not in t and "." not in t:
            continue
        if t.startswith(("http", "-")) or t.endswith((":",)):
            continue
        out.append(("tick", t))
    return text, out


def resolve(doc: Path, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    if target.startswith(("./", "../")):
        p = (doc.parent / target).resolve()
        try:
            return p.relative_to(ROOT).as_posix()
        except ValueError:
            return target
    return target


# --- controls -------------------------------------------------------------
assert not exists("docs/__definitely_not_here__.md"), "C1 FAILED: fabricated path read PRESENT"
assert exists("docs/roadmap.md"), "C2 FAILED: real path read ABSENT"

total = 0
for name in ("docs/roadmap.md", "CLAUDE.md", "AGENTS.md", "README.md"):
    doc = ROOT / name
    text, cands = candidates(doc)
    if not cands:
        print(f"FAILED C3: extractor found 0 candidates in {name}")
        sys.exit(2)
    dead = []
    seen = set()
    for kind, t in cands:
        rel = resolve(doc, t)
        if rel in seen:
            continue
        seen.add(rel)
        # skip obvious non-paths: bare filenames with a dot but no dir that are
        # tool/version tokens (e.g. 0.15.17) or module dotted names
        if "/" not in rel and not (ROOT / rel).exists() and rel not in tracked:
            if re.match(r"^[0-9.]+$", rel) or rel.count(".") > 1:
                continue
        if not exists(rel):
            dead.append((kind, t, rel))
    total += len(dead)
    print(f"== {name}: {len(seen)} unique path-ish refs, {len(dead)} unresolved")
    for kind, t, rel in dead:
        print(f"   DEAD [{kind}] {t}   -> {rel}")

print(f"TOTAL unresolved = {total}")
