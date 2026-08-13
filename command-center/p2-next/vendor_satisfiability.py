r"""For each BLOCKED unit: who ACTUALLY produced it, and which vendor may therefore review it?

=============================== READ THIS FIRST ===============================
TWO EARLIER VERSIONS OF THIS SCRIPT WERE WRONG. Both are recorded, not deleted, because the next
person will reach for the same wrong field and the same wrong shortcut.

--- v1 (REFUTED, round 1) -----------------------------------------------------
It resolved "cross-vendor" against the CATALOG's `assigned_model_vendor_role.vendor` and reported
32 SATISFIABLE_NOW / 19 RAIL_BLOCKED. That is the wrong field. The catalog records the vendor a
unit was ASSIGNED to; the receipt's `produced_by.vendor` records who actually built it. Those
differ precisely because the Codex rail has been down -- units planned for Codex were executed by
Claude instead.

ADV-0003 states the trap in its own reviewer.notes, in the artifact, in plain language:

    "The catalog also assigns this unit to openai/gpt-5-codex; it was in fact produced by
     anthropic/claude-opus-5, which makes an Anthropic reviewer SAME-vendor and therefore
     non-qualifying by the unit's own rule. A qualifying refuter is openai/gpt-5-codex."

--- v2 (REFUTED, round 2 -- CONFIRMED by an independent auditor) ---------------
v2 shipped rule D as "requirement names the producer's own vendor -> that is self-defeating, so it
resolves to the OTHER vendor", with NO test that the requirement actually contains a cross-vendor
clause. Consequence, measured: this lane's own round-1 edits rewrote `failure.blocked_on` on the six
AUD receipts (the review was done, so the field was updated to name the REMAINING blocker). That
removed the word "Claude" from blocked_on, rule A stopped firing, and all six fell through to rule
D -- which inverted "one fresh-context Claude reviewer" into a demand for an openai reviewer.
Re-running the script therefore printed 47 RAIL_BLOCKED / 4 SATISFIABLE where the artifact it
overwrote said 41/10. The published verification command did not reproduce its own number.
FIX: rule D only inverts when the requirement CARRIES a cross-vendor clause (D vs D2 below).

v2 also had a second hole that the D-fix alone would have made WORSE, in the dangerous direction:
`failure.blocked_on` can demand a cross-vendor refuter WITHOUT naming a vendor -- BLD-0023 says
"plus one cross-vendor refuter to re-derive the 1-of-2007 and zero-CI findings from the raw tree".
`named_vendor()` sees neither "openai" nor "anthropic" there and returns None, so v2 fell through
to rule D and got the right answer (RAIL_BLOCKED) for the wrong reason. Gating rule D without
adding rule A2 would have flipped BLD-0023 to SATISFIABLE and sent a same-vendor reviewer at a unit
whose own operative field demands the opposite -- the exact letter-vs-purpose failure this lane was
told not to produce. FIX: rule A2, an undirected cross-vendor clause in blocked_on.
===============================================================================

RESOLUTION ORDER (first match wins; the source of each decision is printed per unit):
  0. requirement is the self-contradictory "cross-vendor Anthropic" form on an anthropic-produced
     unit                                                     -> openai
  A. receipt `failure.blocked_on` NAMES a vendor as the required refuter -> that vendor. This is
     the unit's own operative statement of what it is waiting for and it outranks everything else.
  A2. receipt `failure.blocked_on` carries an UNDIRECTED cross-vendor clause (no vendor named)
                                                              -> NOT(produced_by.vendor)
  B. receipt `reviewer.notes` names a qualifying vendor       -> that vendor.
  C. catalog reviewer_requirement is RELATIVE ("other vendor than the author")
                                                              -> NOT(produced_by.vendor)
  D. catalog reviewer_requirement names a vendor:
       - names the PRODUCER's vendor AND carries a cross-vendor clause -> the OTHER vendor
         (self-defeating as written; the clause is the thing that makes it self-defeating)
       - D2: names the PRODUCER's vendor with NO cross-vendor clause -> that same vendor, because
         same-vendor is what the requirement ASKS FOR, not a substitution for something stricter
       - names the other vendor                               -> that vendor
  E. cross-vendor with no direction                           -> NOT(produced_by.vendor)
  F. no vendor constraint                                     -> any (SATISFIABLE)

BASIS. `--basis committed` (DEFAULT) reads every receipt and the catalog from the COMMITTED HEAD
blobs. The worktree is shared with sibling lanes and carries their UNCOMMITTED edits: measured
2026-08-13, ADV-0041 is BLOCKED in every commit since fb2f477f but SUCCESS in the worktree via an
uncommitted sibling edit, which alone moves the headline from 42 to 41. A number an owner will act
on must name the tree it was measured against. `--basis worktree` prints the other one.

WRITE. The default is a CHECK, not a write. v2 rewrote the committed artifact on every run, so an
auditor re-running the published command silently corrupted the deliverable and turned the lane's
own final verifier red. Pass `--write` to regenerate.

CONTROLS. The selftest exercises, in both directions: the v1 assigned-vs-produced inversion; the v2
rule-D over-generalization (must NOT invert); the D-gate firing when a cross-vendor clause IS
present (must invert); and the BLD-0023 undirected-clause case (must resolve to the other vendor).
main() additionally runs a STABILITY check -- every unit is classified from the PRE-EDIT blobs
(899ff779^) and from HEAD, and any unit whose verdict differs between the two is a re-execution
instability of exactly the kind that produced the v2 defect. The script exits non-zero on any of it.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
OUT_REL = "command-center/p2-next/VENDOR-SATISFIABILITY.json"
PRE_EDIT_REV = "899ff779^"  # the commit before this lane's first round-1 commit

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

#: An UNDIRECTED cross-vendor demand -- the clause that makes a same-vendor reviewer non-qualifying
#: without naming which vendor must review. Deliberately does NOT include the bare vendor names
#: (openai/codex/anthropic/claude): those are handled by named_vendor(), and treating a bare name as
#: a cross-vendor clause is how a requirement that ASKS for a vendor gets inverted into forbidding
#: it. That inversion is the v2 defect.
CROSS_CLAUSE = re.compile(
    r"cross[-_ ]?vendor|cross[-_ ]?model|different\s+vendor|separate\s+vendor"
    r"|other\s+vendor|non[-_ ]?anthropic|non[-_ ]?openai"
    r"|same[-\s]?vendor[^.;]{0,60}?(?:does\s+not|do\s+not|cannot|is\s+not|non[-\s]?qualif|shares)",
    re.I,
)

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

    # A2: blocked_on can demand cross-vendor review WITHOUT naming a vendor (BLD-0023).
    if CROSS_CLAUSE.search(blocked_on or ""):
        return (
            other(produced),
            "A2:blocked_on carries an undirected cross-vendor clause -> the other vendor",
        )

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
            if CROSS_CLAUSE.search(req or ""):
                return (
                    other(produced),
                    "D:requirement names the producer's vendor AND carries a cross-vendor clause -> self-defeating, resolves to other",
                )
            return (
                v,
                "D2:requirement names the producer's vendor with NO cross-vendor clause -> same-vendor is what it asks for",
            )
        return v, "D:requirement names a vendor, differs from producer"

    if VENDOR_ANY.search(req or ""):
        return other(produced), "E:cross-vendor undirected"
    if REVIEW_ANY.search(req or ""):
        return "any", "F:review gate, no vendor constraint"
    return "any", "F:no vendor constraint"


AUD_REQ = (
    "one fresh-context Claude reviewer who has not seen this unit's transcript; the reviewer "
    "must try to FALSIFY the headline count before PASS, not re-read the artifact"
)


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
            "completion condition 11: manifest_registration.registered is false; NOT a review "
            "blocker any more -- the review is done",
            "",
            AUD_REQ,
            "anthropic",
            "anthropic",
            "THE v2 BUG: requirement asks for a Claude reviewer, no cross-vendor clause, "
            "blocked_on no longer names the vendor -> must stay anthropic, NOT invert",
        ),
        (
            "owner decisions BS-02, BS-07; plus one cross-vendor refuter to re-derive the "
            "findings from the raw tree rather than from this receipt.",
            "",
            "An Anthropic-vendor reviewer samples ten JUSTIFIED verdicts.",
            "anthropic",
            "openai",
            "THE v2 SECOND HOLE (BLD-0023): undirected cross-vendor clause in blocked_on, no "
            "vendor named -> must be openai even though the requirement names Anthropic",
        ),
        (
            "",
            "",
            "one fresh-context Claude reviewer; a same-vendor reviewer does not satisfy the "
            "requirement",
            "anthropic",
            "openai",
            "D-GATE FIRES: same requirement shape but WITH a cross-vendor clause -> invert",
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
        f"  selftest: {'PASS' if not bad else 'FAIL'} ({len(cases)} cases incl. the v1 and both v2 regressions)"
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


def batch_blobs(rev: str, paths: list[str]) -> dict[str, str | None]:
    """Read many blobs at one revision with a single `git cat-file --batch` process."""
    proc = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=REPO,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    payload = "".join(f"{rev}:{p}\n" for p in paths).encode("utf-8")
    out, _ = proc.communicate(payload)
    res: dict[str, str | None] = {}
    pos = 0
    for p in paths:
        nl = out.find(b"\n", pos)
        if nl < 0:
            res[p] = None
            continue
        header = out[pos:nl].decode("utf-8", "replace")
        pos = nl + 1
        if header.endswith(("missing", "ambiguous")):
            res[p] = None
            continue
        size = int(header.split()[-1])
        res[p] = out[pos : pos + size].decode("utf-8", "replace")
        pos += size + 1
    return res


def load_units(basis: str, rev: str = "HEAD") -> list[dict]:
    """Every BLOCKED/FAILED unit with the fields the ladder reads, from one tree."""
    if basis == "committed":
        cat_txt = batch_blobs(rev, [CATALOG_REL])[CATALOG_REL]
        if cat_txt is None:
            raise SystemExit(f"FAILED:vendor-satisfiability catalog absent at {rev}")
        cat = json.loads(cat_txt)
    else:
        cat = json.loads((REPO / CATALOG_REL).read_text(encoding="utf-8"))

    units = cat["work_units"]
    paths = [
        u["output_path"]
        for u in units
        if u.get("output_path") and str(u["output_path"]).lower().endswith(".json")
    ]
    blobs = (
        batch_blobs(rev, paths)
        if basis == "committed"
        else {
            p: (
                (REPO / p).read_text(encoding="utf-8") if (REPO / p).is_file() else None
            )
            for p in paths
        }
    )

    rows = []
    for u in units:
        p = u.get("output_path")
        if not p or p not in blobs or blobs[p] is None:
            continue
        try:
            rec = json.loads(blobs[p])
        except Exception:
            continue
        if str(rec.get("state", "")).upper() not in ("BLOCKED", "FAILED"):
            continue
        amr = u.get("assigned_model_vendor_role")
        assigned = (amr.get("vendor") if isinstance(amr, dict) else str(amr)) or ""
        pb = rec.get("produced_by")
        produced = (pb.get("vendor") if isinstance(pb, dict) else "") or ""
        produced_known = bool(produced)
        blocked_on = dig(rec.get("failure") or {}, "blocked_on")
        notes = (
            (rec.get("reviewer") or {}).get("notes", "")
            if isinstance(rec.get("reviewer"), dict)
            else ""
        )
        req = str(u.get("reviewer_requirement") or "")
        rv, rule = resolve(blocked_on, notes, req, produced or "anthropic")
        rows.append(
            {
                "id": u["id"],
                "title": (u.get("title") or "")[:80],
                "assigned_vendor": assigned,
                "produced_by_vendor": produced
                if produced_known
                else "anthropic (ASSUMED - receipt has no produced_by)",
                "produced_by_known": produced_known,
                "reviewer_vendor": rv,
                "rule": rule,
                "verdict": BLOCKED_RAIL if rv == "openai" else SAT,
                "reviewer_requirement": " ".join(req.split())[:300],
                "blocked_on": " ".join((blocked_on or "").split())[:300],
                "output_path": p,
            }
        )
    return rows


def stability_check(committed_rows: list[dict]) -> list[str]:
    """Re-execution instability is the v2 defect. Classify the SAME units from the pre-edit tree
    and require the verdicts to agree. A unit whose verdict depends on this lane's own later edits
    to its receipt is a number that cannot be re-derived, whatever it says today."""
    try:
        pre = {r["id"]: r for r in load_units("committed", PRE_EDIT_REV)}
    except SystemExit:
        return [f"stability: catalog unreadable at {PRE_EDIT_REV}"]
    problems = []
    checked = 0
    for r in committed_rows:
        p = pre.get(r["id"])
        if p is None:
            continue
        checked += 1
        if p["verdict"] != r["verdict"]:
            problems.append(
                f"{r['id']}: {PRE_EDIT_REV}={p['verdict']} ({p['rule'][:28]}) HEAD={r['verdict']} ({r['rule'][:28]})"
            )
    print(
        f"  STABILITY: {checked} units classified at BOTH {PRE_EDIT_REV} and HEAD; "
        f"{len(problems)} verdict(s) moved"
    )
    for p in problems:
        print(f"    MOVED {p}")
    if checked < 40:
        problems.append(
            f"stability control is inert: only {checked} units comparable (expected >=40)"
        )
    return problems


def report(rows: list[dict], label: str) -> None:
    print(f"  ==== {label}: {len(rows)} BLOCKED/FAILED units ====")
    print(f"  PRODUCED BY     : {dict(Counter(r['produced_by_vendor'] for r in rows))}")
    print("  required REVIEWER vendor:")
    for v, n in Counter(r["reviewer_vendor"] for r in rows).most_common():
        print(f"    {n:>4}  {v}")
    print("  VERDICT:")
    for v, n in Counter(r["verdict"] for r in rows).most_common():
        print(f"    {n:>4}  {v}")
    print("  deciding rule:")
    for v, n in Counter(r["rule"] for r in rows).most_common():
        print(f"    {n:>4}  {v}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--basis", choices=("committed", "worktree"), default="committed")
    ap.add_argument(
        "--write",
        action="store_true",
        help="regenerate the artifact (default is CHECK-only)",
    )
    args = ap.parse_args(argv)

    if _selftest():
        print("FAILED:vendor-satisfiability selftest did not discriminate")
        return 1

    rows = load_units(args.basis)
    report(rows, f"BASIS={args.basis}")

    other_basis = "worktree" if args.basis == "committed" else "committed"
    other_rows = load_units(other_basis)
    ids_a, ids_b = {r["id"] for r in rows}, {r["id"] for r in other_rows}
    rail_a = sum(1 for r in rows if r["verdict"] == BLOCKED_RAIL)
    rail_b = sum(1 for r in other_rows if r["verdict"] == BLOCKED_RAIL)
    print(
        f"\n  BASIS COMPARISON: {args.basis}={len(rows)} blocked / {rail_a} rail-blocked   "
        f"{other_basis}={len(other_rows)} blocked / {rail_b} rail-blocked"
    )
    print(f"    only in {args.basis:<9}: {sorted(ids_a - ids_b)}")
    print(f"    only in {other_basis:<9}: {sorted(ids_b - ids_a)}")

    problems = stability_check(rows) if args.basis == "committed" else []

    payload = {
        "generated_by": "command-center/p2-next/vendor_satisfiability.py",
        "basis": args.basis,
        "supersedes": [
            "v1: read assigned_model_vendor_role, reported 32 SATISFIABLE / 19 RAIL_BLOCKED. REFUTED - wrong field.",
            "v2: rule D inverted any producer-named requirement, so this lane's own receipt edits "
            "flipped 6 units and the published command reproduced 47/4 instead of 41/10. REFUTED - "
            "confirmed by an independent auditor. Gated on a cross-vendor clause, plus rule A2.",
        ],
        "blocked_units": len(rows),
        "verdict_counts": dict(Counter(r["verdict"] for r in rows)),
        "reviewer_vendor_counts": dict(Counter(r["reviewer_vendor"] for r in rows)),
        "rule_counts": dict(Counter(r["rule"] for r in rows)),
        "basis_comparison": {
            args.basis: {"blocked": len(rows), "rail_blocked": rail_a},
            other_basis: {"blocked": len(other_rows), "rail_blocked": rail_b},
            "only_in_" + args.basis: sorted(ids_a - ids_b),
            "only_in_" + other_basis: sorted(ids_b - ids_a),
        },
        "stability_problems": problems,
        "units": rows,
    }
    out = REPO / OUT_REL
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    if args.write:
        out.write_text(text, encoding="utf-8", newline="\n")
        print(f"\n  WROTE {OUT_REL}")
    else:
        cur = out.read_text(encoding="utf-8") if out.is_file() else ""
        drift = cur != text
        print(f"\n  CHECK-only (pass --write to regenerate). artifact drift: {drift}")
        if drift:
            problems.append(
                f"{OUT_REL} differs from a fresh {args.basis}-basis computation"
            )

    if problems:
        print(f"FAILED:vendor-satisfiability {problems}")
        return 1
    print("SUCCESS:vendor-satisfiability")
    return 0


if __name__ == "__main__":
    sys.exit(main())
