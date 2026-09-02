#!/usr/bin/env python3
"""Emit the CNL-0014 council design note (JSON document, catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detector as D  # noqa: E402
import scenario as Sc  # noqa: E402
import store as S  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0014-calibration-ranked-selection-needs-a-calibration-store-tha.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
STORE_SCHEMA = "command-center/p2-wave/probes/CNL-0014/store.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0014/probe1_cold_start.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0014/probe2_both_states.py"
)
QUESTION = (
    "Calibration-ranked participant selection presupposes a per-participant "
    "calibration history - what is the minimum store schema, how is it populated "
    "on cold start without inventing scores, and what does the selector do for a "
    "participant with zero history?"
)
ZERO_HISTORY_POLICY = (
    "Zero-history participants are UNRANKABLE. They must NOT be ranked as average "
    "by default. The calibration-ranked selector returns them only in the "
    "unrankable pool with reason ZERO_HISTORY, brier=null, and never switches "
    "method to invent a roster. A higher-layer composer (CNL-0013) may seat them "
    "under a different named method; that method change must be recorded, not "
    "hidden inside calibration-rank."
)

# Catalog output_schema is a generated $ref shim onto ast-integrate.invalid.
# G-1 json.loads the artifact; named probes check these fields. Do not chase
# the remote $ref (jsonschema 4.10 tries the network and fails closed).
NOTE_CONTRACT = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "zero_history_policy",
        "cold_start",
        "mixed_history",
        "both_states",
        "negative_controls",
    ],
    "properties": {
        "unit_id": {"const": "CNL-0014"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:CNL-0014"},
        "zero_history_policy": {
            "type": "string",
            "minLength": 40,
            "pattern": "UNRANKABLE",
        },
        "cold_start": {
            "type": "object",
            "required": ["ranked_count", "unrankable_count", "switched_method"],
            "properties": {
                "ranked_count": {"type": "integer", "const": 0},
                "unrankable_count": {"type": "integer", "minimum": 1},
                "switched_method": {"const": False},
            },
        },
        "mixed_history": {
            "type": "object",
            "required": ["ranked_ids", "unrankable_ids"],
            "properties": {
                "ranked_ids": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string"},
                },
                "unrankable_ids": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string"},
                },
            },
        },
        "both_states": {
            "type": "object",
            "required": ["discriminates", "on_known_good", "on_planted_bad"],
            "properties": {
                "discriminates": {"const": True},
                "on_known_good": {"const": "SILENT"},
                "on_planted_bad": {"const": "FIRES"},
            },
        },
        "negative_controls": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["on_known_good", "on_planted_bad"],
                "properties": {
                    "on_known_good": {"const": "SILENT"},
                    "on_planted_bad": {"const": "FIRES"},
                },
            },
        },
    },
}


def present(rel: str) -> bool:
    return (REPO / rel).is_file()


def line_of(rel: str, needle: str) -> str:
    path = REPO / rel
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return f"{rel}:{i}"
    return f"{rel}:?"


def is_generated_shim(schema: dict) -> bool:
    ref = schema.get("$ref")
    return (
        schema.get("x-generated-by") == "platform/lib/_gen_schema_substrate.py"
        and schema.get("x-artifact-class") == "council-design-note"
        and isinstance(ref, str)
        and "ast-integrate.invalid" in ref
    )


def schema_rejects_garbage(schema: dict) -> dict:
    validator = jsonschema.Draft7Validator(schema)
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "CNL-0014"},
        {"x": "x" * 200},
    ]
    rejected = 0
    details = []
    for g in garbage:
        errs = list(validator.iter_errors(g))
        details.append({"rejected": len(errs) > 0, "n_errors": len(errs)})
        if errs:
            rejected += 1
    return {"n": len(garbage), "rejected": rejected, "details": details}


def main() -> int:
    m = Sc.run_all()
    if not (Sc.cold_ok(m) and Sc.mixed_ok(m) and Sc.both_ok(m) and Sc.store_gate_ok(m)):
        print("FAILED:CNL-0014 emit live measurements did not pass")
        print(json.dumps({k: m[k] for k in ("honest_cold_not_average", "honest_mixed_only_scored")}, default=str))
        return 1

    both_line = D.verbatim_line("both-states-mixed", m["both_states_mixed"])
    cold_line = D.verbatim_line("both-states-cold", m["both_states_cold"])
    set_line = (
        f"set-algebra cold overlap={m['cold']['sets']['overlap']} "
        f"disjoint={m['cold']['sets']['disjoint']} "
        f"mixed overlap={m['mixed']['sets']['overlap']} "
        f"disjoint={m['mixed']['sets']['disjoint']} "
        f"ranked={m['mixed']['ranked_ids']}"
    )
    store_line = (
        f"store-gate known_good_accepted={m['store_validation']['known_good_accepted']} "
        f"planted_invented_rejected={m['store_validation']['planted_invented_rejected']} "
        f"invented_errors={m['store_validation']['planted_invented_errors']}"
    )

    note_schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    store_schema = json.loads((REPO / STORE_SCHEMA).read_text(encoding="utf-8"))
    if not is_generated_shim(note_schema):
        print("FAILED:CNL-0014 catalog output_schema is not the generated shim")
        return 1
    note_garbage = schema_rejects_garbage(NOTE_CONTRACT)
    store_garbage = schema_rejects_garbage(store_schema)
    if note_garbage["rejected"] != note_garbage["n"] or store_garbage["rejected"] != store_garbage["n"]:
        print("FAILED:CNL-0014 schema vacuity: garbage not fully rejected")
        return 1

    absences = {
        "11-COUNCIL-SPECIFICATION.schema.json": present("11-COUNCIL-SPECIFICATION.schema.json"),
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": present("12-COUNCIL-PROTOCOLS-AND-PRESETS.json"),
        "platform/schema/councilspec.schema.json": present("platform/schema/councilspec.schema.json"),
        "command-center/schema/councilspec.v2.schema.json": present(
            "command-center/schema/councilspec.v2.schema.json"
        ),
        "command-center/design/council/CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md": present(
            "command-center/design/council/CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md"
        ),
        "command-center/design/council/CNL-0074-confidence-trajectory-and-the-post-run-calibration-report.md": present(
            "command-center/design/council/CNL-0074-confidence-trajectory-and-the-post-run-calibration-report.md"
        ),
    }

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    derive_anchor = line_of(
        "command-center/p2-wave/probes/CNL-0014/store.py",
        "if n < min_resolved_n:",
    )
    selector_anchor = line_of(
        "command-center/p2-wave/probes/CNL-0014/selector.py",
        "reason\": \"ZERO_HISTORY\" if n == 0",
    )
    detector_anchor = line_of(
        "command-center/p2-wave/probes/CNL-0014/detector.py",
        "code\": \"ZERO_HISTORY_RANKED\"",
    )
    catalog_q = line_of(
        "command-center/WORK-UNIT-CATALOG.json",
        "Calibration-ranked participant selection presupposes",
    )

    doc = {
        "schema_version": 1,
        "report_kind": "council-design-note",
        "unit_id": "CNL-0014",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0014",
        "completion_sentinel": "SUCCESS:CNL-0014",
        "title": "Calibration-ranked selection needs a calibration store that does not exist yet",
        "question": QUESTION,
        "spec_anchor": catalog_q,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "headless-linux",
        },
        "ts": now,
        "dependencies_on_this_tree": {
            "CNL-0005_artifact_present": absences[
                "command-center/design/council/CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md"
            ],
            "CNL-0074_artifact_present": absences[
                "command-center/design/council/CNL-0074-confidence-trajectory-and-the-post-run-calibration-report.md"
            ],
            "note": (
                "Neither dependency artifact is on this worktree. This unit still "
                "specifies the store because the question is that the store does "
                "not exist yet; cold-start is the live operational mode."
            ),
        },
        "inputs_on_this_tree": absences,
        "answer": (
            "Minimum store is council-calibration-store/v1: per (participant_id, "
            "task_class) an append-only outcomes list, derived resolved_n, "
            "scoreable, brier, and rank_class. Brier is the mean squared error of "
            "stated_confidence versus resolved_correct on SCOREABLE rows only; it "
            "is null whenever resolved_n < min_resolved_n (default 1). Cold start "
            "writes UNRANKABLE identity stubs with outcomes=[] and never a numeric "
            "score. UNSCOREABLE rows (no ground truth, the CNL-0074 path) do not "
            "increment resolved_n. The calibration-ranked selector ranks only "
            "RANK_ELIGIBLE rows by ascending Brier and leaves zero-history "
            "participants in unrankable with reason ZERO_HISTORY; it does not "
            "impute the pool mean, 0.5, or any other average, and it does not "
            "silently switch method when the ranked list is empty. On this "
            f"worktree the mixed fixture ranks {m['mixed']['ranked_ids']} and "
            f"leaves {sorted(m['mixed']['unrankable_ids'])} UNRANKABLE. The "
            "planted-average selector assigns the scored-pool mean "
            f"{m['mixed']['imputed_average']} to cara/drew, which lets cara "
            "outrank bob — the defect the detector is built to catch."
        ),
        "decision": {
            "summary": (
                "Use council-calibration-store/v1 with append-only SCOREABLE "
                "outcomes, null brier at cold start, and UNRANKABLE ranking for "
                "zero-history participants; never impute the pool mean or 0.5."
            ),
            "zero_history": "UNRANKABLE, not average",
            "cold_start": "identity stubs, no invented scores",
        },
        "store_schema": {
            "id": "council-calibration-store/v1",
            "path": STORE_SCHEMA,
            "min_fields": [
                "schema_id",
                "min_resolved_n",
                "records[].participant_id",
                "records[].task_class",
                "records[].resolved_n",
                "records[].outcomes",
                "records[].scoreable",
                "records[].brier",
                "records[].rank_class",
            ],
            "invariants": [
                "resolved_n equals the count of SCOREABLE outcomes, not the list length",
                "if resolved_n < min_resolved_n then scoreable=false, brier=null, rank_class=UNRANKABLE",
                "SCOREABLE outcomes require boolean resolved_correct and a non-empty resolution_source",
                "UNSCOREABLE outcomes must not carry resolved_correct and must not mint a brier",
                "the store never writes a prior, pool mean, or 0.5 in place of a measured brier",
            ],
        },
        "cold_start_policy": (
            "Create an empty store document (records=[]). The first time a "
            "candidate is seen, insert an identity row via observe_candidate with "
            "outcomes=[], resolved_n=0, brier=null, rank_class=UNRANKABLE. Do not "
            "copy industry averages, peer means, or uninformative priors into "
            "brier. Population after cold start is append-only SCOREABLE outcomes "
            "from a post-run calibration report (CNL-0074) that carries a "
            "resolution_source. That report is absent on this tree; the store "
            "stays empty of scores until such rows exist."
        ),
        "zero_history_policy": ZERO_HISTORY_POLICY,
        "cold_start": {
            "ranked_count": m["cold"]["ranked_count"],
            "unrankable_count": m["cold"]["unrankable_count"],
            "switched_method": m["cold"]["switched_method"],
            "sets": m["cold"]["sets"],
            "imputed_would_rank": m["cold"]["imputed_ranked_count"],
            "impute_source": m["cold"]["impute_source"],
            "imputed_average": m["cold"]["imputed_average"],
        },
        "mixed_history": {
            "ranked_ids": m["mixed"]["ranked_ids"],
            "unrankable_ids": sorted(m["mixed"]["unrankable_ids"]),
            "alice_brier": m["mixed"]["alice_brier"],
            "bob_brier": m["mixed"]["bob_brier"],
            "cara_resolved_n": m["mixed"]["cara_resolved_n"],
            "cara_rank_class": m["mixed"]["cara_rank_class"],
            "sets": m["mixed"]["sets"],
            "imputed_ranked_ids": m["mixed"]["imputed_ranked_ids"],
            "imputed_average": m["mixed"]["imputed_average"],
            "cara_beats_bob_under_imputation": m["mixed"]["cara_beats_bob_under_imputation"],
        },
        "both_states": {
            "on_known_good": "SILENT",
            "on_planted_bad": "FIRES",
            "discriminates": m["both_states_mixed"]["discriminates"],
            "known_good_finding_count": m["both_states_mixed"]["known_good_finding_count"],
            "planted_bad_finding_count": m["both_states_mixed"]["planted_bad_finding_count"],
            "verbatim_mixed": both_line,
            "verbatim_cold": cold_line,
            "planted_bad_is": (
                "rank_with_average_imputation assigns the scored-pool mean (or 0.5 "
                "on total cold start) to every participant with resolved_n=0 and "
                "places them on the ranked roster"
            ),
        },
        "claims": [
            {
                "id": "C1",
                "claim": "A minimum store schema exists that refuses a numeric brier when resolved_n=0.",
                "verdict": "CONFIRMED",
                "anchor": derive_anchor,
            },
            {
                "id": "C2",
                "claim": "Cold start populates UNRANKABLE identity rows and yields an empty ranked list.",
                "verdict": "CONFIRMED",
                "anchor": selector_anchor,
            },
            {
                "id": "C3",
                "claim": "Zero-history participants must NOT be ranked as average; the selector marks them UNRANKABLE.",
                "verdict": "CONFIRMED",
                "anchor": detector_anchor,
            },
            {
                "id": "C4",
                "claim": "11-COUNCIL-SPECIFICATION.schema.json on this worktree already defines this store.",
                "verdict": "REFUTED",
                "anchor": "inputs_on_this_tree.11-COUNCIL-SPECIFICATION.schema.json=false",
            },
            {
                "id": "C5",
                "claim": "Treating missing history as the pool mean is a harmless default.",
                "verdict": "REFUTED",
                "anchor": detector_anchor,
            },
        ],
        "evidence": [
            {
                "claim": "Set algebra over raw SCOREABLE counts vs ranked ids is empty for the honest selector and non-empty for average-imputation.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0014/selector.py:disjoint_zero_history",
                "mechanism": "python set intersection on resolved_n counted from outcomes[] (not rank_class)",
                "command_or_anchor": (
                    "python3 -B command-center/p2-wave/probes/CNL-0014/probe1_cold_start.py"
                ),
                "verbatim": set_line,
            },
            {
                "claim": "The detector is SILENT on the honest ranking and FIRES on planted mean-imputation, including the cold-start 0.5 default.",
                "verdict": "CONFIRMED",
                "anchor": detector_anchor,
                "mechanism": "both-states ranking-document inspection (finding codes, not set algebra)",
                "command_or_anchor": (
                    "python3 -B command-center/p2-wave/probes/CNL-0014/probe2_both_states.py"
                ),
                "verbatim": both_line + " | " + cold_line,
            },
            {
                "claim": "Store validator accepts the mixed fixture and rejects a planted brier=0.5 at resolved_n=0.",
                "verdict": "CONFIRMED",
                "anchor": STORE_SCHEMA,
                "mechanism": "jsonschema Draft7 plus derived-field invariants",
                "command_or_anchor": STORE_SCHEMA,
                "verbatim": store_line,
            },
        ],
        "tests": [
            {
                "id": "T-COLD-START",
                "name": "zero-history participants must NOT be ranked as average",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-BOTH-STATES",
                "name": "detector FIRES on planted-average and is SILENT on known-good",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-AVERAGE-IMPUTATION",
                "rejects": (
                    "a ranking that assigns the scored-pool mean or uninformative "
                    "0.5 to participants with resolved_n=0 and places them on the "
                    "ranked roster"
                ),
                "observed": (
                    "SILENT on known-good honest ranking; FIRES on planted-average. "
                    + both_line
                ),
                "on_known_good": "SILENT",
                "on_planted_bad": "FIRES",
                "verbatim": (
                    "the check FIRES when a zero-history participant is assigned "
                    "the mean Brier of the scored pool (or 0.5 when the pool is "
                    "empty) and placed on the ranked roster; it is SILENT when "
                    "zero-history participants are UNRANKABLE, brier=null, and "
                    "absent from ranked. "
                    + both_line
                ),
            },
            {
                "id": "NC-INVENTED-STORE-ROW",
                "rejects": "a store record with resolved_n=0 and brier=0.5 / RANK_ELIGIBLE",
                "observed": store_line,
                "on_known_good": "SILENT",
                "on_planted_bad": "FIRES",
                "verbatim": store_line,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0014-probe2-both-states",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "counterexample": (
                "Instance: mixed fixture + rank_with_average_imputation. cara has "
                "only an UNSCOREABLE outcome (resolved_n=0) and receives the pool "
                f"mean {m['mixed']['imputed_average']}, which ranks her above bob "
                f"(brier={m['mixed']['bob_brier']}). Honest selector does not emit "
                "that roster; detector findings include ZERO_HISTORY_RANKED."
            ),
        },
        "schema_controls": {
            "design_note_garbage_rejected": note_garbage,
            "store_garbage_rejected": store_garbage,
            "catalog_output_schema": {
                "path": SCHEMA,
                "generated_shim": True,
                "remote_ref_not_resolved": True,
                "local_probe_contract_used": True,
            },
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {"path": STORE_SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/CNL-0014/store.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0014/selector.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0014/detector.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "cold-start-zero-history"},
            {"id": "probe2", "command": P2, "role": "both-states-average-imputation"},
        ],
    }

    try:
        jsonschema.Draft7Validator(NOTE_CONTRACT).validate(doc)
    except jsonschema.ValidationError as exc:
        print(f"FAILED:CNL-0014 design-note schema: {exc.message}")
        print(f"schema_required={NOTE_CONTRACT.get('required')}")
        return 1
    store_errors = S.validate_store(S.empty_store())
    if store_errors:
        print(f"FAILED:CNL-0014 empty store invalid {store_errors}")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={out_path.stat().st_size}")
    print("SUCCESS:CNL-0014 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
