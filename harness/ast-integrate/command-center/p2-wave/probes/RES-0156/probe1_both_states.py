#!/usr/bin/env python3
"""Probe 1: both-states evidence-standard checker.

GROUNDED with a resolving file:line PASSES.
GROUNDED with zero citations FAILS (ZERO_CITATION).
GROUNDED with only an external URL FAILS (WRONG_STANDARD).
IDEATION with an external citation PASSES.
IDEATION grounded only in this repo FAILS (FORBIDDEN_GROUNDING).
IDEATION with external + already-present-negative file:line PASSES.
CONTESTED unbound stays CONTESTED (not assigned by preference).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import checker as C  # noqa: E402
from lenses import CONTESTED, REPO  # noqa: E402

ART = (
    REPO
    / "command-center/research/gem-hunt"
    / "RES-0156-grounded-vs-ideation-evidence-split.json"
)
FIXTURES = HERE / "fixtures" / "findings.json"
SENTINEL = "SUCCESS:RES-0156"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0156-probe1 {msg}")
    return 1


def load_findings() -> dict:
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    return data["findings"]


def main() -> int:
    findings = load_findings()
    results = {name: C.check_finding(f) for name, f in findings.items()}
    print(json.dumps({k: v.get("status") for k, v in results.items()}, indent=2))

    expect_pass = ("grounded_ok", "ideation_ok", "ideation_mention_ok")
    expect_zero = ("grounded_zero",)
    expect_wrong = ("grounded_external_only",)
    expect_forbidden = ("ideation_repo_only",)
    expect_contested = ("contested_unbound",)

    for name in expect_pass:
        if not results[name]["compliant"]:
            return fail(f"{name} should PASS got {results[name]}")
    for name in expect_zero:
        if results[name].get("status") != "ZERO_CITATION":
            return fail(f"{name} should ZERO_CITATION got {results[name]}")
    for name in expect_wrong:
        if results[name].get("status") != "WRONG_STANDARD":
            return fail(f"{name} should WRONG_STANDARD got {results[name]}")
    for name in expect_forbidden:
        if results[name].get("status") != "FORBIDDEN_GROUNDING":
            return fail(f"{name} should FORBIDDEN_GROUNDING got {results[name]}")
    for name in expect_contested:
        if results[name].get("status") != CONTESTED:
            return fail(f"{name} should stay CONTESTED got {results[name]}")
        if results[name].get("compliant"):
            return fail(f"{name} must not be assigned a passing standard")

    # Mention-only: claim text may contain a URL; citations drive the verdict.
    mention = C.check_finding(
        {
            "lens_id": "source-code-archaeology",
            "claim": "See https://example.invalid/not-a-citation",
            "citations": [
                {
                    "kind": "file_line",
                    "value": "command-center/WORK-UNIT-CATALOG.json:71662",
                }
            ],
        }
    )
    if not mention["compliant"]:
        return fail(f"URL-in-claim-text mention fired {mention}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("catalog artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel missing from artifact")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    recorded = ((doc.get("design") or {}).get("both_states") or {}).get("statuses") or {}
    for name in list(expect_pass) + list(expect_zero) + list(expect_wrong) + list(
        expect_forbidden
    ) + list(expect_contested):
        if recorded.get(name) != results[name]["status"]:
            return fail(
                f"artifact both_states.{name}={recorded.get(name)!r} "
                f"!= live {results[name]['status']!r}"
            )

    print(
        "grounded_ok=PASS grounded_zero=ZERO_CITATION "
        "ideation_ok=PASS ideation_repo_only=FORBIDDEN_GROUNDING "
        "contested_unbound=CONTESTED mention_silent=True"
    )
    print("SUCCESS:RES-0156-probe1 both-states grounded vs ideation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
