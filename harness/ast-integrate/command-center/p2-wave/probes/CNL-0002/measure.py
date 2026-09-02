"""Live measurements for CNL-0002. Never treat schema_relationship prose as signal."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from constants import (  # noqa: E402
    ORIGIN_CANDIDATES,
    OVERLAP_OPTIONAL,
    RELATED_NOT_ORIGIN,
    REQUIRED_12,
)
from fixtures import write_all

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"


def load(name: str):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def error_list(schema: dict, instance) -> list[dict]:
    v = Draft202012Validator(schema)
    out = []
    for err in v.iter_errors(instance):
        out.append(
            {
                "validator": err.validator,
                "message": err.message,
                "path": list(err.path),
            }
        )
    return out


def origin_presence() -> dict:
    rows = []
    for rel in ORIGIN_CANDIDATES:
        p = Path(rel)
        if not p.is_absolute():
            p = REPO / rel
        rows.append({"path": rel, "is_file": p.is_file(), "kind": "named-original"})
    related = []
    for rel in RELATED_NOT_ORIGIN:
        p = Path(rel)
        if not p.is_absolute():
            p = REPO / rel
        related.append({"path": rel, "is_file": p.is_file(), "kind": "related-not-origin"})
    return {
        "any_present": any(r["is_file"] for r in rows),
        "rows": rows,
        "related_not_origin": related,
    }


def catalogue_vs_v1() -> dict:
    schema = load("v1-charter.schema.json")
    cat = load("catalogue-v1-mismatch.json")
    assert "schema_relationship" in cat
    # Signal 1: validator. Signal 2: set algebra. Prose field is not consulted.
    errors = error_list(schema, cat)
    inst_keys = set(cat)
    required = set(REQUIRED_12)
    present_required = sorted(inst_keys & required)
    return {
        "id": "catalogue-root-vs-v1",
        "error_count": len(errors),
        "errors": errors,
        "instance_keys": sorted(inst_keys),
        "required_12": list(REQUIRED_12),
        "required_present": present_required,
        "required_present_count": len(present_required),
        "intersection_empty": present_required == [],
        "schema_relationship_ignored": True,
        "schema_relationship_prefix": str(cat["schema_relationship"])[:24],
    }


def cm01_vs_v1() -> dict:
    schema = load("v1-charter.schema.json")
    rec = load("C-M01.json")
    errors = error_list(schema, rec)
    props = set(schema["properties"])
    recognised = sorted(set(rec) & props)
    return {
        "id": "C-M01-alone-vs-v1",
        "error_count": len(errors),
        "errors": errors,
        "key_count": len(rec),
        "recognised_keys": recognised,
        "recognised_count": len(recognised),
        "overlap_optional_expected": list(OVERLAP_OPTIONAL),
        "required_present": sorted(set(rec) & set(REQUIRED_12)),
    }


def losing_tagged_union() -> dict:
    schema = load("tagged-union.schema.json")
    untagged = load("catalogue-v1-mismatch.json")
    tagged = load("catalogue-synthetic-tag.json")
    cm01 = load("C-M01.json")
    e_un = error_list(schema, untagged)
    e_tag = error_list(schema, tagged)
    e_cm = error_list(schema, cm01)
    return {
        "id": "losing-tagged-union",
        "untagged_error_count": len(e_un),
        "untagged_errors": e_un,
        "untagged_rejected": len(e_un) > 0,
        "synthetic_tag_error_count": len(e_tag),
        "synthetic_tag_accepted": len(e_tag) == 0,
        "cm01_wrong_grain_error_count": len(e_cm),
        "cm01_rejected": len(e_cm) > 0,
        "predicted_failure": (
            "existing catalogue has no artifact_type; discriminated union "
            "cannot classify it without a synthetic tag"
        ),
        "observed_matches_prediction": len(e_un) > 0 and len(e_tag) == 0,
    }


def winning_two_schemas() -> dict:
    cat_schema = load("catalogue.schema.json")
    charter_schema = load("v1-charter.schema.json")
    repaired = load("catalogue-repaired.json")
    charter = load("charter-valid.json")
    cm01 = load("C-M01.json")
    invalid = load("protocol-invalid.json")
    e_cat = error_list(cat_schema, repaired)
    e_charter = error_list(charter_schema, charter)
    proto_schema = cat_schema["$defs"]["protocol_record"]
    preset_schema = cat_schema["$defs"]["preset_record"]
    proto_errs = [
        (p["id"], len(error_list(proto_schema, p))) for p in repaired["protocols"]
    ]
    preset_errs = [
        (p["id"], len(error_list(preset_schema, p))) for p in repaired["presets"]
    ]
    e_cm01 = error_list(proto_schema, cm01)
    e_bad = error_list(proto_schema, invalid)
    proto_nonzero = [i for i, n in proto_errs if n]
    preset_nonzero = [i for i, n in preset_errs if n]
    return {
        "id": "winning-two-schemas-plus-typed-edge",
        "catalogue_error_count": len(e_cat),
        "catalogue_errors": e_cat,
        "charter_error_count": len(e_charter),
        "protocol_records": len(proto_errs),
        "preset_records": len(preset_errs),
        "protocol_nonzero": proto_nonzero,
        "preset_nonzero": preset_nonzero,
        "cm01_protocol_schema_error_count": len(e_cm01),
        "invalid_protocol_error_count": len(e_bad),
        "invalid_protocol_errors": e_bad,
        "spec_ref": repaired.get("spec_ref"),
        "pass": (
            len(e_cat) == 0
            and len(e_charter) == 0
            and not proto_nonzero
            and not preset_nonzero
            and len(e_cm01) == 0
            and len(e_bad) > 0
        ),
    }


def negative_control_v1_still_fires() -> dict:
    """The check that rejects the mismatched catalogue must still fire after repair exists."""
    schema = load("v1-charter.schema.json")
    cat = load("catalogue-v1-mismatch.json")
    errors = error_list(schema, cat)
    return {
        "id": "negative-control-v1-rejects-catalogue",
        "intended_reject_state": "catalogue root validated as if it were a v1 charter",
        "error_count": len(errors),
        "fires": len(errors) == 13,
        "verbatim_messages": [e["message"] for e in errors],
        "what_the_check_does": (
            "Draft202012Validator(v1-charter) over catalogue-v1-mismatch.json "
            "emits 12 missing-required errors plus 1 additionalProperties error "
            "listing protocols/presets/schema_relationship."
        ),
    }


def run() -> dict:
    write_all()
    cat = catalogue_vs_v1()
    cm = cm01_vs_v1()
    lose = losing_tagged_union()
    win = winning_two_schemas()
    neg = negative_control_v1_still_fires()
    origins = origin_presence()
    ok = (
        cat["error_count"] == 13
        and cat["intersection_empty"]
        and cat["required_present_count"] == 0
        and cm["error_count"] == 14
        and cm["key_count"] == 20
        and cm["recognised_count"] == 4
        and lose["observed_matches_prediction"]
        and lose["cm01_rejected"]
        and win["pass"]
        and neg["fires"]
        and origins["any_present"] is False
    )
    return {
        "ok": ok,
        "origins": origins,
        "catalogue_vs_v1": cat,
        "cm01_vs_v1": cm,
        "losing": lose,
        "winning": win,
        "negative_control": neg,
    }


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: r[k] if k != "catalogue_vs_v1" else {
        "error_count": r[k]["error_count"],
        "required_present_count": r[k]["required_present_count"],
    } for k in ("ok", "catalogue_vs_v1", "cm01_vs_v1", "losing", "winning", "negative_control")}, indent=2, default=str)[:4000])
    print("ok", r["ok"])
    if not r["ok"]:
        raise SystemExit(1)
    print("SUCCESS:CNL-0002-measure")
