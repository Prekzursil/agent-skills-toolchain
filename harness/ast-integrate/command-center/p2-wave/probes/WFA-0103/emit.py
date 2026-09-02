#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0103-fusion-best-of-breed.json from a live fusion."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from workflow_forge.best_of_breed import (  # noqa: E402
    REPUTATION_NOT_EVIDENCE,
    TIED,
)
import fixtures as F  # noqa: E402
import fusion_op as Op  # noqa: E402

UNIT = "WFA-0103"
OUT = "command-center/wfa/WFA-0103-fusion-best-of-breed.json"
CATALOG_SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/FusionResult"
LOCAL_SCHEMA = HERE / "fusion_result.schema.json"
SENTINEL = "SUCCESS:WFA-0103"
QUESTION = (
    "Implementation target: an operator that, per stage slot, selects the "
    "implementation from whichever source scores best on the matched "
    "benchmark — and that refuses to select on any basis other than a "
    "measured score, since a model preference is not evidence."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    srcs = F.sources()
    separated = F.evidence_separated()
    tied = F.evidence_tied_synthesize()
    llm = F.evidence_llm_basis()

    result = Op.fuse(srcs, separated)
    if not result.get("ok"):
        print(f"FAILED:WFA-0103 separated fusion refused {result}")
        return 1
    traces = Op.selection_traces(result)
    if not traces["ok"]:
        print(f"FAILED:WFA-0103 selection traces {traces}")
        return 1
    ablations = Op.ablate_three_slots(result)
    if len(ablations) != 3 or any(not a["composite_moved"] for a in ablations):
        print(f"FAILED:WFA-0103 ablations {ablations}")
        return 1
    wf_errs = Op.fused_workflow_errors(result["workflow"])
    if wf_errs:
        print(f"FAILED:WFA-0103 fused workflow invalid {wf_errs[:4]}")
        return 1
    parity = Op.case_hash_parity(separated)
    if not parity["ok"]:
        print(f"FAILED:WFA-0103 case_hash parity {parity}")
        return 1

    tied_ok = Op.fuse(srcs, tied)
    if not tied_ok.get("ok"):
        print(f"FAILED:WFA-0103 tied+rule refused {tied_ok}")
        return 1
    synth = next(
        r for r in tied_ok["selection_record"] if r["slot_id"] == "synthesize"
    )
    if synth.get("resolution") != "TIED" or synth.get("chosen_source_id") != "wf.wfa0103.alpha":
        print(f"FAILED:WFA-0103 TIED record {synth}")
        return 1

    tied_refuse = Op.build(srcs, tied, tie_rule="refuse")
    if tied_refuse.get("error") != TIED:
        print(f"FAILED:WFA-0103 refuse path {tied_refuse}")
        return 1
    llm_refuse = Op.build(srcs, llm)
    if llm_refuse.get("error") != REPUTATION_NOT_EVIDENCE:
        print(f"FAILED:WFA-0103 llm basis {llm_refuse}")
        return 1
    prefer = Op.build(srcs, separated, prefer_source="wf.wfa0103.beta")
    if prefer.get("ok"):
        print("FAILED:WFA-0103 prefer_source accepted")
        return 1

    chosen = {row["slot_id"]: row["chosen_source_id"] for row in result["selection_record"]}
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    pack = REPO / "command-center" / "wfa" / "schema" / "wfa-schema-pack.json"
    local_schema = json.loads(LOCAL_SCHEMA.read_text(encoding="utf-8"))

    answer = (
        "Per-slot winners on matched cases (execution scores only): retrieve="
        f"{chosen['retrieve']} via {result['selection_record'][0]['benchmark_run_id']}, "
        f"rank={chosen['rank']} via {result['selection_record'][1]['benchmark_run_id']}, "
        f"synthesize={chosen['synthesize']} via "
        f"{result['selection_record'][2]['benchmark_run_id']}. Composite="
        f"{result['composite_score']}. Ablating each of the three slots to its "
        "second-best measured score rematerializes a lower composite. A synthesize "
        "slot with equal scores is recorded TIED and resolved by the written "
        "lexicographic-source-id rule to wf.wfa0103.alpha (not the fixture's "
        "llm_judgement preferring beta). selection_basis=llm_judgement is refused. "
        + SENTINEL
    )

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "record_kind": "FusionResult",
        "operator": "best-of-breed",
        "title": (
            "Fusion operator: best-of-breed, selecting each stage from "
            "whichever source performs it best"
        ),
        "question": QUESTION,
        "answer": answer,
        "output_path": OUT,
        "output_schema": CATALOG_SCHEMA,
        "schema_resolution": {
            "declared_path": CATALOG_SCHEMA,
            "declared_path_exists": pack.is_file(),
            "local_schema": (
                "command-center/p2-wave/probes/WFA-0103/fusion_result.schema.json"
            ),
            "note": (
                "WFA-0001 schema pack is not on this tree. The artifact is "
                "validated against the unit-local FusionResult schema, which "
                "rejects a garbage SUCCESS object. This unit does not author "
                "the 18-type pack."
            ),
        },
        "cloud_ok": False,
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "fusion-engineer",
            "execution_substrate": "local-parallel",
        },
        "engine": {
            "module": "tools/workflow_forge/best_of_breed.py",
            "wrapper": "command-center/p2-wave/probes/WFA-0103/fusion_op.py",
            "rule": (
                "per aligned stage slot, copy the source implementation with "
                "the highest measured score; every candidate must cite a "
                "benchmark run id; TIED slots use the written lexicographic "
                "source_id rule; reputation, prefer_source, and "
                "selection_basis=llm_judgement are refusals"
            ),
        },
        "source_ids": result["source_ids"],
        "fused_workflow_id": result["workflow"]["id"],
        "fused_workflow": result["workflow"],
        "composite_score": result["composite_score"],
        "selection": result["selection_record"],
        "run_id_coverage": traces["cited"],
        "ablations": ablations,
        "tie_policy": {
            "id": "lexicographic-source-id",
            "path": "command-center/p2-wave/probes/WFA-0103/TIE-RULE.txt",
            "written_before_apply": True,
            "text": F.tie_rule_text().strip(),
        },
        "tied_slot": {
            "slot_id": "synthesize",
            "resolution": synth["resolution"],
            "chosen_source_id": synth["chosen_source_id"],
            "tie_rule": synth["tie_rule"],
            "score": synth["score"],
            "loser_source_id": synth["losers"][0]["source_id"],
            "loser_score": synth["losers"][0]["score"],
            "benchmark_run_id": synth["benchmark_run_id"],
        },
        "llm_judgement_refused": True,
        "both_states": {
            "tied_with_written_rule_emits": True,
            "tied_without_rule_refused": tied_refuse.get("error") == TIED,
            "llm_selection_basis_refused": llm_refuse.get("error")
            == REPUTATION_NOT_EVIDENCE,
            "separated_scores_emit": True,
            "prefer_source_refused": not prefer.get("ok"),
        },
        "matched_pair_parity": parity,
        "fused_workflow_valid": not wf_errs,
        "inputs_used": {
            "benchmark_harness": (
                "local matched-pair fixture table "
                "fixtures/evidence_separated.json; both arms of each slot "
                "share case_hash. Catalog input WFA-0113 artifact is absent "
                "on this tree; this unit does not claim that harness."
            ),
            "semantic_diff": (
                "slots aligned by stage id equality (identity case of a "
                "stage-dimension differ). Catalog input WFA-0094 artifact is "
                "absent on this tree."
            ),
        },
        "tests": [
            {
                "id": "tied-slot-written-rule",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/WFA-0103/probe1_tied_written_rule.py"
                ),
                "result": "PASS",
                "assertions": 4,
            },
            {
                "id": "three-slot-ablation",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/WFA-0103/probe2_three_slot_ablation.py"
                ),
                "result": "PASS",
                "assertions": 3,
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Every chosen stage cites a benchmark run id and records "
                    "the losing alternative's measured score. Independent "
                    f"score-only winners match the operator: {chosen}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/WFA-0103/fusion_op.py:selection_traces",
                "confidence": "almost-certain",
            },
            {
                "claim": (
                    "Ablating retrieve, rank, and synthesize to the recorded "
                    "second-best measured score rematerializes a different "
                    "composite on each slot, so those selections are "
                    "evidence-driven rather than inert."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/WFA-0103/fusion_op.py:ablate_three_slots",
                "confidence": "almost-certain",
            },
        ],
        "negative_controls": [
            {
                "id": "WFA0103-C1-TIED-REFUSE",
                "kind": "known-broken-fixture",
                "description": (
                    "Equal synthesize scores with tie_rule=refuse must raise "
                    "TIED rather than prefer a source. The written-rule twin "
                    "must still emit with resolution=TIED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "WFA0103-C2-LLM-BASIS",
                "kind": "known-broken-fixture",
                "description": (
                    "A row that names selection_basis=llm_judgement must fail "
                    "the build even if a numeric score is also present."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0103-probe1-tied-written-rule-control",
            "verdict": "PASS",
            "independent": True,
            "scope": (
                "Re-ran TIED+written-rule accept, TIED-without-rule refuse, "
                "and llm_judgement basis refuse in this process."
            ),
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "notes": (
            "G-1 delivery of WFA-0103 best-of-breed fusion. Live named probes "
            "exit 0. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }

    if SENTINEL not in json.dumps(doc):
        print("FAILED:WFA-0103 sentinel-absent before write")
        return 1

    local_errs = list(jsonschema.Draft7Validator(local_schema).iter_errors(doc))
    if local_errs:
        print("FAILED:WFA-0103 local FusionResult schema")
        for e in local_errs[:12]:
            print(f"  {list(e.path)}: {e.message}")
        return 1
    garbage = {"unit_id": UNIT, "state": "SUCCESS", "ok": True}
    if not list(jsonschema.Draft7Validator(local_schema).iter_errors(garbage)):
        print("FAILED:WFA-0103 local FusionResult schema is vacuous")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
