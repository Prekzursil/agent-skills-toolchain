"""Does the CITING status doc still assert the premise the OWNING doc retracted?

Round 3 corrected `CROSS-VENDOR-RAIL-STATUS.md` (rail ANSWERS). `rail_count_gate.py` already
declares `E2E-WAVE-STATUS.md` a citing doc and scans it -- but only for unit COUNTS, and the
count in that sentence (42) is still correct. So the gate returns SUCCESS while the two
owner-facing pages assert opposite states of the same fact. This probe measures that, and
controls the detector in both directions before anything is fixed.

Run:  python command-center/p2-next/_k1_premise_scan.py
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OWNING = "command-center/CROSS-VENDOR-RAIL-STATUS.md"
CITING = ("command-center/E2E-WAVE-STATUS.md",)
#: NOT scanned -- historical round artifacts legitimately record what a past round believed.
#: Counting them would be the use-vs-mention error: a document that NARRATES the old verdict is
#: not a document that ASSERTS it. Kept here so the scope is a stated choice, not an accident.
HISTORICAL = ("command-center/p2-next/P2NEXT-BUILD-R2.md",)

#: A present-tense rail-state ASSERTION: the word rail, then `is/are` within a short window, then
#: a state token. Past tense ("was pronounced down", "was never down") and negation-free prose
#: about the rail are deliberately not matched -- this is about what a page asserts TODAY.
ASSERT_RE = re.compile(
    r"\brail\b[^.\n]{0,40}?(?:\b(?:is|are)\b\s*\**\s*(?P<c>DOWN|UP)|\**\s*(?P<v>ANSWERS?))\b",
    re.I,
)
#: MEASURED FALSE POSITIVE, and the reason a DISJUNCTION guard exists at all. The first version of
#: this probe reported the owning doc as asserting UP -- on the strength of
#: `"...whether the rail is up or down. That is a control that looks the same under both
#: hypotheses"`, a sentence about the GATE being state-blind. Right answer, wrong evidence. A
#: hypothetical is not an assertion, and this is exactly why the gate below reads a DECLARED field
#: instead of inferring the owning state from prose.
DISJUNCTION = re.compile(r"\A\s*or\s+(?:up|down)\b", re.I)
#: Quoted spans are MENTIONS. The owning doc quotes its own retracted headline verbatim; that is
#: a record, not a claim. Stripping quotes before matching is the use-vs-mention rule mechanised.
QUOTED = re.compile(r"\"[^\"\n]*\"|“[^”\n]*”|`[^`\n]*`")


def blob(rev: str, rel: str) -> str:
    out = subprocess.run(
        ["git", "show", f"{rev}:{rel}"],
        cwd=REPO,
        capture_output=True,
        check=True,
    )
    return out.stdout.decode("utf-8", "replace")


def assertions(text: str, strip_quotes: bool = True) -> list[tuple[int, str, str]]:
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        probe = QUOTED.sub(" ", line) if strip_quotes else line
        for m in ASSERT_RE.finditer(probe):
            if DISJUNCTION.match(probe[m.end() :]):
                continue  # "the rail is up or down" is a hypothetical, not a claim
            token = (m.group("c") or m.group("v")).lower()
            state = "down" if token == "down" else "up"
            hits.append((lineno, state, line.strip()[:120]))
    return hits


def main() -> int:
    rev = (
        subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )

    owning = assertions(blob(rev, OWNING))
    print(f"HEAD={rev}")
    print(f"\nOWNING {OWNING}")
    for lineno, state, line in owning:
        print(f"  L{lineno:<5} {state.upper():<5} {line!r}")
    owning_states = {s for _, s, _ in owning}

    citing_hits: dict[str, list] = {}
    for rel in CITING:
        hits = assertions(blob(rev, rel))
        citing_hits[rel] = hits
        print(f"\nCITING {rel}")
        for lineno, state, line in hits:
            print(f"  L{lineno:<5} {state.upper():<5} {line!r}")

    contradictions = [
        (rel, lineno, state)
        for rel, hits in citing_hits.items()
        for lineno, state, _ in hits
        if owning_states and state not in owning_states
    ]
    print(f"\nowning asserts: {sorted(owning_states)}")
    print(f"CONTRADICTIONS: {contradictions}")

    # --- CONTROL A: the quote-stripper is what removes the owning doc's retracted headline,
    # not luck. With stripping off, the quoted DOWN line must reappear.
    raw = assertions(blob(rev, OWNING), strip_quotes=False)
    raw_down = [h for h in raw if h[1] == "down"]
    stripped_down = [h for h in owning if h[1] == "down"]
    ctrl_a = bool(raw_down) and not stripped_down
    print(
        f"\nCONTROL A quote-strip discriminates: {ctrl_a} "
        f"(unstripped DOWN lines {[h[0] for h in raw_down]}, stripped {[h[0] for h in stripped_down]})"
    )

    # --- CONTROL B: mutation. Flip the citing doc's assertion to UP in memory; the contradiction
    # must vanish. Without this, a scanner that flags any citing doc at all looks identical.
    mutated = blob(rev, CITING[0]).replace("rail is DOWN", "rail is UP")
    mut_hits = assertions(mutated)
    mut_contra = [h for h in mut_hits if h[1] not in owning_states]
    ctrl_b = bool(contradictions) and not mut_contra
    print(
        f"CONTROL B mutation clears it: {ctrl_b} (post-mutation contradictions {mut_contra})"
    )

    # --- CONTROL C: use-vs-mention. A historical round artifact DOES assert the old state; it is
    # excluded by DOC SET, not because the scanner cannot see it.
    hist = assertions(blob(rev, HISTORICAL[0]))
    ctrl_c = any(s == "down" for _, s, _ in hist)
    print(
        f"CONTROL C scanner CAN see the historical assertion (scope is a choice): {ctrl_c} "
        f"({HISTORICAL[0]} lines {[h[0] for h in hist if h[1] == 'down'][:6]})"
    )

    # --- After the fix: the same scan over the WORKING TREE, plus a survey of pages that are
    # candidates for the gate's scan set. A doc is only worth adding if it actually asserts a
    # state; adding one that merely mentions the rail buys coverage of nothing and risks firing
    # on narration. Measured, not assumed.
    print("\nWORKTREE (post-fix) and scan-set candidates:")
    wt: dict[str, list] = {}
    for rel in (
        OWNING,
        *CITING,
        "command-center/p2-next/OWNER-DECISION-condition-11.md",
    ):
        p = REPO / rel
        if not p.is_file():
            continue
        hits = assertions(p.read_text(encoding="utf-8"))
        wt[rel] = hits
        states = sorted({s for _, s, _ in hits})
        print(f"  {rel}: {len(hits)} assertion(s) {states}")

    (REPO / "command-center/p2-next/K1-PREMISE-SCAN.json").write_text(
        json.dumps(
            {
                "head": rev,
                "owning_states": sorted(owning_states),
                "owning_hits": owning,
                "citing_hits": {k: v for k, v in citing_hits.items()},
                "contradictions": contradictions,
                "control_a_quote_strip": ctrl_a,
                "control_b_mutation": ctrl_b,
                "control_c_scanner_sees_historical": ctrl_c,
                "worktree_post_fix": {k: v for k, v in wt.items()},
            },
            indent=2,
        ),
        encoding="utf-8",
        newline="\n",
    )

    if not (ctrl_a and ctrl_b and ctrl_c):
        print("\nFAILED:k1-premise-scan a detector control did not discriminate")
        return 2
    print(
        "\nSUCCESS:k1-premise-scan"
        if contradictions
        else "\nSUCCESS:k1-premise-scan no contradiction found"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
