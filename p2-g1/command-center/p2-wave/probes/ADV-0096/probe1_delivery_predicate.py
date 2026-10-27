#!/usr/bin/env python3
"""ADV-0096 probe1 -- structural + schema delivery predicate (live, fail-closed)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/adversarial/ADV-0096-idea-count-gaming-uniqueness-gate.json"
SCHEMA_REL = "command-center/schema/council-pathology-sim.schema.json"
SENTINEL = "SUCCESS:ADV-0096 emitted ONLY when the artifact at output_path exists, is non-empty, parses against output_schema, records BOTH named probes verbatim with their raw output, carries exactly one verdict from {CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, and records the result of every listed control/negative test. Any missing control downgrades the unit's verdicts to NOT-CHECKED. Otherwise FAILED:ADV-0096 <reason>."
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def main() -> int:
    import jsonschema

    fails = []

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(f"{label}{(': ' + detail) if detail else ''}")

    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print(f"FAILED:ADV-0096-probe1 artifact unreadable/unparseable: {type(exc).__name__}")
        return 1
    check(OUT.stat().st_size > 0, "artifact-empty")
    state = str(doc.get("state") or "").upper()
    check(state not in NOT_DELIVERING, "self-declared", state)
    check(str(doc.get("unit_id")) == "ADV-0096", "unit_id", str(doc.get("unit_id")))
    check(SENTINEL in text, "completion-sentinel-absent")
    check(doc.get("schema_version") == 1, "schema_version", repr(doc.get("schema_version")))

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    errs = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(doc),
        key=lambda e: str(list(e.absolute_path)),
    )
    check(not errs, "schema-invalid", f"{len(errs)} errors; first: {str(errs[0].message)[:200] if errs else ''}")

    ev = doc.get("evidence") or []
    check(len(ev) >= 2, "evidence-minItems-2", str(len(ev)))
    for i, item in enumerate(ev):
        probes = item.get("probes") or []
        roles = {p.get("role") for p in probes}
        fps = {p.get("fingerprint") for p in probes}
        check("source" in roles, f"evidence[{i}]-source-probe-absent")
        check("verifier" in roles, f"evidence[{i}]-verifier-probe-absent")
        check(len(fps) == len(probes) and len(probes) >= 2,
              f"evidence[{i}]-fingerprints-not-distinct")

    if fails:
        for f in fails[:10]:
            print(f"FAILED:ADV-0096-probe1 {f}")
        return 1
    print(f"SUCCESS:ADV-0096-probe1 artifact parses, schema-valid, sentinel present, "
          f"evidence pairs complete, state={state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
