#!/usr/bin/env python3
"""Probe 1: enumerator control + instrumentation-vs-intent control + schema.

Live re-run of the algebra. A reserved-name drop or a nested-archive drop is a
false-clean DIFFERENCE. COVERED must be opens, not the walker's intent list.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

ART = L.REPO / L.OUT_REL


def fail(msg: str, payload: dict | None = None) -> int:
    if payload is not None:
        print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"FAILED:ADV-0141-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    raw = ART.read_text(encoding="utf-8")
    doc = json.loads(raw)
    if L.SENTINEL not in raw:
        return fail("sentinel-absent")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    errs = L.schema_errors(doc)
    if errs:
        return fail("schema-invalid", {"errs": errs[:8]})
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    if not L.schema_errors(garbage):
        return fail("schema-vacuous-garbage")

    m = L.measure(L.UNIVERSE)
    if not m["nul_ok"]:
        return fail("reserved NUL missing from PRODUCED")
    if not m["nested_ok"]:
        return fail("nested archive member missing from PRODUCED")
    if m["excluded_in_covered"]:
        return fail(
            "excluded_by_config appeared in COVERED (instrumentation recorded intent)",
            {"covered": m["covered_paths"]},
        )
    if not m["intent_has_excluded"]:
        return fail("intent walker did not see excluded_by_config (control silent)")
    if m["state"] != "SUCCESS":
        return fail("live algebra not SUCCESS", {"controls": m["controls"]})

    produced_paths = {r["path"] for r in m["produced_rows"]}
    if "reserved/NUL" not in produced_paths:
        return fail("produced path reserved/NUL missing", {"paths": sorted(produced_paths)})
    if not any("inner.zip!hidden.txt" in p for p in produced_paths):
        return fail("produced nested hidden.txt missing")

    art_cov = {r["path"] for r in (L.report_view(doc).get("COVERED") or [])}
    if any(p.startswith("excluded_by_config/") for p in art_cov):
        return fail("artifact COVERED contains excluded_by_config")
    rep = L.report_view(doc)
    if rep.get("covered_measurement") != "instrumentation":
        return fail("covered_measurement is not instrumentation")
    if (rep.get("instrumentation") or {}).get("not_glob_config") is not True:
        return fail("instrumentation.not_glob_config is not true")

    payload = {
        "probe": "probe1-enumerator-and-instrumentation",
        "nul_in_produced": True,
        "nested_member_in_produced": True,
        "excluded_in_covered": False,
        "intent_walker_sees_excluded": True,
        "schema_rejects_garbage": True,
        "covered_count": len(m["covered_paths"]),
        "produced_count": len(m["produced_rows"]),
        "pass": True,
        "unit_id": L.UNIT,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print("SUCCESS:ADV-0141-probe1 enumerator and instrumentation controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
