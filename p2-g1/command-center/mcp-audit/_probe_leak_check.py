"""Leak check over every artifact this lane wrote. Classify by STRUCTURE only --
never print a value. Includes a both-states control: a synthetic known-secret must
FIRE, and a synthetic clean string must NOT.
"""

import pathlib
import re

BASE = pathlib.Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/mcp-audit"
)
DOC = pathlib.Path(r"C:/Users/Prekzursil/source/ast-integrate/docs/mcp-audit")

PATS = {
    "openai-sk": re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    "github-pat": re.compile(
        r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
    ),
    "xai": re.compile(r"xai-[A-Za-z0-9]{20,}"),
    "google": re.compile(r"AIza[A-Za-z0-9_\-]{30,}"),
    "aws": re.compile(r"AKIA[0-9A-Z]{16}"),
    "slack": re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
    "jwt": re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\."),
    "bearer": re.compile(r"[Bb]earer\s+[A-Za-z0-9_\-.=]{20,}"),
    "hf": re.compile(r"hf_[A-Za-z0-9]{20,}"),
    "pem": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "long-opaque-assign": re.compile(
        r"(?i)(token|secret|api[_-]?key|password)\W{1,3}[A-Za-z0-9_\-]{24,}"
    ),
}

# ---- BOTH-STATES CONTROL ---------------------------------------------------
KNOWN_BAD = "sk-" + "A" * 32 + " ghp_" + "B" * 36 + " AIza" + "C" * 35
KNOWN_GOOD = "SONARQUBE_TOKEN present  EXA_API_KEY absent  FIGMA_API_KEY reference"
fired = [n for n, p in PATS.items() if p.search(KNOWN_BAD)]
clean = [n for n, p in PATS.items() if p.search(KNOWN_GOOD)]
print("=== DETECTOR CONTROL (both states) ===")
print(f"  known-BAD fixture fires : {sorted(fired)}   (must be non-empty)")
print(f"  known-GOOD fixture fires: {sorted(clean)}   (must be empty)")
ok = bool(fired) and not clean
print(f"  control {'PASSED' if ok else 'FAILED -- results below are meaningless'}")
print()

files = sorted(list(BASE.glob("*")) + list(DOC.glob("*")))
total_hits = 0
print("=== SCAN ===")
for f in files:
    if f.is_dir():
        continue
    try:
        t = f.read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    hits = {}
    for n, p in PATS.items():
        c = len(p.findall(t))
        if c:
            hits[n] = c
    total_hits += sum(hits.values())
    flag = "LEAK?" if hits else "clean"
    print(
        f"  {flag:6} {f.stat().st_size:>9,} B  {f.name}"
        + (f"   {hits}" if hits else "")
    )

print()
print(f"TOTAL structural credential matches across lane artifacts: {total_hits}")
print(
    "SUCCESS:leak-check" if (ok and total_hits == 0) else "REVIEW-REQUIRED:leak-check"
)
