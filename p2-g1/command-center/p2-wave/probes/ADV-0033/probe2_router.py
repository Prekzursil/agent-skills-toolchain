#!/usr/bin/env python3
"""Named probe 2: static router selection, then that cell of the matrix."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

ART = L.REPO / L.OUTPUT_REL
SCHEMA = L.REPO / L.SCHEMA_REL


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0033-probe2 {msg}")
    return 1


def main() -> int:
    m = L.measure()
    report = L.probe2_report(m)
    print(report, end="")
    router = m["router"]
    if router["untrusted_routed_to"] != "local-process":
        return fail("unexpected-untrusted-route")
    if router["os_substrate_dispatcher_present"]:
        return fail("false-os-dispatcher-claim")
    if not router["plugin_hooks_spawn_local_subprocess"]:
        return fail("heartbeat-popen-missing")
    if not router["plugin_longrun_spawn_local_subprocess"]:
        return fail("longrun-run-missing")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return fail("artifact-unparseable")
    if not isinstance(doc, dict):
        return fail("artifact-not-object")
    # shard0-w2 2026-10-25 reprobe: IMP-0064 exec-policy schema+test SHIPPED
    # since the 2026-08-24 measurement. The August absence invariant is stale;
    # the live assertion is now consistency with the artifact's recorded
    # reprobe block (presence measured, routing conclusion re-derived).
    reprobe = doc.get("extensions", {}).get("reprobe_2026_10_25", {})
    live_exec = bool(router["imp0064_exec_policy_schema_present"])
    if not reprobe:
        return fail("reprobe-block-absent")
    if bool(reprobe.get("imp0064_exec_policy_schema_present")) is not live_exec:
        return fail("reprobe-exec-policy-disagrees-with-live")
    route = m["routing"]
    if route["verdict"] != "REFUTED":
        return fail(f"routing-cell-not-refuted:{route['verdict']}")
    if route["unused_sandbox_protects"]:
        return fail("unused-sandbox-overclaim")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if L.catalog_sentinel() not in text:
        return fail("sentinel-absent")
    if L.PROBE2_NAME not in text:
        return fail("probe2-name-absent")
    raw = ""
    for item in doc.get("named_probes") or []:
        if isinstance(item, dict) and item.get("id") == "probe2":
            raw = str(item.get("raw_output") or "")
    if raw != report:
        return fail("named-probe2-raw-mismatch")
    art_route = None
    for t in doc.get("targets") or []:
        if isinstance(t, dict) and t.get("target_id") == route["target_id"]:
            art_route = t
    if art_route is None:
        return fail("routing-target-absent")
    if art_route.get("verdict") != route["verdict"]:
        return fail("routing-verdict-drift")
    try:
        import jsonschema
    except ImportError:
        return fail("jsonschema-missing")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        return fail(f"schema:{errs[0].message}")
    garbage = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "ADV-0033", "state": "SUCCESS"},
    ]
    rejected = 0
    for g in garbage:
        if list(jsonschema.Draft7Validator(schema).iter_errors(g)):
            rejected += 1
    if rejected != len(garbage):
        return fail(f"schema-accepts-garbage rejected={rejected}")
    table = doc.get("defense_table") or []
    if len(table) < 4:
        return fail("defense-table-short")
    classes = set()
    for row in table:
        rails = row.get("rails") or []
        kinds = {r.get("kind") for r in rails if isinstance(r, dict)}
        if "structured_api_probe" not in kinds or "prose_source" not in kinds:
            return fail(f"{row.get('id')} missing dual rails")
        for r in rails:
            cap = Path(str(r.get("capture_path") or "")).name
            if not L.live_capture_ok(cap, str(r.get("sha256") or "")):
                return fail(f"rail-sha-mismatch:{cap}")
        classes.add(row.get("automatable/moderation-dependent"))
        bx = row.get("bypass_attempt") or {}
        if "bypasses" not in bx or "construction" not in bx:
            return fail(f"{row.get('id')} bypass incomplete")
    if "automatable" not in classes or "moderation-dependent" not in classes:
        return fail("defense-classes-not-honest")
    print("SUCCESS:ADV-0033-probe2 router-then-matrix-cell")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
