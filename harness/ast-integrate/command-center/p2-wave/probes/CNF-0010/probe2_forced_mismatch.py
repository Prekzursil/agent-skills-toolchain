#!/usr/bin/env python3
"""Named probe 2: forced version mismatch is environment, not code.

Mechanically different from probe 1 (resolver/PATH vs attributor/versions).
The opposite control (same env, different source sha) must stay `code`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from attributor import code_control, forced_mismatch  # noqa: E402
from capture import capture_live  # noqa: E402
from contract import COMPLETION_SENTINEL, OUT_REL, SCHEMA_REL, UNIT_ID  # noqa: E402

ART = REPO / OUT_REL
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0010-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0010-probe2 self-declared", doc.get("state"))
        return 1
    if COMPLETION_SENTINEL not in json.dumps(doc):
        print("FAILED:CNF-0010-probe2 sentinel absent")
        return 1

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0010-probe2 schema accepted garbage")
            return 1
    errs = list(validator.iter_errors(doc))
    if errs:
        print("FAILED:CNF-0010-probe2 artifact schema-invalid", errs[0].message)
        return 1

    live = capture_live(REPO)
    mismatch = forced_mismatch(live)
    if mismatch["attribution"] != "environment":
        print("FAILED:CNF-0010-probe2 forced mismatch ->", mismatch["attribution"])
        print(json.dumps(mismatch, indent=2))
        return 1
    if not mismatch["not_code"] or mismatch["attribution"] == "code":
        print("FAILED:CNF-0010-probe2 attributed to code")
        return 1
    if "tools.ruff.version" not in mismatch["delta_fields"]:
        print("FAILED:CNF-0010-probe2 ruff version not in delta", mismatch["delta_fields"])
        return 1

    opposite = code_control(live)
    if opposite["attribution"] != "code":
        print("FAILED:CNF-0010-probe2 code control ->", opposite["attribution"])
        return 1

    recorded = doc.get("forced_mismatch_control") or {}
    if recorded.get("attribution") != "environment" or not recorded.get("not_code"):
        print("FAILED:CNF-0010-probe2 artifact control drift", recorded)
        return 1
    if recorded.get("pinned_version") != mismatch["pinned_version"]:
        print("FAILED:CNF-0010-probe2 pin drift")
        return 1
    if recorded.get("forced_version") != mismatch["forced_version"]:
        print("FAILED:CNF-0010-probe2 forced version drift")
        return 1

    families = {m.get("os", {}).get("family") for m in doc.get("manifests") or []}
    if "linux" not in families or "windows" not in families:
        print("FAILED:CNF-0010-probe2 missing OS family", sorted(families))
        return 1

    out = {
        "probe": "probe2-forced-mismatch-environment",
        "unit_id": UNIT_ID,
        "attribution": "environment",
        "not_code": True,
        "code_control": "code",
        "delta_fields": mismatch["delta_fields"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0010-probe2 forced-mismatch attributed to environment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
