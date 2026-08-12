r"""Split the self-declared-BLOCKED Prompt Two units by WHAT REVIEW THEY ACTUALLY DEMAND.

WHY THIS EXISTS. `blocker_census.py` answered "why are they blocked" and its structured pass is
correct as far as it goes. But its headline line --

    review = sum(n for c, n in structured.items() if "review" in c.lower() or "refut" in c.lower())
    print(f"  tags naming an independent/cross-vendor REVIEW gate: {review}")

-- sums TAG OCCURRENCES across receipts, then prints the total next to a receipt count. It happens
to render "51" beside "51 receipts", which reads as "every receipt is review-gated" and is not what
was computed. A receipt carrying three review tags contributes three. That is counting the document
instead of the field. This script counts UNITS, once each, and prints both numbers so the
difference is visible rather than silent.

THE SPLIT THAT MATTERS. A fresh-context Claude agent that did not build the unit satisfies
"independent review". It does NOT satisfy "independent CROSS-VENDOR review" -- same vendor means
shared blind spots, which is the exact thing that gate guards. Substituting one for the other
satisfies the letter and defeats the purpose. So each unit lands in exactly one bucket:

  CROSS_VENDOR  - the receipt's own classification tags, or the catalog's reviewer_requirement,
                  explicitly say cross-vendor / different-vendor / Codex.
  ANY_INDEP     - a review gate is named but no vendor constraint is attached anywhere.
  NO_REVIEW_GATE- blocked for some other reason entirely.

TWO SOURCES, DELIBERATELY. The receipt classification is the unit's SELF-declaration; the catalog
reviewer_requirement is the demand the program placed on it. They can disagree, and a disagreement
is the interesting case -- a unit whose receipt says only "independent review" while its catalog
row demands cross-vendor must be treated as CROSS_VENDOR (the stricter of the two governs). Every
disagreement is printed.

DETECTOR CONTROL. Both states are exercised in the __main__ block: synthetic receipts that MUST
classify CROSS_VENDOR and MUST classify ANY_INDEP are run through the same functions before the
real sweep, and the script exits non-zero if either is misfiled. A classifier that has never been
shown to discriminate is not a classifier.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

#: A vendor constraint. "cross-vendor" and "different vendor" are explicit; naming Codex/GPT/OpenAI
#: as the required reviewer is equally a vendor constraint even without the word "cross".
VENDOR_PAT = re.compile(
    r"cross[-_ ]?vendor|different\s+vendor|other\s+vendor|separate\s+vendor"
    r"|\bcodex\b|\bgpt-?5|\bopenai\b|\bgemini\b|cross[-_ ]?model",
    re.I,
)
#: A review gate of any kind, vendor-agnostic.
REVIEW_PAT = re.compile(
    r"review|reviewer|refut|self-review-is-not-review|independent\s+(agent|verif)",
    re.I,
)

CROSS_VENDOR, ANY_INDEP, NO_GATE = "CROSS_VENDOR", "ANY_INDEP", "NO_REVIEW_GATE"


def classification_tags(doc: object) -> list[str]:
    """Every `classification` entry anywhere in the receipt, as a flat list of strings."""
    out: list[str] = []
    if isinstance(doc, dict):
        c = doc.get("classification")
        if isinstance(c, list):
            out += [str(x) for x in c]
        elif isinstance(c, str):
            out.append(c)
        for v in doc.values():
            out += classification_tags(v)
    elif isinstance(doc, list):
        for v in doc:
            out += classification_tags(v)
    return out


def reason_text(doc: object) -> str:
    """The receipt's `failure.reason` prose, used ONLY as a tie-breaker and always reported."""
    if isinstance(doc, dict):
        f = doc.get("failure")
        if isinstance(f, dict) and isinstance(f.get("reason"), str):
            return f["reason"]
        for v in doc.values():
            r = reason_text(v)
            if r:
                return r
    elif isinstance(doc, list):
        for v in doc:
            r = reason_text(v)
            if r:
                return r
    return ""


def classify(
    tags: list[str], reviewer_requirement: str, reason: str
) -> tuple[str, str]:
    """Return (bucket, why). The STRICTER of receipt-tags and catalog-requirement governs."""
    tagblob = " ".join(tags)
    if VENDOR_PAT.search(tagblob):
        return CROSS_VENDOR, "receipt tag names a vendor constraint"
    if VENDOR_PAT.search(reviewer_requirement or ""):
        return CROSS_VENDOR, "catalog reviewer_requirement names a vendor constraint"
    if VENDOR_PAT.search(reason or ""):
        return CROSS_VENDOR, "receipt reason prose names a vendor constraint"
    if REVIEW_PAT.search(tagblob) or REVIEW_PAT.search(reviewer_requirement or ""):
        return ANY_INDEP, "review gate named, no vendor constraint anywhere"
    return NO_GATE, "no review gate found in tags or reviewer_requirement"


