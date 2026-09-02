#!/usr/bin/env python3
"""Probe 1: template resolution + schema-conformance over every template and custom role.

Signal 1: schema_conformance_pass over builtin templates (error count must be 0).
Signal 2: resolve_template(id).as_dict() identity for every builtin id, independent
of the schema walk (different code path: registry lookup vs parse_role).
A mutated template with an extra key must be reported as drift (detector not vacuous).
A valid custom role authored from observer must pass the same schema pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.roles.templates import (  # noqa: E402
    SPEC_ANCHOR,
    author_custom_role,
    builtin_registry,
    detect_template_drift,
    resolve_template,
    schema_conformance_pass,
)

ART = REPO / "command-center/receipts/IMP-0360.json"
UNIT = "IMP-0360"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0360-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0360-probe1 receipt unparseable {exc}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:IMP-0360-probe1 receipt not object")
        return 1
    if str(doc.get("unit_id")) != UNIT:
        print(f"FAILED:IMP-0360-probe1 unit_id {doc.get('unit_id')}")
        return 1
    if "SUCCESS:IMP-0360" not in text:
        print("FAILED:IMP-0360-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0360-probe1 self-declared {doc.get('state')}")
        return 1

    reg = builtin_registry()
    templates = list(reg.templates())
    if len(templates) < 7:
        print(f"FAILED:IMP-0360-probe1 template_count={len(templates)} want>=7")
        return 1

    conf = schema_conformance_pass(templates)
    print(f"schema_templates ok={conf.ok} checked={conf.checked} errors={list(conf.errors)}")
    if not conf.ok or conf.checked != len(templates):
        print("FAILED:IMP-0360-probe1 schema pass over templates")
        return 1

    resolved = []
    for tmpl in templates:
        got = resolve_template(tmpl.id, reg)
        if got.as_dict() != tmpl.as_dict():
            print(f"FAILED:IMP-0360-probe1 resolve mismatch {tmpl.id}")
            return 1
        resolved.append(tmpl.id)
    print(f"resolved {len(resolved)} templates: {resolved}")

    live_drift = detect_template_drift(reg)
    print(f"live_drift count={len(live_drift)}")
    if live_drift:
        print("FAILED:IMP-0360-probe1 live templates drifted from mandate schema")
        print(json.dumps([f.reason for f in live_drift], indent=2)[:2000])
        return 1

    mutant = templates[0].as_dict()
    mutant["secret_right"] = True
    mutant_drift = detect_template_drift(reg, mutant=mutant)
    print(f"mutant_drift fired={bool(mutant_drift)} reasons={[f.reason for f in mutant_drift]}")
    if not mutant_drift:
        print("FAILED:IMP-0360-probe1 extra-key mutant produced no drift (vacuous detector)")
        return 1
    if not any("unknown mandate fields" in f.reason and "secret_right" in f.reason for f in mutant_drift):
        print("FAILED:IMP-0360-probe1 mutant drift did not name secret_right")
        return 1

    type_mutant = templates[0].as_dict()
    type_mutant["vote"] = "yes"
    type_drift = detect_template_drift(reg, mutant=type_mutant)
    print(f"type_mutant_drift fired={bool(type_drift)} reasons={[f.reason for f in type_drift]}")
    if not type_drift:
        print("FAILED:IMP-0360-probe1 vote=string mutant produced no drift")
        return 1

    custom = author_custom_role(
        {
            "id": "custom.observer.narrow",
            "name": "Narrow observer",
            "template_id": "observer",
            "tool_access": ["read"],
            "speaking": True,
            "vote": False,
            "veto": False,
        },
        reg,
    )
    print(f"custom_valid accepted={custom.accepted} refusals={list(custom.refusals)}")
    if not custom.accepted or custom.role is None:
        print("FAILED:IMP-0360-probe1 valid custom role refused")
        return 1
    custom_conf = schema_conformance_pass(templates + [custom.role])
    print(
        f"schema_templates_and_custom ok={custom_conf.ok} "
        f"checked={custom_conf.checked} errors={list(custom_conf.errors)}"
    )
    if not custom_conf.ok:
        print("FAILED:IMP-0360-probe1 custom role failed schema pass")
        return 1

    try:
        resolve_template("no-such-template", reg)
        print("FAILED:IMP-0360-probe1 missing template did not raise")
        return 1
    except KeyError as exc:
        print(f"missing_template_raises={type(exc).__name__}")

    out = {
        "pass": True,
        "probe": "probe1-schema-and-resolution",
        "unit_id": UNIT,
        "spec_anchor": SPEC_ANCHOR,
        "templates_checked": conf.checked,
        "custom_schema_checked": custom_conf.checked,
        "live_drift": 0,
        "mutant_drift_fired": True,
        "type_mutant_drift_fired": True,
        "custom_accepted": True,
        "resolved_ids": resolved,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0360-probe1 template resolution and schema-conformance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
