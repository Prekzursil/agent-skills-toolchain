#!/usr/bin/env python3
"""Probe 2: tree-wide census replay + independent 10-sample review.

Re-runs the live-tree AST census and requires the receipt's live_census to
match. Re-confirms ten flagged tests by a second method (bytecode / settrace /
runtime JSON len / fresh parse). A well-formed live test must stay unflagged.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402
import reviewer as R  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0041.json"
LIVE_NEGATIVE = "tools/command-center/tests/test_validate.py::test_empty_catalog_fails_closed"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0041-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:BLD-0041" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    if doc.get("kind") != "test-quality-census":
        return fail("kind mismatch")
    if doc.get("schema_contract_discriminates") is not True:
        return fail("schema_contract_discriminates is not true")

    live = C.live_census()
    rec_live = doc.get("live_census") or {}
    rec_flagged = rec_live.get("flagged")
    if rec_flagged != live["flagged"]:
        return fail(f"live flagged receipt={rec_flagged} now={live['flagged']}")
    rec_scanned = rec_live.get("tests_scanned")
    if rec_scanned != live["tests_scanned"]:
        return fail(
            f"live tests_scanned receipt={rec_scanned} now={live['tests_scanned']}"
        )
    rec_findings = [
        (f.get("test_id"), f.get("reason_class"), f.get("line"))
        for f in rec_live.get("findings") or []
    ]
    now_findings = [
        (f.get("test_id"), f.get("reason_class"), f.get("line"))
        for f in live["findings"]
    ]
    if rec_findings != now_findings:
        return fail(f"live findings drifted {rec_findings} vs {now_findings}")
    rec_files = list(rec_live.get("files") or [])
    missing = [p for p in rec_files if not (REPO / p).is_file()]
    if missing:
        return fail(f"receipt live files vanished {missing[:5]}")
    extra = sorted(set(live["files"]) - set(rec_files))
    if extra:
        return fail(f"live files appeared after receipt {extra[:5]}")
    print(
        f"live_census tests_scanned={live['tests_scanned']} "
        f"flagged={live['flagged']} extra_files={len(extra)}"
    )

    if LIVE_NEGATIVE in live["test_ids"]:
        flagged_ids = {f["test_id"] for f in live["findings"]}
        if LIVE_NEGATIVE in flagged_ids:
            return fail("live negative control was flagged")
        print(f"live_negative_unflagged {LIVE_NEGATIVE}")
    else:
        return fail(f"live negative control missing from scan {LIVE_NEGATIVE}")

    planted = C.planted_census()
    rev = R.review_sample(planted["findings"])
    print(
        f"reviewer verdict={rev['verdict']} sampled={rev['sampled']} "
        f"confirmed={rev['confirmed']}"
    )
    if rev["verdict"] != "PASS" or rev["confirmed"] != 10:
        return fail(f"reviewer {rev['verdict']} confirmed={rev['confirmed']}")
    rec_rev = doc.get("reviewer") or {}
    # Reviewer DETAIL (confirmed/samples/scope) lives in extensions.reviewer_detail
    # because the receipt_core reviewer schema forbids additional keys; the checks
    # and thresholds are unchanged.
    rev_detail = (doc.get("extensions") or {}).get("reviewer_detail") or {}
    if rec_rev.get("independent") is not True:
        return fail("reviewer.independent is not true")
    if rec_rev.get("vendor") != "anthropic":
        return fail("reviewer vendor is not anthropic")
    if int(rev_detail.get("confirmed") or 0) != 10:
        return fail("receipt reviewer confirmed != 10")
    if rev_detail.get("scope_not_agreement") is not True:
        return fail("receipt reviewer scope_not_agreement is not true")
    for i, sample in enumerate(rev["samples"]):
        rec_row = (rev_detail.get("samples") or [None] * 10)[i]
        if not rec_row:
            return fail(f"receipt missing reviewer sample {i}")
        if rec_row.get("test_id") != sample["test_id"]:
            return fail(f"reviewer sample {i} test_id drifted")
        path = REPO / sample["path"]
        line = int(sample["line"])
        text = path.read_text(encoding="utf-8").splitlines()
        if line < 1 or line > len(text):
            return fail(f"sample {i} line oob {sample['path']}:{line}")
        snippet = (rec_row.get("notes") or sample.get("notes") or "")[:8]
        print(
            f"anchor[{i}] ok=True {sample['path']}:{line} "
            f"{sample['reason_class']} cannot_fail={sample['cannot_fail']}"
        )
        _ = snippet

    empty_class = [
        f
        for f in (doc.get("findings") or [])
        if f.get("reason_class") == "EMPTY_BENCHMARK_INPUT"
    ]
    for row in empty_class:
        if "measured_input_size" not in row:
            return fail("empty-input finding missing measured_input_size")
        if row.get("fixture_name_not_consulted") is not True:
            return fail("empty-input finding used fixture name")
        live_size = C.measure_json_input_size(
            REPO / str(row["fixture_path"])
        )
        if int(row["measured_input_size"]) != live_size:
            return fail("measured_input_size does not match re-load")
        print(
            f"empty_input runtime_size={live_size} fixture={row.get('fixture_path')}"
        )

    print("SUCCESS:BLD-0041-probe2 live census reviewer-sample-10")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
