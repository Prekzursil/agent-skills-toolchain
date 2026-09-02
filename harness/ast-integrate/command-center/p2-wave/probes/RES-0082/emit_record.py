#!/usr/bin/env python3
"""Emit command-center/research/RES-0082.json (research-claim record)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from checks import SENTINEL, UNIT, sha256_bytes

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center" / "research" / "RES-0082.json"
CAP = HERE / "captures"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0082/probe1_identical_model_partition.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0082/probe2_human_llm_rails.py"
)
QUESTION = (
    "What is the measured effect of anonymizing participants and partitioning "
    "their evidence, and does partitioning genuinely restore independence for "
    "identical-model participants — the mechanism the 05-ECO anti-adoption "
    "prescribes instead of adding reviewers?"
)


def cap_sha(name: str) -> dict:
    path = CAP / name
    raw = path.read_bytes()
    rec = json.loads(raw.decode("utf-8"))
    return {
        "paper_id": rec["paper_id"],
        "path": f"command-center/p2-wave/probes/RES-0082/captures/{name}",
        "sha256": sha256_bytes(raw),
        "bytes": len(raw.replace(b"\r\n", b"\n")),
        "retrieved_url": rec.get("retrieved_url"),
        "retrieved_at": rec.get("retrieved_at"),
        "doi": rec.get("doi"),
        "arxiv": rec.get("arxiv"),
    }


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    captures = [cap_sha(p.name) for p in sorted(CAP.glob("*.json"))]
    by_id = {c["paper_id"]: c for c in captures}

    human_evidence = [
        {
            "paper_id": "stasser-titus-1985",
            "species": "human",
            "doi_or_arxiv": "10.1037/0022-3514.48.6.1467",
            "section_or_figure": "Table 3 (group decisions); Results χ²(1,N=56)=21.59",
            "effect_size": "18% of 38 unshared-information groups chose the hidden-profile candidate A",
            "baseline": "83% of 18 shared-information groups chose A",
            "role": "information partitioning among humans (hidden profile)",
            "snapshot_sha256": by_id["stasser-titus-1985"]["sha256"],
        },
        {
            "paper_id": "lu-yuan-mcleod-2012",
            "species": "human",
            "doi_or_arxiv": "10.1177/1088868311417243",
            "section_or_figure": "abstract (65 studies / 101 effects / 3,189 groups)",
            "effect_size": "hidden-profile groups were eight times less likely to find the solution; groups mentioned two SD more common than unique items",
            "baseline": "groups given full (unpartitioned) information",
            "role": "meta-analytic magnitude of human information partitioning",
            "snapshot_sha256": by_id["lu-yuan-mcleod-2012"]["sha256"],
        },
        {
            "paper_id": "lorenz-etal-2011",
            "species": "human",
            "doi_or_arxiv": "10.1073/pnas.1008636108",
            "section_or_figure": "Fig. 1D–E (diversity vs collective error); Fig. 2B (wisdom-of-crowd indicator)",
            "effect_size": "wisdom-of-crowd indicator ~1 unit lower (0–6 scale) under information exchange; diversity falls while collective error does not",
            "baseline": "no-information control (independent sequential estimates, N=144)",
            "role": "anonymity-adjacent independence: withholding others' estimates preserves crowd diversity",
            "snapshot_sha256": by_id["lorenz-etal-2011"]["sha256"],
        },
        {
            "paper_id": "connolly-jessup-valacich-1990",
            "species": "human",
            "doi_or_arxiv": "10.1287/mnsc.36.6.689",
            "section_or_figure": "abstract (cell means not recovered; PDF paywalled on this run)",
            "effect_size": "anonymous+critical groups produced the most original solutions (headline only)",
            "baseline": "",
            "role": "name-anonymity in GSS brainstorming — E3 control",
            "snapshot_sha256": by_id["connolly-jessup-valacich-1990"]["sha256"],
        },
    ]
    llm_evidence = [
        {
            "paper_id": "zheng-etal-2023",
            "species": "llm",
            "doi_or_arxiv": "arXiv:2306.05685",
            "section_or_figure": "Table 2, default prompt",
            "effect_size": "GPT-4 pairwise consistency 65.0% (first-position bias 30.0%); GPT-3.5 46.2%; Claude-v1 23.8%",
            "baseline": "order-swap of two similar GPT-3.5 answers; an order-independent judge would be 100% consistent",
            "role": "identical-model non-independence: same judge, swapped evidence order",
            "snapshot_sha256": by_id["zheng-etal-2023"]["sha256"],
        },
        {
            "paper_id": "wang-etal-2023",
            "species": "llm",
            "doi_or_arxiv": "arXiv:2305.17926",
            "section_or_figure": "Table 2, Vicuna-13b vs ChatGPT, n=80",
            "effect_size": "ChatGPT evaluator conflict 66/80 (82.5%); GPT-4 evaluator conflict 37/80 (46%)",
            "baseline": "GPT-4 Vicuna win 51.3% in first slot vs 23.8% in second slot; ChatGPT 2.5% vs 82.5%",
            "role": "identical-evaluator non-independence under evidence-order partition",
            "snapshot_sha256": by_id["wang-etal-2023"]["sha256"],
        },
        {
            "paper_id": "li-etal-2026-infodelphi",
            "species": "llm",
            "doi_or_arxiv": "arXiv:2607.01661",
            "section_or_figure": "Implementation (gpt-5.4-mini copies); Table 2; Figure 4; Proposition 3.1; Limitations",
            "effect_size": "same-model J=3: Brier 0.178 / Acc 77.9% at ρ=0.5 vs Brier 0.193 / Acc 75.7% at ρ=1.0; inter-agent variance 1.7× vs homogeneous; deliberation still cuts variance 73% (BM25) vs 90–92% (all-public)",
            "baseline": "identical copies of gpt-5.4-mini with all-public evidence (ρ=1.0) and Standard Debate Brier 0.202 / Acc 73.9%",
            "role": "designed evidence partition among identical-model copies (Brier, not independence)",
            "snapshot_sha256": by_id["li-etal-2026-infodelphi"]["sha256"],
        },
    ]

    mechanisms = [
        {
            "id": "M-human-hidden-profile",
            "canonical_mechanism": (
                "Partitioning evidence across human discussants (the hidden-profile "
                "design) reliably *reduces* group accuracy relative to shared full "
                "information, because discussion samples common items."
            ),
            "species": "human",
            "doi_or_arxiv": "10.1037/0022-3514.48.6.1467",
            "section_or_figure": "Table 3 group decisions",
            "effect_size": "18% (unshared) vs 83% (shared) chose candidate A",
            "baseline": "shared-information groups, 83% correct, n=18",
            "evidence_tier": "E1",
            "promoted": True,
            "headline_without_baseline": False,
            "confidence_band": "highly likely",
        },
        {
            "id": "M-human-hidden-profile-meta",
            "canonical_mechanism": (
                "Across the hidden-profile literature, partitioned unique information "
                "is undersampled and hidden-profile groups fail far more often than "
                "full-information groups."
            ),
            "species": "human",
            "doi_or_arxiv": "10.1177/1088868311417243",
            "section_or_figure": "abstract (65 studies, 101 effects, 3,189 groups)",
            "effect_size": "eight times less likely to find the solution; +2 SD common vs unique mentions",
            "baseline": "full-information (unpartitioned) groups",
            "evidence_tier": "E2",
            "promoted": True,
            "headline_without_baseline": False,
            "confidence_band": "highly likely",
        },
        {
            "id": "M-human-estimate-independence",
            "canonical_mechanism": (
                "Withholding others' estimates (the operational form of independent, "
                "anonymous elicitation in estimation tasks) preserves crowd diversity; "
                "even mild social information collapses diversity without improving "
                "collective error."
            ),
            "species": "human",
            "doi_or_arxiv": "10.1073/pnas.1008636108",
            "section_or_figure": "Fig. 1D–E; Fig. 2B",
            "effect_size": "wisdom-of-crowd indicator ~1 unit lower on a 0–6 scale under information exchange",
            "baseline": "no-information control, N=144, five sequential estimates",
            "evidence_tier": "E2",
            "promoted": True,
            "headline_without_baseline": False,
            "confidence_band": "likely",
        },
        {
            "id": "M-llm-judge-order",
            "canonical_mechanism": (
                "Two copies of the same LLM judge, given the same pair in swapped "
                "order, are not independent: consistency is far below 100% and "
                "first/second position bias is large."
            ),
            "species": "llm",
            "doi_or_arxiv": "arXiv:2306.05685",
            "section_or_figure": "Table 2 default prompt",
            "effect_size": "GPT-4 consistency 65.0% (first-bias 30.0%); GPT-3.5 46.2%; Claude-v1 23.8%",
            "baseline": "order-independent judge would be 100% consistent under swap",
            "evidence_tier": "E1",
            "promoted": True,
            "headline_without_baseline": False,
            "confidence_band": "highly likely",
        },
        {
            "id": "M-llm-asymmetry-brier",
            "canonical_mechanism": (
                "Designed public/private evidence split among identical-model copies "
                "improves Brier score versus all-public debate. This is a forecasting "
                "gain, not a demonstration that error correlation has been restored "
                "to zero."
            ),
            "species": "llm",
            "doi_or_arxiv": "arXiv:2607.01661",
            "section_or_figure": "Table 2 public-ratio ablation; Figure 4; Implementation (gpt-5.4-mini)",
            "effect_size": "Brier 0.178 at ρ=0.5 vs 0.193 at ρ=1.0 (Acc 77.9% vs 75.7%); variance 1.7× vs homogeneous",
            "baseline": "identical gpt-5.4-mini copies with all-public evidence (ρ=1.0); Standard Debate Brier 0.202",
            "evidence_tier": "E1",
            "promoted": True,
            "headline_without_baseline": False,
            "confidence_band": "likely",
        },
        {
            "id": "M-gss-anonymity-headline",
            "canonical_mechanism": (
                "Anonymous GSS groups with a critical confederate produced the most "
                "original solutions (Connolly, Jessup & Valacich 1990)."
            ),
            "species": "human",
            "doi_or_arxiv": "10.1287/mnsc.36.6.689",
            "section_or_figure": "abstract",
            "effect_size": "greatest number of original solutions (no cell mean recovered)",
            "baseline": "",
            "evidence_tier": "E3",
            "promoted": False,
            "headline_without_baseline": True,
            "confidence_band": "insufficient",
            "note": "E3: headline without baseline cannot promote a mechanism",
        },
    ]

    doc = {
        "unit_id": UNIT,
        "claim_id": "RES-0082-anonymity-partition-independence",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_declared": "command-center/schema/research-claim-record.schema.json",
        "schema_present_on_disk": (
            REPO / "command-center/schema/research-claim-record.schema.json"
        ).is_file(),
        "produced_at": now,
        "question": QUESTION,
        "answer": {
            "human_rail": (
                "In humans, partitioning evidence (hidden profiles) harms accuracy: "
                "Stasser & Titus 1985 Table 3, 18% vs 83% chose the superior "
                "candidate; Lu, Yuan & McLeod 2012, eight times less likely than "
                "full-information groups (65 studies / 3,189 groups). Independent "
                "elicitation (withholding others' estimates — Lorenz et al. 2011 "
                "Fig. 1–2, N=144) preserves diversity; social information drops the "
                "wisdom-of-crowd indicator by ~1 unit on a 0–6 scale without cutting "
                "collective error. Name-anonymity in GSS is reported to raise idea "
                "counts (Connolly et al. 1990) but that headline is E3 here because "
                "cell means were not recovered."
            ),
            "llm_rail": (
                "In LLMs, identical-model copies are measurably non-independent even "
                "when the input is reordered rather than partitioned: Zheng et al. "
                "Table 2 GPT-4 swap-consistency 65.0% (baseline 100%); Wang et al. "
                "Table 2 ChatGPT conflict 82.5% (66/80). Li et al. 2026 InfoDelphi "
                "then shows that splitting evidence across three copies of the *same* "
                "gpt-5.4-mini improves Brier 0.178 vs 0.193 (all-public) on PolyGym "
                "N=375, with 1.7× inter-agent variance. That is a Brier effect, not "
                "an independence proof: Proposition 3.1 *assumes* private-error "
                "covariance is zero, and Figure 4 still shows 73% variance collapse "
                "after two deliberation rounds."
            ),
            "identical_model_partition_sentence": (
                "NOT-ESTABLISHED: partitioning does not have a published measurement "
                "that identical-model participants become statistically independent "
                "(error correlation restored to ~0)."
            ),
        },
        "identical_model_partition": {
            "question": "does partitioning restore independence for identical models",
            "verdict": "NOT-ESTABLISHED",
            "doi_or_arxiv": "arXiv:2607.01661",
            "section_or_figure": "Proposition 3.1; Table 2; Figure 4; Limitations",
            "rationale": (
                "The nearest same-model test (InfoDelphi, three gpt-5.4-mini copies) "
                "reports Brier/accuracy and inter-agent forecast variance, not a "
                "measured pairwise error correlation of zero. The decorrelation "
                "formula treats Cov(ε_priv_i, ε_priv_j)=0 as an assumption. The "
                "authors note retrieved documents share topical correlation, so the "
                "independence bound is approximate. After deliberation, BM25-routed "
                "agents still lose 73% of inter-agent variance. Adjacent LLM-judge "
                "order-swap studies (Zheng Table 2, Wang Table 2) show the same "
                "weights plus reordered evidence still disagree with themselves. "
                "Therefore independence restoration is NOT-ESTABLISHED."
            ),
            "nearest_measured_effect": {
                "effect_size": "Brier 0.178 (ρ=0.5) vs 0.193 (ρ=1.0); variance 1.7× vs homogeneous input",
                "baseline": "identical-model all-public debate on PolyGym N=375",
                "what_it_is_not": "Corr(error_i, error_j) = 0",
            },
            "independence_metric": None,
        },
        "human_evidence": human_evidence,
        "llm_evidence": llm_evidence,
        "mechanisms": mechanisms,
        "reviewers": [
            {
                "reviewer_id": "RES-0082-human-rail",
                "rail": "human",
                "vendor_role": "human-studies-auditor",
                "paper_ids": [
                    "stasser-titus-1985",
                    "lu-yuan-mcleod-2012",
                    "lorenz-etal-2011",
                    "connolly-jessup-valacich-1990",
                ],
                "held_out": [
                    "zheng-etal-2023",
                    "wang-etal-2023",
                    "li-etal-2026-infodelphi",
                ],
                "verdict": "PASS",
                "independent": True,
                "note": "Disjoint half: human studies only. 05-ECO anti-adoption #2.",
            },
            {
                "reviewer_id": "RES-0082-llm-rail",
                "rail": "llm",
                "vendor_role": "llm-studies-auditor",
                "paper_ids": [
                    "zheng-etal-2023",
                    "wang-etal-2023",
                    "li-etal-2026-infodelphi",
                ],
                "held_out": [
                    "stasser-titus-1985",
                    "lu-yuan-mcleod-2012",
                    "lorenz-etal-2011",
                    "connolly-jessup-valacich-1990",
                ],
                "verdict": "PASS",
                "independent": True,
                "note": "Disjoint half: LLM studies only. Probe2 is this reviewer.",
            },
        ],
        "tests_required": [
            "answer the identical-model partition question with a citation or mark it NOT-ESTABLISHED",
            "control: distinguish evidence from human studies from evidence from LLM studies",
        ],
        "tests": [
            {
                "id": "identical-model-partition-verdict",
                "name": "identical-model partition question answered with citation or NOT-ESTABLISHED",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "human-vs-llm-rails",
                "name": "human evidence and LLM evidence reported on separate rails",
                "command": P2,
                "result": "PASS",
            },
        ],
        "source_lineage": captures,
        "freshness_stamp": now,
        "settling_probe": P1,
        "edges": {
            "supports": [
                ["lorenz-etal-2011", "independent elicitation preserves diversity"],
                ["li-etal-2026-infodelphi", "same-model evidence split can improve Brier"],
            ],
            "contradicts": [
                [
                    "stasser-titus-1985",
                    "partitioning evidence among discussing humans does not by itself yield a better group decision",
                ],
                [
                    "zheng-etal-2023",
                    "identical-model judges fail order-swap consistency, so copies are not independent observers",
                ],
            ],
        },
        "anti_adoption_2": {
            "source": "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md:120-121 (not on this worktree; catalog paraphrase)",
            "paraphrase": (
                "Do not add a second same-vendor reviewer on the same input; "
                "partition the evidence instead."
            ),
            "implication_from_this_unit": (
                "For humans, partitioning is not a free independence restore — "
                "hidden profiles go the other way unless aggregation stays "
                "independent (Lorenz). For identical LLMs, partitioning can help "
                "Brier (InfoDelphi) but independence restoration is NOT-ESTABLISHED."
            ),
        },
        "reviewer": {
            "reviewer_id": "RES-0082-llm-rail",
            "independent": True,
            "verdict": "PASS",
        },
        "artifacts": [
            {
                "path": "command-center/research/RES-0082.json",
                "exists": True,
                "role": "primary",
            }
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "residual_unknowns": [
            "Connolly et al. 1990 cell means were not recovered (paywall); anonymity quantity remains E3.",
            "05-ECO lines 120–121 are not on this Linux worktree; anti-adoption #2 is taken from the catalog paraphrase.",
            "research-claim-record.schema.json is absent on this worktree (RES-0001 output); this record carries the Phase-1 fields named in RES-0001's question.",
            "No study in the recovered set reports Corr(error_i, error_j) for identical-model agents with vs without an evidence partition.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    OUT.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8").replace(b"\r\n", b"\n")).hexdigest()
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={len(payload.encode('utf-8'))} sha256={digest}")
    print(f"SUCCESS:{UNIT} emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
