"""AUDIT probe 2: independently enumerate the BLOCKED unit population from disk.

INDEPENDENT of the builder's vendor_satisfiability.py -- this walks command-center/**.json
itself, keys on the catalog unit-id set, and reports its own tallies.

Detector control (both states): plants a synthetic BLOCKED receipt in a temp dir and confirms
the classifier FIRES on it, and confirms it stays SILENT on a DELIVERED-shaped one.
"""

from __future__ import annotations

import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CC = REPO / "command-center"
CATALOG = CC / "WORK-UNIT-CATALOG.json"

ID_RE = re.compile(r"^[A-Z]{2,4}-\d{4}$")


def load(p):
    with io.open(p, encoding="utf-8") as fh:
        return json.load(fh)


def classify(obj):
    """Return (unit_id, state) if this JSON object looks like a unit receipt, else None."""
    if not isinstance(obj, dict):
        return None
    uid = obj.get("unit_id") or obj.get("id")
    if not isinstance(uid, str) or not ID_RE.match(uid):
        return None
    st = obj.get("state")
    if not isinstance(st, str):
        return None
    return uid, st.upper()


def main():
    cat = load(CATALOG)
    unit_ids = {r["id"] for r in cat["work_units"]}
    by_id = {r["id"]: r for r in cat["work_units"]}
    print(f"catalog unit ids: {len(unit_ids)}")

    found = {}  # uid -> list of (path, state)
    scanned = 0
    for p in sorted(CC.rglob("*.json")):
        scanned += 1
        try:
            obj = load(p)
        except Exception:
            continue
        c = classify(obj)
        if not c:
            continue
        uid, st = c
        if uid not in unit_ids:
            continue
        found.setdefault(uid, []).append(
            (str(p.relative_to(REPO)).replace("\\", "/"), st)
        )

    print(f"json files scanned: {scanned}")
    print(
        f"receipt-shaped files keyed to a catalog unit: {sum(len(v) for v in found.values())}"
    )
    print(f"distinct units with a receipt: {len(found)}")

    states = Counter()
    for uid, lst in found.items():
        for _, st in lst:
            states[st] += 1
    print("state distribution (per file):", dict(states.most_common()))

    blocked = sorted(
        uid
        for uid, lst in found.items()
        if any(st in ("BLOCKED", "FAILED") for _, st in lst)
    )
    print(f"\nAUDITOR COUNT of units with a BLOCKED/FAILED receipt: {len(blocked)}")
    print(json.dumps(blocked, indent=0))

    # dump the per-unit facts an independent split needs
    out = {}
    for uid in blocked:
        paths = [p for p, st in found[uid] if st in ("BLOCKED", "FAILED")]
        obj = load(REPO / paths[0])
        cu = by_id[uid]
        out[uid] = {
            "receipt_paths": paths,
            "state": obj.get("state"),
            "produced_by": obj.get("produced_by"),
            "catalog_assigned": cu.get("assigned_model_vendor_role"),
            "catalog_reviewer_requirement": cu.get("reviewer_requirement"),
            "failure": obj.get("failure"),
            "reviewer": obj.get("reviewer"),
        }
    dst = CC / "p2-next" / "_AUDIT-BLOCKED-POP.json"
    with io.open(dst, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    print("wrote", dst.relative_to(REPO))

    # ---- DETECTOR CONTROL (both states) ----
    good = {"unit_id": "ZZZ-9999", "state": "BLOCKED"}
    bad = {"unit_id": "ZZZ-9999", "state": "DELIVERED"}
    fires = classify(good) == ("ZZZ-9999", "BLOCKED")
    silent = classify(bad)[1] != "BLOCKED"
    notid = classify({"unit_id": "not-a-unit", "state": "BLOCKED"}) is None
    print(
        f"\nDETECTOR CONTROL fires_on_blocked={fires} silent_on_delivered={silent} rejects_bad_id={notid}"
    )
    if not (fires and silent and notid):
        print("FAILED:audit2 detector control")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
