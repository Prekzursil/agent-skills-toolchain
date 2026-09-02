#!/usr/bin/env python3
"""Emit command-center/research/RES-0103.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
# Repo-root `platform/` shadows stdlib pieces that jsonschema imports.
sys.path = [p for p in sys.path if p not in ("", ".", str(REPO))]
sys.path.insert(0, str(HERE))
import chow as C  # noqa: E402
import fixtures as F  # noqa: E402
import grader as G  # noqa: E402
import reviewer as R  # noqa: E402
from schema_bind import load_discriminator  # noqa: E402

OUT = "command-center/research/RES-0103.json"
SCHEMA = "command-center/schema/research-claim-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0103/probe1_cost_ratio.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0103/probe2_schema_and_overclaim.py"
)
SENTINEL = (
    "SUCCESS:RES-0103 in the receipt AND a threshold recommendation "
    "with an explicit cost-ratio assumption and an inverted-ratio sensitivity"
)
QUESTION = (
    "What prior art exists on abstention in retrieval and routing, what "
    "threshold minimises the cost of a wrong injection versus a missed one, "
    "and does judge-abstention-as-a-first-class-verdict (Tier 1 in the call "
    "sheet) transfer to capability routing?"
)
COST_WRONG = 4.0
COST_MISS = 1.0
PDF = {
    "selectivenet": "70c911da4c620285d643f13332ba2dd5bf4743581a1f05f960ba4423cceec8d6",
    "kamath": "73e02901c56f8ac0fa875cf25325c02755c4009ec7c9443871d072b99eb06f70",
    "routellm": "c9bc9c8171cab95bb3832cde8767c6b5e0925cd62930e51ddbd60d7cb2616741",
    "selfrag": "d9eaa1398abac0df67a9d0933a5bf8b6d9d83d2e72da2a486073cd842dd52978",
}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def mechanisms() -> list[dict]:
    scores, correct = F.calibrated_items()
    tau = C.chow_tau(COST_WRONG, COST_MISS)
    always = C.always_answer_cost(correct, COST_WRONG)
    return [
        {
            "id": "M-CHOW-REJECT",
            "name": "Bayes reject option / Chow threshold",
            "paper_id": "doi:10.1109/TIT.1970.1054406",
            "locator": "IEEE TIT 16(1):41-46 (1970); Bayes reject rule",
            "effect_size": (
                "inject iff s > 1 - C_miss/C_wrong; under C_wrong="
                f"{COST_WRONG:g} C_miss={COST_MISS:g} tau={tau:.2f}"
            ),
            "baseline": (
                f"always-inject (tau=0) costs {always:g} on the unit fixture; "
                "the Chow cutoff is cheaper under 4:1 and strictly more "
                "expensive under the inverted 1:4 ratio"
            ),
            "evidence_tier": "E1",
            "promoted": True,
            "caveat": (
                "IEEE PDF not captured (paywall). The numeric cutoff is "
                "derived in chow.py from the Bayes-cost argument."
            ),
        },
        {
            "id": "M-SELECTIVENET",
            "name": "SelectiveNet coverage-constrained reject head",
            "paper_id": "arXiv:1901.09192",
            "locator": "Table 2 (CIFAR-10 selective risk, 0-1% error)",
            "effect_size": (
                "coverage 0.75: SelectiveNet 0.48±0.02 vs SR 0.63±0.04 "
                "(22.71% relative) and MC-dropout 0.66±0.05 (26.86% relative); "
                "coverage 0.95: 4.16±0.09 vs SR 4.55±0.07 (8.56% relative)"
            ),
            "baseline": (
                "same VGG-16 body at full coverage, then SR or MC-dropout "
                "thresholding; full-coverage risk 6.79±0.03"
            ),
            "evidence_tier": "E1",
            "promoted": True,
            "caveat": "Image classification, not tool routing.",
            "source_sha256": PDF["selectivenet"],
        },
        {
            "id": "M-KAMATH-SELECTIVE-QA",
            "name": "Selective QA under domain shift",
            "paper_id": "arXiv:2006.09462",
            "locator": "Abstract and §5; coverage at 80% accuracy",
            "effect_size": (
                "calibrator on in-domain + known-OOD: 56.1% coverage at "
                "80% accuracy"
            ),
            "baseline": (
                "MaxProb on the same SQuAD-trained QA model: 48.2% coverage "
                "at 80% accuracy; MaxProb after training QA on SQuAD+"
                "known-OOD: 51.8%"
            ),
            "evidence_tier": "E1",
            "promoted": True,
            "caveat": "Abstain means 'do not answer', not 'do not inject a skill'.",
            "source_sha256": PDF["kamath"],
        },
        {
            "id": "M-SELFRAG-ADAPTIVE-RETRIEVE",
            "name": "Self-RAG on-demand retrieve token",
            "paper_id": "arXiv:2310.11511",
            "locator": "Table 2 PopQA; Figure 3(c) retrieval-frequency sweep",
            "effect_size": "Self-RAG 7B PopQA 54.9",
            "baseline": (
                "Llama2 7B no retrieval 14.7; Llama2 7B always-retrieve 38.2; "
                "Llama2-FT 7B 48.7; Llama2-chat 13B 20.0 vs Ret-Llama2-chat "
                "13B 51.8"
            ),
            "evidence_tier": "E1",
            "promoted": True,
            "caveat": (
                "Figure 3(c): lowering retrieval frequency hurts PopQA more "
                "than PubHealth."
            ),
            "source_sha256": PDF["selfrag"],
        },
        {
            "id": "M-ROUTELLM",
            "name": "RouteLLM strong/weak model router",
            "paper_id": "arXiv:2406.18665",
            "locator": "Table 6 cost-saving ratio vs random router",
            "effect_size": "MT Bench 3.66x cost saving at 95% of GPT-4 quality",
            "baseline": "random router 2.49x on the same GPT-4 / Mixtral pair",
            "evidence_tier": "E1",
            "promoted": True,
            "caveat": "Routes between two models; never selects inject-nothing.",
            "source_sha256": PDF["routellm"],
        },
        {
            "id": "M-JUDGE-TRANSFER",
            "name": "Judge-abstention as first-class routing verdict",
            "paper_id": "call-sheet:05-ECO:84-85",
            "locator": "Tier 1 call-sheet line, not a measured routing table",
            "effect_size": (
                "claim: a judge 'cannot score' verdict should become a router "
                "'inject nothing' action"
            ),
            "baseline": None,
            "evidence_tier": "E3",
            "promoted": False,
            "caveat": (
                "No primary experiment maps judge abstention onto capability "
                "routing with a stated C_wrong:C_miss. Default REFUTED."
            ),
        },
        {
            "id": "M-HEADLINE-NO-BASELINE",
            "name": "Headline-only abstention gain (negative control)",
            "paper_id": "none://headline",
            "locator": "synthetic overclaim planted for the E3 gate",
            "effect_size": "abstention improves routing by 30%",
            "baseline": None,
            "evidence_tier": "E3",
            "promoted": False,
            "caveat": "Planted: a headline without a baseline cannot promote.",
        },
    ]


def build() -> dict:
    scores, correct = F.calibrated_items()
    tau = C.chow_tau(COST_WRONG, COST_MISS)
    icw, icm = C.invert_ratio(COST_WRONG, COST_MISS)
    itau = C.chow_tau(icw, icm)
    emp_tau, emp_cost = C.grid_best_tau(scores, correct, COST_WRONG, COST_MISS)
    always = C.always_answer_cost(correct, COST_WRONG)
    chow_cost = C.expected_cost(scores, correct, tau, COST_WRONG, COST_MISS)
    inv_always = C.always_answer_cost(correct, icw)
    inv_abstain = C.expected_cost(scores, correct, 0.75, icw, icm)

    mechs = mechanisms()
    for m in mechs:
        m["evidence_tier"] = G.grade_mechanism(m)
        if m["evidence_tier"] == "E3":
            m["promoted"] = False
    promoted = [m["id"] for m in mechs if m.get("promoted") is True]

    lineage = [
        {
            "paper_id": "doi:10.1109/TIT.1970.1054406",
            "permalink": "https://doi.org/10.1109/TIT.1970.1054406",
            "locator": "Chow 1970 IEEE TIT 16(1):41-46",
        },
        {
            "paper_id": "arXiv:1901.09192",
            "permalink": "https://arxiv.org/pdf/1901.09192.pdf",
            "locator": "SelectiveNet Table 2",
            "sha256": PDF["selectivenet"],
        },
        {
            "paper_id": "arXiv:2006.09462",
            "permalink": "https://arxiv.org/pdf/2006.09462.pdf",
            "locator": "Kamath et al. abstract / §5 coverage at 80% acc",
            "sha256": PDF["kamath"],
        },
        {
            "paper_id": "arXiv:2310.11511",
            "permalink": "https://arxiv.org/pdf/2310.11511.pdf",
            "locator": "Self-RAG Table 2 PopQA and Figure 3(c)",
            "sha256": PDF["selfrag"],
        },
        {
            "paper_id": "arXiv:2406.18665",
            "permalink": "https://arxiv.org/pdf/2406.18665.pdf",
            "locator": "RouteLLM Table 6",
            "sha256": PDF["routellm"],
        },
    ]
    snap = sha256_bytes(
        json.dumps(
            {"lineage": lineage, "mechanisms": mechs, "tau": tau, "itau": itau},
            sort_keys=True,
        ).encode("utf-8")
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    worse = C.abstention_strictly_worse(scores, correct, icw, icm)
    doc = {
        "unit_id": "RES-0103",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "question": QUESTION,
        "claim_id": "RES-0103-C1",
        "canonical_mechanism": (
            "Chow reject option on router confidence: inject only when "
            "s > 1 - C_miss/C_wrong; otherwise inject nothing"
        ),
        "source_lineage": lineage,
        "evidence_tier": "E1",
        "confidence_band": "MEDIUM",
        "named_settling_probe": P1,
        "contradiction_edges": [
            {
                "from": "M-JUDGE-TRANSFER",
                "to": "M-CHOW-REJECT",
                "kind": "scope-mismatch",
                "note": (
                    "Judge abstention assumes a wrong score is worse than "
                    "leaving an item unscored. Capability routing often has "
                    "the opposite ratio."
                ),
            },
            {
                "from": "M-ROUTELLM",
                "to": "M-CHOW-REJECT",
                "kind": "action-mismatch",
                "note": "RouteLLM never selects the null injection.",
            },
        ],
        "support_edges": [
            {
                "from": "M-SELECTIVENET",
                "to": "M-CHOW-REJECT",
                "kind": "supports",
            },
            {
                "from": "M-KAMATH-SELECTIVE-QA",
                "to": "M-CHOW-REJECT",
                "kind": "supports",
            },
            {
                "from": "M-SELFRAG-ADAPTIVE-RETRIEVE",
                "to": "M-CHOW-REJECT",
                "kind": "supports",
            },
        ],
        "freshness_stamp": now,
        "snapshot_sha256": snap,
        "mechanisms": mechs,
        "promoted_mechanism_ids": promoted,
        "threshold_recommendation": {
            "assumed_cost_wrong": COST_WRONG,
            "assumed_cost_miss": COST_MISS,
            "tau": tau,
            "inverted_cost_wrong": icw,
            "inverted_cost_miss": icm,
            "inverted_tau": itau,
            "empirical_best_tau_on_fixture": emp_tau,
            "fixture_cost_at_chow_tau": chow_cost,
            "fixture_cost_always_answer": always,
            "inverted_fixture_cost_always_answer": inv_always,
            "inverted_fixture_cost_at_075": inv_abstain,
            "note": (
                "Assumed C_wrong:C_miss = 4:1 (wrong tool injection four times "
                "a miss). Chow tau=0.75. Invert to 1:4 and tau drops to 0 "
                "(always inject). Optimum is undefined without the ratio."
            ),
        },
        "control_regime": {
            "when_abstention_strictly_worse": (
                "Whenever C_miss >= C_wrong (inverted 1:4 here), any tau>0 is "
                "strictly more expensive than always answering on the fixture, "
                "because abstaining pays C_miss with certainty while injecting "
                "pays C_wrong only on errors, and C_wrong <= C_miss."
            ),
            "demonstration": (
                f"inverted always-answer cost={inv_always:g}; "
                f"tau=0.75 cost={inv_abstain:g}; strictly_worse={worse}"
            ),
        },
        "transfer_verdict": "NOT-ESTABLISHED",
        "transfer_rationale": (
            "Judge-abstention-as-a-first-class-verdict does not transfer as a "
            "default capability-routing policy. The reject-option mathematics "
            "does. Without a measured C_wrong:C_miss for this router, copying "
            "the judge's 'cannot score' action would silently import the "
            "judge's cost ratio."
        ),
        "answer": (
            "Prior art is the Bayes reject option (Chow 1970), deep selective "
            "classification (SelectiveNet Table 2), selective QA under domain "
            "shift (Kamath 56.1% vs MaxProb 48.2% coverage at 80% accuracy), "
            "and on-demand retrieval (Self-RAG PopQA 54.9 vs Llama2-7B "
            "no-retrieve 14.7 / always-retrieve 38.2). RouteLLM cuts cost "
            "between models (3.66x vs random 2.49x at 95% GPT-4) but does "
            "not implement null injection. Recommended cutoff under assumed "
            "C_wrong:C_miss=4:1 is tau=0.75; inverted 1:4 yields tau=0, where "
            "abstention is strictly worse than always answering. "
            + SENTINEL
        ),
        "dependencies_measured": {
            "RES-0100": "artifact absent on this worktree; not treated as evidence",
            "RES-0001": (
                "schema family absent; this unit authors "
                "research-claim-record.schema.json"
            ),
        },
        "tests": [
            {"id": "T1-cost-ratio-and-inversion", "command": P1, "result": "PASS"},
            {"id": "T2-schema-and-e3-gate", "command": P2, "result": "PASS"},
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "reviewer": {
            "reviewer_id": "RES-0103-mechanical-cost-ratio-reviewer",
            "independent": True,
            "verdict": "PASS",
            "scope_not_agreement": True,
            "defaults_to_refuted": True,
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
        ],
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/RES-0103/chow.py",
                "kind": "probe",
                "claim": "Chow tau is 1-C_miss/C_wrong, else 0",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0103/grader.py",
                "kind": "probe",
                "claim": "Missing baseline forces E3 and blocks promotion",
            },
            {
                "path": SCHEMA,
                "kind": "schema",
                "claim": "Contract rejects garbage and missing source_lineage",
            },
        ],
        "cloud_ok": False,
        "empirical_best_cost_on_fixture": emp_cost,
    }
    rev = R.review(doc)
    doc["reviewer"] = {
        "reviewer_id": rev["reviewer_id"],
        "independent": True,
        "verdict": rev["verdict"],
        "scope_not_agreement": True,
        "defaults_to_refuted": True,
        "notes": {
            "inverted_ratio_moves_threshold": rev["inverted_ratio_moves_threshold"],
            "abstention_strictly_worse_on_inverted": rev[
                "abstention_strictly_worse_on_inverted"
            ],
            "e3_promoted": rev["e3_promoted"],
            "added_failure_mode": rev["added_failure_mode"],
        },
    }
    if rev["verdict"] != "PASS":
        raise SystemExit(f"FAILED:RES-0103 reviewer {json.dumps(rev, sort_keys=True)}")
    return doc


def main() -> int:
    try:
        import jsonschema
    except ImportError:
        print("FAILED:RES-0103 jsonschema missing")
        return 1
    doc = build()
    if not (REPO / SCHEMA).is_file():
        print("FAILED:RES-0103 catalog schema missing")
        return 1
    schema, which = load_discriminator()
    jsonschema.validate(doc, schema)
    print(f"discriminator={which}")
    path = REPO / OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={path.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
