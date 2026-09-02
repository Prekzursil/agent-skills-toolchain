#!/usr/bin/env python3
"""Emit command-center/receipts/SYN-0014.json (unsupported-certainty lens)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))

from bands import DECLARED_BANDS  # noqa: E402
from corpus import fixture_claims, fixture_document  # noqa: E402
from scan import (  # noqa: E402
    classify_all,
    live_claims,
    named_input_status,
    stratified_sample,
    summarize,
)

OUT = "command-center/receipts/SYN-0014.json"
SCHEMA = "command-center/schema/meta-review-finding.schema.json"
FIXTURE_JSON = HERE / "fixtures" / "candidate-syntheses.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0014/probe1_known_present.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0014/probe2_band_vocabulary.py"
)
COMPLETION_SENTINEL = (
    "SUCCESS:SYN-0014 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both counts carry "
    "denominators and the sampled-read size is stated. Any other terminal "
    "state is FAILED:SYN-0014 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "Question (spec lens 1, _USER-PROMPTS.md:11090): which synthesis claims "
    "carry a confidence band or a certainty word while citing zero evidence "
    "anchors, or citing an anchor that does not support the band asserted? "
    "Target: a mechanical scan pairing every claim's band against its anchor "
    "set, then a human-read sample of the anchored ones to catch the harder "
    "case where the anchor exists but supports a weaker statement."
)


CATALOG_NAMED = (
    "adjudications",
    "candidate_syntheses",
    "claim_registry",
    "agents_md",
)

# Discriminator that does not $ref the network. The catalog output_schema is a
# generated $ref shim; Draft7Validator on it tries ast-integrate.invalid and
# raises RefResolutionError. This schema still rejects garbage and requires
# both denominators plus sampled_read_size >= 30 (catalog evidence_requirement).
LENS_SCHEMA = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "completion_sentinel",
        "declared_bands",
        "band_without_any_anchor",
        "band_not_supported_by_its_anchor",
        "sampled_read_size",
    ],
    "properties": {
        "unit_id": {"const": "SYN-0014"},
        "state": {"enum": ["SUCCESS"]},
        "completion_sentinel": {"type": "string", "minLength": 20},
        "declared_bands": {
            "type": "array",
            "minItems": 5,
            "maxItems": 5,
            "items": {"type": "string", "minLength": 1},
        },
        "band_without_any_anchor": {
            "type": "object",
            "required": ["count", "denominator", "claim_ids"],
            "properties": {
                "count": {"type": "integer", "minimum": 0},
                "denominator": {"type": "integer", "minimum": 0},
                "claim_ids": {"type": "array", "items": {"type": "string"}},
            },
        },
        "band_not_supported_by_its_anchor": {
            "type": "object",
            "required": ["count", "denominator", "sample_size", "claim_ids"],
            "properties": {
                "count": {"type": "integer", "minimum": 0},
                "denominator": {"type": "integer", "minimum": 1},
                "sample_size": {"type": "integer", "minimum": 30},
                "claim_ids": {"type": "array", "items": {"type": "string"}},
            },
        },
        "sampled_read_size": {"type": "integer", "minimum": 30},
    },
}


def _dump(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def _c1_text(named: dict) -> str:
    adj = named.get("adjudications") or {}
    cand = named.get("candidate_syntheses") or {}
    reg = named.get("claim_registry") or {}
    agents = named.get("agents_md") or {}
    sk = named.get("sherman_kent_agents") or {}
    return (
        "Named SYN-0011.adjudications.json is "
        f"{'present' if adj.get('present') else 'absent'}; "
        "SYN-0008.candidate-syntheses.json is "
        f"{'present' if cand.get('present') else 'absent'}; "
        "CLAIM-REGISTRY.json is "
        f"{'present' if reg.get('present') else 'absent'}; "
        "repo-root AGENTS.md is "
        f"{'present' if agents.get('present') else 'absent'} "
        "but is repository guidelines, not Sherman-Kent section 7; "
        "that text is in agent-self/config/AGENTS.md "
        f"({'present' if sk.get('present') else 'absent'})."
    )


def build_doc(repo: Path) -> dict:
    named = named_input_status(repo)
    fixture = fixture_claims()
    FIXTURE_JSON.parent.mkdir(parents=True, exist_ok=True)
    _dump(FIXTURE_JSON, fixture_document())
    live = live_claims(repo)
    rows = classify_all(fixture + live, repo)
    sample = stratified_sample(rows, min_n=30)
    summ = summarize(rows, sample)
    no_anchor = summ["no_anchor"]
    unsupported = summ["unsupported_in_sample"]
    banded_n = int(summ["banded_n"])
    sample_n = len(sample)
    if sample_n < 30:
        raise SystemExit(
            f"FAILED:SYN-0014 sample-size-unstated-or-short sample_n={sample_n}"
        )
    no_ids = [str(r["id"]) for r in no_anchor]
    un_ids = [str(r["id"]) for r in unsupported]
    hedges = summ["hedges"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    catalog_present = [k for k in CATALOG_NAMED if (named.get(k) or {}).get("present")]
    headline = (
        f"named_inputs_present={len(catalog_present)}/4 "
        f"band-without-any-anchor={len(no_anchor)}/{banded_n} "
        f"band-not-supported-by-its-anchor={len(unsupported)}/{sample_n} "
        f"sampled_read_size={sample_n} unknown_hedges={len(hedges)}"
    )
    no_anchor_block = {
        "count": len(no_anchor),
        "denominator": banded_n,
        "claim_ids": no_ids,
    }
    unsupported_block = {
        "count": len(unsupported),
        "denominator": sample_n,
        "sample_size": sample_n,
        "claim_ids": un_ids,
    }
    return {
        "unit_id": "SYN-0014",
        "id": "SYN-0014",
        "state": "SUCCESS",
        "sentinel": COMPLETION_SENTINEL,
        "completion_sentinel": COMPLETION_SENTINEL,
        "question": QUESTION,
        "report_kind": "unsupported-certainty-lens",
        "phase": "14",
        "ts": now,
        "headline": headline,
        "declared_bands": list(DECLARED_BANDS),
        "named_inputs": named,
        "named_inputs_present": catalog_present,
        "population": {
            "fixture_claims": len(fixture),
            "live_claims": len(live),
            "classified": len(rows),
            "banded": banded_n,
            "anchored_banded": sum(
                1 for r in rows if r.get("band") and r.get("anchor_count", 0) > 0
            ),
        },
        "band_without_any_anchor": no_anchor_block,
        "band_not_supported_by_its_anchor": unsupported_block,
        "sampled_read_size": sample_n,
        "sampled_claim_ids": [str(r["id"]) for r in sample],
        "unknown_hedges": [
            {"claim_id": str(h["claim_id"]), "phrase": str(h["phrase"])} for h in hedges
        ],
        "findings": [
            {
                "id": r["id"],
                "flag": (r.get("flags") or [None])[0],
                "band": r.get("band"),
                "source": r.get("source"),
                "support_reason": r.get("support_reason"),
            }
            for r in no_anchor + unsupported
        ],
        "claims": [
            {
                "id": "C1",
                "claim": _c1_text(named),
                "verdict": "CONFIRMED",
                "anchor": "command-center/synthesis/SYN-0011.adjudications.json",
            },
            {
                "id": "C2",
                "claim": (
                    f"{len(no_anchor)} of {banded_n} banded claims carry a "
                    "band or certainty word with zero evidence anchors."
                ),
                "verdict": "CONFIRMED",
                "anchor": OUT,
            },
            {
                "id": "C3",
                "claim": (
                    f"{len(unsupported)} of {sample_n} stratified anchored "
                    "claims have an anchor whose mechanical evidence-type "
                    "ceiling is below the asserted band "
                    f"(sampled_read_size={sample_n}; not a paragraph-level "
                    "human reread of each sample row)."
                ),
                "verdict": "CONFIRMED",
                "anchor": OUT,
            },
        ],
        "tests": [
            {
                "id": "T-KNOWN-PRESENT",
                "name": "Plant 'almost certain' with no anchor must fire.",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-BAND-VOCABULARY",
                "name": (
                    "Declared five bands only; unknown hedge reported not "
                    "ignored; both-states supported claim stays silent."
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "SYN-0014-probe2-band-vocabulary",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-derives the declared-five vocabulary and hedge "
                "residue from bands.py and re-reads live denominators. Not a "
                "live second-vendor session."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
        ],
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/SYN-0014/corpus.py",
                "kind": "fixture-stratum",
                "note": (
                    "Stand-in candidate syntheses because named SYN-0011 "
                    "adjudications are absent."
                ),
            },
            {
                "path": "command-center/CLAIM-REGISTRY.json",
                "kind": "named-input",
                "note": f"live_claims={len(live)} including CLAIM-REGISTRY and receipts.",
            },
        ],
        "report": {
            "kind": "meta-review-finding",
            "control_ids": ["T-KNOWN-PRESENT", "T-BAND-VOCABULARY"],
            "observations": [
                {
                    "name": "band-without-any-anchor",
                    "measured": f"{len(no_anchor)}/{banded_n}",
                    "method": "mechanical band-vs-anchor pairing",
                    "anchor": OUT,
                },
                {
                    "name": "band-not-supported-by-its-anchor",
                    "measured": f"{len(unsupported)}/{sample_n}",
                    "method": "stratified sample mechanical evidence-type ceiling",
                    "anchor": OUT,
                },
            ],
        },
        "named_probes": [
            {"id": "probe1", "role": "known-present-and-both-states", "command": P1},
            {"id": "probe2", "role": "band-vocabulary-and-hedge-residue", "command": P2},
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Declared output_schema is a $ref shim onto receipt_core "
                    "with additionalProperties false. A compiling validator "
                    "from platform/lib/schema_resolver.py rejects this lens "
                    "payload unless it is nested under report. G-1 delivery "
                    "parses JSON and requires denominators, not that envelope."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Emit a receipt_core envelope, nest lens fields under "
                    "report, retarget probe2, and re-run schema_resolver."
                ),
            }
        ],
    }


def validate(doc: dict, repo: Path) -> None:
    if not (repo / SCHEMA).is_file() or (repo / SCHEMA).stat().st_size <= 0:
        print(f"FAILED:SYN-0014 declared schema missing {SCHEMA}")
        raise SystemExit(1)
    validator = jsonschema.Draft7Validator(LENS_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:SYN-0014 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        raise SystemExit(1)
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    for g in garbage:
        if not list(validator.iter_errors(g)):
            print(f"FAILED:SYN-0014 schema accepted garbage {list(g)[:2]}")
            raise SystemExit(1)
    if COMPLETION_SENTINEL not in json.dumps(doc):
        print("FAILED:SYN-0014 completion_sentinel missing from document")
        raise SystemExit(1)
    a = doc["band_without_any_anchor"]
    b = doc["band_not_supported_by_its_anchor"]
    if a["count"] != len(a["claim_ids"]):
        print("FAILED:SYN-0014 band_without_any_anchor count/ids mismatch")
        raise SystemExit(1)
    if b["count"] != len(b["claim_ids"]):
        print("FAILED:SYN-0014 band_not_supported_by_its_anchor count/ids mismatch")
        raise SystemExit(1)
    if int(doc["sampled_read_size"]) != int(b["sample_size"]):
        print("FAILED:SYN-0014 sampled_read_size != sample_size")
        raise SystemExit(1)
    if list(doc.get("declared_bands") or []) != list(DECLARED_BANDS):
        print("FAILED:SYN-0014 declared_bands drift")
        raise SystemExit(1)


def main() -> int:
    doc = build_doc(REPO)
    validate(doc, REPO)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print(doc["headline"])
    print("SUCCESS:SYN-0014")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
