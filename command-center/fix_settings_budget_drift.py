r"""Raise the REPO's skill-listing budget to match the live change, so a redeploy cannot re-hide skills.

THE DRIFT THIS CLOSES. Tonight's fix for "220 invisible skills" raised
`skillListingBudgetFraction` from 0.02 to 0.04 in the LIVE file `~/.claude/settings.json`. The repo
source `agent-self/config/settings.json` still said 0.02. `agent-self/bootstrap.ps1` deploys the repo
copy over the live one, so the next bootstrap would silently revert the budget to 20,000 tokens --
which is 8,413 tokens BELOW the measured listing cost of the 328 curated skills. The regression would
be invisible: descriptions collapse to names on overflow rather than erroring.

That is the exact edit-the-deployed-copy anti-pattern `rules/common/harness-vcs-hygiene.md` names --
"the repo is the source of truth; the live tree is a deploy target" -- and I committed it four hours
after flagging the same class in a live hook. Fixing the source, not just the deployed copy.

CORROBORATION, not a guess: `docs/research/2026-06-11-fanout-corpus.md:131` already recommended
"raise skillListingBudgetFraction to 0.04-0.05 to prevent silent skill dropping at 100+ skills".
Independent of tonight's measurement, and it agrees.

WHY BYTE-SURGERY RATHER THAN json.load + json.dump. The live file is NOT a copy of the repo file --
it carries live credential env vars the repo copy does not. Round-tripping either file through a JSON
writer would reformat every line and make the diff unreadable; worse, doing that to the LIVE file
would rewrite a file holding secrets. So this touches ONE line in the REPO file only, asserts the
line it is replacing, and never reads or writes the live file at all.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TARGET = REPO / "agent-self" / "config" / "settings.json"

OLD = '  "skillListingBudgetFraction": 0.02,'
NEW = '  "skillListingBudgetFraction": 0.04,'

#: Measured 2026-08-11: 328 curated skills cost ~113,654 chars of listing.
LISTING_CHARS = 113_654
WINDOW_TOKENS = 1_000_000


def main() -> int:
    # newline="" preserves the file's real line endings; a naive read would rewrite CRLF as LF and
    # produce a whole-file diff (windows-shell rule 8b).
    raw = TARGET.read_text(encoding="utf-8", newline="")
    eol = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.split(eol)

    hits = [i for i, ln in enumerate(lines) if ln == OLD]
    if not hits:
        already = [i for i, ln in enumerate(lines) if ln == NEW]
        if already:
            print(f"NOT-CHECKED:settings-budget already 0.04 at line {already[0] + 1}")
            return 0
        print(f"FAILED:settings-budget anchor not found in {TARGET}")
        return 1
    if len(hits) > 1:
        print(f"FAILED:settings-budget anchor is ambiguous, {len(hits)} matches")
        return 1

    lines[hits[0]] = NEW
    out = eol.join(lines)

    # Post-condition: exactly one line changed, and nothing else moved.
    if sum(1 for a, b in zip(raw.split(eol), lines) if a != b) != 1:
        print("FAILED:settings-budget more than one line differs")
        return 1
    TARGET.write_text(out, encoding="utf-8", newline="")

    for frac in (0.02, 0.04):
        budget = int(WINDOW_TOKENS * frac)
        verdict = "FITS" if LISTING_CHARS // 4 <= budget else "OVERFLOWS"
        print(
            f"  {frac}: {budget:,} tokens vs ~{LISTING_CHARS // 4:,} needed -> {verdict}"
        )
    print(
        f"  patched line {hits[0] + 1} of {TARGET.relative_to(REPO)} (eol preserved: {eol!r})"
    )
    print("\nSUCCESS:settings-budget-drift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
