"""B4: two-directional unique-line report for the 6 ui-audit entry points.

DIVERGED means BOTH sides hold unique lines, so a blind copy in either direction destroys
content.  This prints each side's unique lines so a union merge can be authored by reading,
not guessed.
"""
import difflib
from pathlib import Path

DAILY = Path(r"C:/Users/Prekzursil/.claude/skills.daily/ui-audit")
REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate/.agents/skills/ui-audit")

TARGETS = ["capture.mjs", "run_audit.mjs", "layout_lint.mjs", "visual_diff.mjs",
           "axe_scan.mjs", "critique.mjs"]


def lines(p):
    return p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").splitlines()


for name in TARGETS:
    a, b = lines(DAILY / name), lines(REPO / name)
    sm = difflib.SequenceMatcher(None, b, a, autojunk=False)
    left_only, right_only = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            right_only += [(i1 + k + 1, b[i1 + k]) for k in range(i2 - i1)]
        if tag in ("replace", "insert"):
            left_only += [(j1 + k + 1, a[j1 + k]) for k in range(j2 - j1)]
    print(f"===== {name}: live={len(a)} repo={len(b)} "
          f"live-unique={len(left_only)} repo-unique={len(right_only)}")
    print("  -- REPO-ONLY lines (would be LOST if live overwrote repo):")
    for n, ln in right_only:
        print(f"     repo:{n}: {ln[:160]}")
    print("  -- LIVE-ONLY lines (the fix; would be LOST if repo overwrote live):")
    for n, ln in left_only[:40]:
        print(f"     live:{n}: {ln[:160]}")
    if len(left_only) > 40:
        print(f"     ... +{len(left_only)-40} more live-only lines")
    print()
