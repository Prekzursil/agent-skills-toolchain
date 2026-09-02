#!/usr/bin/env python3
"""Probe 2: independent reviewer — force two fallbacks on the user surface; controls."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "fixtures"))

import census  # noqa: E402
import events as E  # noqa: E402
import product as P  # noqa: E402
from jsonschema import Draft7Validator  # noqa: E402

ART = REPO / "command-center" / "receipts" / "BLD-0026.json"
SCHEMA = REPO / "command-center" / "schema" / "blindspot-register.schema.json"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="bld0026-rev-") as tmp:
        work = Path(tmp) / "work.json"
        original = '{"reviewer": true, "keep": "BLD-0026"}'
        work.write_text(original, encoding="utf-8")

        # Force 1: default-on-exception (user surface, not debug log)
        E.reset()
        work.write_text("{broken", encoding="utf-8")
        P.default_on_exception(work)
        if not work.is_file():
            print("FAILED:BLD-0026-probe2 artifact lost after default-on-exception")
            return 1
        if not E.USER_EVENTS:
            print("FAILED:BLD-0026-probe2 default-on-exception never reached user surface")
            return 1
        if E.USER_EVENTS[-1].get("user_visible") is not True:
            print("FAILED:BLD-0026-probe2 event not user_visible")
            return 1
        print("forced_1=default-on-exception user_visible=True")

        # Force 2: vendor-adapter-substitution
        E.reset()
        work.write_text(original, encoding="utf-8")
        P.vendor_adapter_substitution("openai", work)
        if not work.is_file() or work.read_text(encoding="utf-8") != original:
            print("FAILED:BLD-0026-probe2 artifact lost after vendor substitution")
            return 1
        if not E.USER_EVENTS:
            print("FAILED:BLD-0026-probe2 vendor substitution never reached user surface")
            return 1
        print("forced_2=vendor-adapter-substitution user_visible=True")

        # SILENT control: debug logger only
        E.reset()
        work.write_text("{broken", encoding="utf-8")
        P.silent_debug_only(work)
        if E.USER_EVENTS:
            print("FAILED:BLD-0026-probe2 silent control leaked user event")
            return 1
        if not E.DEBUG_EVENTS:
            print("FAILED:BLD-0026-probe2 silent control produced no debug event")
            return 1
        print("control_silent=SILENT debug_only=True")

        # no-fallback control
        fx = census.as_entries(census.scan_fixtures())
        if not census.no_fallback_in_register(fx):
            print("FAILED:BLD-0026-probe2 no_fallback_strict in register")
            return 1
        print("control_no_fallback=absent-from-register")

    if not ART.is_file() or not SCHEMA.is_file():
        print("FAILED:BLD-0026-probe2 receipt or schema missing")
        return 1
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    v = Draft7Validator(schema)
    for name, garbage in (
        ("empty", {}),
        ("unrelated", {"passing_tests": 999999}),
        ("blob", {"blob": "x" * 2000}),
    ):
        if not list(v.iter_errors(garbage)):
            print(f"FAILED:BLD-0026-probe2 schema accepted garbage {name}")
            return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    errs = list(v.iter_errors(doc))
    if errs:
        print(f"FAILED:BLD-0026-probe2 receipt schema {errs[0].message}")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:BLD-0026-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:BLD-0026" not in ART.read_text(encoding="utf-8"):
        print("FAILED:BLD-0026-probe2 sentinel absent")
        return 1
    silent_entries = [e for e in doc.get("entries") if e.get("classification") == "SILENT"]
    if not silent_entries:
        print("FAILED:BLD-0026-probe2 register has no SILENT row (control missing)")
        return 1
    print("reviewer_id=BLD-0026-probe2-user-surface verdict=PASS independent=True")
    print("SUCCESS:BLD-0026-probe2 user-surface reviewer controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
