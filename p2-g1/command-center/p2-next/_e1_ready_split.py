"""Re-derive the 449 READY split a THIRD time, and explain the two prior disagreements.

Round-1 build asserted "all 449 name a cross-vendor reviewer". The audit measured 164/285 and
the refuter 163/286 -- both single probes, disagreeing by one, and both differ from 449/0.
Neither wins by authority (fan-out-contract rule 4: read the probe, do not vote), so this
derives it again from COMMITTED blobs at a PINNED rev with the predicate written out, and then
tries to REPRODUCE each prior figure so the +-1 is explained rather than argued.

Sections
  A  population: the 449 ids, presence in the catalog, empty-requirement count
  B  distinct requirement texts (the structure the classification runs over)
  C  classification under an explicit predicate, with a both-states detector control
  D  regex-free floor: byte-identical to a requirement this lane itself ruled SATISFIABLE_NOW
  E  reconciliation: which predicate yields 164 and which yields 163
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter

REV = "5423de0f3eaae28975f62268f705ba85746312ff"
REPO = "C:/Users/Prekzursil/source/ast-integrate"


def git_show(rev: str, path: str) -> str:
    out = subprocess.run(
        ["git", "-C", REPO, "show", f"{rev}:{path}"],
        capture_output=True,
        check=True,
    )
    return out.stdout.decode("utf-8")


def blob_json(path: str) -> object:
    return json.loads(git_show(REV, path))


# The predicate, written out rather than described. A requirement "names cross-vendor" when it
# uses the literal phrase, or names the other vendor as the reviewer. Deliberately NOT keyed on
# the word "independent" -- every requirement in the corpus carries that, so it cannot separate.
CROSS = re.compile(r"cross-vendor|\bcodex\b|\bopenai\b|\bgpt-5", re.IGNORECASE)
# The narrow variant: the literal phrase only.
CROSS_LITERAL = re.compile(r"cross-vendor", re.IGNORECASE)


def main() -> int:
    ready = blob_json("command-center/READY-UNITS.json")
    catalog = blob_json("command-center/WORK-UNIT-CATALOG.json")
    vend = blob_json("command-center/p2-next/VENDOR-SATISFIABILITY.json")

    by_id = {u["id"]: u for u in catalog["work_units"]}
    ready_ids = list(ready["ready_units"])

    print(f"REV {REV[:8]}")
    print("== A population ==")
    print(f"  ready ids                    : {len(ready_ids)}")
    print(f"  distinct                     : {len(set(ready_ids))}")
    missing = [i for i in ready_ids if i not in by_id]
    print(f"  absent from catalog          : {len(missing)} {missing[:5]}")
    reqs = {
        i: (by_id[i].get("reviewer_requirement") or "") for i in ready_ids if i in by_id
    }
    empty = [i for i, r in reqs.items() if not r.strip()]
    print(f"  empty reviewer_requirement   : {len(empty)} {empty[:5]}")

    print("== B distinct requirement texts ==")
    texts = Counter(reqs.values())
    print(f"  distinct texts               : {len(texts)}")
    for text, n in texts.most_common(8):
        print(f"   {n:>4}x  {text[:96]}")

    print("== C classification (predicate above) ==")
    names = [i for i, r in reqs.items() if CROSS.search(r)]
    not_names = [i for i, r in reqs.items() if not CROSS.search(r)]
    print(f"  NAMES cross-vendor           : {len(names)}")
    print(f"  does NOT                     : {len(not_names)}")
    print(
        f"  sum == population            : {len(names) + len(not_names) == len(reqs)}"
    )

    # Detector control, both states. A predicate that says True for everything, or False for
    # everything, produces a plausible-looking split too -- so prove it discriminates on text
    # this lane has already classified by hand.
    same_vendor = (
        "one fresh-context Claude reviewer who has not seen this unit's transcript; the "
        "reviewer must try to FALSIFY the headline count before PASS"
    )
    cross_vendor = (
        "one cross-vendor Codex (openai) refuter who re-derives the counterexample from the "
        "raw artifact and NOT from this unit's report"
    )
    ctrl_neg = bool(CROSS.search(same_vendor))
    ctrl_pos = bool(CROSS.search(cross_vendor))
    print(f"  CONTROL same-vendor text     : {ctrl_neg} (want False)")
    print(f"  CONTROL cross-vendor text    : {ctrl_pos} (want True)")
    if ctrl_neg or not ctrl_pos:
        print(
            "FAILED:e1-ready-split detector does not discriminate; no count below is usable"
        )
        return 1

    print("== D regex-free floor (byte equality, no judgement) ==")
    sat_texts = {
        row["reviewer_requirement"]
        for row in vend["units"]
        if row["verdict"] == "SATISFIABLE_NOW"
    }
    rail_texts = {
        row["reviewer_requirement"]
        for row in vend["units"]
        if row["verdict"] == "RAIL_BLOCKED"
    }
    overlap = sat_texts & rail_texts
    print(f"  SATISFIABLE_NOW distinct texts: {len(sat_texts)}")
    print(f"  RAIL_BLOCKED distinct texts   : {len(rail_texts)}")
    print(f"  OVERLAP control (want 0)      : {len(overlap)}")
    floor = sorted(i for i, r in reqs.items() if r in sat_texts)
    print(
        f"  READY units byte-identical to a SATISFIABLE_NOW requirement: {len(floor)}"
    )
    print(f"    first ten: {floor[:10]}")
    floor_rail = sorted(i for i, r in reqs.items() if r in rail_texts)
    print(
        f"  READY units byte-identical to a RAIL_BLOCKED requirement   : {len(floor_rail)}"
    )

    print("== E reconciliation of the two prior figures ==")
    lit = [i for i, r in reqs.items() if CROSS_LITERAL.search(r)]
    print(
        f"  literal 'cross-vendor' only  : {len(lit)}  (complement {len(reqs) - len(lit)})"
    )
    print(
        f"  broad predicate              : {len(names)}  (complement {len(not_names)})"
    )
    delta = sorted(set(names) - set(lit))
    print(f"  in broad but not literal     : {len(delta)} {delta[:5]}")
    for i in delta[:3]:
        print(f"    {i}: {reqs[i][:150]}")

    out = {
        "rev": REV,
        "population": len(reqs),
        "names_cross_vendor": len(names),
        "not_naming": len(not_names),
        "literal_phrase_only": len(lit),
        "byte_identical_floor": len(floor),
        "floor_ids": floor,
        "overlap_control": len(overlap),
        "control_negative": ctrl_neg,
        "control_positive": ctrl_pos,
    }
    dest = f"{REPO}/command-center/p2-next/E1-READY-SPLIT.json"
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"SUCCESS:e1-ready-split wrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
