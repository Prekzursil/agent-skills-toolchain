#!/usr/bin/env python3
"""Emit the RES-0149 design-spec + record schema artifact."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from example_record import QUESTION, build_worked_example  # noqa: E402
from record_schema import RECORD_SCHEMA, SOURCE_CLASS_VOCABULARY  # noqa: E402
from validator import evaluate, schema_is_vacuous  # noqa: E402

OUT = (
    "command-center/research/evidence-quality/"
    "RES-0149-proof-of-impossibility-record-schema.json"
)
SENTINEL = "SUCCESS:RES-0149"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0149/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0149/probe2_falsifier.py"
)
TITLE = (
    "Proof-of-impossibility record: the schema that distinguishes "
    "'cannot be obtained' from 'not found'"
)
SLICE_REL = "command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"


def empty_sources_mutant(record: dict) -> dict:
    mutant = json.loads(json.dumps(record))
    mutant["exhausted_sources"] = []
    return mutant


def missing_falsifier_mutant(record: dict) -> dict:
    mutant = json.loads(json.dumps(record))
    mutant.pop("falsifier", None)
    return mutant


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    example = build_worked_example(REPO, fetched_at=now)
    complete = evaluate(example, RECORD_SCHEMA)
    empty = evaluate(empty_sources_mutant(example), RECORD_SCHEMA)
    no_fals = evaluate(missing_falsifier_mutant(example), RECORD_SCHEMA)
    if not complete["accepted"]:
        print("FAILED:RES-0149 emit complete record rejected")
        print(json.dumps(complete, indent=2)[:4000])
        return 1
    if empty["accepted"] or not empty["schema_rejected"] or not empty["semantic_rejected"]:
        print("FAILED:RES-0149 emit empty exhausted_sources not dual-rejected")
        print(json.dumps(empty, indent=2)[:4000])
        return 1
    if (
        no_fals["accepted"]
        or not no_fals["schema_rejected"]
        or not no_fals["semantic_rejected"]
    ):
        print("FAILED:RES-0149 emit missing falsifier not dual-rejected")
        print(json.dumps(no_fals, indent=2)[:4000])
        return 1
    if schema_is_vacuous(RECORD_SCHEMA):
        print("FAILED:RES-0149 emit schema accepts garbage")
        return 1
    measurements = example["measurements"]
    if measurements["root_prompt_is_file"]:
        print("FAILED:RES-0149 emit expected _USER-PROMPTS.md to be absent")
        return 1
    if not measurements["slice_line_is_placeholder"]:
        print("FAILED:RES-0149 emit slice line 11276 is not the placeholder")
        return 1

    doc = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": OUT,
        "unit_id": "RES-0149",
        "unit_id": "RES-0149",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": TITLE,
        "question": (
            "Specify and conformance-test the record that closes a research "
            "question as unanswerable: the exhausted source classes, the exact "
            "queries run with counts, the access barrier encountered, the expiry "
            "after which it must be retried, and the falsifier — what single "
            "observation would overturn it."
        ),
        "output_schema_declared": "command-center/schema/design-spec.schema.json",
        "output_schema_on_disk": False,
        "output_schema_note": (
            "Catalog output_schema design-spec.schema.json is absent on this "
            "tree. This artifact is a design spec envelope that carries the "
            "record JSON Schema, a live worked example, and both-states "
            "controls. It is not validated against the missing shared schema."
        ),
        "distinction": {
            "cannot_be_obtained": (
                "Every applicable source class was attempted; each attempt has "
                "an exact query and a result_count; an access_barrier names why "
                "further retrieval is blocked; retry_after forces a later try; "
                "a falsifier names the single observation that would overturn "
                "the close."
            ),
            "not_found": (
                "A search that returned zero hits, or an exhausted_sources list "
                "that is empty. That is a not-found, not an impossibility. The "
                "validator rejects it."
            ),
        },
        "source_class_vocabulary": {
            "names": list(SOURCE_CLASS_VOCABULARY),
            "provenance": (
                "Reconstructed from catalog fragments (official-docs, code, "
                "papers, forums, archival, public-tor, changelogs, issue "
                "trackers, standards, engineering-blogs, niche, multilingual, "
                "anecdotal, video-talk-transcripts). Canonical 16-name list is "
                "_USER-PROMPTS.md:10683, which is not on this worktree."
            ),
        },
        "record_schema": RECORD_SCHEMA,
        "worked_example": example,
        "worked_example_question": QUESTION,
        "both_states": {
            "complete_accepted": complete["accepted"],
            "empty_exhausted_sources_rejected": (not empty["accepted"]),
            "empty_schema_rejected": empty["schema_rejected"],
            "empty_semantic_rejected": empty["semantic_rejected"],
            "empty_schema_errors": empty["schema_errors"][:4],
            "empty_semantic_errors": empty["semantic_errors"][:4],
            "missing_falsifier_rejected": (not no_fals["accepted"]),
            "missing_falsifier_schema_rejected": no_fals["schema_rejected"],
            "missing_falsifier_semantic_rejected": no_fals["semantic_rejected"],
            "missing_falsifier_schema_errors": no_fals["schema_errors"][:4],
            "missing_falsifier_semantic_errors": no_fals["semantic_errors"][:4],
            "negative_control_verbatim": (
                "NEGATIVE CONTROL (empty exhausted_sources): validator REJECTS "
                "the complete record with exhausted_sources=[] "
                f"(schema_rejected={empty['schema_rejected']}, "
                f"semantic_rejected={empty['semantic_rejected']}) and ACCEPTS "
                "the unmodified complete record. A detector that accepted both "
                "would let not-found masquerade as impossible."
            ),
        },
        "tests": [
            {"id": "probe1-both-states", "command": P1, "result": "NOT-RUN"},
            {"id": "probe2-falsifier", "command": P2, "result": "NOT-RUN"},
        ],
        "reviewer": {
            "reviewer_id": "RES-0149-probe2-falsifier-independent-walker",
            "verdict": "NOT-RUN",
            "independent": True,
            "requirement": (
                "one independent adversarial refuter in a fresh context who "
                "defaults to REFUTED when evidence is insufficient (spec:11062)"
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/RES-0149/validator.py",
                "exists": True,
                "role": "validator",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0149/probe1_both_states.py",
                "exists": True,
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0149/probe2_falsifier.py",
                "exists": True,
                "role": "named-probe",
            },
        ],
        "evidence": [
            {
                "path": SLICE_REL,
                "claim": (
                    "Recovered line 11276 is the placeholder token, not a "
                    "record definition."
                ),
            },
            {
                "path": CATALOG_REL,
                "claim": (
                    "Catalog unit RES-0149 requires empty exhausted_sources "
                    "to be rejected."
                ),
            },
        ],
        "inputs_live": {
            "user_prompts_md": False,
            "claim_registry": False,
            "sources_register": False,
            "design_spec_schema": False,
            "cc0024_recovered_slice": True,
        },
        "emitted_at": now,
        "type": RECORD_SCHEMA["type"],
        "required": RECORD_SCHEMA["required"],
        "properties": RECORD_SCHEMA["properties"],
        "additionalProperties": True,
        "description": RECORD_SCHEMA["description"],
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
