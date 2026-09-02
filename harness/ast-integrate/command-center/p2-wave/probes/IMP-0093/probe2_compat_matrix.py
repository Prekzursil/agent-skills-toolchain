#!/usr/bin/env python3
"""Probe 2: closure-pair compatibility against the published matrix.

Mechanically different from probe 1: does not score SPDX-list membership.
Loads the matrix JSON independently, cross-checks pair_verdict against cells,
asserts an unlisted pair is UNKNOWN-NEEDS-REVIEW (never COMPATIBLE), asserts
an incompatible closure names the exact offending pair, and asserts a missing
license is LICENSE-ABSENT and blocks publication. UNKNOWN routes to the owner.
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

from marketplace.compatibility import (  # noqa: E402
    COMPATIBLE,
    INCOMPATIBLE,
    UNKNOWN_NEEDS_REVIEW,
    MATRIX_PATH,
    pair_key,
)
from marketplace.license import (  # noqa: E402
    LICENSE_ABSENT,
    LICENSE_UNSATISFIABLE,
    check_closure,
    pair_verdict,
    publication_gate,
    resolve_with_license_gate,
)
from marketplace.tests.test_license import TestLicense  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0093.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0093-probe2 {msg}")
    return 1


def matrix_cell(pairs: list, left: str, right: str) -> dict | None:
    key = pair_key(left, right)
    for row in pairs:
        if pair_key(row["left"], row["right"]) == key:
            return row
    return None


def main() -> int:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    pairs = list(matrix.get("pairs") or [])
    if matrix.get("unlisted_pair_verdict") != UNKNOWN_NEEDS_REVIEW:
        return fail("matrix default is not UNKNOWN-NEEDS-REVIEW")
    if "not legal advice" not in str(matrix.get("disclaimer") or "").lower():
        return fail("matrix disclaimer missing")

    good = matrix_cell(pairs, "MIT", "Apache-2.0")
    if not good or good.get("verdict") != COMPATIBLE:
        return fail(f"matrix MIT|Apache-2.0 not COMPATIBLE: {good}")
    live_good = pair_verdict("MIT", "Apache-2.0")
    if live_good["verdict"] != COMPATIBLE or live_good["compatible"] is not True:
        return fail(f"pair_verdict MIT|Apache-2.0 {live_good['verdict']}")
    if live_good.get("in_matrix") is not True:
        return fail("MIT|Apache-2.0 not marked in_matrix")
    print("matrix_crosscheck MIT|Apache-2.0 COMPATIBLE agree=True")

    bad = matrix_cell(pairs, "Apache-2.0", "GPL-2.0-only")
    if not bad or bad.get("verdict") != INCOMPATIBLE:
        return fail(f"matrix Apache-2.0|GPL-2.0-only not INCOMPATIBLE: {bad}")
    live_bad = pair_verdict("Apache-2.0", "GPL-2.0-only")
    if live_bad["verdict"] != INCOMPATIBLE or live_bad["compatible"] is not False:
        return fail(f"pair_verdict Apache-2.0|GPL-2.0-only {live_bad['verdict']}")
    print("matrix_crosscheck Apache-2.0|GPL-2.0-only INCOMPATIBLE agree=True")

    unknown_cell = matrix_cell(pairs, "MIT", "MPL-2.0")
    if unknown_cell is not None:
        return fail("MIT|MPL-2.0 must be absent from the matrix (unknown-pair control)")
    live_unknown = pair_verdict("MIT", "MPL-2.0")
    if live_unknown["verdict"] != UNKNOWN_NEEDS_REVIEW:
        return fail(f"unlisted pair verdict {live_unknown['verdict']}")
    if live_unknown["compatible"] is True or live_unknown["verdict"] == COMPATIBLE:
        return fail("NEGATIVE CONTROL failed: unknown pair resolved to compatible")
    if live_unknown["owner_route"] is not True:
        return fail("UNKNOWN did not route to owner")
    if live_unknown["legal_advice"] is not False:
        return fail("tool asserted legal advice")
    print("negative_control unknown_pair MIT|MPL-2.0 compatible=False owner_route=True")

    closure = check_closure(
        [
            {"name": "app", "version": "1.0.0", "license": "Apache-2.0"},
            {"name": "gpl_lib", "version": "3.2.0", "license": "GPL-2.0-only"},
        ]
    )
    if closure["status"] != LICENSE_UNSATISFIABLE:
        return fail(f"incompatible closure status {closure['status']}")
    off = closure["offending_pair"] or {}
    if {off.get("left"), off.get("right")} != {"Apache-2.0", "GPL-2.0-only"}:
        return fail(f"offending pair not exact {off}")
    if {off.get("left_package"), off.get("right_package")} != {"app", "gpl_lib"}:
        return fail(f"offending packages not exact {off}")
    print(
        "resolve_time offending_pair "
        f"{off.get('left_package')}:{off.get('left')} "
        f"{off.get('right_package')}:{off.get('right')}"
    )

    resolved = resolve_with_license_gate(
        "app",
        {
            "util": {"name": "util", "version": "0.1.0", "license": "BSD-3-Clause", "dependencies": []},
            "app": {
                "name": "app",
                "version": "1.0.0",
                "license": "Apache-2.0",
                "dependencies": ["gpl_lib"],
            },
            "gpl_lib": {
                "name": "gpl_lib",
                "version": "3.2.0",
                "license": "GPL-2.0-only",
                "dependencies": ["util"],
            },
        },
    )
    if resolved["status"] != LICENSE_UNSATISFIABLE:
        return fail(f"resolve_with_license_gate status {resolved['status']}")
    roff = resolved["offending_pair"] or {}
    if {roff.get("left"), roff.get("right")} != {"Apache-2.0", "GPL-2.0-only"}:
        return fail(f"resolve offending pair {roff}")
    print("resolve_with_license_gate named exact offending pair")

    good_closure = check_closure(
        [
            {"name": "app", "version": "1.0.0", "license": "MIT"},
            {"name": "lib", "version": "2.0.0", "license": "Apache-2.0"},
        ]
    )
    if good_closure["compatible"] is not True or good_closure["status"] != COMPATIBLE:
        return fail("compatible closure did not pass")

    gate = publication_gate({"name": "no-license"})
    if gate["code"] != LICENSE_ABSENT or gate["blocked"] is not True:
        return fail(f"missing license did not block publication: {gate}")
    print("publication LICENSE-ABSENT blocked=True")

    suite = unittest.TestSuite()
    suite.addTest(TestLicense("test_compatible_closure"))
    suite.addTest(TestLicense("test_incompatible_closure"))
    suite.addTest(TestLicense("test_unknown_pair"))
    suite.addTest(TestLicense("test_missing_license_blocks_publication"))
    suite.addTest(TestLicense("test_disclaimer_is_not_legal_advice"))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        return fail("unittest compatibility cases failed")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:IMP-0093" not in text:
        return fail("sentinel absent")

    out = {
        "probe": "probe2-compat-matrix",
        "unit_id": "IMP-0093",
        "matrix_pairs": len(pairs),
        "compatible_cell_agrees": True,
        "incompatible_cell_agrees": True,
        "unknown_pair_not_compatible": True,
        "offending_pair_named": True,
        "license_absent_blocks_publication": True,
        "legal_advice": False,
        "owner_route_on_unknown": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0093-probe2 compatibility matrix and unknown-pair negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
