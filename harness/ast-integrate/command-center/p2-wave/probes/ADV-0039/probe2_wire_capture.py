#!/usr/bin/env python3
"""Probe 2: intercepting-proxy capture of serialized telemetry JSON keys.

Mechanically different from probe 1: real HTTP POST through a local sink
proxy after json.dumps. Catches serializer/exception keys the constructor
AST cannot see. Planted forbidden field proves capture completeness.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from extract import (  # noqa: E402
    FORBIDDEN_CONTROL,
    PERMITTED_CONTROL,
    PLANTED_VALUE,
    UNIT,
    live_records,
)
from proxy import capture_posts  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0039-telemetry-field-level-dataflow.json"
SCHEMA = REPO / "command-center/schema/privacy-dataflow.schema.json"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def wire_capture() -> dict:
    records = live_records()
    planted = dict(records[0])
    planted[FORBIDDEN_CONTROL] = PLANTED_VALUE
    captured = capture_posts([records, planted])
    production_keys = set(captured[0]["keys"])
    planted_keys = set(captured[1]["keys"])
    permitted = PERMITTED_CONTROL in production_keys
    forbidden_on_good = FORBIDDEN_CONTROL in production_keys
    planted_caught = FORBIDDEN_CONTROL in planted_keys
    return {
        "probe": "probe2-wire-capture",
        "unit_id": UNIT,
        "method": "local-http-sink-proxy",
        "production_keys": sorted(production_keys),
        "planted_keys": sorted(planted_keys),
        "permitted_on_production_wire": permitted,
        "forbidden_on_production_wire": forbidden_on_good,
        "planted_forbidden_caught": planted_caught,
        "posts": len(captured),
        "proxy_paths": [row["path"] for row in captured],
        "pass": permitted and planted_caught and not forbidden_on_good,
    }


def main() -> int:
    live = wire_capture()
    if not live["permitted_on_production_wire"]:
        return fail("permitted field missing on production wire", live)
    if live["forbidden_on_production_wire"]:
        return fail("forbidden field present on clean production wire", live)
    if not live["planted_forbidden_caught"]:
        return fail("planted forbidden field not observed on wire", live)
    if live["posts"] < 2:
        return fail("proxy did not capture both posts", live)

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    blob = json.dumps(doc)
    if f"SUCCESS:{UNIT}" not in blob:
        return fail("sentinel absent")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errors:
        return fail("artifact fails schema", errors[0].message)

    wire = doc.get("wire_observation") or {}
    if sorted(wire.get("production_keys") or []) != live["production_keys"]:
        return fail("wire production_keys mismatch", {"art": wire, "live": live})
    if wire.get("planted_forbidden_caught") is not True:
        return fail("artifact planted_forbidden_caught")
    if wire.get("permitted_on_production_wire") is not True:
        return fail("artifact permitted_on_production_wire")
    targets = {t["id"]: t["verdict"] for t in (doc.get("targets") or []) if isinstance(t, dict)}
    if targets.get("permitted-field-in-both-probes") != "CONFIRMED":
        return fail("permitted-field-in-both-probes", targets)
    if targets.get("planted-forbidden-caught-on-wire") != "CONFIRMED":
        return fail("planted-forbidden-caught-on-wire", targets)

    ncs = doc.get("negative_controls") or []
    if not ncs or ncs[0].get("detector_fired") is not True:
        return fail("negative control did not fire", ncs)
    if ncs[0].get("silent_on_good") is not True:
        return fail("negative control not silent on good", ncs)

    cmds = [p.get("command") for p in (doc.get("named_probes") or []) if isinstance(p, dict)]
    if not any("probe2_wire_capture.py" in str(c) for c in cmds):
        return fail("named probe2 command absent", cmds)

    print(json.dumps(live, sort_keys=True))
    print("SUCCESS:ADV-0039-probe2 wire capture via local intercepting proxy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
