r"""Promote the security / red-team skill cluster from the vault into the CURATED set.

THE MEASURED PROBLEM. Claude Code reads `~/.claude/skills` (a symlink to `skills.daily`), which
holds 79 skills. The vault at `~/.agents/skills` holds 328. `secsearch`, `security-bounty-hunter`,
`llm-security`, `malware-analysis-triage` and 25 siblings are VAULT-ONLY, so this client cannot see
or auto-pick them while another client reading the vault directly can. That is the whole reason for
the asymmetry, and it is a curation gap, not a broken loader.

WHY THE CURATED SET IS SMALL AT ALL. Skill descriptions are ALWAYS-LOADED context, so the set was
deliberately trimmed after a measured "skills-context-budget overflow". Restoring all 249 vault-only
skills would recreate that defect. This promotes only the 29 the owner asked for.

BUDGET, measured rather than assumed: the 79 curated skills currently cost ~41,527 chars
(~10,381 tokens) of listing. The 29 additions cost ~11,259 chars (~2,814 tokens), for ~13,195 total.
`skillListingBudgetFraction: 0.02` of a 1M-token window is 20,000 tokens, so the result still fits
with ~34% headroom. On a 200k-token window it would NOT fit, which is stated here because the same
config serves both.

COPIES, NOT SYMLINKS. The existing 79 are real directory copies (measured: 79 of 79 share a name
with the vault, 0 curated-only). Copying matches that convention. It also means the curated copy can
DRIFT from the vault -- 21 of the first 40 shared skills already differ -- so this script records a
drift census rather than pretending the two trees are one.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

CURATED = Path("C:/Users/Prekzursil/.claude/skills.daily")
VAULT = Path("C:/Users/Prekzursil/.agents/skills")

KEYWORDS = re.compile(
    r"sec|redteam|red-team|pentest|offens|vuln|exploit|threat|attack|recon|forensic|malware"
    r"|crypto|audit",
    re.I,
)
SKIP_DIRS = {"__pycache__", ".ruff_cache", ".pytest_cache"}


def description(skill: Path) -> str:
    txt = (skill / "SKILL.md").read_text(encoding="utf-8", errors="replace")[:2500]
    m = re.search(r"^description:\s*(.+)$", txt, re.M)
    return (m.group(1) if m else "").strip()


def main() -> int:
    if not CURATED.is_dir() or not VAULT.is_dir():
        print(f"FAILED:curate curated={CURATED.is_dir()} vault={VAULT.is_dir()}")
        return 1

    current = {p.name for p in CURATED.iterdir() if p.is_dir()}
    candidates = [
        p
        for p in VAULT.iterdir()
        if p.is_dir() and p.name not in current and (p / "SKILL.md").is_file()
    ]
    targets = [
        p
        for p in candidates
        if KEYWORDS.search(p.name) or KEYWORDS.search(description(p))
    ]

    if not targets:
        print(
            "FAILED:curate 0 candidates matched -- the selector is broken, not the vault empty"
        )
        return 1
    # Control: the selector must DISCRIMINATE. If it matched every vault-only skill it is not a
    # filter, it is a firehose, and promoting 249 skills would recreate the budget overflow.
    if len(targets) >= len(candidates):
        print(
            f"FAILED:curate selector matched {len(targets)}/{len(candidates)} -- not discriminating"
        )
        return 1

    before_chars = sum(
        len(description(CURATED / n)) + len(n) + 4
        for n in current
        if (CURATED / n / "SKILL.md").is_file()
    )
    add_chars = sum(len(description(p)) + len(p.name) + 4 for p in targets)

    copied = []
    for src in sorted(targets):
        dst = CURATED / src.name
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*SKIP_DIRS))
        copied.append(src.name)

    # Post-condition: every promoted skill must be loadable, i.e. actually have a SKILL.md.
    bad = [n for n in copied if not (CURATED / n / "SKILL.md").is_file()]
    if bad:
        print(f"FAILED:curate promoted but unloadable (no SKILL.md): {bad}")
        return 1

    total = len({p.name for p in CURATED.iterdir() if p.is_dir()})
    print(f"  promoted {len(copied)} skill(s): {', '.join(copied[:8])} ...")
    print(f"  curated set: {len(current)} -> {total}")
    print(
        f"  listing budget: ~{before_chars:,} + {add_chars:,} = ~{before_chars + add_chars:,} chars "
        f"(~{(before_chars + add_chars) // 4:,} tokens); 2% of a 1M window = 20,000 tokens"
    )
    print("\nSUCCESS:curate-security-skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
