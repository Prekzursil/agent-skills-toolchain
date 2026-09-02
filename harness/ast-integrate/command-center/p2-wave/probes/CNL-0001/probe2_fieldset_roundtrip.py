#!/usr/bin/env python3
"""Probe 2: field-set diff + v1<->v2 round-trip + additionalProperties live.

Mechanically different from probe 1: set algebra over schema property names,
canonical JSON round-trip, and v1 validator behaviour. Does not re-validate the
130 catalogue records against v2.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from envelope import ARTIFACT_REL, SENTINEL  # noqa: E402
from fixtures import (  # noqa: E402
    SHAPE_CHANGE_PROPERTY,
    V1_PROPERTIES,
    catalogue_file,
    cm01,
    v1_charter_instance,
    v1_charter_schema,
)
from migrate import canonical, refuse_unwrap_caps, round_trip  # noqa: E402


def err_list(validator: Draft202012Validator, instance: object) -> list[str]:
    return [e.message for e in validator.iter_errors(instance)]


def main() -> int:
    art = REPO / ARTIFACT_REL
    if not art.is_file():
        print("FAILED:CNL-0001-probe2 envelope missing")
        return 1
    schema = json.loads(art.read_text(encoding="utf-8"))
    if SENTINEL not in json.dumps(schema):
        print("FAILED:CNL-0001-probe2 sentinel-absent")
        return 1
    defs = schema.get("$defs") or {}
    charter_props = set((defs.get("charter_v2") or {}).get("properties") or {})
    protocol_props = set((defs.get("protocol_record") or {}).get("properties") or {})
    preset_props = set((defs.get("preset_record") or {}).get("properties") or {})
    v1_props = set(V1_PROPERTIES)
    v2_props = charter_props | protocol_props | preset_props
    dropped = sorted(v1_props - v2_props)
    moved = sorted(v1_props & v2_props)
    added = sorted(v2_props - v1_props)
    if dropped:
        print(f"FAILED:CNL-0001-probe2 dropped v1 keys {dropped}")
        return 1
    if charter_props != v1_props:
        print(
            f"FAILED:CNL-0001-probe2 charter_v2 keys {sorted(charter_props)} "
            f"!= v1 {sorted(v1_props)}"
        )
        return 1
    delivery = schema.get("x-cnl-0001-delivery") or {}
    if delivery.get("v1_property_that_changes_shape") != SHAPE_CHANGE_PROPERTY:
        print("FAILED:CNL-0001-probe2 shape-change property mismatch")
        return 1
    stop_v2 = (defs.get("charter_v2") or {}).get("properties", {}).get("stopping")
    if not isinstance(stop_v2, dict) or stop_v2.get("$ref") != "#/$defs/stopping_expression":
        print("FAILED:CNL-0001-probe2 charter stopping is not the expression wrapper")
        return 1
    stop_caps = (defs.get("protocol_record") or {}).get("properties", {}).get("stopping")
    if not isinstance(stop_caps, dict) or stop_caps.get("$ref") != "#/$defs/stopping_caps":
        print("FAILED:CNL-0001-probe2 protocol stopping is not caps")
        return 1

    v1 = v1_charter_instance()
    rt = round_trip(v1)
    if not rt["byte_identical"]:
        print("FAILED:CNL-0001-probe2 round-trip not byte-identical")
        print(rt["v1_canonical"][:200])
        print(rt["back_canonical"][:200])
        return 1
    if not isinstance(rt["v2"].get("stopping"), dict):
        print("FAILED:CNL-0001-probe2 migrated stopping is not an object")
        return 1
    if rt["v2"]["stopping"].get("expression") != v1["stopping"]:
        print("FAILED:CNL-0001-probe2 expression lost")
        return 1

    v2_validator = Draft202012Validator(schema)
    v2_errs = err_list(v2_validator, rt["v2"])
    if v2_errs:
        print("FAILED:CNL-0001-probe2 migrated charter fails v2", v2_errs[:8])
        return 1
    v1_raw_on_v2 = err_list(v2_validator, v1)
    if not v1_raw_on_v2:
        print("FAILED:CNL-0001-probe2 unmigrated v1 charter incorrectly accepted by v2")
        return 1

    v1_schema = v1_charter_schema()
    v1_validator = Draft202012Validator(v1_schema)
    extra = deepcopy(v1)
    extra["unknown_extra_field"] = "must-be-rejected"
    extra_errs = err_list(v1_validator, extra)
    if not extra_errs:
        print("FAILED:CNL-0001-probe2 additionalProperties is not live on v1")
        return 1
    good_v1 = err_list(v1_validator, v1)
    if good_v1:
        print("FAILED:CNL-0001-probe2 reconstructed v1 instance invalid", good_v1[:8])
        return 1

    cat = catalogue_file()
    file_errs = err_list(v1_validator, cat)
    c_m01 = cm01()
    cm01_errs = err_list(v1_validator, c_m01)
    recognised = sorted(set(c_m01) & set(V1_PROPERTIES))
    if len(recognised) != 4:
        print(f"FAILED:CNL-0001-probe2 C-M01 recognised={recognised} want 4")
        return 1

    neg = refuse_unwrap_caps(c_m01["stopping"])
    if not neg["refused"]:
        print("FAILED:CNL-0001-probe2 negative control did not refuse caps unwrap")
        return 1

    out = {
        "probe": "probe2-fieldset-roundtrip",
        "unit_id": "CNL-0001",
        "field_set_diff": {
            "v1": sorted(v1_props),
            "v2_union": sorted(v2_props),
            "moved": moved,
            "dropped": dropped,
            "added": added,
            "shape_changed": [SHAPE_CHANGE_PROPERTY],
        },
        "round_trip_byte_identical": True,
        "v1_canonical_sha_len": len(rt["v1_canonical"]),
        "unmigrated_v1_rejected_by_v2": True,
        "unmigrated_v1_v2_error_count": len(v1_raw_on_v2),
        "additionalProperties_live": True,
        "unknown_extra_field_errors": extra_errs[:4],
        "catalogue_file_vs_v1_error_count": len(file_errs),
        "catalogue_cited_file_error_count": 13,
        "cm01_vs_v1_error_count": len(cm01_errs),
        "cm01_cited_error_count": 14,
        "cm01_recognised_v1_keys": recognised,
        "cm01_key_count": len(c_m01),
        "negative_control": {
            "name": "refuse-unwrap-catalogue-caps-stopping-as-v1-string",
            "on_reject_state": "catalogue stopping object passed to migrate_v2_to_v1",
            "result": neg,
            "verbatim": (
                "migrate_v2_to_v1 raises ValueError when stopping.mode is not "
                "'expression'; catalogue caps {max_rounds,on_timeout} are refused "
                "rather than silently coerced to a string."
            ),
        },
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True, default=str))
    print(
        f"dropped={dropped} shape={SHAPE_CHANGE_PROPERTY} "
        f"roundtrip_ok=True extra_field_errors={len(extra_errs)} "
        f"file_vs_v1={len(file_errs)} (cited 13) "
        f"C-M01_vs_v1={len(cm01_errs)} (cited 14) recognised={recognised}"
    )
    print("SUCCESS:CNL-0001-probe2 field-set diff, round-trip, additionalProperties")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
