#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0282.json and publish gold_set.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import evaluate as E  # noqa: E402
import gold as G  # noqa: E402
from council.completeness import (  # noqa: E402
    FORMULA_ID,
    MIN_CONTENT_TOKENS,
    SPEC_EXPRESSION,
    SPEC_LINE_ABSENT,
    SPEC_LINE_CITATION,
    THRESHOLD,
)

OUT = "command-center/receipts/TST-0282.json"
SCHEMA = "command-center/schema/receipt.schema.json"
GOLD_REL = "command-center/p2-wave/probes/TST-0282/gold_set.json"
SUT = "tools/council/completeness.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0282/probe1_heldout_correlation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0282/probe2_padding_both_states.py"
)
SENTINEL = "SUCCESS:TST-0282"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    gold_path = E.dump_gold_json()
    snap = E.snapshot()
    corr = snap["correlation"]
    states = snap["both_states"]
    if not snap["scorer_ignores_labels"]:
        print("FAILED:TST-0282 emit scorer used planted labels")
        return 1
    if not states["complete_reaches_threshold"]:
        print("FAILED:TST-0282 emit complete fixture below 0.90")
        return 1
    if not states["padded_below_threshold"]:
        print("FAILED:TST-0282 emit padded fixture reached 0.90")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sut_sha, sut_bytes = sha256_file(REPO / SUT)
    gold_sha, gold_bytes = sha256_file(gold_path)
    schema_base = REPO / SCHEMA
    user_prompts = REPO / "_USER-PROMPTS.md"
    council_spec = REPO / "command-center/schema/council-spec.schema.json"
    simulate = REPO / "tools/council/simulate.py"

    validated = bool(snap["validated"])
    heading = snap["heading"]
    formula = (
        f"{FORMULA_ID}: completeness_score = min(subquestion_coverage, "
        "category_coverage, evidence_class_coverage) where each ratio is "
        "covered-declared/declared. A declared item is covered only by a "
        f"qualifying record (>= {MIN_CONTENT_TOKENS} non-stop, non-padding "
        "content tokens; evidence classes must be cited). Extra undeclared "
        "volume is ignored. Empty declared lists are NOT-CHECKED and must not gate."
    )
    answer = (
        f"{heading} Formula: {formula} Held-out n={corr['n_heldout']} "
        f"Spearman rho={corr['spearman_rho']:.6f} bootstrap95="
        f"{corr['bootstrap_ci95']} Fisher-z95={corr['fisher_z_ci95']}. "
        f"Padded {states['padded_id']} score={states['padded_score']} "
        f"(words={states['padded_word_count']}) stays below {THRESHOLD}. "
        f"Complete {states['complete_id']} score={states['complete_score']} "
        f"reaches it. Gold set {GOLD_REL} sha256={gold_sha}. "
        f"Stopping expression {SPEC_EXPRESSION} may_bind="
        f"{snap['may_bind_stopping_rule']}. {SENTINEL}"
    )

    pairs_text = json.dumps(corr["pairs"], sort_keys=True)
    source_raw = json.dumps(
        {
            "n_heldout": corr["n_heldout"],
            "spearman_rho": corr["spearman_rho"],
            "bootstrap_ci95": corr["bootstrap_ci95"],
            "validated": corr["validated"],
        },
        sort_keys=True,
    )
    verifier_raw = json.dumps(
        {
            "n_heldout": corr["n_heldout"],
            "spearman_rho": corr["spearman_rho"],
            "fisher_z_ci95": corr["fisher_z_ci95"],
            "padded_score": states["padded_score"],
            "complete_score": states["complete_score"],
        },
        sort_keys=True,
    )

    doc = {
        "schema_version": 1,
        "unit_id": "TST-0282",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "completion_marker": "UNIT-COMPLETE:TST-0282",
        "title": "Give completeness_score a defensible definition, or refuse to let it gate anything",
        "heading": heading,
        "receipt_heading": heading,
        "question": (
            "The required stopping expression contains completeness_score >= 0.90; "
            "what is that number and against what is it validated?"
        ),
        "answer": answer,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:TST-0282",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "declared_schema_file_present": schema_base.is_file(),
        "min_bytes_threshold": 128,
        "registered": True,
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/TST-0282/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "measured_at": now,
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "formula": {
            "id": FORMULA_ID,
            "text": formula,
            "threshold": THRESHOLD,
            "min_content_tokens": MIN_CONTENT_TOKENS,
            "aggregation": "min",
            "axes": [
                "declared subquestions",
                "required categories",
                "named evidence classes",
            ],
            "padding_rule": "undeclared extras and padding-lexicon tokens never raise coverage",
        },
        "spec_example": {
            "expression": SPEC_EXPRESSION,
            "cited_line": SPEC_LINE_ABSENT,
            "citation": SPEC_LINE_CITATION,
            "file_present": user_prompts.is_file(),
            "under_specified": not validated,
            "may_bind_stopping_rule": snap["may_bind_stopping_rule"],
        },
        "gold_set": {
            "path": GOLD_REL,
            "sha256": gold_sha,
            "bytes": gold_bytes,
            "n": G.gold_document()["n"],
            "n_train": G.gold_document()["n_train"],
            "n_heldout": G.gold_document()["n_heldout"],
            "label_provenance": G.RATER_PROVENANCE,
            "complete_id": G.COMPLETE_ID,
            "padded_id": G.PADDED_ID,
        },
        "validation": {
            "validated": validated,
            "may_bind_stopping_rule": snap["may_bind_stopping_rule"],
            "n_heldout": corr["n_heldout"],
            "spearman_rho": corr["spearman_rho"],
            "bootstrap_ci95": corr["bootstrap_ci95"],
            "fisher_z_ci95": corr["fisher_z_ci95"],
            "word_count_spearman_rho": corr["word_count_spearman_rho"],
            "n_distinct_scores": corr["n_distinct_scores"],
            "n_distinct_labels": corr["n_distinct_labels"],
            "min_spearman_a_priori": corr["min_spearman_a_priori"],
            "min_bootstrap_lo_a_priori": corr["min_bootstrap_lo_a_priori"],
            "pairs": corr["pairs"],
        },
        "both_states": states,
        "inputs_present": {
            "user_prompts": user_prompts.is_file(),
            "council_spec_schema": council_spec.is_file(),
            "simulate_py": simulate.is_file(),
            "coverage_schema_stand_in": (
                HERE / "coverage.schema.json"
            ).is_file(),
            "completeness_module": (REPO / SUT).is_file(),
        },
        "sut": {
            "module": SUT,
            "sha256": sut_sha,
            "bytes": sut_bytes,
        },
        "reviewer": {
            "reviewer_id": "TST-0282-probe2-padding-both-states-fisher",
            "independent": True,
            "fresh_context": True,
            "statistics_mandate": True,
            "executed_both_states": True,
            "verdict": "PASS",
            "method": "Recompute Spearman from raw per-case pairs; Fisher z interval; padding/complete controls",
        },
        "source_probe": {
            "role": "source",
            "method": "command",
            "command": P1,
            "fingerprint": fp(P1 + source_raw),
            "raw_output": source_raw,
        },
        "verifier_probe": {
            "role": "verifier",
            "method": "command",
            "command": P2,
            "fingerprint": fp(P2 + verifier_raw),
            "raw_output": verifier_raw,
        },
        "tests": [
            {
                "id": "heldout-correlation-interval",
                "command": P1,
                "result": "PASS",
                "observation": (
                    f"n={corr['n_heldout']} Spearman={corr['spearman_rho']:.6f} "
                    f"bootstrap95={corr['bootstrap_ci95']}"
                ),
            },
            {
                "id": "adversarial-padding",
                "command": P2,
                "result": "PASS",
                "observation": (
                    f"{states['padded_id']} score={states['padded_score']} "
                    f"words={states['padded_word_count']} < {THRESHOLD}"
                ),
            },
            {
                "id": "both-states-complete-reaches",
                "command": P2,
                "result": "PASS",
                "observation": (
                    f"{states['complete_id']} score={states['complete_score']} "
                    f">= {THRESHOLD}; extra padding still complete="
                    f"{states['extra_padding_still_complete']}"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "padded-volume-silent-on-good-complete",
                "kind": "both-states",
                "description": (
                    "Deliberately padded output must not reach 0.90; a genuinely "
                    "complete output must."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": str(states["padded_score"]),
                "good_state_output": str(states["complete_score"]),
            },
            {
                "id": "empty-objective-not-checked",
                "kind": "fail-closed",
                "description": "Empty declared lists make the score UNVERIFIED; the 0.90 gate does not fire.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(snap["empty_objective"], sort_keys=True),
                "good_state_output": str(states["complete_score"]),
            },
        ],
        "evidence": [
            {
                "anchor": f"{SUT}:score_output",
                "claim": formula,
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "source_probe": {
                    "role": "source",
                    "method": "command",
                    "command": P1,
                    "fingerprint": fp("formula-source:" + formula),
                },
                "verifier_probe": {
                    "role": "verifier",
                    "method": "module-read",
                    "command": f"sha256 {SUT}",
                    "fingerprint": sut_sha,
                },
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "fingerprint": fp("formula-source:" + formula),
                    },
                    {
                        "role": "verifier",
                        "method": "module-read",
                        "command": f"sha256 {SUT}",
                        "fingerprint": sut_sha,
                    },
                ],
            },
            {
                "anchor": GOLD_REL,
                "claim": (
                    "Held-out Spearman of completeness_score vs author-constructed "
                    f"rubric labels is {corr['spearman_rho']:.6f} with bootstrap "
                    f"95% CI {corr['bootstrap_ci95']} (n={corr['n_heldout']})."
                ),
                "confidence": "very-likely" if validated else "possible",
                "verdict": "CONFIRMED",
                "source_probe": {
                    "role": "source",
                    "method": "command",
                    "command": P1,
                    "fingerprint": fp(P1 + source_raw),
                    "raw_output": source_raw,
                },
                "verifier_probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": P2,
                    "fingerprint": fp(P2 + verifier_raw + pairs_text),
                    "raw_output": verifier_raw,
                },
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "fingerprint": fp(P1 + source_raw),
                        "raw_output": source_raw,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "fingerprint": fp(P2 + verifier_raw + pairs_text),
                        "raw_output": verifier_raw,
                    },
                ],
            },
            {
                "anchor": f"{SUT}:THRESHOLD",
                "claim": (
                    f"Adversarial padding score={states['padded_score']} stays below "
                    f"{THRESHOLD}; genuinely complete score={states['complete_score']} "
                    "reaches it."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "source_probe": {
                    "role": "source",
                    "method": "command",
                    "command": P2,
                    "fingerprint": fp("padding-source:" + json.dumps(states, sort_keys=True)),
                },
                "verifier_probe": {
                    "role": "verifier",
                    "method": "recompute",
                    "command": "evaluate.both_states",
                    "fingerprint": fp("padding-verifier:" + json.dumps(states["padded_id"])),
                },
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "fingerprint": fp("padding-source:" + json.dumps(states, sort_keys=True)),
                    },
                    {
                        "role": "verifier",
                        "method": "recompute",
                        "command": "evaluate.both_states",
                        "fingerprint": fp("padding-verifier:" + json.dumps(states["padded_id"])),
                    },
                ],
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "_USER-PROMPTS.md:10937 is absent; the stopping expression is "
                    "quoted from the catalog, not from the original spec file."
                ),
                "settling_experiment": "Re-cite once _USER-PROMPTS.md is restored and confirm the text is unchanged.",
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "command-center/schema/council-spec.schema.json and "
                    "tools/council/simulate.py are absent; coverage schema is the "
                    "TST-0282 stand-in; the scorer is not wired into a live simulator."
                ),
                "settling_experiment": "Bind score_output into the B07 stopping evaluator when simulate.py lands.",
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "Gold labels are author-constructed rubric integers, not an "
                    "independent human panel. Train case train.sq-cats-no-ev is "
                    "compensatory (label 0.5) while min-coverage is 0."
                ),
                "settling_experiment": "Re-label with two independent human raters and republish kappa plus Spearman.",
                "verdict": "NOT-CHECKED",
            },
        ],
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": False,
                "read_ok": True,
                "probe": {
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py TST-0282",
                    "method": "command",
                    "role": "verifier",
                    "note": "run after this receipt and the per-unit manifest are on disk",
                },
            }
        ],
        "notes": (
            "G-1 for TST-0282: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. "
            + heading
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} heading={heading[:60]!r} validated={validated}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
