"""AUDIT probe 4: re-derive the split from the PRE-BUILDER blobs.

WHY THIS MATTERS MORE THAN PROBE 3. Probe 3 read the receipts as they stand TODAY -- and the
builder EDITED those very receipts (899ff779 / 03349ac1 touched all 10). Their current
failure.blocked_on literally says "NOT a review blocker any more". Classifying a unit as
SATISFIABLE from text the builder wrote is circular. So: pull each receipt from the PARENT of the
builder's first commit (899ff779^) and re-run the conservative classifier on the ORIGINAL wording.

If a unit's ORIGINAL blocked_on/reviewer_requirement demanded cross-vendor review and the builder
reclassified it as satisfiable, that is the exact defect this lane was told not to commit.

Detector control: also print the pre-edit text for a unit the builder calls RAIL_BLOCKED
(ADV-0003) and confirm the classifier fires there on the pre-edit bytes -- proving the pre-edit
reader is not just returning SATISFIABLE for everything (e.g. because a path was wrong).
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
POP = REPO / "command-center" / "p2-next" / "_AUDIT-BLOCKED-POP.json"
BASE = "899ff779^"

CROSS = re.compile(
    r"cross[-_ ]?vendor|cross[-_ ]?model|different\s+vendor|other\s+vendor|separate\s+vendor"
    r"|\bopenai\b|\bcodex\b|gpt-?5|non[-_ ]?anthropic",
    re.I,
)
TEN = [
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
]


def show(rev: str, path: str) -> str | None:
    r = subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return r.stdout if r.returncode == 0 else None


def op_fields(obj: dict) -> dict:
    f = obj.get("failure") or {}
    return {
        "receipt.reviewer_requirement": obj.get("reviewer_requirement") or "",
        "failure.blocked_on": f.get("blocked_on") or "",
        "failure.classification": json.dumps(f.get("classification") or []),
        "reviewer(pre-edit)": json.dumps(obj.get("reviewer") or {})[:200],
    }


def main() -> int:
    pop = json.load(io.open(POP, encoding="utf-8"))
    bad = []
    print(f"=== PRE-BUILDER ({BASE}) operative text of the 10 ===")
    for uid in TEN:
        path = pop[uid]["receipt_paths"][0]
        raw = show(BASE, path)
        if raw is None:
            print(f"\n--- {uid} :: {path}  *** DID NOT EXIST at {BASE} (new file) ***")
            bad.append((uid, "absent-preedit"))
            continue
        obj = json.loads(raw)
        fields = op_fields(obj)
        hits = []
        for k, v in fields.items():
            if k == "reviewer(pre-edit)":
                continue
            m = CROSS.search(v)
            if m:
                hits.append(f"{k}~'{m.group(0)}'")
        v = "RAIL_BLOCKED" if hits else "SATISFIABLE"
        print(f"\n--- {uid} :: {path}  PRE-EDIT VERDICT={v} state={obj.get('state')}")
        for k, val in fields.items():
            print(f"   {k}: {val[:300]}")
        if hits:
            print(f"   *** CROSS-VENDOR HITS: {hits}")
            bad.append((uid, hits))

    print(
        f"\nPRE-EDIT: of the 10 claimed satisfiable, {len(bad)} would be RAIL_BLOCKED/absent: {bad}"
    )

    # ---- CONTROL: a builder-declared RAIL_BLOCKED unit must FIRE on its pre-edit bytes ----
    ctrl = "ADV-0003"
    cpath = pop[ctrl]["receipt_paths"][0]
    raw = show(BASE, cpath)
    print(f"\n=== CONTROL {ctrl} :: {cpath} present_at_base={raw is not None}")
    if raw:
        obj = json.loads(raw)
        f = op_fields(obj)
        fired = any(CROSS.search(v) for k, v in f.items() if k != "reviewer(pre-edit)")
        for k, val in f.items():
            print(f"   {k}: {val[:300]}")
        print(f"   CONTROL fires_on_railblocked_preedit={fired}")
        if not fired:
            print("FAILED:audit4 control did not fire -- pre-edit reader is inert")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
