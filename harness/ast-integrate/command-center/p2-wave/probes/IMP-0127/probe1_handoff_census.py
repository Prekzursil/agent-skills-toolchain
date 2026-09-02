#!/usr/bin/env python3
"""Named probe 1: schema-valid handoff flows end to end; census matches direct install."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))

from scenario import build_demo_payload  # noqa: E402

from marketplace.handoff import build_handoff, load_schema, validate_handoff  # noqa: E402
from marketplace.install import install as marketplace_install  # noqa: E402
from plugin.errors import MissingTransactionIdError  # noqa: E402
from plugin.install import install_from_handoff  # noqa: E402
from plugin.payload import census_tree  # noqa: E402

import jsonschema  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0127.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0127-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0127":
        print("FAILED:IMP-0127-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:IMP-0127" not in text:
        print("FAILED:IMP-0127-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0127-probe1 self-declared", doc.get("state"))
        return 1

    schema = load_schema()
    jsonschema.Draft7Validator.check_schema(schema)
    garbage = {"blob": "x" * 200, "passing_tests": 999999}
    if not list(jsonschema.Draft7Validator(schema).iter_errors(garbage)):
        print("FAILED:IMP-0127-probe1 handoff schema is vacuous")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0127-p1-") as tmp:
        root = Path(tmp)
        payload = build_demo_payload(root)
        mkt = marketplace_install(payload, root / "via-mkt")
        handoff = mkt["handoff"]
        jsonschema.Draft7Validator(schema).validate(handoff)
        validate_handoff(handoff)

        direct_h = build_handoff(payload, source="direct")
        direct = install_from_handoff(direct_h, root / "via-direct")
        a = census_tree(root / "via-mkt")
        b = census_tree(root / "via-direct")
        expected = {
            str(e["dest"]).replace("\\", "/")
            for e in handoff["projection_map"]["entries"]
        }
        if not expected:
            print("FAILED:IMP-0127-probe1 empty projection")
            return 1
        if set(a) != expected or a != b:
            print("FAILED:IMP-0127-probe1 census mismatch")
            print(json.dumps({"mkt": sorted(a), "direct": sorted(b), "expected": sorted(expected)}))
            return 1
        if set(mkt["result"]["placed"]) != expected or set(direct["placed"]) != expected:
            print("FAILED:IMP-0127-probe1 placed mismatch")
            return 1

        bypass_visible = False
        try:
            install_from_handoff({"payload_path": str(payload)}, root / "bypass")
        except MissingTransactionIdError as exc:
            bypass_visible = "transaction_id" in str(exc)
        if not bypass_visible or (root / "bypass").exists():
            print("FAILED:IMP-0127-probe1 bypass not visible")
            return 1

        summary = {
            "probe": "probe1-handoff-census",
            "unit_id": "IMP-0127",
            "pass": True,
            "files_placed": sorted(expected),
            "marketplace_equals_direct": True,
            "schema_validated": True,
            "bypass_without_transaction_id_refused": True,
        }
        print(json.dumps(summary, sort_keys=True))
        print(
            "SUCCESS:IMP-0127-probe1 schema-valid handoff end-to-end; "
            "marketplace census equals direct-install census"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
