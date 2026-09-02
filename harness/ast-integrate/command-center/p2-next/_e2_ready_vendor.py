"""Which READY units actually need the DEAD rail -- i.e. demand a Codex reviewer?

_e1 showed the cheap question ("does the text say cross-vendor") is not the decision-relevant one.
46 READY units demand a cross-vendor *Anthropic* refuter: those name cross-vendor, yet a fresh
Claude reviewer satisfies them whenever the unit is Codex-produced. Counting them as "blocked on
codex login" overstates the credential write's value -- the opposite direction from round 1's
error, but the same class of error.

Buckets are the vendor the requirement DEMANDS, not the words it uses:
  NEEDS_CODEX      names Codex/openai as a reviewer (alone, or alongside a Claude reviewer)
  CROSS_UNDIRECTED a cross-vendor clause naming no vendor -> resolves to NOT(producer)
  CROSS_ANTHROPIC  a cross-vendor clause naming only Anthropic -> a Claude reviewer, unless the
                   unit is itself Claude-produced, in which case it self-defeats (shipped rule 0)
  SAME_OR_ANY      no cross-vendor clause and no Codex named -> any independent reviewer

The first version of this probe was WRONG and its own control caught it: "two reviewers, one
fresh-context Claude and one Codex" carries no cross-vendor PHRASE, so a clause-first predicate
filed it as same-vendor-satisfiable. Naming both vendors IS the cross-vendor demand. Recorded
rather than deleted -- it is the same use-vs-mention class that produced round 1's bad sentence.

Controls are asserted before any count prints; a broken predicate aborts.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter, defaultdict

REV = "5423de0f3eaae28975f62268f705ba85746312ff"
REPO = "C:/Users/Prekzursil/source/ast-integrate"

# Deliberately re-implemented rather than imported from vendor_satisfiability.py: a control that
# shares its subject's reader inherits the defect it exists to catch (round-3 lesson, _d2).
CROSS_CLAUSE = re.compile(
    r"cross-vendor|different vendors?|other vendor|another vendor", re.I
)
OPENAI = re.compile(r"\bcodex\b|\bopenai\b|gpt-5", re.I)
ANTHROPIC = re.compile(r"\bclaude\b|\banthropic\b|\bopus\b", re.I)


def git_show(path: str) -> str:
    out = subprocess.run(
        ["git", "-C", REPO, "show", f"{REV}:{path}"], capture_output=True, check=True
    )
    return out.stdout.decode("utf-8")


def bucket(text: str) -> str:
    """Which reviewer vendor does this requirement demand?"""
    if OPENAI.search(text):
        # Naming Codex as a reviewer needs the rail whether or not the text also says
        # "cross-vendor" and whether or not a Claude reviewer is demanded alongside it.
        return "NEEDS_CODEX"
    if CROSS_CLAUSE.search(text):
        return "CROSS_ANTHROPIC" if ANTHROPIC.search(text) else "CROSS_UNDIRECTED"
    return "SAME_OR_ANY"


CONTROLS = [
    (
        "one fresh-context Claude reviewer who has not seen this transcript",
        "SAME_OR_ANY",
    ),
    ("one independent adversarial reviewer in a fresh context", "SAME_OR_ANY"),
    ("one cross-vendor Codex (openai) refuter who re-derives it", "NEEDS_CODEX"),
    ("two reviewers, one fresh-context Claude and one Codex", "NEEDS_CODEX"),
    ("one cross-vendor Anthropic (opus) refuter who re-derives it", "CROSS_ANTHROPIC"),
    ("two reviewers from DIFFERENT vendors must each reproduce it", "CROSS_UNDIRECTED"),
]


def main() -> int:
    for text, want in CONTROLS:
        got = bucket(text)
        ok = "ok" if got == want else "MISMATCH"
        print(f"  CONTROL {want:<17} -> {got:<17} {ok}")
        if got != want:
            print("FAILED:e2-ready-vendor control mismatch; no count below is usable")
            return 1

    ready = json.loads(git_show("command-center/READY-UNITS.json"))["ready_units"]
    catalog = json.loads(git_show("command-center/WORK-UNIT-CATALOG.json"))
    by_id = {u["id"]: u for u in catalog["work_units"]}

    rows = []
    for uid in ready:
        req = by_id[uid].get("reviewer_requirement") or ""
        rows.append(
            {
                "id": uid,
                "bucket": bucket(req),
                "assigned_vendor": by_id[uid]["assigned_model_vendor_role"]["vendor"],
                "requirement": req,
            }
        )

    counts = Counter(r["bucket"] for r in rows)
    print(f"\nREV {REV[:8]}  population {len(rows)}")
    for name, n in counts.most_common():
        print(f"  {name:<18} {n:>4}")

    texts = defaultdict(Counter)
    for r in rows:
        texts[r["bucket"]][r["requirement"]] += 1
    for name in ("NEEDS_CODEX", "CROSS_UNDIRECTED", "CROSS_ANTHROPIC", "SAME_OR_ANY"):
        print(f"\n-- {name} distinct texts ({len(texts[name])}) --")
        for text, n in texts[name].most_common(3):
            print(f"   {n:>4}x {text[:114]}")

    # CROSS_UNDIRECTED and CROSS_ANTHROPIC resolve against the PRODUCER, which for an unbuilt
    # unit is only a plan. Report the assignment mix instead of assuming one.
    for name in ("CROSS_UNDIRECTED", "CROSS_ANTHROPIC"):
        mix = Counter(r["assigned_vendor"] for r in rows if r["bucket"] == name)
        print(f"  {name} assigned-vendor mix: {dict(mix)}")

    print(f"\n  Codex reviewer NAMED (rail required)     : {counts['NEEDS_CODEX']}")
    print(
        f"  cross-vendor clause, direction depends on producer: "
        f"{counts['CROSS_UNDIRECTED'] + counts['CROSS_ANTHROPIC']}"
    )
    print(f"  no cross-vendor demand at all             : {counts['SAME_OR_ANY']}")

    out = {
        "rev": REV,
        "population": len(rows),
        "counts": dict(counts),
        "needs_codex_named": counts["NEEDS_CODEX"],
        "producer_dependent": counts["CROSS_UNDIRECTED"] + counts["CROSS_ANTHROPIC"],
        "no_cross_vendor_demand": counts["SAME_OR_ANY"],
        "assigned_mix": {
            name: dict(
                Counter(r["assigned_vendor"] for r in rows if r["bucket"] == name)
            )
            for name in counts
        },
    }
    dest = f"{REPO}/command-center/p2-next/E2-READY-VENDOR.json"
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"SUCCESS:e2-ready-vendor wrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
