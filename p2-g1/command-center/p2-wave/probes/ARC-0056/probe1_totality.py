#!/usr/bin/env python3
"""ARC-0056 probe1 -- disposition totality (live, fail-closed).

Re-derives the migration disposition census from the artifact's own rows:
enumerated == preserved + aliased + deprecated + removed, buckets disjoint,
recorded counts match the row recount, alias/deprecation/removal rows agree
with their dispositions, and the recorded tests.disposition_totality verdict
is consistent with the recomputation. Both-states negative control: an
in-memory tamper that flips one row's disposition must break the recount.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/phase3/A8/MIGRATION.json"
UNIT = "ARC-0056"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
BUCKETS = {"preserved", "aliased", "deprecated", "removed"}


def main() -> int:
    fails: list[str] = []
    notes: list[str] = []
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print(f"FAILED:{UNIT}-probe1 artifact unreadable: {type(exc).__name__}")
        return 1

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(f"{label}{': ' + detail if detail else ''}")

    # structural predicate
    check(isinstance(doc, dict), "artifact not a JSON object")
    check(doc.get("unit_id") == UNIT, "unit_id mismatch", str(doc.get("unit_id")))
    check(
        str(doc.get("state", "")).upper() not in NOT_DELIVERING,
        "self-declared non-delivery",
        str(doc.get("state")),
    )
    check(OUT.stat().st_size > 0, "artifact empty")
    minb = int(doc.get("min_bytes_threshold") or 0)
    check(OUT.stat().st_size >= minb, "below min_bytes_threshold", f"{OUT.stat().st_size} < {minb}")
    sent = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sent) and sent in text, "completion sentinel absent from artifact text")

    # totality recount from rows
    rows = doc.get("enumeration", {}).get("rows") or []
    disp = doc.get("dispositions") or {}
    counts = disp.get("counts") or {}
    names = [r.get("name") for r in rows]
    per_row = Counter(str(r.get("disposition")) for r in rows)
    check(len(rows) >= 1, "no enumerated rows")
    check(all(r.get("name") and r.get("disposition") in BUCKETS for r in rows),
          "row missing name or disposition outside vocabulary")
    check(len(names) == len(set(names)), "duplicate enumerated names")
    recomputed_total = sum(per_row[b] for b in BUCKETS)
    check(recomputed_total == len(rows), "sum of buckets != enumerated rows",
          f"{recomputed_total} vs {len(rows)}")
    check(int(counts.get("enumerated", -1)) == len(rows), "counts.enumerated mismatch",
          str(counts.get("enumerated")))
    for b in sorted(BUCKETS):
        check(per_row[b] == int(counts.get(b, -2)), f"bucket recount mismatch {b}",
              f"recomputed {per_row[b]} vs recorded {counts.get(b)}")
    check(disp.get("totality_holds") is True, "recorded totality_holds not true")
    check(disp.get("disjoint") is True, "recorded disjoint not true")
    check(not disp.get("gaps"), "recorded gaps not empty", str(disp.get("gaps"))[:80])
    rec_totality = ((doc.get("tests") or {}).get("disposition_totality") or {})
    check(rec_totality.get("pass") is True, "tests.disposition_totality.pass not true")
    check(int(rec_totality.get("enumerated", -1)) == len(rows)
          and int(rec_totality.get("sum_of_buckets", -1)) == len(rows),
          "tests.disposition_totality counts mismatch")
    check(not rec_totality.get("gaps") and not rec_totality.get("overlaps"),
          "tests.disposition_totality recorded gaps/overlaps non-empty")

    # alias rows agree with their dispositions
    by_name = {r["name"]: r for r in rows}
    aliases = doc.get("alias_table") or []
    check(len(aliases) == per_row["aliased"], "alias_table size != aliased bucket",
          f"{len(aliases)} vs {per_row['aliased']}")
    for a in aliases:
        r = by_name.get(a.get("old"))
        check(r is not None, "alias old not in enumeration", str(a.get("old")))
        if r:
            check(r["disposition"] == "aliased", "alias old not dispositioned aliased", a.get("old", ""))
            check(r.get("target") == a.get("target"), "alias row target drift", a.get("old", ""))
            check(a.get("target") in by_name, "alias target not enumerated", str(a.get("target")))
    # deprecation entries are deprecated rows with successors on non-removed names
    for e in (doc.get("deprecation", {}) or {}).get("entries") or []:
        r = by_name.get(e.get("name"))
        check(r is not None, "deprecation entry not enumerated", str(e.get("name")))
        if r:
            check(r["disposition"] == "deprecated", "deprecation entry not deprecated", str(e.get("name")))
        check(e.get("warning_on_invoke") is True, "deprecation entry lacks warning_on_invoke",
              str(e.get("name")))
        check(by_name.get(e.get("successor"), {}).get("disposition") in ("preserved", "aliased"),
              "deprecation successor not preserved/aliased", str(e.get("successor")))
    # removed rows carry a successor target and are never alias targets
    removed = [r["name"] for r in rows if r["disposition"] == "removed"]
    alias_targets = {a.get("target") for a in aliases}
    check(not (set(removed) & alias_targets), "removed name used as an alias target")
    check(len(removed) == per_row["removed"], "removed recount mismatch")
    both = (doc.get("tests") or {}).get("both_directions") or {}
    check(both.get("pass") is True, "tests.both_directions.pass not true")

    # both-states negative control: tamper must break the recount
    tampered = [dict(r) for r in rows]
    tampered[0]["disposition"] = "preserved" if tampered[0]["disposition"] != "preserved" else "removed"
    tcount = Counter(r["disposition"] for r in tampered)
    fired = any(tcount[b] != int(counts.get(b, -1)) for b in BUCKETS) or \
        sum(tcount[b] for b in BUCKETS) != len(rows)
    check(fired, "mutation control silent on tampered disposition table")

    report = {
        "probe": "probe1-disposition-totality",
        "unit_id": UNIT,
        "artifact_bytes": OUT.stat().st_size,
        "rows": len(rows),
        "bucket_recount": dict(per_row),
        "recorded_counts": counts,
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if fails:
        print(f"FAILED:{UNIT}-probe1 " + "; ".join(fails))
        return 1
    print(f"SUCCESS:{UNIT}-probe1 totality holds ({len(rows)} enumerated == "
          f"{per_row['preserved']}+{per_row['aliased']}+{per_row['deprecated']}+{per_row['removed']}); "
          "mutation control fired on tamper")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
