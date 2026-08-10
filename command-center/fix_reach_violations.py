"""Repair the 4 validator violations my own close-apply introduced.

WHAT I BROKE, AND HOW I MISSED IT. Closing 7 register items produced `FAILED:cc-validate
violations=4`. I ran `render.py --check`, read its `SUCCESS:cc-render no drift` line, and stopped --
but `render_status()` EMBEDS the validator's violations, so the drift check was green precisely
because it faithfully re-rendered a STATUS.md that says `4 VIOLATIONS`. A green gate I did not read
past is a signal I did not take. A peer lane surfaced it; the validator confirmed it directly.

FIX 1 -- REACH-1 x3 (`closed but depends on still-open R-A03`).

R-A03 is owner-gated on OQ-1+OQ-2 and has 11 dependents. Lane A1 measured the edges as
COUNTERFACTUAL: the supposedly-gated work SHIPPED WITHOUT THE GATE, so the edge is factually false
as a precondition. Two options were available and I took the narrower one:

  * retire all 11 edges  -- what two lanes recommended, but it restructures 8 items that are still
    OPEN and whose gate the owner may still want. Not mine to pre-empt.
  * retire the edge ONLY where the gated work is demonstrably complete -- the 3 closed items. This
    resolves every violation with the minimum structural change, and each retirement rests on
    positive evidence rather than on a policy about the gate.

The edge is NOT silently deleted: it moves into `history` with its reason, because a refuted premise
must be recorded, not overwritten. The other 8 edges are left exactly as they were.

FIX 2 -- REACH-6 (register snapshot hash). I rewrote `sources/REGISTER.md` in the same batch, so the
recorded digest went stale. Re-recorded from LF-NORMALISED bytes, matching what the validator hashes
and what git stores -- hashing raw working-tree bytes would make this gate unsatisfiable on any
Windows checkout.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
REGISTER = REPO / "command-center/sources/REGISTER.md"

GATE = "R-A03"
#: Only items whose gated deliverable is verified complete (see CLOSE-VERIFY.json).
RETIRE_ON = ("R-A06", "R-A09", "R-A12")
REASON = (
    "Dependency edge on R-A03 RETIRED as counterfactual, 2026-08-10. R-A03 is owner-gated on "
    "OQ-1+OQ-2 and remains OPEN, but this item's deliverable shipped WITHOUT that gate and is "
    "verified complete (see command-center/CLOSE-VERIFY.json). The edge asserted a precondition "
    "that execution demonstrably walked past, so leaving it in place made the item's own closure "
    "read as a contradiction (validator REACH-1) and would keep every future reachability report "
    "naming a blocker that no longer blocks. Recorded rather than deleted. Predicted by "
    "command-center/CLOSE-PROPOSALS-A1.md:73-76 before it happened. The 8 OTHER R-A03 dependents "
    "are still OPEN and their edges are deliberately left intact -- retiring those is an owner call."
)


def main() -> int:
    raw = CATALOG.read_text(encoding="utf-8")
    doc = json.loads(raw)
    assert json.dumps(doc, indent=1, ensure_ascii=False) == raw, (
        "serialiser no longer round-trips this file byte-exactly; refusing to rewrite"
    )

    # ---- FIX 1 ----
    retired = []
    for item in doc["items"]:
        if item["id"] not in RETIRE_ON:
            continue
        deps = list(item.get("dependencies") or [])
        if GATE not in deps:
            continue
        item["dependencies"] = [d for d in deps if d != GATE]
        item.setdefault("history", []).append(
            {
                "event": "dependency-retired",
                "date": "2026-08-10",
                "retired_dependency": GATE,
                "reason": REASON,
            }
        )
        retired.append(item["id"])

    if sorted(retired) != sorted(RETIRE_ON):
        print(f"FAILED:fix-reach expected to retire {RETIRE_ON}, retired {retired}")
        return 1

    # Guard: no OTHER item may lose an R-A03 edge.
    remaining = [i["id"] for i in doc["items"] if GATE in (i.get("dependencies") or [])]
    if len(remaining) != 8:
        print(
            f"FAILED:fix-reach expected 8 surviving R-A03 edges, found {len(remaining)}: {remaining}"
        )
        return 1

    # ---- FIX 2 ----
    lf = REGISTER.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(lf).hexdigest()
    old_sha = doc["provenance"].get("register_sha256", "")
    doc["provenance"]["register_sha256"] = digest
    doc["provenance"]["register_bytes"] = len(lf)

    CATALOG.write_text(
        json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8", newline=""
    )

    print(f"  retired {GATE} edge on: {', '.join(sorted(retired))}")
    print(
        f"  {GATE} edges left intact on {len(remaining)} still-open items: {', '.join(sorted(remaining))}"
    )
    print(
        f"  register_sha256 {old_sha[:12]} -> {digest[:12]}  ({len(lf)} LF-normalised bytes)"
    )
    print(
        "\nSUCCESS:fix-reach 2 fixes applied; re-run validate.py to confirm 0 violations"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
