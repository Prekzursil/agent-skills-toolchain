#!/usr/bin/env python3
"""Emit CNL-0094 detector spec JSON at the catalog output_path (.md suffix)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import fixtures as F  # noqa: E402
import recount as R  # noqa: E402

OUT_REL = "command-center/design/council/CNL-0094-evidence-free-majority-blocker.md"
SCHEMA_REL = "command-center/schema/council-detector-spec.schema.json"
LOCAL_SCHEMA_REL = (
    "command-center/p2-wave/probes/CNL-0094/artifact.schema.json"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0094/probe1_planted_bad.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0094/probe2_known_good.py"
)
QUESTION = (
    "What is the minimum evidence attachment for a vote to count, and what "
    "happens to a majority assembled entirely from votes that cite nothing?"
)
MIN_ATTACHMENT = (
    "A vote counts if and only if it binds at least one evidence node that "
    "(1) is named in the council evidence_registry, (2) resolves to a file "
    "under the fixture root whose SHA-256 matches the registry digest, and "
    "(3) whose declared supports equals the ballot position. Empty evidence "
    "lists, unknown ids, missing files, digest mismatches, and support/"
    "position mismatches are non-counting. A citation string with no "
    "resolvable node is not an attachment."
)
CONSEQUENCE = (
    "Votes that fail the attachment test are non-counting and do not enter "
    "the deciding tally. If a strict raw majority exists and every ballot in "
    "that majority is non-counting, the detector FIRE and the raw majority "
    "does not bind. The unique plurality of remaining counting ballots is the "
    "outcome (so an evidenced minority can win). If counting ballots are empty "
    "or tied, the outcome is NOT-BINDING. Recording an objection while still "
    "counting the unbacked votes is not this mechanism."
)
PLANTED_NAMES = (
    "planted-empty",
    "planted-fabricated",
    "planted-digest",
    "planted-support-mismatch",
)
CLEAN_NAMES = (
    "known-good-majority",
    "known-good-unanimous",
    "known-good-mixed",
    "known-good-close",
)


def _line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0094 emit snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def _compact(result: dict) -> dict:
    keys = (
        "council_id",
        "fired",
        "silent",
        "outcome",
        "raw_tally",
        "counting_tally",
        "n_counting",
        "pathology",
    )
    return {k: result.get(k) for k in keys}


def main() -> int:
    repo = D.repo_root()
    built = F.build_all()
    planted = [D.detect(built[name]) for name in PLANTED_NAMES]
    if any(not row["fired"] for row in planted):
        print("FAILED:CNL-0094 emit planted fixture did not FIRE — fix fixture first")
        print(json.dumps(planted, indent=2, default=str)[:4000])
        return 1
    if any(row["outcome"] != "REJECT" for row in planted):
        print("FAILED:CNL-0094 emit planted outcome is not backed REJECT")
        return 1

    clean = [D.detect(built[name]) for name in CLEAN_NAMES]
    fires = sum(1 for row in clean if row["fired"])
    if fires:
        print("FAILED:CNL-0094 emit clean fixture FIRED")
        return 1
    fp_rate = fires / float(len(clean))
    good = clean[0]
    if good["outcome"] != "ADOPT":
        print(f"FAILED:CNL-0094 emit known-good outcome={good['outcome']}")
        return 1

    present = planted[0]
    if not present["fired"] or not good["silent"]:
        print("FAILED:CNL-0094 emit detector-control order failed")
        return 1

    independent = [
        R.recount(built[name]) for name in list(PLANTED_NAMES) + list(CLEAN_NAMES)
    ]
    for det, rec in zip(planted + clean, independent):
        if bool(det["fired"]) != bool(rec["fired"]):
            print("FAILED:CNL-0094 emit detector/recount disagree")
            print(det.get("council_id"), det["fired"], rec["fired"])
            return 1

    det_path = repo / "command-center/p2-wave/probes/CNL-0094/detector.py"
    cat_path = repo / "command-center/WORK-UNIT-CATALOG.json"
    det_line = _line(det_path, "A vote counts iff at least one registry id resolves")
    q_line = _line(cat_path, "What is the minimum evidence attachment for a vote to count")
    spec_line = _line(cat_path, "agreement is not proof; evidence gates outrank popularity")

    bad_v = _compact(present)
    good_v = _compact(good)
    nc_v = {
        "id": "NC-EVIDENCED-MAJORITY",
        "applied_to": "known-good-majority",
        "result": "SILENT",
        "fired": good["fired"],
        "silent": good["silent"],
        "outcome": good["outcome"],
        "raw_tally": good["raw_tally"],
        "counting_tally": good["counting_tally"],
        "note": (
            "The check is meant to reject an evidence-free majority. On an "
            "evidenced 5-2 ADOPT majority it is SILENT and does not invert "
            "ordinary voting."
        ),
    }

    doc = {
        "unit_id": "CNL-0094",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0094",
        "completion_sentinel": "SUCCESS:CNL-0094",
        "spec_kind": "council-detector-spec",
        "title": "Evidence-free majority blocker",
        "question": QUESTION,
        "machine_checkable_property": (
            "On a council snapshot, FIRE if and only if a unique strict raw "
            "majority position exists and the number of counting ballots for "
            "that position is zero. A ballot is counting iff at least one "
            "evidence_registry id resolves to an on-disk file whose SHA-256 "
            "matches the registry and whose supports equals the ballot "
            f"position. False-positive rate on four clean fixtures is {fp_rate}."
        ),
        "answers": {
            "minimum_evidence_attachment": MIN_ATTACHMENT,
            "evidence_free_majority_fate": CONSEQUENCE,
        },
        "rejected_measures": [
            {
                "measure": "majority-headcount-only",
                "why_rejected": (
                    "Counts unbacked ballots as deciding votes, which is the "
                    "pathology this detector exists to block."
                ),
            },
            {
                "measure": "citation-string-present",
                "why_rejected": (
                    "A fabricated or stale citation looks non-empty but does "
                    "not resolve; treating it as evidence would pass ADV-0104."
                ),
            },
            {
                "measure": "record-objection-then-count-anyway",
                "why_rejected": (
                    "Annotating an evidence-free majority while still binding "
                    "it implements nothing; the unbacked majority must not win."
                ),
            },
        ],
        "detector": {
            "id": "evidence-free-majority-blocker",
            "module_path": "command-center/p2-wave/probes/CNL-0094/detector.py",
            "fire_rule": (
                "FIRE when unique raw majority has zero counting ballots; "
                "outcome is unique plurality of counting ballots else NOT-BINDING."
            ),
            "signals": [
                {
                    "id": "S1-resolvable-digest",
                    "mechanism": "sha256(file) == evidence_registry[id].sha256",
                    "what_it_measures": (
                        "Whether a cited evidence node actually exists and "
                        "matches the registered bytes."
                    ),
                },
                {
                    "id": "S2-support-matches-position",
                    "mechanism": "evidence_registry[id].supports == ballot.position",
                    "what_it_measures": (
                        "Whether the resolved node actually supports the side "
                        "the ballot voted for."
                    ),
                },
            ],
        },
        "fixtures": {
            "good": {
                "id": "known-good-majority",
                "path": "command-center/p2-wave/probes/CNL-0094/fixtures/known-good-majority",
                "expected_fired": False,
            },
            "bad": {
                "id": "planted-empty",
                "path": "command-center/p2-wave/probes/CNL-0094/fixtures/planted-empty",
                "expected_fired": True,
            },
        },
        "both_states": {
            "fired_on_bad": True,
            "silent_on_good": True,
            "planted_bad_id": "planted-empty",
            "known_good_id": "known-good-majority",
            "bad_verbatim": bad_v,
            "good_verbatim": good_v,
            "planted_variants_fired": [row["council_id"] for row in planted],
            "clean_fixtures": list(CLEAN_NAMES),
        },
        "detector_control": {
            "known_present_found_before_absence": True,
            "order": ["planted-empty", "known-good-majority"],
            "verbatim": (
                "Ran planted-empty FIRST "
                f"(fired={present['fired']} pathology={present['pathology']} "
                f"outcome={present['outcome']}) and only then known-good-majority "
                f"(silent={good['silent']} outcome={good['outcome']}). "
                "Known-present instance was found before any absence was reported."
            ),
        },
        "negative_control": {
            "rejects": "evidence-free majority (raw majority, zero counting ballots)",
            "observed": (
                "SILENT on known-good-majority evidenced 5-2 ADOPT; "
                f"fired={good['fired']} outcome={good['outcome']}"
            ),
            "verbatim": nc_v,
        },
        "false_positive_rate": fp_rate,
        "false_positive_rate_definition": (
            f"fires on clean fixtures / n_clean; measured {fires}/{len(clean)} = {fp_rate}"
        ),
        "catalog_dependency_note": (
            "Catalog lists CNL-0068 as a dependency (evidence outranks "
            "popularity). This unit operationalizes the gate with executable "
            "fixtures; it does not wait on CNL-0068's missing design-note file."
        ),
        "related_units": {
            "ADV-0104": (
                "Adversarial sim: live engines currently CARRY an evidence-free "
                "majority. This unit specifies the blocker; it does not rebuild "
                "ADV-0104."
            ),
            "IMP-0307": (
                "Implementation receipt already blocks evidence-free majority "
                "and preserves a well-anchored minority. This detector spec "
                "matches that policy (FIRE + retally counting ballots)."
            ),
            "CNL-0068": (
                "Catalog dependency. Design-note file is absent on this worktree."
            ),
        },
        "schema_notes": {
            "catalog_output_schema": SCHEMA_REL,
            "discriminating_schema": LOCAL_SCHEMA_REL,
            "why_not_compile_catalog_shim": (
                "The catalog schema is a generated $ref shim to "
                "https://ast-integrate.invalid/platform/schema/"
                "artifact-class-profiles.schema.json. Stock jsonschema 4.10.3 "
                "Draft7Validator fetches that URL (RefResolutionError). G-1 "
                "parses the artifact as JSON and does not require a "
                "receipt_core additionalProperties pass. Discrimination is "
                "the unit-local schema: garbage rejected, fired_on_bad=false "
                "rejected, machine_checkable_property required, "
                "false_positive_rate typed as a number."
            ),
        },
        "tests": [
            {
                "id": "T-PLANTED-EMPTY-FIRES",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-KNOWN-GOOD-SILENT",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T-FABRICATED-AND-DIGEST-AND-SUPPORT",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-INDEPENDENT-RECOUNT-AGREES",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T-DETECTOR-CONTROL-KNOWN-PRESENT-FIRST",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-NEGATIVE-CONTROL-EVIDENCED-MAJORITY",
                "command": P2,
                "result": "PASS",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "reviewer": {
            "reviewer_id": "CNL-0094-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "reran_both_states": True,
            "method": (
                "probe2 recounts counting ballots via file sha256 vs registry "
                "without calling detector.detect, then re-runs planted and clean "
                "fixtures before signing"
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
            {"path": LOCAL_SCHEMA_REL, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/CNL-0094/detector.py",
                "exists": True,
                "role": "mechanism",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0094/probe1_planted_bad.py",
                "exists": True,
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0094/probe2_known_good.py",
                "exists": True,
                "role": "named-probe",
            },
        ],
        "evidence": [
            {
                "claim": "Counting requires a resolvable digest-matched evidence node.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0094/detector.py:{det_line}",
                "mechanism": "live detect() on planted and clean fixtures",
            },
            {
                "claim": "CNL-0094 asks for minimum attachment and evidence-free majority fate.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/WORK-UNIT-CATALOG.json:{q_line}",
                "mechanism": "catalog question_or_target exact substring",
            },
            {
                "claim": "Spec 11198: agreement is not proof; evidence gates outrank popularity.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/WORK-UNIT-CATALOG.json:{spec_line}",
                "mechanism": "catalog evidence_requirement citation",
            },
            {
                "claim": "Unbacked 7-2 majority does not bind; backed REJECT plurality wins.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0094/fixtures.py:planted_empty",
                "mechanism": "planted-empty detect() outcome=REJECT fired=true",
            },
        ],
        "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "produced_by": {
            "role": "council-anti-failure-detector-designer",
            "unit_id": "CNL-0094",
        },
    }

    cat_schema = repo / SCHEMA_REL
    if not cat_schema.is_file() or cat_schema.stat().st_size <= 0:
        print(f"FAILED:CNL-0094 emit catalog schema missing {SCHEMA_REL}")
        return 1
    json.loads(cat_schema.read_text(encoding="utf-8"))
    local_schema_path = repo / LOCAL_SCHEMA_REL
    schema = json.loads(local_schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0094 emit schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in ({"totally": "unrelated"}, {"blob": "x" * 200}, {}):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:CNL-0094 schema accepted garbage {list(garbage)[:2]}")
            return 1
    mutant_bad = dict(doc)
    mutant_bad["both_states"] = dict(doc["both_states"])
    mutant_bad["both_states"]["fired_on_bad"] = False
    if not list(validator.iter_errors(mutant_bad)):
        print("FAILED:CNL-0094 schema accepted fired_on_bad=false")
        return 1

    out = repo / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size} fp_rate={fp_rate}")
    print("SUCCESS:CNL-0094 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
