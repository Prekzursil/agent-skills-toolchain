#!/usr/bin/env python3
"""Instrument D2: independent jsonschema Draft2020-12 validation with
file:// source-ref remap into THIS repo. Standalone from the resolver."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
_SCHEMA_TAIL = re.compile(r"/(platform/schema/|command-center/schema/)(.+)$")

UNITS = {
    "BLD-0016": "command-center/schema/traceability-matrix.schema.json",
    "BLD-0023": "command-center/schema/blindspot-register.schema.json",
    "BLD-0024": "command-center/schema/triage-resvalidation-placeholder.json",
    "BLD-0024b": "command-center/schema/triage-revalidation.schema.json",
    "BLD-0027": "command-center/schema/blindspot-register.schema.json",
    "BLD-0028": "command-center/schema/detector-control-audit.schema.json",
    "BLD-0031": "command-center/schema/tag-position-audit.schema.json",
    "BLD-0032": "command-center/schema/tag-position-audit.schema.json",
    "BLD-0033": "command-center/schema/prior-art-register.schema.json",
    "BLD-0035": "command-center/schema/salvage-closure.schema.json",
    "BLD-0037": "command-schema-placeholder.json",
    "BLD-0037b": "command-center/schema/contradiction-register.schema.json",
    "BLD-0040": "command-center/schema/oracle-strength-census.schema.json",
    "BLD-0042": "command-center/schema/test-quality-census.schema.json",
}


def _remap(node: Any) -> None:
    if isinstance(node, dict):
        for k in ("$id", "$ref"):
            v = node.get(k)
            if isinstance(v, str) and v.startswith("file:"):
                mm = _SCHEMA_TAIL.search(v.split("#", 1)[0])
                if mm:
                    frag = "#" + v.split("#", 1)[1] if "#" in v else ""
                    node[k] = (REPO / (mm.group(1) + mm.group(2))).resolve().as_uri() + frag
        for v in node.values():
            _remap(v)
    elif isinstance(node, list):
        for v in node:
            _remap(v)


def retrieve(uri: str) -> Resource:
    m = _SCHEMA_TAIL.search(uri)
    if not m:
        raise FileNotFoundError(uri)
    p = REPO / (m.group(1) + m.group(2))
    body = json.loads(p.read_text(encoding="utf-8"))
    _remap(body)
    return Resource.from_contents(body, default_specification=DRAFT202012)


def validate(uid: str, schema_decl: str) -> tuple[int, list[str]]:
    doc = json.loads(
        (REPO / "command-center" / "receipts" / f"{uid}.json").read_text(encoding="utf-8")
    )
    shim = json.loads((REPO / schema_decl.replace("\\", "/")).read_text(encoding="utf-8"))
    _remap(shim)
    validator = Draft202012Validator(shim, registry=Registry(retrieve=retrieve))
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    msgs = [
        "/".join(map(str, e.absolute_path)) or "<root>" + ": " + ""
        for e in errs
    ]
    msgs = [
        ("%s: %s" % ("/".join(map(str, e.absolute_path)) or "<root>", e.message[:200]))
        for e in errs
    ]
    return len(errs), msgs[:6]


def main() -> int:
    rows = {}
    for key, sd in UNITS.items():
        if "placeholder" in sd:
            continue
        uid = key.removesuffix("b")
        n, msgs = validate(uid, sd)
        rows[uid] = {"errors": n, "first": msgs}
        print(uid, n)
        for m in msgs:
            print("   ", m)
    Path(__file__).with_name("d2_out.json").write_text(
        json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
