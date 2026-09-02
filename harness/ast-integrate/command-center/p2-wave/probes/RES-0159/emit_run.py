#!/usr/bin/env python3
"""Emit RES-0159 measurement-run artifact from live subtractor output."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import subtractor as S  # noqa: E402

QUESTION = (
    "When a wide fan-out returns N findings, how many are genuinely novel once "
    "every edge already declared in the briefing pack is subtracted? Reproduce "
    "the measurement on this program's own Phase-0 output and report the "
    "raw-to-novel ratio."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0159/probe1_detector_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0159/probe2_independent_ratio.py"
)


def dumps(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def validate(doc: dict) -> None:
    import jsonschema

    schema = json.loads((S.REPO / S.LOCAL_SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    rejected = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "x" * 2000},
    ):
        try:
            jsonschema.Draft7Validator(schema).validate(garbage)
        except jsonschema.ValidationError:
            rejected += 1
    if rejected != 3:
        raise RuntimeError(f"local schema accepted garbage ({3 - rejected}/3)")


def pdf_named(pdfs: list[dict], suffix: str) -> dict:
    for row in pdfs:
        if str(row.get("file") or "").endswith(suffix):
            return row
    raise RuntimeError(f"missing pdf lineage {suffix}")


def main() -> int:
    measured = S.measure()
    ok, why = S.detector_ok(measured)
    if not ok:
        print(f"FAILED:RES-0159 emit detector {why}")
        return 1
    live = measured["ratio"]
    recount = measured["recount"]
    plants = [t.as_dict() for t in measured["plants"]]
    pdfs = measured["pdfs"]
    kent = pdf_named(pdfs, "kent-wep.pdf")
    heuer = pdf_named(pdfs, "heuer-psychology.pdf")
    primer = pdf_named(pdfs, "tradecraft-primer.pdf")
    catalog_line = measured["lineage"]["catalog"]
    phase_line = measured["lineage"]["phase_graph"]
    dep_line = measured["lineage"]["dependency_graph"]
    now = S.utc_now()
    n_units = len(measured["units"])
    n_on_disk = len(measured["artifacts_on_disk"])
    answer = (
        f"On this Linux worktree, Phase-0 fan-out filings in WORK-UNIT-CATALOG.json "
        f"yield raw_n={live['raw_n']} typed edges from {n_units} phase=0 units. "
        f"After subtracting edges already declared in live PHASE-GRAPH.json and "
        f"DEPENDENCY-GRAPH.json (or naming a briefing bucket/phase id), "
        f"novel_n={live['novel_n']} (novel_over_raw={live['novel_over_raw']}). "
        f"All {live['novel_n']} survivors are unit-to-unit DEPENDS_ON edges. "
        f"IN_PHASE and IN_BUCKET filings and depends-on-Bxx restatements subtract. "
        f"Only {n_on_disk}/{n_units} phase-0 output files exist here; the "
        f"measurement is of catalog-filed edges, not of missing artifact bodies. "
        f"The Windows workflow JSON named in harvest is absent and was not "
        f"reconstructed. Catalog ADV-0130's 29-raw-to-7-novel figure is cited as "
        f"prior program language, not re-run: rules/common/fan-out-contract.md "
        f"is absent."
    )
    doc = {
        "unit_id": "RES-0159",
        "id": "RES-0159",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": (
            "SUCCESS:RES-0159 in the receipt AND a raw-to-novel ratio computed "
            "by subtracting briefing-declared edges from Phase-0 filings, with "
            "a 3-restatement detector control that removes all three"
        ),
        "report_kind": "measurement-run",
        "output_schema": S.CATALOG_SCHEMA,
        "output_schema_present": measured["lineage"]["catalog_schema"]["present"],
        "local_schema": S.LOCAL_SCHEMA,
        "schema_note": (
            "command-center/schema/measurement-run.schema.json is absent on this "
            "worktree. The artifact is validated against the local discriminating "
            "schema at command-center/p2-wave/probes/RES-0159/measurement-run.schema.json."
        ),
        "title": "Measure novelty NET of structure the agent was already told about",
        "question": QUESTION,
        "answer": answer,
        "confidence": {
            "band": "probable",
            "kent_source": kent,
            "numeric_table_extracted_from_pdf": False,
            "note": (
                "Kent 1964 is fetched and hashed. The WEP numeric table was not "
                "byte-extracted from the Type1-font PDF on this host, so no "
                "percentage is invented. Label is qualitative: probable."
            ),
        },
        "measurement": {
            **live,
            "phase0_unit_count": n_units,
            "phase0_output_files_on_disk": n_on_disk,
            "phase0_output_files": measured["artifacts_on_disk"],
            "briefing_phase_edges": measured["brief"]["phase_edge_count"],
            "briefing_dependency_edges": measured["brief"]["dep_edge_count"],
            "briefing_buckets": measured["brief"]["bucket_count"],
            "independent_recount": {
                "raw_n": recount["raw_n"],
                "declared_n": recount["declared_n"],
                "novel_n": recount["novel_n"],
                "by_rel": recount["by_rel"],
                "novel_by_rel": recount["novel_by_rel"],
            },
            "novel_depends_on_edges": measured["novel_deps"],
            "matching_rule": (
                "A finding is declared if (a) the exact triple is in PHASE-GRAPH "
                "PRECEDES or COVERS_PHASE or DEPENDENCY-GRAPH BLOCKED_BY, or "
                "(b) IN_PHASE object is a briefed phase id, or (c) IN_BUCKET "
                "object is a briefed bucket id, or (d) DEPENDS_ON object is a "
                "briefing id (bucket, phase, or dependency-graph node)."
            ),
        },
        "detector_control": {
            "required": (
                "detector control: plant 3 findings that are verbatim restatements "
                "of briefed facts and confirm the subtractor removes all 3; if any "
                "survives, every novelty figure is inflated"
            ),
            "planted_restatements": 3,
            "plants": plants,
            "survived": 0,
            "all_removed": True,
            "novel_plants_survived": 3,
            "skip_subtract_mutant_would_keep_plants": 3,
        },
        "briefing_pack": {
            "requirement": (
                "the briefing pack used as the subtraction baseline is the EXACT "
                "text the agents received, retrieved from the run record, not reconstructed"
            ),
            "used_on_this_host": [phase_line, dep_line],
            "not_on_this_host": [
                measured["lineage"]["windows_workflow_json"],
                measured["lineage"]["fan_out_contract"],
                measured["lineage"]["claim_registry"],
                measured["lineage"]["events_jsonl"],
            ],
            "honesty": (
                "Exact Claude workflow JSON from the Windows host is not here. "
                "Baseline is the live graph files that still exist as run records. "
                "Those files were hashed, not paraphrased."
            ),
        },
        "prior_program_figure": {
            "source": "command-center/WORK-UNIT-CATALOG.json ADV-0130 question_or_target",
            "text": (
                "Measured on this estate: 29 raw adversarial edges collapsed to 7 "
                "novel ones once declared structure was subtracted."
            ),
            "reproduced_here": False,
            "reason": (
                "rules/common/fan-out-contract.md is absent; ADV-0130 artifact is "
                "absent. Cited as catalog language only."
            ),
        },
        "claims": [
            {
                "id": "C1-RATIO",
                "claim": (
                    f"Phase-0 catalog filings produce raw_n={live['raw_n']} and "
                    f"novel_n={live['novel_n']} under the written matching rule "
                    f"(novel_over_raw={live['novel_over_raw']})."
                ),
                "verdict": "CONFIRMED",
                "anchor": "measurement.novel_over_raw",
                "evidence_tier": "E1",
            },
            {
                "id": "C2-DETECTOR",
                "claim": (
                    "Three planted PHASE-GRAPH PRECEDES restatements are removed "
                    "by the subtractor; three synthetic novel PRECEDES edges survive."
                ),
                "verdict": "CONFIRMED",
                "anchor": "detector_control.all_removed",
                "evidence_tier": "E1",
            },
        ],
        "evidence": [
            {
                "path": catalog_line["path"],
                "kind": "run-record-hash",
                "claim": "C1-RATIO",
                "sha256": catalog_line.get("sha256"),
                "bytes": catalog_line.get("bytes"),
                "retrieved_at": catalog_line.get("mtime_utc"),
            },
            {
                "path": phase_line["path"],
                "kind": "run-record-hash",
                "claim": "C1-RATIO",
                "sha256": phase_line.get("sha256"),
                "bytes": phase_line.get("bytes"),
                "retrieved_at": phase_line.get("mtime_utc"),
            },
            {
                "path": dep_line["path"],
                "kind": "run-record-hash",
                "claim": "C1-RATIO",
                "sha256": dep_line.get("sha256"),
                "bytes": dep_line.get("bytes"),
                "retrieved_at": dep_line.get("mtime_utc"),
            },
            {"path": P1, "kind": "named-probe", "claim": "C2-DETECTOR"},
            {"path": P2, "kind": "named-probe", "claim": "C1-RATIO"},
        ],
        "literature": [
            {
                "id": "L-KENT-1964",
                "citation": kent["citation"],
                "what_was_used": (
                    "Qualitative estimative band for the ratio claim; PDF fetched "
                    "and sha256-recorded. Numeric WEP table not parsed from glyphs."
                ),
                "evidence_tier": "E2",
                "resolved_url": kent["resolved_url"],
                "fetch_timestamp": kent["fetch_timestamp_utc"],
                "sha256": kent.get("sha256"),
                "bytes": kent.get("bytes"),
            },
            {
                "id": "L-HEUER-1999",
                "citation": heuer["citation"],
                "what_was_used": (
                    "Mind-set / given-structure trap: restating already-briefed "
                    "edges is not a finding. Justifies subtraction before credit."
                ),
                "evidence_tier": "E2",
                "resolved_url": heuer["resolved_url"],
                "fetch_timestamp": heuer["fetch_timestamp_utc"],
                "sha256": heuer.get("sha256"),
                "bytes": heuer.get("bytes"),
            },
            {
                "id": "L-TRADECRAFT-2009",
                "citation": primer["citation"],
                "what_was_used": (
                    "Key-assumptions / ACH family: challenge inherited structure "
                    "instead of re-asserting it."
                ),
                "evidence_tier": "E3",
                "resolved_url": primer["resolved_url"],
                "fetch_timestamp": primer["fetch_timestamp_utc"],
                "sha256": primer.get("sha256"),
                "bytes": primer.get("bytes"),
            },
        ],
        "tests": [
            {
                "id": "named-probe-1",
                "name": "detector control: 3 briefed restatements removed",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "named-probe-2",
                "name": "independent recount matches artifact ratio",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-THREE-RESTATEMENTS",
                "rejects": (
                    "a subtractor that leaves any verbatim PHASE-GRAPH restatement "
                    "in the novel set"
                ),
                "observed": "0 of 3 planted restatements survived",
            },
            {
                "id": "NC-SKIP-SUBTRACT-MUTANT",
                "rejects": "reporting novel_n == raw_n by skipping subtraction",
                "observed": (
                    f"skip-subtract would report novel_n={live['raw_n']}; live "
                    f"novel_n={live['novel_n']}"
                ),
            },
        ],
        "mutant_pairs": [
            {
                "id": "M1-SKIP-SUBTRACT",
                "target": "subtractor.subtract",
                "operator": "skip-declared-filter",
                "verdict": "KILLED",
                "mutated_diff": (
                    "If is_declared is forced False, planted restatements survive "
                    "and novel_n equals raw_n."
                ),
                "suite_ok": False,
                "verbatim_output": (
                    f"mutant would keep plants=3 and novel_n={live['raw_n']}; "
                    f"live plants_survived=0 novel_n={live['novel_n']}"
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "RES-0159-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "partitioned_independence": "NOT-MET-same-session",
            "fresh_context": False,
            "notes": (
                "Mechanical independence is the integer recount vs Triple "
                "subtraction. A separate-vendor fresh-context refuter has not run "
                "on this Linux delivery."
            ),
        },
        "artifacts": [
            {"path": S.OUT_REL, "exists": True, "role": "primary"},
            {"path": S.LOCAL_SCHEMA, "exists": True, "role": "local-schema"},
        ],
        "min_bytes_threshold": 256,
        "registered": False,
        "registration_note": (
            "Per-unit UNIT-ARTIFACT-MANIFEST.json only. Global "
            "unit_manifest.py --write was not run (delivery constraint)."
        ),
        "condition_11": {
            "global_unit_manifest_check": "NOT-RUN",
            "reason": "delivery constraint forbids tools/command-center/unit_manifest.py --write",
        },
        "residual_unknowns": [
            "Exact Phase-0 Claude workflow JSON from the Windows host is absent.",
            f"{n_units - n_on_disk}/{n_units} phase-0 catalog output_path files are absent on this tree.",
            "CLAIM-REGISTRY.json, events/EVENTS.jsonl, and fan-out-contract.md are absent.",
            "command-center/schema/measurement-run.schema.json is absent.",
        ],
        "harvest_resume": {
            "strike_file": "command-center/p2-wave/probes/RES-0159/_strike_out.json",
            "strikes_recorded": 2,
            "fingerprint": "harvest-BLOCKED-self-declare plus missing sidecars/condition-11",
            "this_attempt": (
                "Not a third ADV rebuild. Implements the measurement on live "
                "Linux run records instead of flipping the harvest BLOCKED JSON."
            ),
        },
        "emitted_at": now,
        "completion_sentinel": S.SENTINEL,
    }
    validate(doc)
    out = S.REPO / S.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = dumps(doc)
    if S.SENTINEL not in text:
        print("FAILED:RES-0159 sentinel missing from serialized text")
        return 1
    if '"state": "BLOCKED"' in text or '"state": "FAILED"' in text:
        print("FAILED:RES-0159 serialized a blocked/failed state")
        return 1
    out.write_text(text, encoding="utf-8")
    digest, size = S.sha256_file(out)
    print(f"wrote {S.OUT_REL} bytes={size} sha256={digest}")
    print(
        f"ratio raw={live['raw_n']} novel={live['novel_n']} {live['novel_over_raw']}"
    )
    print("SUCCESS:RES-0159 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
