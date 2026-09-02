#!/usr/bin/env python3
"""Named probe 2: artifact schema, sentinel, live gate re-run, garbage reject."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

OUT = "command-center/wfa/WFA-0076-terminal-disposition-reversibility.json"
SCHEMA = HERE / "audit_report.schema.json"
PACK = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)
LOCAL_CONSTRAINT_KEYS = (
    "type",
    "required",
    "properties",
    "allOf",
    "anyOf",
    "oneOf",
    "enum",
    "const",
)


def pack_fragment_is_locally_constrained(fragment: dict) -> bool:
    """True only when the fragment constrains instances without a remote fetch.

    command-center/wfa/schema/wfa-schema-pack.json is a generated shim whose
    $defs/*.AuditReport is a $ref to https://ast-integrate.invalid/... . That
    host does not resolve; fetching it is not a retrieval receipt. The pack
    file itself says it carries no constraints of its own.
    """
    ref = str(fragment.get("$ref") or "")
    if ref.startswith("http://") or ref.startswith("https://"):
        return any(k in fragment for k in LOCAL_CONSTRAINT_KEYS)
    return any(k in fragment for k in LOCAL_CONSTRAINT_KEYS) or bool(ref)


def main() -> int:
    out = REPO / OUT
    if not out.is_file() or out.stat().st_size <= 0:
        print("FAILED:WFA-0076-probe2 artifact absent")
        return 1
    try:
        text = out.read_text(encoding="utf-8")
        doc = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"FAILED:WFA-0076-probe2 unparseable {type(exc).__name__}")
        return 1
    if "SUCCESS:WFA-0076" not in text:
        print("FAILED:WFA-0076-probe2 sentinel-absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:WFA-0076-probe2 self-declared:{doc.get('state')}")
        return 1
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:WFA-0076-probe2 schema errors")
        for err in errs[:12]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            print("FAILED:WFA-0076-probe2 schema accepted garbage")
            return 1
    pack_local = False
    if PACK.is_file():
        pack = json.loads(PACK.read_text(encoding="utf-8"))
        defs = pack.get("$defs") or pack.get("definitions") or {}
        audit = defs.get("AuditReport")
        if isinstance(audit, dict) and pack_fragment_is_locally_constrained(audit):
            pack_local = True
            pack_validator = jsonschema.Draft202012Validator(
                {"$defs": defs, **audit} if "$defs" in pack else audit
            )
            pack_errs = sorted(
                pack_validator.iter_errors(doc), key=lambda e: list(e.path)
            )
            if pack_errs:
                print("FAILED:WFA-0076-probe2 pack AuditReport errors")
                for err in pack_errs[:8]:
                    print(" ", list(err.path), err.message)
                return 1
    live = E.process_scenario()
    if not E.gate_holds(live):
        print("FAILED:WFA-0076-probe2 live gate re-run failed")
        return 1
    artifact_ids = [
        r["id"] for r in doc.get("terminal_records") or [] if r.get("recorded")
    ]
    if artifact_ids != live["recorded_ids"]:
        print("FAILED:WFA-0076-probe2 artifact recorded ids != live re-run")
        print(" artifact", artifact_ids)
        print(" live", live["recorded_ids"])
        return 1
    squash = next(
        r for r in doc["terminal_records"] if r.get("role") == "squash-negative"
    )
    if squash.get("recorded") or not squash.get("squash_merge_rejected"):
        print("FAILED:WFA-0076-probe2 artifact squash row recorded")
        return 1
    if doc.get("live_irreversible_action") is not False:
        print("FAILED:WFA-0076-probe2 live irreversible action claimed")
        return 1
    if doc.get("owner_approval_required") is not True:
        print("FAILED:WFA-0076-probe2 owner_approval_required missing")
        return 1
    print(
        "schema_ok=True sentinel_ok=True live_rerun=True "
        f"recorded={live['recorded_count']} refused={live['refused_count']} "
        f"pack_present={PACK.is_file()} pack_local_constraints={pack_local}"
    )
    print("SUCCESS:WFA-0076-probe2 schema evidence live-rerun")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
