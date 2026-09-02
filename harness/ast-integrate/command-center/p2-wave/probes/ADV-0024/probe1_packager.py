#!/usr/bin/env python3
"""Named probe 1: packager exit code plus diagnostic per fixture."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

ART = L.REPO / L.OUT_REL
LEGAL = L.LEGAL


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0024-probe1 {msg}")
    return 1


def main() -> int:
    m = L.measure()
    report = L.format_probe1(m)
    print(report, end="" if report.endswith("\n") else "\n")
    if not m["clean_ok"]:
        return fail("clean-control fixtures did not package")
    if not m["mutant_packages_clean"]:
        return fail("mutant did not package the clean control")
    if not m["mutant_refuses_token"]:
        return fail("mutant did not loudly refuse the token fixture")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return fail("artifact-unparseable")
    if not isinstance(doc, dict):
        return fail("artifact-not-object")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if L.catalog_sentinel() not in text:
        return fail("sentinel-absent")
    if L.PROBE1_NAME not in text:
        return fail("probe1-name-absent")
    errs = L.schema_errors(doc)
    if errs:
        return fail(f"schema:{errs[0]}")
    garbage = {"unit_id": "ADV-0024", "state": "SUCCESS"}
    if not L.schema_errors(garbage):
        return fail("schema-vacuous-garbage")
    raw = ""
    for p in doc.get("named_probes") or []:
        if isinstance(p, dict) and p.get("id") == "probe1":
            raw = str(p.get("raw_output") or "")
    if raw != report:
        return fail("named-probe1-raw-mismatch")
    live = {t["target_id"]: t["verdict"] for t in m["targets"]}
    seen: set[str] = set()
    for t in doc.get("targets") or []:
        if not isinstance(t, dict):
            continue
        tid = t.get("target_id")
        if tid in seen:
            return fail(f"duplicate-target:{tid}")
        seen.add(str(tid))
        if t.get("verdict") not in LEGAL:
            return fail(f"illegal-verdict:{tid}")
        if live.get(tid) != t.get("verdict"):
            return fail(f"verdict-drift:{tid}")
    if set(live) - seen:
        return fail("target-set-drift")
    if live.get("token-shaped-file") != "CONFIRMED":
        return fail("token-target-not-confirmed")
    if doc.get("overall_verdict") != m["overall_verdict"]:
        return fail("overall-verdict-drift")
    print("SUCCESS:ADV-0024-probe1 packager-exit-diagnostic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
