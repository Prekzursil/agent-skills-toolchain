#!/usr/bin/env python3
"""Probe 2: timestamp ordering check per citation edge.

Flags any citation pointing at a version of the source that predates a
known correction. The citation graph alone cannot see this. Control: the
known 2026-08-07 doc-13 correction must produce at least one
stale-downstream flag; zero flags on that known case means the check is inert.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import engine as E  # noqa: E402
import schema_local as SL  # noqa: E402

ART = REPO / "command-center/audit/AUD-0074-source-lineage-graph.json"
SCHEMA = REPO / "command-center/schema/audit-graph.schema.json"
SENTINEL = "SUCCESS:AUD-0074"
FRESH_POST = "14-NO-REGRESSION-CONTRACT.md"
NEVER_CORR = "01-BLOCKER-REPRODUCTION.md"
EARLY_NO_CITE = "16-VERIFICATION-PLAN.md"


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0074-probe2 {msg}")
    return 1


def flag_key(f: dict) -> tuple[str, str, str]:
    return (str(f.get("from")), str(f.get("to")), str(f.get("cited_version") or ""))


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if SENTINEL not in blob:
        return fail("sentinel absent")
    catalog_line = (
        "SUCCESS:AUD-0074 emitted only when the artifact at output_path exists, "
        "is non-empty, parses against output_schema, and both named probes are "
        "recorded with their verbatim output"
    )
    if catalog_line not in blob:
        return fail("completion_sentinel absent")

    if not SL.catalog_schema_on_disk():
        return fail("catalog schema missing on disk")
    errs = SL.iter_errors(doc)
    print(f"schema_errors={len(errs)}")
    if errs:
        return fail(f"schema {errs[0].message}")
    garbage_n = SL.garbage_error_count({"nope": 1})
    print(f"garbage_schema_errors={garbage_n}")
    if garbage_n < 1:
        return fail("schema does not discriminate garbage")

    pack = C.load()
    edges = E.extract_citation_edges(pack["records"])
    flags = E.flag_stale(edges, pack["corrections"])
    doc13 = E.doc13_stale(flags)
    blind = E.timestamp_blind_flags(edges)
    recorded = [f for f in (doc.get("stale_downstream") or []) if isinstance(f, dict)]
    rec_keys = {flag_key(f) for f in recorded}
    live_keys = {flag_key(f) for f in flags}

    print(
        json.dumps(
            {
                "probe": "probe2-timestamp-order",
                "unit_id": "AUD-0074",
                "live_stale": len(flags),
                "recorded_stale": len(recorded),
                "doc13_stale": [f["from"] for f in doc13],
                "blind_mutant": len(blind),
                "equal": rec_keys == live_keys,
            },
            sort_keys=True,
        )
    )
    if not doc13:
        return fail("known doc-13 correction produced zero stale-downstream flags; timestamp check is inert")
    if rec_keys != live_keys:
        return fail(f"stale set mismatch live={sorted(live_keys)} rec={sorted(rec_keys)}")
    headline = doc.get("headline") or {}
    if int(headline.get("stale_downstream_count") or -1) != len(flags):
        return fail("headline stale_downstream_count disagrees with live")
    if int(headline.get("doc13_stale_downstream_count") or -1) != len(doc13):
        return fail("headline doc13 count disagrees with live")

    if any(f["from"] == FRESH_POST for f in flags):
        return fail("post-correction cite of doc 13 was flagged")
    if any(f["from"] == NEVER_CORR for f in flags):
        return fail("never-corrected inventory cite was flagged")
    if any(f["from"] == EARLY_NO_CITE for f in flags):
        return fail("early file with no doc-13 cite was flagged")
    if blind:
        return fail("timestamp-blind mutant produced flags")

    print(
        "negative_control verbatim: known doc-13 correction FIRES stale-downstream "
        f"on {sorted({f['from'] for f in doc13})}; post-correction "
        f"{FRESH_POST} and never-corrected {NEVER_CORR} are SILENT; "
        f"timestamp-blind mutant flags={len(blind)}."
    )
    print("SUCCESS:AUD-0074-probe2 timestamp order flags known doc-13 stale-downstream")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
