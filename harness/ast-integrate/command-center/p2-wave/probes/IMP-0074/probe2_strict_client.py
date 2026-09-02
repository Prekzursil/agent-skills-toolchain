#!/usr/bin/env python3
"""Named probe 2: strict unknown-field-rejecting client + negative controls.

Independent of probe 1: validates with additionalProperties false, then
checks missing-required-field failure and truncated-vs-empty pagination.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.clients import CONTRACT_AMBIGUITIES as CONTRACT_AMBIGUITIES  # noqa: E402
from marketplace.clients import StrictClient  # noqa: E402
from marketplace.conformance import (  # noqa: E402
    run_client_against_cases,
    run_negative_controls,
    run_pagination_distinguish,
)


def main() -> int:
    strict = run_client_against_cases(StrictClient())
    neg = run_negative_controls()
    page = run_pagination_distinguish()
    passed = strict["passed"] and neg["passed"] and page["passed"]
    out = {
        "probe": "probe2-strict-client",
        "unit_id": "IMP-0074",
        "client": "strict",
        "fixtures_ok": strict["ok"],
        "fixtures_n": strict["n"],
        "missing_required_fails_both": neg["missing_required_fails_both"],
        "extra_field_discriminates": neg["extra_field_discriminates"],
        "pagination_distinguishable": page["distinguishable_without_item_bodies"],
        "ambiguities_named": [a["id"] for a in CONTRACT_AMBIGUITIES],
        "passed": passed,
    }
    print(json.dumps(out, sort_keys=True))
    if not passed:
        print("FAILED:IMP-0074-probe2 strict client or controls")
        print(json.dumps({"strict_failed": [r for r in strict["rows"] if not r["passed"]], "neg": neg, "page": page}, default=str)[:4000])
        return 1
    print(
        "SUCCESS:IMP-0074-probe2 strict client "
        f"{strict['ok']}/{strict['n']} missing-required=fail "
        "truncated!=empty extra-field-discriminates"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
