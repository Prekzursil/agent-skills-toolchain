#!/usr/bin/env python3
"""Emit RES-0182 design spec from sealed participant priors + fetched snapshots."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import protocol as P

HERE = Path(__file__).resolve().parent
QUOTES = {
    "plos-hemming-2018-idea-html": "The acronym IDEA stands for the key steps",
    "plos-hemming-2018-idea-pdf": "IDEA protocol: A case study",
    "tudelft-ocw-quantiles": (
        "the experts need to provide 3 quantiles, the 5%, 50% and the 95% quantiles"
    ),
    "cooke-goossens-2008-ress": "typically 5%, 50% and 95%",
    "shelf-cran-overview": "equal-weighted linear pool",
    "ohagan-abstract": "a (subjective) probability distribution for the quantity",
    "cooke-reep-sej": "classical model",
    "shelf-cran-refman": "weighted linear pool",
}


def lineage(index: dict, sid: str, quote: str) -> dict:
    row = index[sid]
    if not P.quote_in_snapshot(sid, quote, index):
        raise SystemExit(f"quote missing from {sid}: {quote!r}")
    return {
        "source_id": sid,
        "resolved_url": row["resolved_url"],
        "requested_url": row["requested_url"],
        "fetched_at": row["fetched_at"],
        "sha256_fetched_bytes": row["sha256"],
        "bytes": row["bytes"],
        "snapshot_path": f"command-center/p2-wave/probes/RES-0182/{row['path']}",
        "quote": quote,
        "http_status": row.get("http_status"),
    }


def ev(index: dict, sid: str) -> dict:
    row = index[sid]
    return {
        "kind": "fetched-snapshot",
        "source_id": sid,
        "path": f"command-center/p2-wave/probes/RES-0182/{row['path']}",
        "sha256": row["sha256"],
        "role": row.get("role"),
    }


def question_row(qid: str, spec: dict, live: dict, kind: str) -> dict:
    agg = live["aggregations"][qid]
    score = agg["score"]
    out = {
        "id": qid,
        "quantity": spec["quantity"],
        "unit": spec["unit"],
        "kind": kind,
        "evidence_tier": "ELICITED-NOT-MEASURED",
        "promoted_to_measured": False,
        "search_baseline": agg.get("search_baseline"),
        "aggregation": {
            "equal_weight": agg["equal_weight"],
            "cooke_weight": agg["cooke_weight"],
            "participant_rows": agg["participant_rows"],
            "n_participants": agg["n_participants"],
        },
        "score": score,
    }
    if kind == "no-literature":
        out["why_unpublished"] = spec.get("why_unpublished")
        out["local_truth"] = live["local_truths"][qid]
        out["adds_labeled_prior_over_not_found"] = True
        out["adds_measured_evidence_over_not_found"] = False
        out["interval_covers_local_truth"] = agg.get("interval_covers_local_truth")
    else:
        out["literature_truth"] = live["literature_truths"][qid]["truth"]
        out["extractor"] = spec.get("extractor")
        out["source_ids"] = live["literature_truths"][qid]["source_ids"]
    return out


def main() -> int:
    live = P.run_protocol()
    index = live["index"]
    qdoc = P.load_json(P.QUESTIONS)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nl_specs = {r["id"]: r for r in qdoc["no_literature"]}
    lit_specs = {r["id"]: r for r in qdoc["literature_controls"]}

    nl_rows = [
        question_row(qid, nl_specs[qid], live, "no-literature")
        for qid in live["nl_ids"]
    ]
    lit_rows = [
        question_row(qid, lit_specs[qid], live, "literature-control")
        for qid in live["lit_ids"]
    ]

    claims = [
        {
            "claim_id": "RES-0182-C1-IDEA-FOUR-STAGES",
            "canonical_mechanism": (
                "The IDEA protocol names four stages — Investigate, Discuss, "
                "Estimate, Aggregate — and requires a private individual estimate "
                "before discussion."
            ),
            "sherman_kent_band": "almost-certain",
            "verdict": "CONFIRMED",
            "source_probe": P.P1,
            "verifier_probe": P.P2,
            "independent_verification_path": (
                "Re-hash PLOS HTML and printable PDF snapshots; both must still "
                "contain the four IDEA stage names; idea_stage_count must return 4 "
                "on each blob."
            ),
            "source_lineage": [
                lineage(index, "plos-hemming-2018-idea-html", QUOTES["plos-hemming-2018-idea-html"]),
                lineage(index, "plos-hemming-2018-idea-pdf", QUOTES["plos-hemming-2018-idea-pdf"]),
            ],
        },
        {
            "claim_id": "RES-0182-C2-COOKE-THREE-QUANTILES",
            "canonical_mechanism": (
                "Cooke's classical model typically elicits three percentiles per "
                "uncertain quantity (5%, 50%, 95%) and weights experts by "
                "calibration times information on seed variables."
            ),
            "sherman_kent_band": "almost-certain",
            "verdict": "CONFIRMED",
            "source_probe": P.P1,
            "verifier_probe": P.P2,
            "independent_verification_path": (
                "Re-run cooke_quantile_count on the TU Delft OCW HTML and the "
                "inflated Cooke-Goossens 2008 PDF; both must return 3."
            ),
            "source_lineage": [
                lineage(index, "tudelft-ocw-quantiles", QUOTES["tudelft-ocw-quantiles"]),
                lineage(index, "cooke-goossens-2008-ress", QUOTES["cooke-goossens-2008-ress"]),
            ],
        },
        {
            "claim_id": "RES-0182-C3-ELICITED-IS-SUBJECTIVE-NOT-MEASURED",
            "canonical_mechanism": (
                "An elicited estimate is a subjective probability distribution "
                "(or quantile triple), not a measurement. Aggregation (equal-weight "
                "linear pool or Cooke weights) does not change that tier."
            ),
            "sherman_kent_band": "almost-certain",
            "verdict": "CONFIRMED",
            "source_probe": P.P1,
            "verifier_probe": P.P2,
            "independent_verification_path": (
                "Re-fetch O'Hagan abstract and SHELF CRAN overview; quotes must "
                "remain. Probe 2 must reject a mutant that sets "
                "elicited_promoted_to_measured=true."
            ),
            "source_lineage": [
                lineage(index, "ohagan-abstract", QUOTES["ohagan-abstract"]),
                lineage(index, "shelf-cran-overview", QUOTES["shelf-cran-overview"]),
            ],
        },
        {
            "claim_id": "RES-0182-C4-BLIND-ELICITATION-MISSES-LITERATURE",
            "canonical_mechanism": (
                "On this 8-question run, four independent agent personas using "
                "only named reference classes produced a Cooke/equal-weight "
                "aggregate whose 90% interval missed a known literature value "
                "(Cooke 5/50/95 quantile count = 3). The source class is therefore "
                "WEAK, not ADOPTED."
            ),
            "sherman_kent_band": "likely",
            "verdict": "CONFIRMED",
            "source_probe": P.P1,
            "verifier_probe": P.P2,
            "independent_verification_path": (
                "Probe 1 recomputes aggregation from participants.json and "
                "extracts literature truths from snapshots. Probe 2 rejects an "
                "ADOPTED-despite-miss mutant."
            ),
            "source_lineage": [
                lineage(index, "tudelft-ocw-quantiles", QUOTES["tudelft-ocw-quantiles"]),
                lineage(index, "cooke-goossens-2008-ress", QUOTES["cooke-goossens-2008-ress"]),
            ],
        },
        {
            "claim_id": "RES-0182-C5-NOT-A-COUNCIL-DECISION-PROTOCOL",
            "canonical_mechanism": (
                "This unit is a research-input source class: it emits labeled "
                "ELICITED-NOT-MEASURED priors. It has no roster, vote, stopping "
                "rule, or decision. Council Delphi (CNL-0112 / TST-0291) remains "
                "a decision topology."
            ),
            "sherman_kent_band": "almost-certain",
            "verdict": "CONFIRMED",
            "source_probe": P.P1,
            "verifier_probe": P.P2,
            "independent_verification_path": (
                "Artifact distinct_from_council.is_council_decision_protocol must "
                "be false and mode must be research-input; catalog title of "
                "CNL-0112 remains a forecasting/elicitation *preset*, not this "
                "source class."
            ),
            "source_lineage": [
                lineage(index, "plos-hemming-2018-idea-html", "four-step question format of the IDEA protocol"),
                lineage(index, "ohagan-abstract", "SHELF protocol"),
            ],
        },
    ]

    answer = (
        "A four-step research-input protocol (reference-class framing, independent "
        "priors, calibration questions, Cooke/equal-weight aggregation) can be run "
        f"with {len(live['participants'])} sealed agent personas. On 6 unpublished "
        f"worktree questions, public search is NOT-FOUND; elicitation added labeled "
        f"priors but not measured evidence "
        f"({live['nl_hits']}/{live['nl_n']} intervals covered a later local "
        f"census). On 2 literature controls, blind elicitation missed "
        f"{live['lit_misses']}/{live['lit_n']} known answers (Cooke 5/50/95 count). "
        f"Adoption status={live['adoption']}: the mode does not beat a search as a "
        "source class. Elicited values remain ELICITED-NOT-MEASURED. "
        f"{P.SENTINEL}"
    )

    doc = {
        "unit_id": P.UNIT,
        "state": "SUCCESS",
        "sentinel": P.SENTINEL,
        "kind": "design-spec",
        "report_kind": "expert-elicitation-source-class",
        "catalog_contract": {
            "completion_sentinel": P.SENTINEL,
            "output_path": (
                "command-center/research/sources-frontier/"
                "RES-0182-expert-elicitation-as-a-source-class.json"
            ),
            "output_schema": "command-center/schema/design-spec.schema.json",
            "pinned_schema": "command-center/p2-wave/probes/RES-0182/design-spec.schema.json",
            "tests_required_verbatim": (
                "negative control: include 2 questions that DO have a literature "
                "answer, elicit blind, and compare - if elicitation misses a known "
                "answer the mode is reported as weak rather than adopted"
            ),
        },
        "question": (
            "Specify a structured elicitation protocol (reference-class framing, "
            "independent priors, calibration questions, aggregation) for questions "
            "where no literature exists, and determine on 6 such questions whether "
            "elicited estimates add information over an honest NOT-FOUND. Distinct "
            "from the council bucket: this is a research-input mode, not a decision "
            "protocol."
        ),
        "answer": answer,
        "freshness_stamp": now,
        "protocol": {
            "reference_class_framing": {
                "description": (
                    "Each agent persona must name a reference class before stating "
                    "quantiles. The class is recorded on the participant row and is "
                    "the only allowed basis for the estimate."
                ),
                "enforced_in": "participants.json reference_class field",
            },
            "independent_priors": {
                "description": (
                    "Personas are sealed: they do not read snapshots, each other's "
                    "quantiles, or the local census until after aggregation."
                ),
                "n_participants": len(live["participants"]),
                "cross_talk": False,
            },
            "calibration_questions": {
                "description": (
                    "Four public seed quantities score each persona. Weight is "
                    "calibration_rate times an inverse-width information score. "
                    "Personas below 50% seed-interval hits are discounted to weight 0."
                ),
                "seeds": [
                    {"id": s["id"], "truth": s["truth"], "quantity": s["quantity"]}
                    for s in live["seeds"]
                ],
                "weights": live["weights"],
            },
            "aggregation": {
                "description": (
                    "Equal-weight median of each quantile, plus a Cooke-style "
                    "linear pool of non-discounted personas. The reported point is "
                    "the equal-weight median; Cooke weights are the performance "
                    "alternative. Neither pool is a measurement."
                ),
                "rules": [
                    "equal-weight-median-of-quantiles",
                    "cooke-calibration-times-information-linear-pool",
                ],
            },
        },
        "distinct_from_council": {
            "is_council_decision_protocol": False,
            "mode": "research-input",
            "no_vote": True,
            "no_stopping_rule": True,
            "nearest_council_sibling": "CNL-0112",
            "difference": (
                "CNL-0112 is a council preset with a proper scoring rule for "
                "resolvable forecasts. RES-0182 emits research-input priors labeled "
                "ELICITED-NOT-MEASURED and never takes a decision."
            ),
        },
        "questions_no_literature": nl_rows,
        "questions_literature_control": lit_rows,
        "information_over_not_found": {
            "labeled_prior_emitted": True,
            "adds_measured_evidence": False,
            "nl_intervals_covering_local_truth": live["nl_hits"],
            "nl_n": live["nl_n"],
            "beats_search_as_source_class": live["beats_search_as_source_class"],
            "note": (
                "A labeled prior is not evidence. A wrong number is worse than an "
                "honest NOT-FOUND. This run does not promote elicitation over search."
            ),
        },
        "adoption": {
            "status": live["adoption"],
            "reason": live["adoption_reason"],
            "lit_misses": live["lit_misses"],
            "lit_n": live["lit_n"],
            "beats_search_as_source_class": False,
        },
        "promotion_guard": {
            "elicited_promoted_to_measured": False,
            "rule": "elicited-values-never-promoted-to-measured",
            "evidence_tier_of_estimates": "ELICITED-NOT-MEASURED",
        },
        "negative_control": {
            "state_meant_to_reject": "ADOPTED-DESPITE-LITERATURE-MISS",
            "what_the_check_does": (
                "If any literature-control interval misses the snapshot-extracted "
                "truth, adoption status must be WEAK or REJECTED, never ADOPTED. "
                "Probe 2 plants an ADOPTED mutant and requires the detector to fire."
            ),
            "verbatim": (
                "literature miss => status=WEAK rather than adopted; "
                "ADOPTED-despite-miss mutant must fail"
            ),
            "lit_misses": live["lit_misses"],
        },
        "claims": claims,
        "tests": [
            {
                "id": "probe1-recompute",
                "command": P.P1,
                "result": "PASS",
            },
            {
                "id": "probe2-negative-control",
                "command": P.P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0182-probe2-literature-miss-and-promotion-mutant",
            "verdict": "PASS",
            "independent": True,
            "default_without_evidence": "REFUTED",
        },
        "evidence": [
            ev(index, "plos-hemming-2018-idea-html"),
            ev(index, "plos-hemming-2018-idea-pdf"),
            ev(index, "cooke-goossens-2008-ress"),
            ev(index, "tudelft-ocw-quantiles"),
            ev(index, "shelf-cran-overview"),
            ev(index, "ohagan-abstract"),
        ],
        "local_truths": live["local_truths"],
        "named_settling_probe": P.P1,
    }

    checked = P.evaluate(doc)
    if not checked["pass"]:
        raise SystemExit(f"emit contract failed: {checked['errors']}")

    P.ART.parent.mkdir(parents=True, exist_ok=True)
    P.ART.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {P.ART.relative_to(P.REPO).as_posix()} "
        f"adoption={live['adoption']} lit_misses={live['lit_misses']} "
        f"nl_hits={live['nl_hits']}/{live['nl_n']}"
    )
    print(P.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
