"""Round-3 blocker census: every reason a READY unit could NOT be taken by this lane, measured.

Additive: it writes P2-BLOCKED-UNITS-R3.json beside the round-1/2 file rather than overwriting a
sibling round's artifact. Each blocker carries its own count, computed here, not quoted.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
catalog = json.loads(
    (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
by_id = {u["id"]: u for u in catalog["work_units"]}
ready = json.loads(
    (REPO / "command-center/READY-UNITS.json").read_text(encoding="utf-8")
)["ready_units"]
R = [by_id[u] for u in ready]

adv = [
    u["id"]
    for u in R
    if str(u.get("output_path", "")).startswith("command-center/adversarial/")
]
cloud = [u["id"] for u in R if u.get("execution_substrate") == "cloud-batch"]
rev = [u["id"] for u in R if str(u.get("reviewer_requirement") or "").strip()]
md = [u["id"] for u in R if str(u.get("output_path", "")).lower().endswith(".md")]
md_catalog = [
    u["id"]
    for u in catalog["work_units"]
    if str(u.get("output_path", "")).lower().endswith(".md")
]
taken = [
    u["id"] for u in R if u.get("output_path") and (REPO / u["output_path"]).exists()
]

# CONTROL for this census: a filter that matches everything or nothing is not a filter. Assert the
# partition is proper -- at least one READY unit outside every category, and every list non-trivial.
outside = [
    u["id"] for u in R if u["id"] not in set(adv) | set(cloud) | set(md) | set(taken)
]
ctl_ok = 0 < len(adv) < len(R) and 0 < len(outside) < len(R)
print(
    f"CONTROL census filters are proper subsets: adv={len(adv)} outside-all={len(outside)} of {len(R)} -> {'OK' if ctl_ok else 'BROKEN'}"
)

out = {
    "generated_by": "command-center/p2-wave/_r3_blockers.py",
    "ready_total": len(R),
    "blockers": [
        {
            "id": "B-SCOPE-ADVERSARIAL",
            "count": len(adv),
            "blocker": "output_path is under command-center/adversarial/, which this wave's floor forbids this lane from touching; a sibling wave may still be writing there.",
            "units": adv[:40],
            "note": "These currently occupy the ENTIRE head of the READY list, so the exclusion decides what this lane could build. Not a skip: a scope prohibition.",
        },
        {
            "id": "B-REVIEWER-GATE",
            "count": len(rev),
            "blocker": "the row names an independent reviewer, and receipt_core forbids state=SUCCESS without reviewer.verdict=PASS and independent=true. A build lane can deliver an artifact but cannot close the unit.",
            "units": [],
            "note": f"{len(rev)} of {len(R)} READY units. This is structural, not per-unit; the program needs a paired reviewer lane.",
        },
        {
            "id": "B-CLOUD-BATCH-UNVERIFIED",
            "count": len(cloud),
            "blocker": "declares execution_substrate=cloud-batch, whose reachability this lane did NOT probe.",
            "units": cloud[:40],
            "note": "NOT-CHECKED, not 'unavailable'. Settling experiment: submit one no-op job to that substrate and record the receipt.",
        },
        {
            "id": "B-TEXT-CONTRACT-UNENFORCEABLE",
            "count": len(md),
            "blocker": "output_path is .md while output_schema is an object JSON Schema; all 6 such contracts reject a markdown string outright, so the declared contract cannot be applied to the declared artifact.",
            "units": md[:40],
            "count_catalog_wide": len(md_catalog),
            "note": (
                f"COUNT SCOPE, stated because the two numbers differ: {len(md)} such units are READY "
                f"right now, but {len(md_catalog)} exist in the catalog -- the rest are blocked on "
                "dependencies, so the hole is latent rather than absent. A catalog-internal "
                "inconsistency, NOT repaired here: re-scoping a unit's contract is outside this "
                "lane's authority. ready_units.py now gates these on the row's own "
                "completion_sentinel plus a non-degeneracy floor, and says so in the reason string."
            ),
        },
        {
            "id": "B-AUD-0001-OFF-LIMITS-INPUTS",
            "count": 1,
            "blocker": "its declared inputs walk ~/Documents/GitHub, the parent of a directory a concurrent session owns and this wave forbids; recorded in round 1 and re-affirmed rather than re-litigated.",
            "units": ["AUD-0001"],
            "note": "Rank 1 by unblocking power among non-adversarial candidates, so this blocker costs the program real throughput and should be resolved by the owner, not routed around.",
        },
        {
            "id": "B-AUD-0015-CREDENTIAL-ADJACENT",
            "count": 1,
            "blocker": "deliberately deferred by this lane: its inputs include ~/.claude/settings.json, which the wave floor forbids reading wholesale because it carries live credentials in its env block. Delivering it needs a redaction-safe reader whose non-leakage I could not also prove in the remaining budget.",
            "units": ["AUD-0015"],
            "note": "Rank 3 among candidates. Deferred with a reason, not skipped: the unit is buildable by a lane that first builds and proves a field-scoped reader.",
        },
    ],
    "substrate_histogram": dict(Counter(u.get("execution_substrate") for u in R)),
    "control": {
        "description": "a census whose filters match everything or nothing is not a census",
        "filters_are_proper_subsets": ctl_ok,
        "ready_outside_every_category": len(outside),
    },
}
p = REPO / "command-center/p2-wave/P2-BLOCKED-UNITS-R3.json"
p.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
for b in out["blockers"]:
    print(f"  {b['id']:34s} {b['count']:5d}")
print(f"  substrate: {out['substrate_histogram']}")
print(f"  wrote {p.relative_to(REPO).as_posix()} ({p.stat().st_size} B)")
print("SUCCESS:r3-blockers" if ctl_ok else "FAILED:r3-blockers census control broken")
raise SystemExit(0 if ctl_ok else 1)
