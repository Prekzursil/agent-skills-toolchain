#!/usr/bin/env python3
"""Probe 2: independent GitHub Advisory re-scan plus artifact diff/snapshot check.

Different network egress (api.github.com) from probe 1 (api.osv.dev).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scanner as S  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0153.json"
SCHEMA = REPO / "command-center/schema/program-gate-report.schema.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"


def catalog_sentinel() -> str:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == "CNF-0153":
            return str(u["completion_sentinel"])
    raise SystemExit("FAILED:CNF-0153-probe2 catalog missing")


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0153-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    sentinel = catalog_sentinel()
    if sentinel not in text:
        print("FAILED:CNF-0153-probe2 sentinel-absent")
        return 1
    if doc.get("unit_id") != "CNF-0153":
        print("FAILED:CNF-0153-probe2 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0153-probe2 self-declared", doc.get("state"))
        return 1
    if doc.get("report_kind") != "program-gate-report":
        print("FAILED:CNF-0153-probe2 report_kind")
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0153-probe2 schema errors")
        for e in errs[:12]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in ({}, {"totally": "unrelated"}, {"x": "x" * 2000}):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0153-probe2 schema accepted garbage")
            return 1

    try:
        vuln, vmeta = S.query_ghsa("lodash", "4.17.11")
        clean, cmeta = S.query_ghsa("bytes", "3.1.2")
    except S.BlockedExternal as exc:
        print(f"FAILED:CNF-0153-probe2 blocked prerequisite={exc.prerequisite}")
        return 1

    active = [f for f in vuln if not f.get("withdrawn")]
    if not active:
        print("FAILED:CNF-0153-probe2 GHSA silent on lodash@4.17.11")
        return 1
    if clean:
        print("FAILED:CNF-0153-probe2 GHSA bytes@3.1.2 not clean", [f["id"] for f in clean])
        return 1

    diff = doc.get("advisory_diff")
    if not isinstance(diff, dict) or "added" not in diff or "removed" not in diff:
        print("FAILED:CNF-0153-probe2 advisory_diff added/removed not published")
        return 1
    if not isinstance(diff.get("added"), list) or not isinstance(diff.get("removed"), list):
        print("FAILED:CNF-0153-probe2 added/removed must be lists")
        return 1

    snap = ((doc.get("evidence") or {}).get("snapshot") or {})
    if not snap.get("identifier") or not snap.get("query_timestamp_utc"):
        print("FAILED:CNF-0153-probe2 snapshot missing")
        return 1

    gates = doc.get("gates") or []
    if not gates:
        print("FAILED:CNF-0153-probe2 no gates")
        return 1
    g0 = gates[0]
    if g0.get("still_a_control_today") is True:
        print("FAILED:CNF-0153-probe2 stored green still_a_control_today=true without snapshot")
        return 1
    if g0.get("live_query") is not True:
        print("FAILED:CNF-0153-probe2 gate not classified live_query")
        return 1

    filed = doc.get("filed_advisories") or []
    if len(filed) < 1:
        print("FAILED:CNF-0153-probe2 no filed advisories")
        return 1
    for row in filed:
        if not row.get("id") or not row.get("severity") or not row.get("affected_artifact"):
            print("FAILED:CNF-0153-probe2 filed advisory missing severity or artifact")
            return 1

    tests = {t.get("id"): t.get("result") for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in (
        "detector-known-vulnerable-lodash-4.17.11",
        "both-states-known-clean-bytes-3.1.2",
        "exit-code-127-vs-1",
        "diff-added-removed-vs-stored",
    ):
        if tests.get(tid) != "PASS":
            print(f"FAILED:CNF-0153-probe2 test {tid} not PASS")
            return 1

    summary = {
        "probe": "probe2-ghsa-reviewer-diff",
        "unit_id": "CNF-0153",
        "ghsa_lodash_n_active": len(active),
        "ghsa_lodash_ids": [f["id"] for f in active],
        "ghsa_bytes_n": len(clean),
        "ghsa_http_date": vmeta.get("http_date"),
        "bytes_http_date": cmeta.get("http_date"),
        "egress": "api.github.com",
        "diff_added": diff.get("added"),
        "diff_removed": diff.get("removed"),
        "snapshot_id": snap.get("identifier"),
        "schema_ok": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:CNF-0153-probe2 GHSA reviewer egress and published diff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
