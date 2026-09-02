#!/usr/bin/env python3
"""Probe 1: re-run live harvest and field-diff; compare to the artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from checker import leak_needles_in  # noqa: E402
from harvest import canonical_live, harvest_live  # noqa: E402
from paths import (  # noqa: E402
    CATALOG_SENTINEL,
    LOCAL_SCHEMA_REL,
    OUT_REL,
    QUESTION,
    REPO,
    UNIT,
)
from suite import decision_ids, live_payload_results, load_json  # noqa: E402

FIXTURES = HERE / "fixtures"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    art = REPO / OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact missing")
    text = art.read_text(encoding="utf-8")
    if CATALOG_SENTINEL not in text:
        return fail("catalog sentinel absent")
    leaks = leak_needles_in(text)
    if leaks:
        return fail(f"artifact leaked sensitive canaries {leaks}")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT:
        return fail("unit_id mismatch")
    if QUESTION not in (doc.get("question") or ""):
        return fail("question drifted")

    schema = json.loads((REPO / LOCAL_SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        return fail(f"schema {errs[0].message}")
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(jsonschema.Draft7Validator(schema).iter_errors(garbage)):
            return fail("schema accepted garbage")

    live = harvest_live()
    fresh = canonical_live(live)
    recorded = doc.get("live_canonical") or {}
    if recorded != fresh:
        print(json.dumps({"recorded": recorded, "fresh": fresh}, sort_keys=True)[:4000])
        return fail("live harvest drifted from artifact")

    log_ids = decision_ids(load_json(FIXTURES / "decision_log.json"))
    checked = live_payload_results(live, log_ids)
    if checked != (doc.get("live_checked") or []):
        return fail("live payload field-diff drifted")

    if not doc.get("empty_live_is_not_a_pass"):
        return fail("artifact treats empty live capture as a pass")
    if fresh["payload_count"] == 0 and not doc.get("negative_controls"):
        return fail("empty live capture without negative controls")

    reviewers = doc.get("reviewers") or []
    if len(reviewers) < 2:
        return fail("need two reviewers")
    for rev in reviewers:
        if rev.get("independent") is not True:
            return fail("reviewer not independent")
        if rev.get("saw_other_verdict_before_filing") is not False:
            return fail("reviewer saw the other verdict")

    out = {
        "canonical_match": True,
        "emitter_files": len(fresh["emitter_files"]),
        "pass": True,
        "payload_count": fresh["payload_count"],
        "probe": "probe1-live-capture",
        "unit_id": UNIT,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"payloads={fresh['payload_count']} emitters={len(fresh['emitter_files'])} "
        f"match=True leaks=0"
    )
    print(f"SUCCESS:{UNIT}-probe1 live capture matches artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
