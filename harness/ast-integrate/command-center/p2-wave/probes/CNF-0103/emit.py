#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0103-longpath-devicename.json."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from measure import (  # noqa: E402
    OUT,
    SCHEMA,
    SENTINEL,
    UNIT,
    build_document,
    payload_from_doc,
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def local_validator():
    """Resolve ast-integrate.invalid $ref onto disk. Never the network."""
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    store = {
        shim["$id"]: shim,
        profiles["$id"]: profiles,
        receipt["$id"]: receipt,
    }
    resolver = RefResolver.from_schema(shim, store=store)
    return Draft202012Validator(shim, resolver=resolver)


def main() -> int:
    doc = build_document()
    validator = local_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print(f"FAILED:{UNIT} schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:{UNIT} schema accepted garbage {list(g)[:2]}")
            return 1
    if doc.get("state") not in {"SUCCESS", "PARTIAL"}:
        why = (doc.get("report") or {}).get("failure_classification_if_failed")
        print(f"FAILED:{UNIT} self-declared {doc.get('state')} {why}")
        return 1
    if SENTINEL not in json.dumps(doc):
        print(f"FAILED:{UNIT} catalog sentinel absent from document")
        return 1
    silent = [
        r["id"]
        for r in payload_from_doc(doc)["results"]
        if r.get("outcome") == "silent-zero"
    ]
    if silent:
        print(f"FAILED:{UNIT} silent-zero {silent}")
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    sha, size = digest(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:{UNIT} artifact {size}B below floor")
        return 1
    landed = json.loads(out.read_text(encoding="utf-8"))
    land_errs = list(validator.iter_errors(landed))
    if land_errs:
        print(f"FAILED:{UNIT} landed bytes schema-invalid")
        for e in land_errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha} state={doc['state']}")
    print(f"SUCCESS:{UNIT} emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
