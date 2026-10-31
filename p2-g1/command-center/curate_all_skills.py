r"""Curate EVERY vault skill into the set Claude reads, losing no ability.

The owner lifted the budget constraint ("if it can go over 20k if quality is preserved") and asked
for SOTA over thrift, so the earlier plan -- trim 44 bloated descriptions to fit 20,000 tokens -- is
DROPPED. Trimming a description shortens exactly the text the model pattern-matches on when deciding
whether a skill applies, so it trades discoverability for tokens. With the budget raised to 0.04
(40,000 tokens on a 1M window) the full set fits untouched and nothing is lost.

WHAT "CURATED" ACTUALLY COSTS, measured, because the premise matters: all 235 SKILL.md BODIES total
~372,659 tokens, while their DESCRIPTIONS total ~17,234. Bodies are 22x the descriptions and are
loaded ONLY when a skill is invoked. So curating a skill costs ~50 tokens of permanent index, not
its whole body -- "all loaded" does not mean "all in context".

WINDOWS RESERVED DEVICE NAMES. The vault contains a file literally named `NUL` under
workflow-monitor/. `NUL`, `CON`, `PRN`, `AUX`, `COM1-9` and `LPT1-9` are reserved device names on
Windows; shutil.copytree dies on them with `[WinError 87] The parameter is incorrect` and aborts the
whole tree mid-copy. They are skipped by name (with the skip COUNTED, never silent) so one poisoned
filename cannot block 90 other skills.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

CURATED = Path("C:/Users/Prekzursil/.claude/skills.daily")
VAULT = Path("C:/Users/Prekzursil/.agents/skills")

SKIP_DIRS = {"__pycache__", ".ruff_cache", ".pytest_cache", ".git"}
#: Windows reserved device names -- uncopyable, and they abort the whole copytree.
RESERVED = (
    {"NUL", "CON", "PRN", "AUX"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


def ignore(_dir: str, names: list[str]) -> set[str]:
    return {n for n in names if n in SKIP_DIRS or n.upper().split(".")[0] in RESERVED}


def description(skill: Path) -> str:
    txt = (skill / "SKILL.md").read_text(encoding="utf-8", errors="replace")[:4000]
    m = re.search(r"^description:\s*(.+)$", txt, re.M)
    return (m.group(1) if m else "").strip()


def main() -> int:
    current = {p.name for p in CURATED.iterdir() if p.is_dir()}
    todo = [
        p
        for p in sorted(VAULT.iterdir())
        if p.is_dir() and p.name not in current and (p / "SKILL.md").is_file()
    ]
    print(f"  curated {len(current)} | to promote {len(todo)}")

    promoted, failed, reserved_skipped = [], [], 0
    for src in todo:
        dst = CURATED / src.name
        for _d, names in [(src, [q.name for q in src.rglob("*")])]:
            reserved_skipped += sum(
                1 for n in names if n.upper().split(".")[0] in RESERVED
            )
        try:
            shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)
            promoted.append(src.name)
        except (OSError, shutil.Error) as exc:
            # Never let one bad tree abort the rest; record it instead.
            failed.append((src.name, str(exc)[:110]))

    all_now = {p.name for p in CURATED.iterdir() if p.is_dir()}
    unloadable = sorted(n for n in all_now if not (CURATED / n / "SKILL.md").is_file())
    vault_all = {
        p.name for p in VAULT.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()
    }
    hidden = sorted(vault_all - all_now)

    listing = sum(
        len(description(CURATED / n)) + len(n) + 4
        for n in all_now
        if (CURATED / n / "SKILL.md").is_file()
    )

    print(
        f"  promoted {len(promoted)} | failed {len(failed)} | reserved-name files skipped {reserved_skipped}"
    )
    for n, why in failed[:6]:
        print(f"    FAILED {n}: {why}")
    print(f"  curated now {len(all_now)} of {len(vault_all)} vault skills")
    print(f"  HIDDEN REMAINING: {len(hidden)} {hidden[:6]}")
    print(f"  unloadable (no SKILL.md): {len(unloadable)} {unloadable[:4]}")
    print(
        f"  listing cost ~{listing:,} chars (~{listing // 4:,} tokens) of 40,000 budget"
    )

    if unloadable:
        print(f"FAILED:curate-all {len(unloadable)} curated dirs have no SKILL.md")
        return 1
    print("\nSUCCESS:curate-all-skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
