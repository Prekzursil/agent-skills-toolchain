#!/usr/bin/env python3
"""Probe 1: post-citation snapshots are rejected; archived bodies are not executed.

A snapshot captured AFTER the citation date does not establish what was true
at citation time. Instruction-shaped text in an archived body is recorded and
never executed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import auditor as A  # noqa: E402
from archive import EXEC_MARKER, capture_on_or_before  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0070-archival-corroboration.json"
SCHEMA = REPO / "command-center/schema/citation-audit.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0070-probe1 {msg}")
    return 1


def main() -> int:
    if EXEC_MARKER.is_file():
        EXEC_MARKER.unlink()

    honest = A.audit_all(accept_late=False)
    naive = A.audit_all(accept_late=True)
    h = A.by_id(honest)
    n = A.by_id(naive)

    if EXEC_MARKER.is_file():
        return fail("archived payload was executed (marker file appeared)")

    never_row = h.get("C-NEVER")
    if never_row is None:
        return fail("C-NEVER missing")
    late = [
        s
        for s in never_row["snapshots_considered"]
        if s.get("rejection_reason") == "capture-after-citation-date"
    ]
    if not late:
        return fail("C-NEVER late snapshot was not rejected")
    if any(s.get("quote_located") for s in late) is False:
        return fail("expected the late C-NEVER snapshot to contain the quote")
    if never_row["verdict"] != A.NEVER:
        return fail(f"C-NEVER verdict={never_row['verdict']} want={A.NEVER}")
    if never_row.get("archived_corroboration"):
        return fail("C-NEVER used a corroboration (late quote must not count)")

    naive_never = n.get("C-NEVER")
    if naive_never["verdict"] != A.WAS_TRUE:
        return fail(
            f"naive late-accept control did not flip C-NEVER to {A.WAS_TRUE} "
            f"(got {naive_never['verdict']})"
        )
    print("post_citation_rejected=true naive_late_accept_would_misclassify=true")

    post = h.get("C-POSTDATE")
    if post is None or post["verdict"] != A.NO_SNAP:
        return fail(f"C-POSTDATE verdict={None if post is None else post['verdict']}")
    if not post["rejected_snapshots"]:
        return fail("C-POSTDATE had no rejected snapshots")
    if post.get("archived_corroboration"):
        return fail("C-POSTDATE treated a late snapshot as corroboration")

    untrusted = h.get("C-UNTRUSTED")
    if untrusted is None:
        return fail("C-UNTRUSTED missing")
    if not untrusted["untrusted_instructions_recorded"]:
        return fail("instruction-shaped archive text was not recorded")
    if untrusted["archived_content_executed"] is not False:
        return fail("archived_content_executed is not false")
    if untrusted["verdict"] != A.WAS_TRUE:
        return fail(f"C-UNTRUSTED verdict={untrusted['verdict']}")
    print(
        "untrusted_recorded="
        f"{len(untrusted['untrusted_instructions_recorded'])} executed=false"
    )

    same = h.get("C-SAMEDAY")
    if same is None or same["verdict"] != A.WAS_TRUE:
        return fail(f"C-SAMEDAY same-calendar-date capture not accepted")
    corr = same["archived_corroboration"]
    if not capture_on_or_before(corr["capture_timestamp"], same["citation_date"]):
        return fail("C-SAMEDAY corroboration not timely")
    print(f"sameday_accepted ts={corr['capture_timestamp']}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0070":
        return fail("unit_id mismatch")
    if SENTINEL_FRAGMENT_MISSING(doc):
        return fail("sentinel-absent")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        return fail(f"schema {errs[0].message}")

    for row in doc.get("citations") or []:
        corr = row.get("archived_corroboration")
        if not corr:
            continue
        if not capture_on_or_before(corr["capture_timestamp"], row["citation_date"]):
            return fail(
                f"{row.get('id')} corroboration capture {corr['capture_timestamp']} "
                f"after citation {row['citation_date']}"
            )
        if not corr.get("snapshot_url") or corr.get("located_quote") is None:
            return fail(f"{row.get('id')} corroboration missing url/quote")
        if row.get("live_versus_snapshot_diff") in (None, ""):
            return fail(f"{row.get('id')} missing live-versus-snapshot diff")
    print("every_archived_corroboration_timely=true")
    print("SUCCESS:CNF-0070-probe1 timestamp-gate untrusted-nonexec")
    return 0


def SENTINEL_FRAGMENT_MISSING(doc: dict) -> bool:
    text = json.dumps(doc)
    return "SUCCESS:CNF-0070" not in text or "capture timestamp at or before the citation date" not in text


if __name__ == "__main__":
    raise SystemExit(main())
