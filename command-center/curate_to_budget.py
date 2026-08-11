r"""Promote as many vault-only skills as the listing budget allows, cheapest-per-skill first.

THE CONSTRAINT IS REAL, not bureaucratic. Skill descriptions are ALWAYS-LOADED context, and this
estate already suffered a measured "skills-context-budget overflow" that produced naive sessions.
`skillListingBudgetFraction: 0.02` of a 1M-token window is 20,000 tokens.

MEASURED: 328 vault skills, 108 curated, 220 hidden. Listing all 328 costs ~26,295 tokens, which
OVERFLOWS 20,000. So "no hidden skills" is not reachable by curation alone at the current setting --
it needs either a budget change (an owner call, since the same settings.json serves 200k sessions
where 26k tokens is 13% of context) or shorter descriptions.

WHAT THIS DOES INSTEAD: fills the remaining headroom with the CHEAPEST skills first, maximising the
number of skills made auto-pickable per token spent. Median description is 240 chars; the 44 worst
exceed 600 and the largest is 1,750 (workflow-foundry). Sorting ascending buys the most coverage.

It stops at the budget and REPORTS what it could not fit, because a curation that silently truncates
is how the estate ended up with 220 invisible skills in the first place.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

CURATED = Path("C:/Users/Prekzursil/.claude/skills.daily")
VAULT = Path("C:/Users/Prekzursil/.agents/skills")
SKIP_DIRS = {"__pycache__", ".ruff_cache", ".pytest_cache"}

#: skillListingBudgetFraction 0.02 x 1,000,000-token window, in TOKENS.
BUDGET_TOKENS = 20_000
#: Leave headroom so a later skill addition does not silently push the listing over.
SAFETY_TOKENS = 1_500
CHARS_PER_TOKEN = 4


def description(skill: Path) -> str:
    txt = (skill / "SKILL.md").read_text(encoding="utf-8", errors="replace")[:4000]
    m = re.search(r"^description:\s*(.+)$", txt, re.M)
    return (m.group(1) if m else "").strip()


def cost(name: str, desc: str) -> int:
    return len(desc) + len(name) + 4


def main() -> int:
    current = {p.name for p in CURATED.iterdir() if p.is_dir()}
    used = sum(
        cost(n, description(CURATED / n))
        for n in current
        if (CURATED / n / "SKILL.md").is_file()
    )
    room = (BUDGET_TOKENS - SAFETY_TOKENS) * CHARS_PER_TOKEN - used
    print(
        f"  curated {len(current)} using ~{used:,} chars (~{used // CHARS_PER_TOKEN:,} tokens)"
    )
    print(f"  headroom: {room:,} chars (~{room // CHARS_PER_TOKEN:,} tokens)")
    if room <= 0:
        print("NOT-CHECKED:curate-budget no headroom -- nothing promoted")
        return 0

    candidates = [
        (cost(p.name, description(p)), p)
        for p in VAULT.iterdir()
        if p.is_dir() and p.name not in current and (p / "SKILL.md").is_file()
    ]
    candidates.sort(key=lambda t: t[0])  # cheapest first = most skills per token

    promoted, spent, skipped = [], 0, []
    for c, p in candidates:
        if spent + c <= room:
            shutil.copytree(
                p, CURATED / p.name, ignore=shutil.ignore_patterns(*SKIP_DIRS)
            )
            promoted.append(p.name)
            spent += c
        else:
            skipped.append((c, p.name))

    bad = [n for n in promoted if not (CURATED / n / "SKILL.md").is_file()]
    if bad:
        print(f"FAILED:curate-budget promoted but unloadable: {bad}")
        return 1

    total = len({p.name for p in CURATED.iterdir() if p.is_dir()})
    print(f"  promoted {len(promoted)} more; curated {len(current)} -> {total}")
    print(
        f"  spent {spent:,} chars; listing now ~{(used + spent) // CHARS_PER_TOKEN:,} tokens of {BUDGET_TOKENS:,}"
    )
    print(
        f"  STILL HIDDEN: {len(skipped)} skills, {sum(c for c, _ in skipped):,} chars"
    )
    if skipped:
        skipped.sort(reverse=True)
        print("  most expensive still-hidden (these are the ones to trim or accept):")
        for c, n in skipped[:8]:
            print(f"    {c:5} chars  {n}")
    print("\nSUCCESS:curate-to-budget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
