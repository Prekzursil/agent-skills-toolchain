r"""For each BLOCKED unit: who ACTUALLY produced it, and which vendor may therefore review it?

=============================== READ THIS FIRST ===============================
AN EARLIER VERSION OF THIS SCRIPT WAS WRONG AND ITS NUMBER MUST NOT BE CITED.

It resolved "cross-vendor" against the CATALOG's `assigned_model_vendor_role.vendor` and reported
32 SATISFIABLE_NOW / 19 RAIL_BLOCKED. That is the wrong field. The catalog records the vendor a
unit was ASSIGNED to; the receipt's `produced_by.vendor` records who actually built it. Those
differ precisely because the Codex rail has been down -- units planned for Codex were executed by
Claude instead.

ADV-0003 states the trap in its own reviewer.notes, in the artifact, in plain language:

    "The catalog also assigns this unit to openai/gpt-5-codex; it was in fact produced by
     anthropic/claude-opus-5, which makes an Anthropic reviewer SAME-vendor and therefore
     non-qualifying by the unit's own rule. A qualifying refuter is openai/gpt-5-codex."

So reading the assignment inverts the answer for exactly the units where it matters most. Acting on
the old number would have dispatched Claude reviewers at 22 units whose own receipts disqualify a
Claude reviewer by name -- satisfying the gate's letter while defeating its purpose, which is the
one outcome this lane was told not to produce. Recorded rather than silently corrected, because the
assignment field is the intuitive thing to read and the next person will reach for it too.
===============================================================================

RESOLUTION ORDER (first match wins; the source of each decision is printed per unit):
  A. receipt `failure.blocked_on` names a vendor as the required refuter -> that vendor. This is
     the unit's own operative statement of what it is waiting for and it outranks everything else.
  B. receipt `reviewer.notes` names a qualifying vendor                  -> that vendor.
  C. catalog reviewer_requirement is RELATIVE ("other vendor than the author")
                                                     -> NOT(produced_by.vendor)
  D. catalog reviewer_requirement names a vendor outright, reconciled against produced_by:
     if the named reviewer vendor == produced_by vendor it is SAME-vendor and therefore
     self-defeating, so the requirement resolves to the OTHER vendor.
  E. cross-vendor with no direction                   -> NOT(produced_by.vendor)
  F. no vendor constraint                             -> any (SATISFIABLE)

Rule D is the one that carries the correction: "cross-vendor Anthropic refuter" on a unit produced
by Anthropic cannot mean "an Anthropic reviewer", because the same sentence says a same-vendor
reviewer does not qualify. The sentence is internally consistent only under the assignment that
never happened.

CONTROL. The selftest exercises both vendor directions AND the assigned-vs-produced divergence that
broke v1: a unit assigned openai but produced by anthropic MUST resolve to an openai reviewer. The
script exits non-zero if that case regresses.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

OPENAI_TOKEN = re.compile(r"openai|codex|gpt-?5", re.I)
ANTHROPIC_TOKEN = re.compile(r"anthropic|claude|opus", re.I)
RELATIVE_PAT = re.compile(
    r"other\s+vendor\s+than\s+the\s+author|OTHER\s+vendor|than\s+the\s+author"
    r"|opposite\s+vendor|not\s+the\s+author'?s?\s+vendor",
    re.I,
)
VENDOR_ANY = re.compile(
    r"cross[-_ ]?vendor|different\s+vendor|separate\s+vendor|cross[-_ ]?model"
    r"|\bcodex\b|\bopenai\b|\bgpt-?5",
    re.I,
)
REVIEW_ANY = re.compile(r"review|refut", re.I)

SAT, BLOCKED_RAIL = "SATISFIABLE_NOW", "RAIL_BLOCKED"


def other(vendor: str) -> str:
    return "openai" if (vendor or "anthropic").lower() == "anthropic" else "anthropic"


def named_vendor(text: str) -> str | None:
    """Which vendor does this text name as the REFUTER? None if ambiguous or absent."""
    if not text:
        return None
    o, a = bool(OPENAI_TOKEN.search(text)), bool(ANTHROPIC_TOKEN.search(text))
    if o and not a:
        return "openai"
    if a and not o:
        return "anthropic"
    return None


#: The self-contradictory requirement. 16 blocked units carry this exact text and ALL 16 were
#: produced by anthropic, so "a same-vendor reviewer does not qualify" and "an Anthropic refuter"
#: cannot both hold. 13 of the 16 receipts reasoned this out and wrote an openai refuter into
#: blocked_on; 3 (ADV-0010/0011/0016) merely echoed the catalog text. Identical requirement +
#: identical producer must not yield two different answers because of receipt prose style, so the
#: 13 that carry the ARGUMENT govern the 3 that carry only a restatement.
CONTRADICTORY_REQ = re.compile(r"cross-vendor\s+Anthropic", re.I)


def resolve(
    blocked_on: str, reviewer_notes: str, req: str, produced: str
) -> tuple[str, str]:
    produced = (produced or "anthropic").lower()

    if CONTRADICTORY_REQ.search(req or "") and produced == "anthropic":
        return (
            "openai",
            "0:cross-vendor-Anthropic req on an anthropic-produced unit -> same-vendor is disqualified by the requirement's own clause",
        )

    v = named_vendor(blocked_on)
    if v:
        return v, "A:receipt.failure.blocked_on names the refuter vendor"

    # reviewer.notes usually mentions both vendors while explaining the reconciliation, so read
    # only the clause that states what QUALIFIES.
    m = re.search(
        r"qualif\w*\s+(?:refuter|reviewer)\s+is\s+([^.,;]{0,40})",
        reviewer_notes or "",
        re.I,
    )
    if m:
        v = named_vendor(m.group(1))
        if v:
            return v, "B:reviewer.notes names the qualifying vendor"

    if RELATIVE_PAT.search(req or ""):
        return other(produced), "C:requirement relative to author"

    v = named_vendor(req or "")
    if v:
        if v == produced:
            return (
                other(produced),
                "D:requirement names produced-by vendor -> same-vendor, resolves to other",
            )
        return v, "D:requirement names a vendor, differs from producer"

    if VENDOR_ANY.search(req or ""):
        return other(produced), "E:cross-vendor undirected"
    if REVIEW_ANY.search(req or ""):
        return "any", "F:review gate, no vendor constraint"
    return "any", "F:no vendor constraint"


def _selftest() -> int:
    bad = 0
    cases = [
        (
            "",
            "",
            "one cross-vendor Anthropic (opus) refuter ...; a same-vendor reviewer shares "
            "this unit's blind spots",
            "anthropic",
            "openai",
            "THE v1 BUG: anthropic-named requirement, anthropic producer -> must be openai",
        ),
        (
            "openai/gpt-5-codex refuter re-deriving from scratch",
            "",
            "anything",
            "anthropic",
            "openai",
            "blocked_on wins",
        ),
        (
            "",
            "A qualifying refuter is openai/gpt-5-codex (reachable via mcp__codex__codex)",
            "one cross-vendor Anthropic refuter",
            "anthropic",
            "openai",
            "reviewer.notes qualifying-clause wins over requirement prose",
        ),
        (
            "",
            "",
            "reviewer from the OTHER vendor than the author",
            "openai",
            "anthropic",
            "relative, openai producer -> anthropic reviewer (genuinely satisfiable)",
        ),
        (
            "",
            "",
            "one independent adversarial reviewer in a fresh context",
            "anthropic",
            "any",
            "no vendor constraint",
        ),
    ]
    for bo, notes, req, prod, expected, label in cases:
        v, rule = resolve(bo, notes, req, prod)
        if v != expected:
            print(f"FAILED:selftest [{label}] expected {expected} got {v} via {rule}")
            bad += 1
    print(
        f"  selftest: {'PASS' if not bad else 'FAIL'} ({len(cases)} cases incl. the v1 regression)"
    )
    return bad


def dig(doc: object, key: str) -> str:
    if isinstance(doc, dict):
        v = doc.get(key)
        if isinstance(v, str) and v.strip():
            return v
        for x in doc.values():
            r = dig(x, key)
            if r:
                return r
    elif isinstance(doc, list):
        for x in doc:
            r = dig(x, key)
            if r:
                return r
    return ""


def main() -> int:
    if _selftest():
        print("FAILED:vendor-satisfiability selftest did not discriminate")
        return 1

    units = json.loads(CATALOG.read_text(encoding="utf-8"))["work_units"]
    rows, mismatch = [], 0
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
            continue
        if str(rec.get("state", "")).upper() not in ("BLOCKED", "FAILED"):
            continue

        amr = u.get("assigned_model_vendor_role")
        assigned = (amr.get("vendor") if isinstance(amr, dict) else str(amr)) or ""
        pb = rec.get("produced_by")
        produced = (pb.get("vendor") if isinstance(pb, dict) else "") or ""
        produced_known = bool(produced)
        if not produced:
            produced = (
                "anthropic"  # conservative: assume same-vendor as the program default
            )
        if assigned and produced_known and assigned.lower() != produced.lower():
            mismatch += 1

        blocked_on = dig(rec.get("failure") or {}, "blocked_on")
        notes = (
            (rec.get("reviewer") or {}).get("notes", "")
            if isinstance(rec.get("reviewer"), dict)
            else ""
        )
        req = str(u.get("reviewer_requirement") or "")
        rv, rule = resolve(blocked_on, notes, req, produced)
        rows.append(
            {
                "id": u["id"],
                "title": (u.get("title") or "")[:80],
                "assigned_vendor": assigned,
                "produced_by_vendor": produced
                if produced_known
                else f"{produced} (ASSUMED - receipt has no produced_by)",
                "produced_by_known": produced_known,
                "reviewer_vendor": rv,
                "rule": rule,
                "verdict": BLOCKED_RAIL if rv == "openai" else SAT,
                "reviewer_requirement": " ".join(req.split())[:300],
                "blocked_on": " ".join((blocked_on or "").split())[:300],
                "output_path": p,
            }
        )

    print(f"  BLOCKED/FAILED units examined: {len(rows)}")
    print(f"  assigned vendor : {dict(Counter(r['assigned_vendor'] for r in rows))}")
    print(f"  PRODUCED BY     : {dict(Counter(r['produced_by_vendor'] for r in rows))}")
    print(
        f"  units where assigned != produced_by: {mismatch}   <-- the field that inverted v1"
    )
    print(
        f"  receipts with NO produced_by (assumed anthropic): {sum(1 for r in rows if not r['produced_by_known'])}"
    )
    print()
    print("  ==== required REVIEWER vendor (each unit once) ====")
    for v, n in Counter(r["reviewer_vendor"] for r in rows).most_common():
        print(f"    {n:>4}  {v}")
    print()
    print("  ==== VERDICT ====")
    for v, n in Counter(r["verdict"] for r in rows).most_common():
        print(f"    {n:>4}  {v}")
    print()
    print("  deciding rule:")
    for v, n in Counter(r["rule"] for r in rows).most_common():
        print(f"    {n:>4}  {v}")

    out = REPO / "command-center" / "p2-next" / "VENDOR-SATISFIABILITY.json"
    out.write_text(
        json.dumps(
            {
                "generated_by": "command-center/p2-next/vendor_satisfiability.py",
                "supersedes": "v1 of this script, which read assigned_model_vendor_role and reported "
                "32 SATISFIABLE / 19 RAIL_BLOCKED. That number is REFUTED - wrong field.",
                "blocked_units": len(rows),
                "assigned_vs_produced_mismatch": mismatch,
                "verdict_counts": dict(Counter(r["verdict"] for r in rows)),
                "reviewer_vendor_counts": dict(
                    Counter(r["reviewer_vendor"] for r in rows)
                ),
                "rule_counts": dict(Counter(r["rule"] for r in rows)),
                "units": rows,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(f"\n  wrote {out.relative_to(REPO)}")
    print("SUCCESS:vendor-satisfiability")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
