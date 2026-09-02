"""B3: SETTLE the ui-audit "silent green no-op" claim by reading the main-guard in both trees.

The claim under test (prior-research lens): 6 ui-audit .mjs entry points carry a main-module
guard fix that exists ONLY in the live curated tree; the repo copies are broken so a repo->live
redeploy would turn ui-audit into a green no-op (main() never runs, exit 0, no artifacts).

DETECTOR CONTROL (both-states): the same extractor is run over BOTH trees.  If it reported the
same string for both, it would be measuring nothing -- so the output below must DIFFER for the
claim to be CONFIRMED, and must MATCH for it to be REFUTED.  Either way the instrument spoke.
"""

import re
from pathlib import Path

DAILY = Path(r"C:/Users/Prekzursil/.claude/skills.daily/ui-audit")
REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate/.agents/skills/ui-audit")
VAULT = Path(r"C:/Users/Prekzursil/.agents/skills/ui-audit")

TARGETS = [
    "capture.mjs",
    "run_audit.mjs",
    "layout_lint.mjs",
    "visual_diff.mjs",
    "axe_scan.mjs",
    "critique.mjs",
]

# any line that decides "am I the entry module?"
GUARD = re.compile(
    r"^.*(import\.meta\.url|process\.argv\[1\]|pathToFileURL|realpathSync|fileURLToPath).*$",
    re.M,
)


def guard_lines(p: Path):
    if not p.exists():
        return ["<MISSING>"]
    txt = p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    hits = [m.group(0).strip() for m in GUARD.finditer(txt)]
    return [h for h in hits if "import.meta.url" in h or "argv[1]" in h] or [
        "<no guard line>"
    ]


for name in TARGETS:
    d = guard_lines(DAILY / name)
    r = guard_lines(REPO / name)
    v = guard_lines(VAULT / name)
    same = d == r
    print(f"--- {name}   live==repo? {same}")
    for tag, lines in (("LIVE", d), ("REPO", r), ("VAULT", v)):
        for line in lines:
            print(f"    {tag:6} {line[:150]}")
