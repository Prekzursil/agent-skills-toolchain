"""Validate a CycloneDX 1.5 JSON BOM against the on-disk schema."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BOM_SCHEMA = HERE / "schema" / "bom-1.5.schema.json"


def _validator():
    import jsonschema
    from jsonschema import Draft7Validator

    schema = json.loads(BOM_SCHEMA.read_text(encoding="utf-8"))
    return Draft7Validator(schema)


def validate_bom(bom: dict[str, Any] | None) -> list[str]:
    if not isinstance(bom, dict):
        return ["<root>: not an object"]
    if not BOM_SCHEMA.is_file():
        # Fail closed: a missing schema is not a pass.
        return [f"schema missing: {BOM_SCHEMA}"]
    try:
        v = _validator()
    except Exception as exc:
        return [f"schema unusable: {exc}"]
    return sorted(
        f"{'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
        for err in v.iter_errors(bom)
    )


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: validate_cdx.py <bom.json>", file=sys.stderr)
        return 2
    path = Path(args[0])
    bom = json.loads(path.read_text(encoding="utf-8"))
    errs = validate_bom(bom)
    if errs:
        for e in errs:
            print(e)
        return 1
    print("SUCCESS:validate_cdx")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
