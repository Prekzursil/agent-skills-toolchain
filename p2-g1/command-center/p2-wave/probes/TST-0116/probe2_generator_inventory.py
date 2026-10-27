#!/usr/bin/env python3
# TST-0116 probe2: generator inventory vs live schema census (fail-closed).
# Rebuild 2026-10-26 (shard19-w3 resume): prior probe lost to the mid-flight
# builder death. Re-derives the receipt census test live:
#   * every named domain type (work unit, receipt, council spec, workflow DAG)
#     has a generator covering its required field space (live proptest);
#   * the receipt recorded required fields are internally consistent with the
#     receipt coverage rows (live structural surfaces have drifted since the
#     receipt era - fields.py, schemas, catalog - drift is NOTEd, not hidden);
#   * the receipt 229 recorded ungenerated ids are each schema-backed on
#     this tree (schema file present OR referenced by the live catalog,
#     underscore/hyphen normalized), none overlap the generated four;
#   * the inventory fails closed if the ungenerated set were ever empty (NC2).
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UNIT = "TST-0116"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
GENERATED = ("work_unit", "receipt", "council_spec", "workflow_dag")
fails = []
notes = []


def chk(ok, label, detail=""):
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def norm(name):
    return str(name).replace("_", "-")


def schema_name(stem):
    if stem.endswith(".schema"):
        stem = stem[: -len(".schema")]
    return stem


def live_census():
    names = set()
    for schema_dir in (REPO / "command-center" / "schema",
                       REPO / "tools" / "proptest" / "schemas"):
        for p in schema_dir.glob("*.json"):
            names.add(schema_name(p.stem))
            names.add(norm(schema_name(p.stem)))
    with (REPO / "command-center" / "WORK-UNIT-CATALOG.json").open(encoding="utf-8") as fh:
        cat = json.load(fh)
    for u in cat.get("work_units") or []:
        s = str(u.get("output_schema") or "")
        if not s:
            continue
        base = s.split("#", 1)[0].rsplit("/", 1)[-1]
        if base.endswith(".json"):
            nm = schema_name(base[: -len(".json")])
            names.add(nm)
            names.add(norm(nm))
    return names


def main():
    try:
        sys.path.insert(0, str(REPO))
        sys.path.insert(0, str(REPO / "tools"))
        from proptest.fields import GENERATED_TYPES, REQUIRED_BY_TYPE
        from proptest.generators import coverage_for
        from proptest.inventory import inventory_report
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe2 proptest-import:" + type(exc).__name__)
        return 1
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe2 artifact-unreadable:" + type(exc).__name__)
        return 1

    # 1-2) live inventory: named types generated, field-space coverage passes.
    inv = inventory_report()
    chk(inv.get("pass") is True and inv.get("coverage_ok") is True, "live-inventory-failed")
    chk(tuple(inv.get("types") or ()) == GENERATED_TYPES, "generated-types-drift",
        json.dumps(inv.get("types")))
    for kind in GENERATED_TYPES:
        cov = coverage_for(kind)
        chk(cov.get("pass") is True, "coverage-failed:" + kind, json.dumps(cov))
        chk(int(cov.get("n_examples") or 0) >= 1, "no-examples:" + kind)
    print("live inventory: %s all generated with field-space coverage" % (list(GENERATED_TYPES),))

    # 3) live schema census (files + catalog references, underscore/hyphen normalized).
    census = live_census()
    chk(len(census) > 0, "census-empty")
    for g in GENERATED_TYPES:
        chk(g in census or norm(g) in census, "generated-type-not-schema-backed:" + g)

    # 4) receipt recorded ungenerated list: consistent and schema-backed live.
    fa = (doc.get("falsifiable_answers") or {}).get("which_domain_types_have_no_generator") or {}
    ung = fa.get("ungenerated_ids") or []
    recorded_count = int(fa.get("ungenerated_count") or -1)
    chk(len(ung) == 229, "recorded-count", str(len(ung)))
    chk(recorded_count == len(ung) == 229, "count-consistency", "%s/%s" % (recorded_count, len(ung)))
    gen_norm = [norm(x) for x in GENERATED]
    overlap = [u for u in ung if u in GENERATED or norm(u) in gen_norm]
    chk(not overlap, "recorded-overlaps-generated", json.dumps(overlap))
    not_backed = [u for u in ung if u not in census and norm(u) not in census]
    chk(not not_backed, "recorded-ids-not-schema-backed", json.dumps(not_backed[:10]))
    chk(str(doc.get("answer", "")).startswith("229 "), "answer-count-drift", str(doc.get("answer"))[:60])
    print("recorded ungenerated list: 229 ids, all schema-backed live (files+catalog refs), zero overlap with the generated four")

    # 5) recorded required fields internally consistent with the receipt coverage rows.
    gi = doc.get("generator_inventory") or {}
    chk(gi.get("generated_types") == list(GENERATED_TYPES), "receipt-generated-drift")
    rec_req = gi.get("required_fields") or {}
    cov_rows = {r.get("type"): r for r in (gi.get("coverage") or [])}
    for kind in GENERATED_TYPES:
        chk(sorted(rec_req.get(kind) or []) == sorted(cov_rows.get(kind, {}).get("required_fields") or []),
            "receipt-internal-required-drift:" + kind)
        chk(bool(cov_rows.get(kind, {}).get("covered_fields")), "receipt-coverage-empty:" + kind)
    # Live structural surfaces have drifted since the receipt era: NOTE, not hide.
    for kind in GENERATED_TYPES:
        live_req = sorted(REQUIRED_BY_TYPE.get(kind) or ())
        rec = sorted(rec_req.get(kind) or [])
        if live_req != rec:
            notes.append("drift %s: receipt required=%d fields, live fields.py=%s"
                         % (kind, len(rec), live_req))
    print("receipt internal consistency: recorded required fields match coverage rows for all four types")
    for n in notes:
        print("NOTE " + n)

    # 6) NC2 fail-closed: empty ungenerated set would be a false claim of total coverage.
    live_ungenerated = census - set(GENERATED_TYPES) - {norm(g) for g in GENERATED_TYPES}
    chk(len(live_ungenerated) > 0, "nc2-live-ungenerated-empty")
    print("NC2: live ungenerated set size %d (fails closed if empty)" % len(live_ungenerated))

    if fails:
        print("FAILED:" + UNIT + "-probe2 " + "; ".join(fails))
        return 1
    print("SUCCESS:" + UNIT + "-probe2 live inventory: work_unit/receipt/council_spec/workflow_dag generated with field-space coverage; receipt 229 ungenerated ids each schema-backed (files+catalog, normalized); receipt internally consistent; ungenerated set non-empty (fail-closed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
