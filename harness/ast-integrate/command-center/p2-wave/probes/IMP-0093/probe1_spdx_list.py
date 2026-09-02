#!/usr/bin/env python3
"""Probe 1: SPDX identifier validity against the official pinned list.

Independent of the compatibility matrix. Loads the SPDX snapshot as JSON,
checks a hardcoded oracle of known-on-list / known-off-list identifiers,
and requires marketplace.license.validate_spdx to agree with set membership.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from marketplace.license import LICENSE_ABSENT, SPDX_INVALID, SPDX_VALID, validate_spdx  # noqa: E402
from marketplace.spdx import PINNED_PATH  # noqa: E402
from marketplace.tests.test_license import TestLicense  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0093.json"

# Hardcoded oracle from the SPDX License List (not read from validate_spdx).
ORACLE_ON = (
    "MIT",
    "Apache-2.0",
    "GPL-2.0-only",
    "GPL-3.0-only",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "0BSD",
    "MPL-2.0",
    "Unlicense",
)
ORACLE_OFF = (
    "MIT License",
    "Apache 2.0",
    "proprietary",
    "GPLv3",
    "not-a-license",
    "LicenseRef-made-up",
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0093-probe1 {msg}")
    return 1


def main() -> int:
    pinned = json.loads(PINNED_PATH.read_text(encoding="utf-8"))
    active = set(pinned.get("licenseIds") or [])
    deprecated = set(pinned.get("deprecatedLicenseIds") or [])
    official = active | deprecated
    if pinned.get("licenseListVersion") != "3.25.0":
        return fail(f"unexpected list version {pinned.get('licenseListVersion')}")
    if "MIT" not in active or "Apache-2.0" not in active:
        return fail("pinned official list missing MIT or Apache-2.0")
    if "MIT License" in official:
        return fail("display name MIT License must not be an identifier")

    disagreements = []
    for ident in ORACLE_ON:
        on_list = ident in official
        got = validate_spdx(ident)
        agree = on_list and got["valid"] is True and got["code"] in {SPDX_VALID, "SPDX-DEPRECATED"}
        print(
            f"on ident={ident} list={on_list} valid={got['valid']} code={got['code']} agree={agree}"
        )
        if not agree:
            disagreements.append(ident)
    for ident in ORACLE_OFF:
        on_list = ident in official
        got = validate_spdx(ident)
        agree = (not on_list) and got["valid"] is False and got["code"] == SPDX_INVALID
        print(
            f"off ident={ident!r} list={on_list} valid={got['valid']} code={got['code']} agree={agree}"
        )
        if not agree:
            disagreements.append(ident)

    absent = validate_spdx(None)
    if absent["code"] != LICENSE_ABSENT or absent["valid"] is not False:
        return fail(f"None did not yield LICENSE-ABSENT: {absent}")

    if disagreements:
        return fail(f"oracle/list/validator disagreement {disagreements}")

    suite = unittest.TestSuite()
    suite.addTest(TestLicense("test_valid_spdx"))
    suite.addTest(TestLicense("test_invalid_spdx"))
    suite.addTest(TestLicense("test_fetch_failure_marks_stale"))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        return fail("unittest SPDX cases failed")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:IMP-0093" not in text:
        return fail("sentinel absent")
    if doc.get("unit_id") != "IMP-0093":
        return fail(f"unit_id {doc.get('unit_id')}")

    out = {
        "probe": "probe1-spdx-list",
        "unit_id": "IMP-0093",
        "list_version": pinned.get("licenseListVersion"),
        "active_ids": len(active),
        "deprecated_ids": len(deprecated),
        "oracle_on": len(ORACLE_ON),
        "oracle_off": len(ORACLE_OFF),
        "disagreements": 0,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0093-probe1 SPDX identifier validity against official list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
