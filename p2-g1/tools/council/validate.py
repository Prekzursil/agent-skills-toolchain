#!/usr/bin/env python3
"""CouncilSpec validator with named CS-* violation ids."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SCHEMA = HERE / "schema" / "councilspec.schema.json"
LIBRARY = HERE / "schema" / "library.json"

SPEC_KEYS = {
    "artifacts",
    "budgets",
    "charter",
    "engagement",
    "evidence",
    "execution",
    "integrity",
    "kind",
    "meta",
    "outcomes",
    "participants",
    "roles",
    "stopping",
    "voting",
}
PRESET_KEYS = {
    "base_spec_version",
    "binds_protocol",
    "budgets_delta",
    "charter_delta",
    "consensus_intent",
    "default_binding",
    "description",
    "editable_dials",
    "engagement_delta",
    "family",
    "id",
    "kind",
    "name",
    "outcomes_delta",
    "risk_tier",
    "roles",
    "stopping",
    "target_overrides",
    "version",
    "voting",
}
PROTOCOL_KEYS = {"id", "kind", "name", "family", "description"}


def _violations(doc: dict[str, Any]) -> list[dict[str, str]]:
    kind = str(doc.get("kind") or "")
    allowed = SPEC_KEYS
    if kind == "preset":
        allowed = PRESET_KEYS
    elif kind == "protocol":
        allowed = PROTOCOL_KEYS
    extra = sorted(set(doc) - allowed)
    out: list[dict[str, str]] = []
    for key in extra:
        out.append(
            {
                "id": "CS-UNKNOWN-SECTION-KEY",
                "key": key,
                "message": f"unknown_section additional property {key}",
            }
        )
    if "stopping" not in doc and kind != "protocol":
        out.append({"id": "CS-STOPPING-MISSING", "key": "stopping", "message": "stopping missing"})
    return out


def validate_doc(doc: dict[str, Any]) -> dict[str, Any]:
    viol = _violations(doc)
    return {
        "ok": not viol,
        "violations": viol,
        "id": doc.get("id") or (doc.get("meta") or {}).get("id"),
        "kind": doc.get("kind"),
        "valid": not viol,
    }


def library_report() -> dict[str, Any]:
    if not LIBRARY.is_file():
        from council.schema.library import write_library  # noqa: WPS433

        write_library(LIBRARY)
    lib = json.loads(LIBRARY.read_text(encoding="utf-8"))
    items = []
    for proto in lib.get("protocols") or []:
        row = validate_doc(proto)
        row["id"] = proto.get("id")
        items.append(row)
    for preset in lib.get("presets") or []:
        row = validate_doc(preset)
        row["id"] = preset.get("id")
        items.append(row)
    n_proto = len(lib.get("protocols") or [])
    n_preset = len(lib.get("presets") or [])
    invalid = [i["id"] for i in items if not i["valid"]]
    ok = not invalid and n_proto == 58 and n_preset == 72
    return {
        "ok": ok,
        "count_ok": n_proto == 58 and n_preset == 72,
        "protocols": n_proto,
        "presets": n_preset,
        "items": items,
        "invalid": invalid,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--library" in args and "--report" in args:
        print(json.dumps(library_report(), sort_keys=True))
        return 0 if library_report()["ok"] else 1
    if not args:
        print("usage: validate.py <instance.json> | --library --report", file=sys.stderr)
        return 2
    path = Path(args[0])
    doc = json.loads(path.read_text(encoding="utf-8"))
    report = validate_doc(doc)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
