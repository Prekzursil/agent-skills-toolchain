"""AUDIT probe 3: independently re-derive the cross-vendor vs any-reviewer split.

The DANGEROUS direction is a unit classified SATISFIABLE that actually demands cross-vendor
review -- that is the outcome the lane was told not to produce. So this probe is deliberately
BIASED TOWARD RAIL_BLOCKED: any cross-vendor/openai/codex token anywhere in the unit's operative
review text forces RAIL_BLOCKED. If my conservative classifier and the builder's rule-ladder agree
on the 10, the 10 are safe.

Detector control (both states): a synthetic unit whose requirement says "cross-vendor Codex
refuter" MUST come back RAIL_BLOCKED; one saying "any independent reviewer" MUST come back
SATISFIABLE. Plus a mention-vs-use control: text that merely NAMES codex inside a quoted
non-requirement field must not be counted (we only read the operative fields).
"""

from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
POP = REPO / "command-center" / "p2-next" / "_AUDIT-BLOCKED-POP.json"

CROSS = re.compile(
    r"cross[-_ ]?vendor|cross[-_ ]?model|different\s+vendor|other\s+vendor|separate\s+vendor"
    r"|\bopenai\b|\bcodex\b|gpt-?5|non[-_ ]?anthropic",
    re.I,
)
CLAIMED_SATISFIABLE = {
    "AUD-0006",
    "AUD-0020",
    "AUD-0021",
    "AUD-0030",
    "AUD-0041",
    "AUD-0051",
    "CC-0002",
    "IMP-0440",
    "TST-0334",
    "TST-0350",
}


def operative_text(rec: dict) -> dict:
    """Only the fields that STATE the requirement -- not free prose that may merely mention."""
    f = rec.get("failure") or {}
    out = {
        "catalog_reviewer_requirement": rec.get("catalog_reviewer_requirement") or "",
        "failure.blocked_on": f.get("blocked_on") or "",
        "failure.classification": f.get("classification") or "",
    }
    return {k: (v if isinstance(v, str) else json.dumps(v)) for k, v in out.items()}


def verdict(rec: dict) -> tuple[str, list[str]]:
    hits = []
    for k, v in operative_text(rec).items():
        m = CROSS.search(v)
        if m:
            hits.append(f"{k}~'{m.group(0)}'")
    return ("RAIL_BLOCKED" if hits else "SATISFIABLE"), hits


def main() -> int:
    pop = json.load(io.open(POP, encoding="utf-8"))
    rail, sat = [], []
    for uid in sorted(pop):
        v, hits = verdict(pop[uid])
        (rail if v == "RAIL_BLOCKED" else sat).append((uid, hits))

    print(
        f"AUDITOR conservative split: RAIL_BLOCKED={len(rail)}  SATISFIABLE={len(sat)}"
    )
    print("SATISFIABLE ids:", [u for u, _ in sat])
    mine = {u for u, _ in sat}
    print(
        f"\nagreement with builder's 10: mine=={len(mine)}  builder=={len(CLAIMED_SATISFIABLE)}"
    )
    print("  in mine not builder :", sorted(mine - CLAIMED_SATISFIABLE))
    print("  in builder not mine :", sorted(CLAIMED_SATISFIABLE - mine))

    # every claimed-satisfiable unit's operative text, verbatim, for the record
    print("\n=== VERBATIM operative text of the 10 claimed satisfiable ===")
    for uid in sorted(CLAIMED_SATISFIABLE):
        rec = pop.get(uid)
        if rec is None:
            print(f"{uid}: *** NOT IN BLOCKED POPULATION ***")
            continue
        t = operative_text(rec)
        print(
            f"\n--- {uid} (state={rec['state']}) produced_by={rec.get('produced_by')}"
        )
        for k, v in t.items():
            print(f"   {k}: {v[:400]}")

    # ---- CONTROL, both states ----
    c1 = verdict(
        {"catalog_reviewer_requirement": "INDEPENDENT CROSS-VENDOR Codex refuter"}
    )[0]
    c2 = verdict(
        {
            "catalog_reviewer_requirement": "any independent reviewer who did not build it"
        }
    )[0]
    c3 = verdict(
        {"catalog_reviewer_requirement": "any independent reviewer", "notes": "codex"}
    )[0]
    print(
        f"\nCONTROL fires_on_crossvendor={c1 == 'RAIL_BLOCKED'} silent_on_any={c2 == 'SATISFIABLE'}"
        f" ignores_nonoperative_mention={c3 == 'SATISFIABLE'}"
    )
    if not (c1 == "RAIL_BLOCKED" and c2 == "SATISFIABLE" and c3 == "SATISFIABLE"):
        print("FAILED:audit3 control")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
