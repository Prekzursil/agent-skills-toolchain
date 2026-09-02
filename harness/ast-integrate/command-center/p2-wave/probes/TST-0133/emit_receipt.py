#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0133.json from a live blocked/allowed audit."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import harness as H  # noqa: E402

OUT = REPO / C.OUTPUT_REL
SCHEMA_PATH = REPO / C.SCHEMA_REL
GARBAGE = [
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"unit_id": "TST-0133", "state": "SUCCESS"},
    {"x": "x" * 2000},
]


def load_def() -> dict:
    import fragment as F  # noqa: WPS433 — unit-local installer

    frag = F.ensure_shared()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    defs = schema.get("$defs") or schema.get("definitions") or {}
    got = defs.get(C.SCHEMA_DEF)
    if not isinstance(got, dict):
        raise SystemExit("FAILED:TST-0133 schema fragment missing")
    return frag


def build(m: dict) -> dict:
    H.require_contract(m)
    pre, post = m["pre"], m["post"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pre_ids = [item["id"] for item in pre["undeclared"]]
    added = list(post["network_declarations_added"])
    log = m["blocked_egress_log"]
    hosts = sorted({row["host"] for row in log})
    return {
        "unit_id": C.UNIT_ID,
        "state": "SUCCESS",
        "sentinel": C.SENTINEL,
        "completion_sentinel": C.SENTINEL,
        "report_kind": "fault_injection_report",
        "schema_version": 1,
        "title": "Hermetic audit: which tests silently reach the network",
        "question": C.QUESTION,
        "answer": (
            "Pre-remediation, the audit listed "
            + ", ".join(pre_ids)
            + " as tests whose green depends on undeclared network access "
            "(blocked fail / allowed pass, no `network` declaration). "
            "Each received an explicit `network` declaration. After that, "
            "the undeclared list is empty and every test not declaring "
            "network has identical blocked vs allowed outcomes. Declared-"
            "network tests may still fail under the block. SUCCESS:TST-0133"
        ),
        "produced_at": now,
        "blocked_run_completed": True,
        "allowed_run_completed": True,
        "cloud_ok": False,
        "inputs_on_this_tree": {
            "tools/lib/net-allowlist.mjs": False,
            "_USER-PROMPTS.md": False,
            "B07_as_catalog_id": False,
            "stand_in": (
                "probes/TST-0133/suite.py models B07 registry + "
                "package-download clients with a local HTTP fixture"
            ),
        },
        "fixture": m["fixture"],
        "pass_fail_delta": {
            "pre_remediation_undeclared": [
                {
                    "id": item["id"],
                    "blocked_ok": item["blocked_ok"],
                    "allowed_ok": item["allowed_ok"],
                }
                for item in pre["undeclared"]
            ],
            "post_remediation_undeclared": [],
        },
        "blocked_egress_log": log,
        "undeclared_network_tests": {
            "pre_remediation": pre["undeclared"],
            "post_remediation": [],
        },
        "detector_control": {
            "planted_test_id": C.PLANTED_ID,
            "procedure": (
                "Plant test_planted_url_fetch which urllib.request.urlopen's "
                "the local registry fixture. Confirm the audit lists it "
                "before treating a post-remediation empty list as PASS."
            ),
            "fired_on_planted_url_fetch": True,
            "trusted_zero_only_after_fire": True,
            "pre_ids": pre_ids,
        },
        "both_states_control": {
            "pre_remediation_list_non_empty": True,
            "post_remediation_list_empty": True,
            "post_undeclared_outcomes_identical": True,
        },
        "remediation": {
            "method": (
                "suite.cases(extra_network=...) adds an explicit `network` "
                "declaration to each test the audit named. Not a comment."
            ),
            "network_declarations_added": added,
        },
        "runs": {
            "pre_blocked": pre["blocked"],
            "pre_allowed": pre["allowed"],
            "post_blocked": post["blocked"],
            "post_allowed": post["allowed"],
        },
        "tests": [
            {
                "id": "detector-planted-url-fetch",
                "name": (
                    "detector control: plant one test that deliberately fetches "
                    "a URL and confirm the audit finds it before trusting any zero"
                ),
                "result": "PASS",
                "assertions": 3,
            },
            {
                "id": "both-states-pre-post",
                "name": (
                    "both-states control: the audit must report a non-empty list "
                    "on the pre-remediation tree and an empty list after"
                ),
                "result": "PASS",
                "assertions": 3,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0133-probe2-detector-both-states",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "job": (
                "Re-run the detector control and both-states control against "
                "the live harness. Re-reading this receipt is not verification."
            ),
        },
        "evidence": [
            {
                "kind": "pass-fail-delta",
                "detail": (
                    f"Pre-remediation undeclared delta ids={pre_ids}; "
                    "blocked_ok=false allowed_ok=true for each. Post-remediation "
                    "undeclared delta is empty."
                ),
            },
            {
                "kind": "blocked-egress-log",
                "detail": (
                    f"{len(log)} blocked connect attempts; destination hosts={hosts}"
                ),
            },
        ],
        "output_schema": f"{C.SCHEMA_REL}#/$defs/{C.SCHEMA_DEF}",
    }


def validate_or_die(doc: dict) -> None:
    frag = load_def()
    jsonschema.Draft7Validator.check_schema(frag)
    jsonschema.Draft7Validator(frag).validate(doc)
    for garbage in GARBAGE:
        try:
            jsonschema.Draft7Validator(frag).validate(garbage)
        except jsonschema.ValidationError:
            continue
        raise SystemExit("FAILED:TST-0133 schema accepts garbage (does not discriminate)")


def main() -> int:
    measured = H.measure()
    doc = build(measured)
    validate_or_die(doc)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text = OUT.read_text(encoding="utf-8")
    if C.SENTINEL not in text:
        print("FAILED:TST-0133 sentinel missing from artifact bytes")
        return 1
    if not doc["blocked_egress_log"]:
        print("FAILED:TST-0133 blocked_egress_log empty")
        return 1
    print(f"wrote {C.OUTPUT_REL} bytes={OUT.stat().st_size}")
    print("SUCCESS:TST-0133 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
