#!/usr/bin/env python3
"""Independent jsonschema CLI for CouncilSpec instances and the library."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SCHEMA = HERE / "councilspec.schema.json"
LIBRARY = HERE / "library.json"


def _validator():
    from jsonschema import Draft202012Validator

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _errors(doc: dict[str, Any]) -> list[dict[str, str]]:
    v = _validator()
    out = []
    for err in v.iter_errors(doc):
        msg = err.message
        if err.validator == "additionalProperties":
            msg = f"unknown_section Additional properties {err.message}"
        out.append({"message": msg, "path": ".".join(str(p) for p in err.path)})
    return out


def library_report() -> dict[str, Any]:
    if not LIBRARY.is_file():
        sys.path.insert(0, str(HERE.parents[1]))
        from council.schema.library import write_library  # noqa: WPS433

        write_library(LIBRARY)
    lib = json.loads(LIBRARY.read_text(encoding="utf-8"))
    items = []
    for proto in lib.get("protocols") or []:
        errs = _errors(proto)
        items.append({"id": proto.get("id"), "valid": not errs, "errors": errs, "kind": "protocol"})
    for preset in lib.get("presets") or []:
        errs = _errors(preset)
        items.append({"id": preset.get("id"), "valid": not errs, "errors": errs, "kind": "preset"})
    n_proto = len(lib.get("protocols") or [])
    n_preset = len(lib.get("presets") or [])
    invalid = [i["id"] for i in items if not i["valid"]]
    return {
        "ok": not invalid,
        "engine": "jsonschema.Draft202012Validator",
        "protocols": n_proto,
        "presets": n_preset,
        "items": items,
        "invalid": invalid,
    }


def main() -> int:
    args = [a for a in sys.argv[1:] if a not in {"-B", "-u", "-I"}]
    if "--library" in args and "--report" in args:
        report = library_report()
        print(json.dumps(report, sort_keys=True))
        return 0 if report["ok"] else 1
    files = [a for a in args if not a.startswith("-")]
    if not files:
        print("usage: jsonschema_cli.py <instance.json> | --library --report", file=sys.stderr)
        return 2
    doc = json.loads(Path(files[0]).read_text(encoding="utf-8"))
    errs = _errors(doc)
    report = {"ok": not errs, "errors": errs, "engine": "jsonschema.Draft202012Validator"}
    print(json.dumps(report, sort_keys=True))
    return 0 if not errs else 1


if __name__ == "__main__":
    raise SystemExit(main())
