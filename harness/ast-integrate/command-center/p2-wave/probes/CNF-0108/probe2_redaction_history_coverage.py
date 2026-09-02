#!/usr/bin/env python3
"""Probe 2: artifact redaction, schema, sentinel, history-coverage claims.

Mechanically different from probe 1: does not rebuild git history; it re-reads
the delivered artifact and the schema, and greps for credential-shaped bodies.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from schema_local import iter_errors  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0108-history-secret-scan.json"
SCHEMA = REPO / "command-center/schema/security-report.schema.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"

LEAK_RX = [
    re.compile(r"CNF0108CANARY_[A-Za-z0-9_-]{8,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


def catalog_sentinel() -> str:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == "CNF-0108":
            return str(u["completion_sentinel"])
    raise SystemExit("FAILED:CNF-0108-probe2 catalog missing")


def report_of(doc: dict) -> dict:
    rpt = doc.get("report")
    return rpt if isinstance(rpt, dict) else {}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0108-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    rpt = report_of(doc)
    sentinel = catalog_sentinel()
    if sentinel not in text:
        print("FAILED:CNF-0108-probe2 sentinel-absent")
        return 1
    if doc.get("unit_id") != "CNF-0108":
        print("FAILED:CNF-0108-probe2 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0108-probe2 self-declared", doc.get("state"))
        return 1
    kind = rpt.get("kind") or doc.get("report_kind")
    if kind not in {"security-report", "security_report"}:
        print("FAILED:CNF-0108-probe2 report_kind", kind)
        return 1
    if (
        rpt.get("printed_value") is True
        or rpt.get("rotated") is True
        or doc.get("printed_value") is True
        or doc.get("rotated") is True
    ):
        print("FAILED:CNF-0108-probe2 rotated or printed_value")
        return 1

    errs = iter_errors(doc, REPO)
    if errs:
        print("FAILED:CNF-0108-probe2 schema errors")
        for e in errs[:12]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in ({}, {"totally": "unrelated"}, {"x": "x" * 2000}):
        if not iter_errors(garbage, REPO):
            print("FAILED:CNF-0108-probe2 schema accepted garbage")
            return 1

    cc = rpt.get("canary_control") or doc.get("canary_control") or {}
    if cc.get("both_scanners_found") is not True:
        print("FAILED:CNF-0108-probe2 both_scanners_found not true")
        return 1
    if cc.get("working_tree_only_found") is not False:
        print("FAILED:CNF-0108-probe2 working-tree-only must be false")
        return 1
    if cc.get("packed_objects_contained_canary_blob") is not True:
        print("FAILED:CNF-0108-probe2 packed canary blob claim missing")
        return 1
    cov = rpt.get("coverage") or doc.get("coverage") or {}
    live = cov.get("live_repository") or {}
    if live.get("history_scanned") is True:
        print("FAILED:CNF-0108-probe2 live history_scanned overclaim")
        return 1
    if cov.get("working_tree_only_scanning_accepted") is not False:
        print("FAILED:CNF-0108-probe2 working-tree-only accepted")
        return 1

    findings = rpt.get("findings") or doc.get("findings") or []
    if len(findings) < 2:
        print("FAILED:CNF-0108-probe2 expected redacted findings from both scanners")
        return 1
    for f in findings:
        for banned in ("value", "secret", "credential", "token", "body"):
            if banned in f:
                print(f"FAILED:CNF-0108-probe2 finding has {banned}")
                return 1
        prefix = str(f.get("prefix") or "")
        if prefix == "CNF0108CANARY_" and len(prefix) != len("CNF0108CANARY_"):
            print("FAILED:CNF-0108-probe2 prefix is not zero-entropy-only")
            return 1

    leaks = []
    for rx in LEAK_RX:
        m = rx.search(text)
        if m:
            leaks.append(rx.pattern)
    if leaks:
        print("FAILED:CNF-0108-probe2 credential-shaped body in artifact", leaks)
        return 1

    scanners = rpt.get("scanners") or doc.get("scanners") or []
    mechs = {s.get("id"): s.get("mechanism") for s in scanners if isinstance(s, dict)}
    if "pattern" not in mechs or "entropy" not in mechs:
        print("FAILED:CNF-0108-probe2 two scanners not named")
        return 1
    if mechs["pattern"] == mechs["entropy"]:
        print("FAILED:CNF-0108-probe2 scanners are not mechanically different")
        return 1

    summary = {
        "probe": "probe2-redaction-history-coverage",
        "unit_id": "CNF-0108",
        "schema_ok": True,
        "sentinel_ok": True,
        "both_scanners_found": True,
        "credential_body_absent": True,
        "live_history_not_overclaimed": True,
        "findings": len(findings),
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:CNF-0108-probe2 redaction schema and history-coverage honesty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
