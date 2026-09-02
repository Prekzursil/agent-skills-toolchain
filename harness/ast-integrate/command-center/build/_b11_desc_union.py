"""B11: adopt the LIVE description for the two lesson skills, so a body edit never shortens one.

MEASURED: after the lesson commit, `two-tier-verify` and `rubric-verifier` are DIVERGED against
the live tree for ONE reason only -- the live `description:` line is the LONGER variant and the
repo holds a shortened one (the never-deployed description cap). live-unique lines: 1 and 2
respectively, and both are the description (plus a blank).

That matters because of the mechanic that governs this whole fleet: the description is
ALWAYS-LOADED and is the entire lexical recall surface, while the body loads only on invocation.
Deploying the repo copy would therefore have silently traded trigger vocabulary for index budget
as a SIDE EFFECT of a body edit -- a real trade, but one that belongs to a deliberate budget
decision with an adversarial review, not to a docs commit.

So the union is taken in the safe direction: keep the LIVE description, keep the NEW body. The
repo copy then strictly contains the live copy and becomes deployable without shortening anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
LIVE = Path(r"C:/Users/Prekzursil/.claude/skills.daily")
RELS = ["two-tier-verify/SKILL.md", "rubric-verifier/SKILL.md"]


def desc_line(lines: list[str]) -> int:
    for i, ln in enumerate(lines[:40]):
        if ln.startswith("description:"):
            return i
    raise SystemExit("no description: line found")


def read(p: Path) -> list[str]:
    return p.read_bytes().replace(b"\r\n", b"\n").decode("utf-8").split("\n")


apply = "--apply" in sys.argv
for rel in RELS:
    live = read(LIVE / rel)
    li = desc_line(live)
    live_desc = live[li]
    for root in (".agents/skills", "skills"):
        dst = REPO / root / rel
        cur = read(dst)
        ci = desc_line(cur)
        if cur[ci] == live_desc:
            print(f"  already-matches {root}/{rel}")
            continue
        print(
            f"  {'ADOPT' if apply else 'WOULD-ADOPT'} live description in {root}/{rel}"
        )
        print(
            f"      repo {len(cur[ci])} chars -> live {len(live_desc)} chars "
            f"({len(live_desc) - len(cur[ci]):+d})"
        )
        if apply:
            cur[ci] = live_desc
            dst.write_bytes("\n".join(cur).encode("utf-8"))
if not apply:
    print("DRY RUN (pass --apply)")
