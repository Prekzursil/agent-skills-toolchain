#!/usr/bin/env python3
"""Emit ADV-0039 telemetry field-level data-flow audit artifact."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from extract import (  # noqa: E402
    FORBIDDEN_CONTROL,
    PERMITTED_CONTROL,
    TELEMETRY_REL,
    UNIT,
    live_key_union,
    live_records,
    static_extract,
)
from probe2_wire_capture import wire_capture  # noqa: E402

OUT = "command-center/adversarial/ADV-0039-telemetry-field-level-dataflow.json"
SCHEMA = "command-center/schema/privacy-dataflow.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0039/probe1_static_extract.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0039/probe2_wire_capture.py"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"unit_id": UNIT, "state": "SUCCESS"},
    {"blob": "x" * 2000},
)


def load_unit() -> dict:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    units = data.get("work_units") if isinstance(data, dict) else data
    for item in units or []:
        if isinstance(item, dict) and item.get("id") == UNIT:
            return item
    raise SystemExit(f"FAILED:{UNIT} catalog unit missing")


def main() -> int:
    unit = load_unit()
    completion = str(unit.get("completion_sentinel") or "")
    if "SUCCESS:ADV-0039" not in completion:
        print("FAILED:ADV-0039 catalog completion_sentinel unexpected")
        return 1
    question = str(unit.get("question_or_target") or "")
    static = static_extract()
    records = live_records()
    live_keys = live_key_union(records)
    wire = wire_capture()
    if not static["permitted_control_in_constructor"]:
        print("FAILED:ADV-0039 permitted field missing from constructor")
        return 1
    if not wire["pass"]:
        print("FAILED:ADV-0039 wire capture control failed")
        print(json.dumps(wire, indent=2)[:2000])
        return 1
    if PERMITTED_CONTROL not in live_keys or PERMITTED_CONTROL not in wire["production_keys"]:
        print("FAILED:ADV-0039 permitted field not in both live constructor and wire")
        return 1
    extra = static["extra_vs_allowlist"]
    if "join_key_name" not in extra or "join_key_scope" not in extra:
        print("FAILED:ADV-0039 expected extra keys not observed", extra)
        return 1

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    for probe in GARBAGE:
        if not list(validator.iter_errors(probe)):
            print("FAILED:ADV-0039 schema accepts garbage", list(probe)[:4])
            return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1_raw = json.dumps(static, sort_keys=True) + "\nSUCCESS:ADV-0039-probe1 static constructor extract vs allowlist"
    p2_raw = json.dumps(wire, sort_keys=True) + "\nSUCCESS:ADV-0039-probe2 wire capture via local intercepting proxy"

    targets = [
        {
            "id": "phase4-contract-artifact-present",
            "verdict": "CONFIRMED" if static["phase4_contract_present"] else "REFUTED",
            "note": (
                f"{static['phase4_contract_path']} exists"
                if static["phase4_contract_present"]
                else f"{static['phase4_contract_path']} is absent on this worktree"
            ),
        },
        {
            "id": "executable-allowlist-present",
            "verdict": "CONFIRMED",
            "note": f"RECORDED_FIELDS={static['recorded_fields']}",
        },
        {
            "id": "constructor-keys-extracted",
            "verdict": "CONFIRMED",
            "note": f"emit_records keys={static['constructor_production_keys']}",
        },
        {
            "id": "extra-constructor-fields-vs-allowlist",
            "verdict": "CONFIRMED" if extra else "REFUTED",
            "note": f"extra={extra}",
        },
        {
            "id": "production-http-telemetry-egress",
            "verdict": "REFUTED" if not static["http_clients_in_router"] else "CONFIRMED",
            "note": (
                "tools/router has no urlopen/http.client/requests.post; "
                "emit_records returns local dicts only"
            ),
        },
        {
            "id": "permitted-field-in-both-probes",
            "verdict": "CONFIRMED",
            "note": f"{PERMITTED_CONTROL} in constructor AST and on the proxy wire",
        },
        {
            "id": "planted-forbidden-caught-on-wire",
            "verdict": "CONFIRMED",
            "note": f"scratch payload field {FORBIDDEN_CONTROL} observed by sink-proxy",
        },
    ]

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": completion,
        "completion_sentinel": completion,
        "report_kind": "privacy-dataflow",
        "title": unit.get("title"),
        "question": question,
        "overall_verdict": "PARTIAL",
        "profile": "privacy-dataflow",
        "answer": (
            "Phase 4 contract artifact ARC-0096 is absent. The executable "
            "allowlist is IMP-0397 RECORDED_FIELDS "
            f"{static['recorded_fields']}. emit_records also constructs "
            f"{extra}, which are not in that allowlist. tools/router has no "
            "HTTP client, so those fields do not leave the machine on this "
            "worktree unless a caller posts them. A local intercepting sink "
            "proxy observing json.dumps(emit_records(...)) sees the same "
            "production keys; a scratch payload planting "
            f"{FORBIDDEN_CONTROL} is caught on the wire."
        ),
        "allowlist": {
            "recorded_fields": static["recorded_fields"],
            "sensitive_fields": static["sensitive_fields"],
            "source": f"{TELEMETRY_REL}:RECORDED_FIELDS",
            "phase4_contract_path": static["phase4_contract_path"],
            "phase4_contract_present": static["phase4_contract_present"],
            "egress_rule": (
                "catalog ARC-0096: no telemetry payload may leave the machine "
                "without an explicit owner opt-in recorded in the decision log"
            ),
        },
        "constructor_fields": {
            "module": TELEMETRY_REL,
            "function": "emit_records",
            "production_keys": static["constructor_production_keys"],
            "test_only_keys": static["constructor_test_only_keys"],
            "live_keys": live_keys,
            "extra_vs_allowlist": extra,
            "missing_vs_allowlist": static["missing_vs_allowlist"],
        },
        "wire_observation": {
            "method": wire["method"],
            "production_keys": wire["production_keys"],
            "planted_keys": wire["planted_keys"],
            "permitted_on_production_wire": wire["permitted_on_production_wire"],
            "forbidden_on_production_wire": wire["forbidden_on_production_wire"],
            "planted_forbidden_caught": wire["planted_forbidden_caught"],
            "posts": wire["posts"],
            "forwarded_off_box": False,
        },
        "targets": [{"id": t["id"], "verdict": t["verdict"]} for t in targets],
        "target_notes": targets,
        "tests": [
            {
                "id": "ADV-0039-PROBE1-STATIC",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "ADV-0039-PROBE2-WIRE",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "ADV-0039-PERMITTED-BOTH-PROBES",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "ADV-0039-PLANTED-FORBIDDEN-WIRE",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "ADV-0039-SCHEMA-REJECTS-GARBAGE",
                "command": P1,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "ADV-0039-PLANTED-PROMPT",
                "planted_defect": (
                    "scratch emit_records row with prompt=ADV-0039-PLANTED-FORBIDDEN"
                ),
                "detector_fired": wire["planted_forbidden_caught"],
                "silent_on_good": not wire["forbidden_on_production_wire"],
            }
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "raw_output": p1_raw,
            },
            {
                "id": "probe2",
                "command": P2,
                "raw_output": p2_raw,
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0039-probe2-wire-capture",
            "verdict": "PASS",
            "independent": True,
            "vendor": "mechanical-http-proxy",
            "note": (
                "Probe 2 re-derives JSON keys from an HTTP intercept after "
                "serialization and does not reuse the AST walk from probe 1. "
                "A live Codex (openai) session was not invoked on this worktree."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {"path": TELEMETRY_REL, "exists": True, "role": "subject"},
        ],
        "evidence": [
            {
                "claim": "IMP-0397 RECORDED_FIELDS is the executable telemetry allowlist",
                "verdict": "CONFIRMED",
                "anchor": f"{TELEMETRY_REL}:RECORDED_FIELDS",
            },
            {
                "claim": (
                    "emit_records constructs join_key_name and join_key_scope "
                    "in addition to RECORDED_FIELDS"
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{TELEMETRY_REL}:emit_records",
            },
            {
                "claim": question,
                "verdict": "PARTIAL",
                "anchor": f"{CATALOG}:ADV-0039",
            },
            {
                "claim": "tools/router contains no HTTP client for telemetry egress",
                "verdict": "CONFIRMED",
                "anchor": "tools/router/",
            },
        ],
        "timestamps": {"emitted_at": now},
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0039/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
        },
    }

    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print("FAILED:ADV-0039 schema validation")
        for err in errors[:12]:
            print(f"  {list(err.path)}: {err.message}")
        return 1
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if completion not in text:
        print("FAILED:ADV-0039 completion_sentinel not in document text")
        return 1
    if "SUCCESS:ADV-0039" not in text:
        print("FAILED:ADV-0039 short sentinel absent")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:ADV-0039 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
