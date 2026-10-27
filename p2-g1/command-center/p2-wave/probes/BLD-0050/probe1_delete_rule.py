#!/usr/bin/env python3
"""BLD-0050 probe1 - structural + sentinel delivery predicate (live, fail-closed).

Checks the 27-boundary census (ids unique, check_status vocabulary), the counts identity 27 = 4 checked + 22 unchecked + 1 consumed, the deliverable number, and the two bidirectional direction pairs.
Recreated 2026-10-25 (wave-2 shard 7) after the original probe tree was lost.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = REPO / "command-center/receipts/BLD-0050.json"
UNIT = "BLD-0050"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def main() -> int:
    fails = []
    notes = []

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(label + (": " + detail if detail else ""))

    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:%s-probe1 artifact unreadable/unparseable: %s" % (UNIT, type(exc).__name__))
        return 1
    if not isinstance(doc, dict):
        print("FAILED:%s-probe1 artifact is not a JSON object" % UNIT)
        return 1

    check(doc.get("unit_id") == UNIT, "unit_id mismatch", str(doc.get("unit_id")))
    check(str(doc.get("state", "")).upper() not in NOT_DELIVERING,
          "self-declared non-delivery", str(doc.get("state")))
    check(OUT.stat().st_size > 0, "artifact empty")
    minb = int(doc.get("min_bytes_threshold") or 0)
    check(OUT.stat().st_size >= minb, "below min_bytes_threshold",
          "%s < %s" % (OUT.stat().st_size, minb))
    sentinel = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sentinel) and sentinel in text, "sentinel absent from artifact text")

    rows = doc.get("boundaries") or []
    counts = doc.get("counts") or {}
    check(len(rows) == 27, "boundary rows != 27", str(len(rows)))
    ids_ = [str(r.get("id")) for r in rows]
    check(len(set(ids_)) == 27, "boundary ids not unique")
    check(all(str(r.get("check_status")).upper() in {"CHECKED", "UNCHECKED", "CONSUMED"} for r in rows),
          "check_status outside vocabulary")
    check(all(str(r.get("crossing", "")).strip() for r in rows), "boundary row missing crossing")
    recomputed = {
        "checked": sum(1 for r in rows if str(r.get("check_status")).upper() == "CHECKED"),
        "unchecked": sum(1 for r in rows if str(r.get("check_status")).upper() == "UNCHECKED"),
        "consumed": sum(1 for r in rows if str(r.get("check_status")).upper() == "CONSUMED"),
        "boundaries_total": len(rows),
    }
    check(recomputed["checked"] == int(counts.get("checked", -1)), "checked count drift", str(recomputed))
    check(recomputed["unchecked"] == int(counts.get("unchecked", -1)), "unchecked count drift", str(recomputed))
    check(recomputed["consumed"] == int(counts.get("consumed", -1)), "consumed count drift", str(recomputed))
    check(recomputed["checked"] + recomputed["unchecked"] + recomputed["consumed"] == len(rows),
          "counts identity fails", str(recomputed))
    check(int(counts.get("boundaries_in_no_existing_threat_model", -1)) == 27 == int(counts.get("boundaries_total", -1)),
          "deliverable count != 27", str(counts.get("boundaries_in_no_existing_threat_model")))
    deliv = doc.get("deliverable") or {}
    check(str(deliv.get("name")) == "boundaries_found_in_no_existing_threat_model",
          "deliverable name drift", str(deliv.get("name")))
    pairs = doc.get("direction_pairs") or []
    check(len(pairs) >= 2, "direction pairs < 2", str(len(pairs)))
    bad_pairs = []
    for p in pairs:
        pid = str(p.get("pair_id"))
        ids_p = p.get("ids") or []
        if not pid or not ids_p:
            bad_pairs.append(pid + ":empty")
        elif p.get("bidirectional") is True:
            if len(ids_p) != 2 or p.get("distinct_checks") is not True:
                bad_pairs.append(pid + ":bidir-needs-2-ids+distinct-checks")
        else:
            # unidirectional is legal only for the consumed single-boundary row
            if len(ids_p) != 1 or str(ids_p[0]) != "TB-INSTALL-ADV0021":
                bad_pairs.append(pid + ":unidir-not-consumed-row")
    check(not bad_pairs, "direction pair shape drift", str(bad_pairs[:4]))
    sm = doc.get("site_map") or {}
    check(len(sm) > 0 and all(v in ids_ for v in sm.values()),
          "site_map values must resolve to boundary ids", str(len(sm)))
    adv21 = REPO / "command-center" / "adversarial" / "ADV-0021-install-path-stride-threat-model.json"
    check(adv21.is_file(), "consumed ADV-0021 threat model absent live", str(adv21))
    walk = HERE / "walk.py"
    census = HERE / "census.py"
    check(walk.is_file() and census.is_file(), "instrument walk.py/census.py missing")

    report = {
        "probe": "probe1-delivery-predicate",
        "unit_id": UNIT,
        "artifact_bytes": OUT.stat().st_size,
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1))
    if fails:
        print("FAILED:%s-probe1 %s" % (UNIT, "; ".join(fails)))
        return 1
    print("SUCCESS:%s-probe1 delivery predicate holds" % UNIT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
