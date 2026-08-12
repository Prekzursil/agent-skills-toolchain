r"""Why do 46 Prompt Two units self-declare BLOCKED? Histogram the causes from their own receipts.

CLOSES AN UNVERIFIED I NAMED RATHER THAN LEAVING IT. DELIVERED-VS-SUBSTANTIVE.md established that 46
units carry `state: BLOCKED` and explicitly did not establish WHY, naming this as the settling
experiment. The data is present -- IMP-0433 documents its blocker in nine places -- it was simply
never aggregated.

THE ANSWER MATTERS MORE THAN THE COUNT. "46 blocked" is a number; "46 blocked because X" is an action.
If they share one cause, one fix unblocks a tranche. If each is unique, the program is genuinely
1,958-units-of-work away and no clever unblock exists.

DETECTOR DISCIPLINE. Receipts do not share a single blocker field -- IMP-0433 has 20 top-level keys
and the blocker text lives nested. So this searches the WHOLE document for blocker-bearing prose
rather than probing for the field names I expect. Probing for expected field names is how I reported
"no blocker recorded -- unactionable" an hour ago against a receipt that documents its blocker nine
times; searching the document is the correction. Every extraction prints its own source key so a
wrong reading is visible rather than silent.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
#: Taken from ready_units.py:34 rather than guessed. My first two guesses were both wrong and the
#: script failed CLOSED with "no catalog found" -- which is the correct behaviour, and the reason it
#: did not instead print an empty histogram that would have read as "nothing is blocked".
CATALOG_CANDIDATES = (REPO / "command-center" / "WORK-UNIT-CATALOG.json",)
#: Keys whose value plausibly explains a block. Ordered: the most specific wins the label.
BLOCKER_KEYS = ("blocker", "blocked_by", "blocked_reason", "failure", "reason", "residual_unknowns",
                "residual", "retry", "report", "summary")
#: Coarse cause buckets. First match wins, so order from specific to generic.
BUCKETS: tuple[tuple[str, str], ...] = (
    ("owner-decision", r"owner[- ]?(decision|approval|gate|ruling)|awaiting the owner"),
    ("dependency-unbuilt", r"depend\w*\s+(is|are|not)\s+\w*built|unbuilt|prerequisite|upstream unit"),
    ("schema-or-contract", r"schema|contract|output_schema|does not validate|invalid"),
    ("independent-reviewer", r"independent\s+review|reviewer\.independent|self-certif"),
    ("evidence-insufficient", r"insufficient evidence|could not measure|unmeasured|NOT-CHECKED"),
    ("tooling-or-access", r"not installed|no such|permission|access denied|unavailable|offline"),
)


def load_units() -> list[dict]:
    for c in CATALOG_CANDIDATES:
        if c.is_file():
            doc = json.loads(c.read_text(encoding="utf-8"))
            u = doc.get("work_units") or doc.get("units")
            if u:
                print(f"  catalog: {c.name} ({len(u)} units)")
                return u
    return []


def blocker_text(doc: object) -> tuple[str, str]:
    """Return (source_key, text). Searches nested structures, not just top level."""
    if isinstance(doc, dict):
        for k in BLOCKER_KEYS:
            v = doc.get(k)
            if isinstance(v, str) and v.strip():
                return k, v
            if isinstance(v, (dict, list)) and v:
                return k, json.dumps(v, ensure_ascii=False)
        for v in doc.values():  # recurse; the blocker is often one level down
            k2, t2 = blocker_text(v)
            if t2:
                return k2, t2
    elif isinstance(doc, list):
        for v in doc:
            k2, t2 = blocker_text(v)
            if t2:
                return k2, t2
    return "", ""


def bucket(text: str) -> str:
    low = text.lower()
    for name, pat in BUCKETS:
        if re.search(pat, low):
            return name
    return "uncategorised"


def classifications(doc: object) -> list[str]:
    """Read the STRUCTURED classification array, not prose.

    The regex pass above put 19 receipts in 'schema-or-contract' purely because their reason text
    contains the word "contract", while the same texts open with "Not a measurement failure" and
    "the measurement is complete". That is counting the document instead of the field -- the exact
    use-vs-mention error this program keeps paying for. Every receipt carries
    failure.classification as a real list, so read that.
    """
    out: list[str] = []
    if isinstance(doc, dict):
        c = doc.get("classification")
        if isinstance(c, list):
            out += [str(x) for x in c]
        elif isinstance(c, str):
            out.append(c)
        for v in doc.values():
            out += classifications(v)
    elif isinstance(doc, list):
        for v in doc:
            out += classifications(v)
    return out


def main() -> int:
    units = load_units()
    if not units:
        print("FAILED:blocker-census no catalog found")
        return 1

    blocked, causes, srcs, examples = [], Counter(), Counter(), {}
    structured: Counter = Counter()
    units_by_class: dict[str, list[str]] = {}
    for u in units:
        p = u.get("output_path")
        if not p:
            continue
        fp = REPO / p
        if not fp.is_file() or fp.suffix.lower() != ".json":
            continue
        try:
            doc = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(doc.get("state", "")).upper() not in ("BLOCKED", "FAILED"):
            continue
        blocked.append(u["id"])
        key, text = blocker_text(doc)
        srcs[key or "<none found>"] += 1
        b = bucket(text) if text else "no-blocker-text"
        causes[b] += 1
        examples.setdefault(b, (u["id"], key, " ".join(text.split())[:220]))
        cls = classifications(doc)
        for c in cls or ["<no classification field>"]:
            structured[c] += 1
        if cls:
            units_by_class.setdefault(cls[0], []).append(u["id"])

    if not blocked:
        print("FAILED:blocker-census found 0 BLOCKED receipts -- detector disagrees with ready_units")
        return 1

    print(f"  BLOCKED/FAILED receipts found: {len(blocked)}")
    print("\n  cause histogram:")
    for name, n in causes.most_common():
        uid, key, ex = examples[name]
        print(f"    {n:>4}  {name}")
        print(f"          e.g. {uid} (from `{key}`): {ex}")
    print("\n  which key supplied the text (detector transparency):")
    for k, n in srcs.most_common(8):
        print(f"    {n:>4}  {k}")

    # THE AUTHORITATIVE VIEW: the structured field, not my regex over prose.
    print(f"\n  STRUCTURED classification tags across {len(blocked)} receipts (a receipt may carry several):")
    for c, n in structured.most_common(14):
        print(f"    {n:>4}  {c}")
    review = sum(n for c, n in structured.items() if "review" in c.lower() or "refut" in c.lower())
    print(f"\n  tags naming an independent/cross-vendor REVIEW gate: {review}")
    print("\nSUCCESS:blocker-census")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
