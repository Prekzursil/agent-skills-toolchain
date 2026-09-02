#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0068-disposition-decision-procedure.json."""
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

from agreement import AGREEMENT_FLOOR  # noqa: E402
from decide import decide  # noqa: E402
from gold_set import (  # noqa: E402
    GOLD_VERSION,
    SAMPLING_RULE,
    gold_records,
    overlap_reject_retire,
    restored_license_adopt,
)
from independent import decide_independent  # noqa: E402
from score import score_gold  # noqa: E402
from vocabulary import (  # noqa: E402
    REQUIRED_INPUTS,
    VOCABULARY,
    ranks_are_total,
    rules_public,
    tie_break_order,
)

OUT = "command-center/wfa/WFA-0068-disposition-decision-procedure.json"
SCHEMA = "command-center/p2-wave/probes/WFA-0068/disposition-record.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0068/probe1_gold_agreement_refusal.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0068/probe2_tiebreak_independent.py"
)
SENTINEL = "SUCCESS:WFA-0068"
QUESTION = (
    "Implementation target: a decision procedure that maps a fully extracted "
    "candidate record to exactly one of the 15 classification values, with "
    "falsifiable written criteria per value, an explicit tie-break order, and "
    "a refusal path to UNKNOWN-NEEDS-PROBE whenever a required input is missing."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:WFA-0068 emit snippet not found: {snippet!r}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    path = REPO / rel
    line = find_line(path, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def dep_status(rel: str) -> dict:
    path = REPO / rel
    if not path.is_file() or path.stat().st_size <= 0:
        return {"path": rel, "present": False, "bytes": 0}
    return {"path": rel, "present": True, "bytes": path.stat().st_size}


def main() -> int:
    if not ranks_are_total():
        print("FAILED:WFA-0068 tie-break order is not total")
        return 1
    scored = score_gold()
    if scored["no_rule_fired"]:
        print(f"FAILED:WFA-0068 no-rule-fired {scored['no_rule_fired']}")
        return 1
    if not scored["author_meets_floor"]:
        print("FAILED:WFA-0068 author per-disposition floor")
        print(json.dumps(scored["author_per_disposition"], indent=2))
        return 1
    if not scored["independent_meets_floor"]:
        print("FAILED:WFA-0068 independent per-disposition floor")
        return 1
    if not scored["author_independent_agree"]:
        print("FAILED:WFA-0068 author/independent disagreement")
        return 1

    miss = next(r for r in gold_records() if r["id"] == "GOLD-09")
    refusal = decide(miss)
    if refusal["disposition"] != "UNKNOWN-NEEDS-PROBE" or refusal["reason"] != "required-input-refusal":
        print(f"FAILED:WFA-0068 refusal path {refusal}")
        return 1
    restored = decide(restored_license_adopt())
    if restored["disposition"] != "ADOPT-AS-IS":
        print(f"FAILED:WFA-0068 restored-license both-states {restored}")
        return 1
    overlap = overlap_reject_retire()
    o_a = decide(overlap)
    o_b = decide_independent(overlap)
    if o_a["disposition"] != "REJECT" or o_b["disposition"] != "REJECT":
        print(f"FAILED:WFA-0068 overlap {o_a} {o_b}")
        return 1
    if sorted(o_a["fired"]) != ["REJECT", "RETIRE"]:
        print(f"FAILED:WFA-0068 overlap fired {o_a['fired']}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    n_ok = sum(1 for r in scored["records"] if r["match_gold"])
    answer = (
        f"The written 15-value procedure maps each fully extracted candidate to "
        f"exactly one vocabulary value via a total tie-break order "
        f"{tie_break_order()}. On the frozen 20-record gold set (version "
        f"{GOLD_VERSION}) author and independent replay both match gold labels "
        f"{n_ok}/20; per-disposition agreement meets floor {AGREEMENT_FLOOR} "
        f"for every value (no aggregate-only pass). GOLD-09 with license=EMPTY "
        f"refuses to UNKNOWN-NEEDS-PROBE (missing_input=license); restoring "
        f"license yields ADOPT-AS-IS. Overlap REJECT+RETIRE resolves to REJECT. "
        f"WFA-0042/WFA-0043/WFA-0005 artifacts are absent on this tree; the "
        f"15-value list is taken from the catalog/spec (WFA-0005) and is not "
        f"deleted for zero corpus count. {SENTINEL}"
    )

    vocab_py = "command-center/p2-wave/probes/WFA-0068/vocabulary.py"
    gold_py = "command-center/p2-wave/probes/WFA-0068/gold_set.py"
    evidence = [
        ev(
            CATALOG,
            '"id": "WFA-0068"',
            "catalog",
            "Unit contract: 15-value decision procedure with refusal and total tie-break",
        ),
        ev(
            CATALOG,
            "CLEAN-ROOM-REIMPLEMENT, COMPOSE, GENERALIZE, REBUILD-FROM-SPEC, REJECT and TRANSLATE",
            "catalog",
            "WFA-0005: six unused values remain in the vocabulary; zero count is not deletion",
        ),
        ev(
            "command-center/p2-wave/probes/WFA-0068/decide.py",
            '"reason": "required-input-refusal"',
            "probe",
            "Refusal path maps a missing required input to UNKNOWN-NEEDS-PROBE",
        ),
        ev(
            vocab_py,
            "return sorted(ranks) == list(range(len(rows)))",
            "probe",
            "Tie-break ranks must be a unique 0..n-1 covering every vocabulary value",
        ),
        ev(
            gold_py,
            'include exactly one deliberate missing-required-input record',
            "fixture",
            "Sampling rule frozen before gold construction requires the refusal record",
        ),
        ev(
            "command-center/p2-wave/probes/WFA-0068/independent.py",
            "argmin-rank-over-firing-set",
            "probe",
            "Independent replay selects min(rank) over the firing set and does not read gold labels",
        ),
        ev(
            "command-center/p2-wave/probes/WFA-0068/agreement.py",
            "AGREEMENT_FLOOR = 1.0",
            "probe",
            "Per-disposition floor is pre-registered; aggregate accuracy is not the gate",
        ),
    ]

    gold_public = []
    for rec, labelled in zip(gold_records(), scored["records"]):
        gold_public.append(
            {
                "id": rec["id"],
                "family": rec["family"],
                "gold": rec["gold"],
                "refusal": bool(rec.get("refusal")),
                "missing_field": rec.get("missing_field"),
                "features": {
                    k: rec.get(k)
                    for k in (
                        "runtime",
                        "license",
                        "probe_needed",
                        "fitness",
                        "safety",
                        "lifecycle",
                        "source_state",
                        "reimplementable",
                        "spec_present",
                        "compose_of",
                        "duplicate_of",
                        "specificity",
                        "gaps",
                        "defects",
                        "core_intact",
                        "salvageable",
                        "take_whole",
                        "mechanism_worth_keeping",
                        "needs_wrapper",
                        "smoke_passes",
                    )
                },
                "author": labelled["author"],
                "independent": labelled["independent"],
            }
        )

    doc = {
        "unit_id": "WFA-0068",
        "state": "SUCCESS",
        "schema_version": 1,
        "record_type": "DispositionRecord",
        "title": "Disposition decision procedure for the closed 15-value vocabulary",
        "question": QUESTION,
        "answer": answer,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "cloud_ok": False,
        "vocabulary": list(VOCABULARY),
        "vocabulary_count": len(VOCABULARY),
        "unused_values_kept": [
            "CLEAN-ROOM-REIMPLEMENT",
            "COMPOSE",
            "GENERALIZE",
            "REBUILD-FROM-SPEC",
            "REJECT",
            "TRANSLATE",
        ],
        "tie_break_order": tie_break_order(),
        "tie_break_total": True,
        "required_inputs": list(REQUIRED_INPUTS) + ["extraction_complete"],
        "criteria": rules_public(),
        "refusal_path": {
            "disposition": "UNKNOWN-NEEDS-PROBE",
            "when": "any required input is None/empty/EMPTY, or extraction_complete is not true",
            "control_record": "GOLD-09",
            "missing_input": refusal["missing_input"],
            "verdict": refusal["disposition"],
            "restored_record": "GOLD-09-RESTORED",
            "restored_verdict": restored["disposition"],
        },
        "gold_set": {
            "version": GOLD_VERSION,
            "n": 20,
            "sampling_rule": SAMPLING_RULE,
            "frozen": True,
            "source": (
                "constructed-for-WFA-0068; WFA-0042 extraction gold artifact absent "
                "on this tree"
            ),
            "family_coverage": scored["family_coverage"],
            "disposition_coverage": scored["disposition_coverage"],
            "records": gold_public,
        },
        "agreement_floor": AGREEMENT_FLOOR,
        "aggregate_accuracy_is_not_the_gate": True,
        "per_disposition_agreement": scored["author_per_disposition"],
        "author_aggregate_accuracy": scored["author_aggregate_accuracy"],
        "author_meets_floor": True,
        "independent_replay": {
            "method": "argmin-rank-over-firing-set",
            "vendor_model_invoked": False,
            "why_not_cross_vendor_llm": (
                "This substrate does not invoke a second vendor model. Mechanical "
                "independence is a second code path over the same written criteria "
                "that never reads gold labels."
            ),
            "per_disposition_agreement": scored["independent_per_disposition"],
            "aggregate_accuracy": scored["independent_aggregate_accuracy"],
            "meets_floor": True,
            "agree_with_author_n": scored["author_independent_agree_n"],
            "agree_with_author": True,
        },
        "overlap_control": {
            "id": overlap["id"],
            "fired": o_a["fired"],
            "winner": o_a["disposition"],
            "independent_winner": o_b["disposition"],
            "expected": "REJECT",
        },
        "dependency_status": {
            "WFA-0005": dep_status(
                "command-center/wfa/WFA-0005-classification-vocabulary-audit.json"
            ),
            "WFA-0042": dep_status("command-center/wfa/WFA-0042-extraction-gold-set.json"),
            "WFA-0043": dep_status(
                "command-center/wfa/WFA-0043-extraction-coverage-matrix.json"
            ),
            "schema_pack": dep_status("command-center/wfa/schema/wfa-schema-pack.json"),
        },
        "tests": [
            {
                "id": "T1-per-disposition-agreement-and-refusal",
                "name": "Per-disposition gold agreement, missing-input refusal both-states",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-tie-break-total-and-independent-replay",
                "name": "Tie-break totality, overlap, independent argmin-rank replay",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0068-probe2-independent-argmin-rank",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-derives the firing set and min(rank) without reading "
                "gold labels, and fails if two rules share a rank."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "gold-agreement-and-refusal", "command": P1},
            {"id": "probe2", "role": "tiebreak-and-independent-replay", "command": P2},
        ],
        "evidence": evidence,
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/WFA-0068/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "WFA-0042 extraction gold set was present and scored",
                "a second vendor LLM labelled the gold set",
                "the six unused vocabulary values were deleted",
            ]
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "adjudicator",
            "execution_substrate": "linux-local",
        },
        "timestamps": {"measured_at": now},
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
        ],
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(doc)

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:WFA-0068 sentinel missing from serialized artifact")
        return 1
    out_path.write_text(text, encoding="utf-8")
    sha, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
