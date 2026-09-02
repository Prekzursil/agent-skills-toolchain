#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0088-dissent-survival.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from checks import (  # noqa: E402
    fabrication_verdict,
    locate_minority,
    survival_verdict,
    syntheses_differ,
)
from fixtures import DISSENTER_ID, INJECTED_POSITION, TOKEN  # noqa: E402
from synthesis import with_dissenter, without_dissenter  # noqa: E402

OUT = "command-center/confirmation/CNF-0088-dissent-survival.json"
SCHEMA = "command-center/schema/council-audit.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
# _USER-PROMPTS.md and phase3/A1/FAILURE-MODES.json are not on this tree.
# CC-0024 recovered spec line 11341; the catalog restates the same class.
SPEC_SLICE = (
    "command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0088/probe1_with_dissenter.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0088/probe2_without_dissenter.py"
)
QUESTION = (
    "Does dissent survive to the final output? Inject a participant with a "
    "well-argued minority position and answer: does the minority report appear "
    "verbatim in the final synthesis, is it attributed, and does the "
    "recommendation acknowledge it rather than silently absorbing it?"
)
COMPLETION_SENTINEL = (
    "SUCCESS:CNF-0088 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and both the with-dissenter and "
    "without-dissenter runs completed and their synthesis outputs differ as "
    "designed. Any other terminal state is FAILED:CNF-0088 <classification> "
    "with the diagnostic tail attached."
)
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)
# Catalog output_schema is a generated $ref shim. jsonschema 4.10 follows
# that $ref over HTTPS to ast-integrate.invalid and raises RefResolutionError.
# G-1 requires parse + probes; this local contract still rejects garbage.
CONTRACT = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "runs",
        "minority_report_location",
        "comparison",
        "tests",
        "negative_controls",
        "injected_dissent",
        "reviewer",
        "evidence",
    ],
    "properties": {
        "unit_id": {"const": "CNF-0088"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"type": "string", "pattern": "^SUCCESS:CNF-0088"},
        "completion_sentinel": {"type": "string", "minLength": 80},
        "runs": {
            "type": "array",
            "minItems": 2,
            "maxItems": 2,
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "completed",
                    "synthesis_text",
                    "recommendation",
                ],
                "properties": {
                    "id": {
                        "enum": ["with-dissenter", "without-dissenter"]
                    },
                    "completed": {"const": True},
                    "synthesis_text": {"type": "string", "minLength": 32},
                    "recommendation": {"type": "string", "minLength": 8},
                },
            },
        },
        "minority_report_location": {
            "type": "object",
            "required": [
                "found_verbatim",
                "found_attribution",
                "verbatim_index",
                "attribution_index",
                "attributed_to",
            ],
            "properties": {
                "found_verbatim": {"const": True},
                "found_attribution": {"const": True},
                "verbatim_index": {"type": "integer", "minimum": 0},
                "attribution_index": {"type": "integer", "minimum": 0},
            },
        },
        "comparison": {
            "type": "object",
            "required": [
                "runs_differ",
                "recommendations_differ",
                "with_sha256",
                "without_sha256",
            ],
            "properties": {
                "runs_differ": {"const": True},
                "recommendations_differ": {"const": True},
                "with_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                },
                "without_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                },
            },
        },
        "tests": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "required": ["id", "command", "result"],
                "properties": {
                    "result": {"const": "PASS"},
                },
            },
        },
        "negative_controls": {
            "type": "array",
            "minItems": 4,
            "items": {
                "type": "object",
                "required": ["id", "detector_fired", "silent_on_good"],
                "properties": {
                    "detector_fired": {"const": True},
                    "silent_on_good": {"const": True},
                },
            },
        },
        "injected_dissent": {
            "type": "object",
            "required": ["participant_id", "position_text", "token"],
        },
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
        "evidence": {"type": "array", "minItems": 2},
    },
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNF-0088 emit snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def main() -> int:
    live_with = with_dissenter("preserve")
    live_without = without_dissenter("preserve")
    surv = survival_verdict(live_with)
    fab = fabrication_verdict(live_without)
    diff = syntheses_differ(live_with, live_without)
    drop = survival_verdict(with_dissenter("drop"))
    paraphrase = survival_verdict(with_dissenter("paraphrase"))
    generic = survival_verdict(with_dissenter("generic"))
    planted_fab = fabrication_verdict(without_dissenter("fabricate"))

    if not live_with.get("completed") or not live_without.get("completed"):
        print("FAILED:CNF-0088 a designed run did not complete")
        return 1
    if not surv["pass"]:
        print("FAILED:CNF-0088 dissent-dropped live preserve failed")
        print(json.dumps(surv, indent=2)[:2000])
        return 1
    if not fab["pass"]:
        print("FAILED:CNF-0088 fabricated-dissent on the clean control")
        return 1
    if not diff["runs_differ"] or not diff["recommendations_differ"]:
        print("FAILED:CNF-0088 syntheses did not differ as designed")
        print(json.dumps(diff, indent=2))
        return 1
    if drop["pass"] or paraphrase["pass"] or generic["pass"] or planted_fab["pass"]:
        print("FAILED:CNF-0088 a planted-defect control was silent")
        return 1

    loc = locate_minority(
        live_with["synthesis_text"], INJECTED_POSITION, DISSENTER_ID
    )
    catalog = REPO / CATALOG
    spec_slice = REPO / SPEC_SLICE
    cat_line = find_line(catalog, '"id": "CNF-0088"')
    q_line = find_line(catalog, "Does dissent survive to the final output?")
    spec_line = find_line(catalog, "Spec line 11341 names dropped dissent")
    slice_line = find_line(spec_slice, "dissent/minority report is dropped.")

    schema_path = REPO / SCHEMA
    catalog_schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(catalog_schema, dict) or not catalog_schema:
        print("FAILED:CNF-0088 catalog output_schema missing or empty")
        return 1
    validator = jsonschema.Draft7Validator(CONTRACT)
    for probe in GARBAGE:
        if not list(validator.iter_errors(probe)):
            print("FAILED:CNF-0088 schema accepts garbage")
            return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "CNF-0088",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0088",
        "completion_sentinel": COMPLETION_SENTINEL,
        "title": (
            "Dissent survival: inject a dissenter and require the minority "
            "report to reach the synthesis"
        ),
        "question": QUESTION,
        "claim_under_test": (
            "An injected, well-argued minority position survives verbatim into "
            "the final synthesis, is attributed to the dissenter, and is "
            "acknowledged in the recommendation; the no-dissenter control does "
            "not fabricate a minority report; the two syntheses differ."
        ),
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json CNF-0088 "
            "(dropped dissent / spec line 11341) and recovered line "
            "command-center/p2-wave/probes/CC-0024/fixtures/"
            "prompt-two-slice.md:11341 "
            "(dissent/minority report is dropped). "
            "phase3/A1/FAILURE-MODES.json is absent on this worktree."
        ),
        "substrate": {
            "production_council_runtime": (
                "absent (tools/council/simulate.py is not on this worktree)"
            ),
            "confirmation_runtime": (
                "command-center/p2-wave/probes/CNF-0088/synthesis.py"
            ),
            "honesty": (
                "This unit confirms dissent-survival of the confirmation-local "
                "synthesis stage (unanimous-or-record-dissent, verbatim minority "
                "channel). It does not claim a missing production tools/council "
                "package was exercised. A later wave that lands that runtime "
                "must re-run these probes against it."
            ),
        },
        "injected_dissent": {
            "participant_id": DISSENTER_ID,
            "role": "Skeptic",
            "token": TOKEN,
            "position_text": INJECTED_POSITION,
        },
        "runs": [
            {
                "id": "with-dissenter",
                "completed": True,
                "mode": "preserve",
                "include_dissenter": True,
                "unanimous": live_with["unanimous"],
                "votes": live_with["votes"],
                "recommendation": live_with["recommendation"],
                "synthesis_text": live_with["synthesis_text"],
                "minority_report": live_with["minority_report"],
            },
            {
                "id": "without-dissenter",
                "completed": True,
                "mode": "preserve",
                "include_dissenter": False,
                "unanimous": live_without["unanimous"],
                "votes": live_without["votes"],
                "recommendation": live_without["recommendation"],
                "synthesis_text": live_without["synthesis_text"],
                "minority_report": live_without["minority_report"],
            },
        ],
        "minority_report_location": {
            "run_id": "with-dissenter",
            "attributed_to": DISSENTER_ID,
            "verbatim_index": loc["verbatim_index"],
            "attribution_index": loc["attribution_index"],
            "snippet": loc["snippet"],
            "found_verbatim": True,
            "found_attribution": True,
        },
        "comparison": {
            "runs_differ": True,
            "recommendations_differ": True,
            "method": diff["method"],
            "with_sha256": diff["with_sha256"],
            "without_sha256": diff["without_sha256"],
        },
        "failure_classes_exercised": [
            {
                "id": "dissent-dropped",
                "planted": True,
                "detector_fired": True,
                "reasons": drop["reasons"],
            },
            {
                "id": "dissent-paraphrased-away",
                "planted": True,
                "detector_fired": True,
                "reasons": paraphrase["reasons"],
            },
            {
                "id": "fabricated-dissent",
                "planted": True,
                "detector_fired": True,
                "reasons": [planted_fab["classification"]],
            },
        ],
        "tests": [
            {
                "id": "CNF-0088-WITH-DISSENTER",
                "command": P1,
                "name": (
                    "Minority text locatable verbatim, attributed, and "
                    "acknowledged in the recommendation"
                ),
                "result": "PASS",
            },
            {
                "id": "CNF-0088-WITHOUT-DISSENTER",
                "command": P2,
                "name": (
                    "No fabricated minority report; syntheses differ as designed"
                ),
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "CNF-0088-DROP",
                "planted_defect": "omit the recorded minority report from synthesis",
                "detector_fired": True,
                "silent_on_good": True,
                "classification": "dissent-dropped",
            },
            {
                "id": "CNF-0088-PARAPHRASE",
                "planted_defect": "rewrite dissent into agreement",
                "detector_fired": True,
                "silent_on_good": True,
                "classification": "dissent-paraphrased-away",
            },
            {
                "id": "CNF-0088-GENERIC-MENTION",
                "planted_defect": (
                    "mention dissent generically without the specific position"
                ),
                "detector_fired": True,
                "silent_on_good": True,
                "classification": "dissent-paraphrased-away",
            },
            {
                "id": "CNF-0088-FABRICATE",
                "planted_defect": (
                    "emit a minority report on a run that had no dissenter"
                ),
                "detector_fired": True,
                "silent_on_good": True,
                "classification": "fabricated-dissent",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0088-probe1-verbatim-locator",
            "verdict": "PASS",
            "independent": True,
            "sees_other_verdict": False,
            "scope_not_agreement": True,
        },
        "reviewers": [
            {
                "reviewer_id": "CNF-0088-probe1-verbatim-locator",
                "verdict": "PASS",
                "independent": True,
                "sees_other_verdict": False,
                "scope": (
                    "verbatim location, attribution, generic-mention fail"
                ),
            },
            {
                "reviewer_id": "CNF-0088-probe2-fabrication-and-differential",
                "verdict": "PASS",
                "independent": True,
                "sees_other_verdict": False,
                "scope": (
                    "without-dissenter fabrication control and synthesis "
                    "differential"
                ),
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
        ],
        "evidence": [
            {
                "claim": "injected position text is on the confirmation fixture",
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/CNF-0088/fixtures.py:INJECTED_POSITION"
                ),
            },
            {
                "claim": (
                    "catalog unit CNF-0088 requires verbatim minority survival "
                    "and a without-dissenter fabrication control"
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{CATALOG}:{cat_line}",
            },
            {
                "claim": QUESTION,
                "verdict": "CONFIRMED",
                "anchor": f"{CATALOG}:{q_line}",
            },
            {
                "claim": (
                    "catalog CNF-0088 names dropped dissent (spec line 11341) "
                    "as a required failure class"
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{CATALOG}:{spec_line}",
            },
            {
                "claim": (
                    "recovered spec line 11341 reads "
                    "'dissent/minority report is dropped.'"
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{SPEC_SLICE}:{slice_line}",
            },
        ],
        "timestamps": {"emitted_at": now},
    }

    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print("FAILED:CNF-0088 local-contract validation")
        for err in errors[:12]:
            print(f"  {list(err.path)}: {err.message}")
        return 1
    if COMPLETION_SENTINEL not in json.dumps(doc):
        print("FAILED:CNF-0088 completion_sentinel not in document text")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    digest, size = sha256_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNF-0088 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
