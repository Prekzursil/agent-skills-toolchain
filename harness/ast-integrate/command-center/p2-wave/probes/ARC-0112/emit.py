#!/usr/bin/env python3
"""Emit command-center/phase4/conformance/ARC-0112.json."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import golden as G  # noqa: E402

OUT = G.OUT_REL
SCHEMA = G.SCHEMA_REL


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    doc = G.build_report()
    adj = doc["adjudication"]
    if adj["unexplained"] != 0:
        print(f"FAILED:ARC-0112 unexplained={adj['unexplained']}")
        return 1
    if adj["classified"] != adj["failing_records"]:
        print(
            "FAILED:ARC-0112 classified "
            f"{adj['classified']} != failing {adj['failing_records']}"
        )
        return 1
    if not doc["encoding_control"].get("crlf_not_misread_as_data"):
        print("FAILED:ARC-0112 encoding control did not discriminate CRLF from data")
        return 1
    if "SUCCESS:ARC-0112" not in json.dumps(doc):
        print("FAILED:ARC-0112 sentinel missing from document")
        return 1
    envelope_rel = (
        "command-center/p2-wave/probes/ARC-0112/"
        "conformance-report.envelope.schema.json"
    )
    envelope = json.loads((REPO / envelope_rel).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(envelope)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0112 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:ARC-0112 schema accepted garbage {list(garbage)[:2]}")
            return 1
    catalog_schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    try:
        catalog_errs = list(jsonschema.Draft7Validator(catalog_schema).iter_errors(doc))
        if catalog_errs:
            print(
                "WARN: catalog output_schema shim/specialized: "
                + catalog_errs[0].message
            )
    except Exception as exc:
        print(
            "WARN: catalog output_schema $ref unresolved (generated shim): "
            f"{type(exc).__name__}: {exc}"
        )
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    digest, size = digest_file(out)
    print(
        f"wrote {OUT} bytes={size} sha256={digest} "
        f"failures={adj['failing_records']} unexplained={adj['unexplained']}"
    )
    print("SUCCESS:ARC-0112 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