def _selftest() -> int:
    """Both-states control. A classifier only counts once it is shown to discriminate."""
    bad = 0
    b, _ = classify(["blocked-on-independent-cross-vendor-review"], "", "")
    if b != CROSS_VENDOR:
        print(f"FAILED:selftest cross-vendor tag classified {b}")
        bad += 1
    b, _ = classify(
        ["blocked-on-independent-review", "reviewer-absent"],
        "an independent reviewer",
        "",
    )
    if b != ANY_INDEP:
        print(f"FAILED:selftest plain-independent tag classified {b}")
        bad += 1
    b, _ = classify(
        ["blocked-on-independent-review"], "an independent Codex reviewer", ""
    )
    if b != CROSS_VENDOR:
        print(f"FAILED:selftest catalog-vendor-requirement classified {b}")
        bad += 1
    b, _ = classify(["dependency-unbuilt"], "none", "")
    if b != NO_GATE:
        print(f"FAILED:selftest no-gate classified {b}")
        bad += 1
    print(f"  selftest: {'PASS' if not bad else 'FAIL'} (4 cases, both directions)")
    return bad


def main() -> int:
    if _selftest():
        print("FAILED:split-review-gate selftest did not discriminate")
        return 1

    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = doc.get("work_units") or doc.get("units")
    print(f"  catalog: {CATALOG.name} ({len(units)} units)")

    buckets: dict[str, list[dict]] = {CROSS_VENDOR: [], ANY_INDEP: [], NO_GATE: []}
    disagreements: list[str] = []
    tag_occurrences = Counter()
    missing_receipt = 0
    states = Counter()

    for u in units:
        p = u.get("output_path")
        if not p:
            continue
        fp = REPO / p
        if not fp.is_file() or fp.suffix.lower() != ".json":
            continue
        try:
            rec = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            missing_receipt += 1
            continue
        state = str(rec.get("state", "")).upper()
        states[state] += 1
        if state not in ("BLOCKED", "FAILED"):
            continue

        tags = classification_tags(rec)
        for t in tags:
            tag_occurrences[t] += 1
        rr = str(u.get("reviewer_requirement") or "")
        reason = reason_text(rec)
        bucket, why = classify(tags, rr, reason)

        tagblob = " ".join(tags)
        if VENDOR_PAT.search(rr) and not VENDOR_PAT.search(tagblob):
            disagreements.append(
                f"{u['id']}: receipt tags say no vendor constraint, catalog reviewer_requirement does"
            )
        if VENDOR_PAT.search(tagblob) and not VENDOR_PAT.search(rr):
            disagreements.append(
                f"{u['id']}: receipt tags demand cross-vendor, catalog reviewer_requirement does not"
            )

        buckets[bucket].append(
            {
                "id": u["id"],
                "title": u.get("title", "")[:90],
                "why": why,
                "tags": tags,
                "reviewer_requirement": rec_trim(rr),
                "reason_head": " ".join((reason or "").split())[:300],
                "output_path": p,
            }
        )

    total = sum(len(v) for v in buckets.values())
    print(f"  receipt states seen: {dict(states.most_common(6))}")
    print(f"  BLOCKED/FAILED units: {total}")
    print()
    print("  ==== THE SPLIT (each unit counted exactly once) ====")
    for b in (CROSS_VENDOR, ANY_INDEP, NO_GATE):
        print(f"    {len(buckets[b]):>4}  {b}")
    print()
    print(
        f"  tag OCCURRENCES (what blocker_census summed): {sum(tag_occurrences.values())}"
    )
    print(f"  distinct UNITS                              : {total}")
    print("    ^ these are different quantities; the first is not a unit count")
    if disagreements:
        print(f"\n  receipt-vs-catalog disagreements ({len(disagreements)}):")
        for d in disagreements[:20]:
            print(f"    {d}")

    out = REPO / "command-center" / "p2-next" / "REVIEW-GATE-SPLIT.json"
    out.write_text(
        json.dumps(
            {
                "generated_by": "command-center/p2-next/split_review_gate.py",
                "catalog_units": len(units),
                "blocked_or_failed": total,
                "counts": {b: len(v) for b, v in buckets.items()},
                "tag_occurrences_total": sum(tag_occurrences.values()),
                "tag_occurrences": dict(tag_occurrences.most_common()),
                "receipt_vs_catalog_disagreements": disagreements,
                "buckets": buckets,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(f"\n  wrote {out.relative_to(REPO)}")
    print("SUCCESS:split-review-gate")
    return 0


def rec_trim(s: str) -> str:
    return " ".join(s.split())[:240]


if __name__ == "__main__":
    raise SystemExit(main())
