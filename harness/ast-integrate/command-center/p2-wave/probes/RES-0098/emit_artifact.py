#!/usr/bin/env python3
"""Emit command-center/research/RES-0098.json from captured sources."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find_repo(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "command-center/WORK-UNIT-CATALOG.json").is_file():
            return p
    raise RuntimeError("cannot locate worktree root")


REPO = find_repo(HERE)
OUT = REPO / "command-center/research/RES-0098.json"
CAP = HERE / "captures"
SENTINEL = (
    "SUCCESS:RES-0098 in the receipt AND a condition-by-condition "
    "satisfiability verdict for same-vendor fresh context, with at least "
    "one cross-vendor-only condition named"
)

CAPTURES = {
    "raff": {
        "file": "raff-2019-neurips.txt",
        "citation": (
            "Raff, E. (2019). A Step Toward Quantifying Independently "
            "Reproducible Machine Learning Research. NeurIPS 2019. "
            "arXiv:1909.06674. DOI 10.48550/arXiv.1909.06674"
        ),
        "permalink": "https://arxiv.org/abs/1909.06674",
        "doi": "10.48550/arXiv.1909.06674",
        "arxiv": "1909.06674",
        "partition": "B-rates",
    },
    "osc": {
        "file": "osc-2015-science.txt",
        "citation": (
            "Open Science Collaboration (2015). Estimating the reproducibility "
            "of psychological science. Science 349(6251), aac4716. "
            "DOI 10.1126/science.aac4716"
        ),
        "permalink": "https://doi.org/10.1126/science.aac4716",
        "doi": "10.1126/science.aac4716",
        "arxiv": None,
        "partition": "B-rates",
    },
    "gundersen": {
        "file": "gundersen-kjensmo-2018-aaai.txt",
        "citation": (
            "Gundersen, O. E., & Kjensmo, S. (2018). State of the Art: "
            "Reproducibility in Artificial Intelligence. AAAI 32(1). "
            "DOI 10.1609/aaai.v32i1.11503"
        ),
        "permalink": "https://doi.org/10.1609/aaai.v32i1.11503",
        "doi": "10.1609/aaai.v32i1.11503",
        "arxiv": None,
        "partition": "B-rates",
    },
    "camerer": {
        "file": "camerer-2018-nhb.txt",
        "citation": (
            "Camerer, C. F. et al. (2018). Evaluating the replicability of "
            "social science experiments in Nature and Science between 2010 "
            "and 2015. Nature Human Behaviour 2, 637-644. "
            "DOI 10.1038/s41562-018-0399-z"
        ),
        "permalink": "https://doi.org/10.1038/s41562-018-0399-z",
        "doi": "10.1038/s41562-018-0399-z",
        "arxiv": None,
        "partition": "B-rates",
    },
    "zheng": {
        "file": "zheng-2023-mtbench.txt",
        "citation": (
            "Zheng, L. et al. (2023). Judging LLM-as-a-Judge with MT-Bench "
            "and Chatbot Arena. NeurIPS 2023 Datasets and Benchmarks. "
            "arXiv:2306.05685. DOI 10.48550/arXiv.2306.05685"
        ),
        "permalink": "https://arxiv.org/abs/2306.05685",
        "doi": "10.48550/arXiv.2306.05685",
        "arxiv": "2306.05685",
        "partition": "B-stability",
    },
    "nasem": {
        "file": "nasem-2019-summary.txt",
        "citation": (
            "National Academies of Sciences, Engineering, and Medicine "
            "(2019). Reproducibility and Replicability in Science. "
            "Washington, DC: The National Academies Press. DOI 10.17226/25303"
        ),
        "permalink": "https://www.ncbi.nlm.nih.gov/books/NBK547531/",
        "doi": "10.17226/25303",
        "arxiv": None,
        "partition": "A-definitions",
    },
}


def sha_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    lineage = []
    snap_parts = []
    for key, meta in CAPTURES.items():
        path = CAP / meta["file"]
        digest = sha_file(path)
        snap_parts.append(digest.encode())
        lineage.append(
            {
                "id": key,
                "class": "paper",
                "citation": meta["citation"],
                "permalink": meta["permalink"],
                "doi": meta["doi"],
                "arxiv": meta["arxiv"],
                "capture_path": (
                    "command-center/p2-wave/probes/RES-0098/captures/"
                    + meta["file"]
                ),
                "retrieved_at": "2026-08-24T18:50:00Z",
                "http_status": 200,
                "sha256": digest,
                "bytes": path.stat().st_size,
                "reviewer_partition": meta["partition"],
            }
        )
    catalog = REPO / "command-center/WORK-UNIT-CATALOG.json"
    lineage.append(
        {
            "id": "catalog-RES-0098",
            "class": "estate-catalog",
            "citation": (
                "WORK-UNIT-CATALOG.json unit RES-0098 (question, tests, "
                "reviewer_requirement, 05-ECO anti-adoption #2)"
            ),
            "permalink": "command-center/WORK-UNIT-CATALOG.json",
            "doi": None,
            "arxiv": None,
            "capture_path": "command-center/WORK-UNIT-CATALOG.json",
            "retrieved_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "http_status": None,
            "sha256": sha_file(catalog),
            "bytes": catalog.stat().st_size,
            "reviewer_partition": "A-definitions",
        }
    )
    snapshot = hashlib.sha256(b"".join(sorted(snap_parts))).hexdigest()

    conditions = [
        {
            "id": "C-TEAM",
            "name": "Different team with no overlapping personnel",
            "literature_statement": (
                "ACM Results Reproduced and Results Replicated both require "
                "a person or team other than the authors. Raff §2 excluded "
                "papers whose authors had any significant relationship with "
                "the reproducer because intimate knowledge of communication "
                "style would bias results."
            ),
            "same_vendor_fresh_context": "NOT-SATISFIED",
            "cross_vendor_only": True,
            "why_same_vendor": (
                "A fresh context window of the same vendor model is the same "
                "weights, the same training corpus, and the same vendor stack. "
                "That is one team identity, not two. 05-ECO anti-adoption #2 "
                "forbids treating a second same-vendor reviewer on the same "
                "input as independent."
            ),
            "why_cross_vendor_only": (
                "Only a different vendor (different training run, different "
                "RLHF data, different tokenizer/runtime) can instantiate "
                "'a person or team other than the authors' for an agent "
                "reproducer."
            ),
        },
        {
            "id": "C-WEIGHTS",
            "name": "Different model family / vendor training corpus",
            "literature_statement": (
                "ACM Results Replicated requires a different measuring system "
                "and independently developed artifacts. Zheng §4.2 Table 5 "
                "shows a single strong judge (GPT-4) is internally stable: "
                "85% agreement with humans (S2, no-tie) vs 81% human-human. "
                "Stability is not independence: resampling the same judge is "
                "one instrument."
            ),
            "same_vendor_fresh_context": "NOT-SATISFIED",
            "cross_vendor_only": True,
            "why_same_vendor": (
                "Same checkpoint + same decoding stack is the same measuring "
                "system. A new context does not create a new measuring system."
            ),
            "why_cross_vendor_only": (
                "A different vendor's model is the agent analogue of ACM's "
                "'different measuring system' / independently developed "
                "artifacts."
            ),
        },
        {
            "id": "C-TOOL",
            "name": "Independently developed artifacts (no author code)",
            "literature_statement": (
                "Raff §1-2 defines independent reproducibility as reproducing "
                "results without using the paper's authors' code, and excluded "
                "any paper whose source was seen before success. Code Available "
                "was not significant (Table 1 p=0.213) for that independent "
                "outcome, while Authors Reply was (p=6.01e-8)."
            ),
            "same_vendor_fresh_context": "NOT-SATISFIED",
            "cross_vendor_only": False,
            "why_same_vendor": (
                "This estate reuses the same probe harness, Python, and "
                "catalog contract. A fresh context can write new scripts but "
                "typically inherits the same toolchain. That is ACM "
                "'Reproduced' (same setup) at best, not 'Replicated' "
                "(independently developed artifacts)."
            ),
            "why_cross_vendor_only": (
                "Not uniquely cross-vendor: a same-vendor agent could in "
                "principle write a new stack. It usually does not, and this "
                "session did not."
            ),
        },
        {
            "id": "C-BLIND",
            "name": "Blind to the original conclusion",
            "literature_statement": (
                "ADV-0005 / Phase 11 confirmation (catalog spec_anchor "
                "_USER-PROMPTS.md:11028-11041) requires the refuter receive "
                "source and question but not the answer, and plant false "
                "claims. Camerer 2018: replications follow analysis plans "
                "reviewed by original authors and pre-registered before the "
                "replications."
            ),
            "same_vendor_fresh_context": "NOT-SATISFIED",
            "cross_vendor_only": False,
            "why_same_vendor": (
                "This unit's prompt includes the question, the expected "
                "sentinel shape, and the uncomfortable case to confront. "
                "Training data may also contain the cited papers' conclusions. "
                "That is not blindness."
            ),
            "why_cross_vendor_only": (
                "Blindness is a protocol property, not a vendor property. A "
                "cross-vendor agent given the same unblinded prompt also "
                "fails it."
            ),
        },
        {
            "id": "C-DATA",
            "name": "Independent data collection (new data, same question)",
            "literature_statement": (
                "NASEM 2019 Summary: reproducibility = same input data, "
                "steps, code, and conditions; replicability = consistent "
                "results across studies that each obtained their own data."
            ),
            "same_vendor_fresh_context": "NOT-SATISFIED",
            "cross_vendor_only": False,
            "why_same_vendor": (
                "Reading the same captured papers is NASEM reproducibility "
                "(same inputs), not replicability (new data). This unit did "
                "not collect new experimental data."
            ),
            "why_cross_vendor_only": (
                "A cross-vendor agent reading the same sources also fails "
                "C-DATA."
            ),
        },
        {
            "id": "C-AUTHOR",
            "name": "No privileged author channel",
            "literature_statement": (
                "Raff §3: authors of 50 papers contacted, 52% reply. 24 "
                "no-reply cases: 1 success (4.2%). 26 reply cases: 22 "
                "successes (84.6%). Most individually predictive attribute "
                "studied."
            ),
            "same_vendor_fresh_context": "PARTIAL",
            "cross_vendor_only": False,
            "why_same_vendor": (
                "This session did not email original authors, so the Raff "
                "'no-reply' channel is satisfied in the narrow sense. Weights "
                "may still encode author-like knowledge from training, so "
                "the condition is only PARTIAL."
            ),
            "why_cross_vendor_only": "Not uniquely cross-vendor.",
        },
        {
            "id": "C-PREREG",
            "name": "Analysis plan fixed before seeing the outcome",
            "literature_statement": (
                "Camerer 2018 abstract: replications follow analysis plans "
                "reviewed by original authors and pre-registered prior to "
                "the replications; sample sizes on average about five times "
                "the originals."
            ),
            "same_vendor_fresh_context": "NOT-SATISFIED",
            "cross_vendor_only": False,
            "why_same_vendor": (
                "This unit generated the verdict in one pass after seeing "
                "the question. No pre-registered analysis plan exists."
            ),
            "why_cross_vendor_only": "Protocol property, not vendor property.",
        },
        {
            "id": "C-CONTEXT",
            "name": "Fresh context / no shared transcript of the original attempt",
            "literature_statement": (
                "Estate Phase 11 / ADV-0005 treats a fresh context as the "
                "minimum for re-derivation. It is necessary and not "
                "sufficient. Zheng §4.2: the same model applies a stable "
                "internal rubric across items (GPT-4 S2 no-tie agreement "
                "with humans 85% vs human-human 81%)."
            ),
            "same_vendor_fresh_context": "SATISFIED",
            "cross_vendor_only": False,
            "why_same_vendor": (
                "A new context window with no prior transcript of this unit "
                "is real. It is the one structural condition a same-vendor "
                "fresh-context agent actually meets."
            ),
            "why_cross_vendor_only": (
                "Satisfiable by same-vendor; therefore not cross-vendor-only."
            ),
        },
    ]

    mechanisms = [
        {
            "id": "M-NASEM-SPLIT",
            "canonical_mechanism": (
                "Computational re-run on the original artifacts is "
                "reproducibility; a second study with new data is "
                "replicability. Conflating them inflates 'independence'."
            ),
            "doi": "10.17226/25303",
            "arxiv": None,
            "section_or_figure": (
                "NASEM 2019 Summary (NCBI Bookshelf NBK547531), "
                "definitions paragraph"
            ),
            "effect_size": (
                "Definitional split (not a rate): reproducibility := same "
                "data+code+steps; replicability := new data, same question"
            ),
            "baseline": (
                "The undifferentiated colloquial use of 'reproduce' for both "
                "same-data reruns and new-data studies"
            ),
            "evidence_tier": "E1",
            "source_ids": ["nasem"],
            "promotes_condition": "C-DATA",
        },
        {
            "id": "M-RAFF-INDEPENDENT",
            "canonical_mechanism": (
                "Independent ML reproduction = reimplementation without "
                "author code, by a party with no significant relationship "
                "to the authors."
            ),
            "doi": "10.48550/arXiv.1909.06674",
            "arxiv": "1909.06674",
            "section_or_figure": (
                "Raff 2019 §2 Procedure (inclusion/exclusion) and opening "
                "result"
            ),
            "effect_size": "162/255 papers independently reproduced = 63.5%",
            "baseline": (
                "Gundersen & Kjensmo 2018 documentation-defined 26% "
                "(Raff §2 explicitly contrasts 63.5% vs that 26%)"
            ),
            "evidence_tier": "E1",
            "source_ids": ["raff", "gundersen"],
            "promotes_condition": "C-TOOL",
        },
        {
            "id": "M-RAFF-AUTHOR-REPLY",
            "canonical_mechanism": (
                "Author correspondence is the strongest measured predictor "
                "of independent reproduction success; absence of reply "
                "nearly kills independent success."
            ),
            "doi": "10.48550/arXiv.1909.06674",
            "arxiv": "1909.06674",
            "section_or_figure": (
                "Raff 2019 §3 Results, author-reply paragraph; Table 1 "
                "Authors Reply p=6.01e-8"
            ),
            "effect_size": "22/26 successes when authors replied = 84.6%",
            "baseline": (
                "1/24 successes when authors did not reply = 4.2% "
                "(50 papers contacted, 52% reply rate)"
            ),
            "evidence_tier": "E1",
            "source_ids": ["raff"],
            "promotes_condition": "C-AUTHOR",
        },
        {
            "id": "M-GUNDERSEN-DOC",
            "canonical_mechanism": (
                "Documentation coverage of method/data/experiment variables "
                "is sparse and is not itself an attempted independent "
                "reproduction."
            ),
            "doi": "10.1609/aaai.v32i1.11503",
            "arxiv": None,
            "section_or_figure": (
                "Gundersen & Kjensmo 2018 Findings + Table 2 Total row; "
                "R1/R2/R3 boolean metrics"
            ),
            "effect_size": (
                "R1D=0.24, R2D=0.25, R3D=0.26 (fraction of required "
                "variables documented); 0/325 empirical papers documented "
                "all variables"
            ),
            "baseline": (
                "Complete documentation = 1.00 of required variables; "
                "boolean R1=R2=R3 fully true on 0 papers"
            ),
            "evidence_tier": "E1",
            "source_ids": ["gundersen"],
            "promotes_condition": "C-TOOL",
        },
        {
            "id": "M-OSC-ATTENUATION",
            "canonical_mechanism": (
                "Independent teams replicating with original materials still "
                "produce a large drop versus the original significant-result "
                "rate and a halved mean effect size. Team characteristics "
                "did not predict success as well as original-evidence strength."
            ),
            "doi": "10.1126/science.aac4716",
            "arxiv": None,
            "section_or_figure": (
                "Open Science Collaboration 2015 Results (abstract/results): "
                "100 replications"
            ),
            "effect_size": (
                "36% of replications significant; replication Mr=0.197 "
                "(SD=0.257)"
            ),
            "baseline": (
                "97% of original studies significant; original Mr=0.403 "
                "(SD=0.188); 39% subjectively rated as replicated"
            ),
            "evidence_tier": "E1",
            "source_ids": ["osc"],
            "promotes_condition": "C-TEAM",
        },
        {
            "id": "M-CAMERER-PREREG",
            "canonical_mechanism": (
                "Even pre-registered, original-author-reviewed, ~5x-powered "
                "replications by independent labs recover the original claim "
                "only about three fifths of the time, with halved effects."
            ),
            "doi": "10.1038/s41562-018-0399-z",
            "arxiv": None,
            "section_or_figure": (
                "Camerer et al. 2018 abstract and main result (21 "
                "Nature/Science experiments, 2010-2015)"
            ),
            "effect_size": (
                "13/21 = 62% significant in the same direction; replication "
                "effects ~50% of original; complementary indicators 57-67%"
            ),
            "baseline": (
                "21/21 originals published as significant findings in Nature "
                "or Science; sample size ~5x original"
            ),
            "evidence_tier": "E1",
            "source_ids": ["camerer"],
            "promotes_condition": "C-PREREG",
        },
        {
            "id": "M-ZHENG-STABLE-JUDGE",
            "canonical_mechanism": (
                "A single strong LLM judge is a stable instrument (agreement "
                "with humans at or above human-human). Resampling the same "
                "model is not a second independent team."
            ),
            "doi": "10.48550/arXiv.2306.05685",
            "arxiv": "2306.05685",
            "section_or_figure": (
                "Zheng et al. 2023 §4.2 High agreement between GPT-4 and "
                "humans; Table 5 S2 (w/o tie)"
            ),
            "effect_size": "GPT-4 vs humans agreement 85% (S2, no-tie)",
            "baseline": (
                "Human-human agreement 81% under the same S2 no-tie setup"
            ),
            "evidence_tier": "E1",
            "source_ids": ["zheng"],
            "promotes_condition": "C-WEIGHTS",
        },
        {
            "id": "M-ESTATE-ANTI-ADOPTION-2",
            "canonical_mechanism": (
                "This estate already forbids counting a second same-vendor "
                "reviewer on the same input as independence (05-ECO "
                "anti-adoption #2; ADV-0005: a same-vendor reviewer shares "
                "this unit's blind spots)."
            ),
            "doi": None,
            "arxiv": None,
            "section_or_figure": (
                "WORK-UNIT-CATALOG.json RES-0098 reviewer_requirement; "
                "ADV-0005 reviewer_requirement"
            ),
            "effect_size": (
                "Policy constraint (not a measured rate): second same-vendor "
                "reviewer on same input = disallowed"
            ),
            "baseline": (
                "Required alternative: partitioned evidence and/or a "
                "different vendor"
            ),
            "evidence_tier": "E1",
            "source_ids": ["catalog-RES-0098"],
            "promotes_condition": "C-TEAM",
            "note": (
                "Estate rule, not a paper. Recorded so the mapping is not "
                "smuggled. Does not replace a paper mechanism."
            ),
        },
    ]

    for mech in mechanisms:
        if not mech.get("baseline"):
            mech["evidence_tier"] = "E3"
            mech["promotes_condition"] = None

    cross_only = [c["id"] for c in conditions if c.get("cross_vendor_only")]
    verdicts = {
        c["id"]: c["same_vendor_fresh_context"] for c in conditions
    }

    doc = {
        "unit_id": "RES-0098",
        "claim_id": "RES-0098-independent-reproduction-conditions",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "schema": "command-center/schema/research-claim-record.schema.json",
        "schema_on_disk": False,
        "schema_note": (
            "Declared schema file is absent on this worktree (RES-0001 not "
            "delivered here). Record is typed to the RES-0001 field list in "
            "the catalog (claim id, canonical mechanism, source lineage, "
            "evidence tier E1-E4, confidence band, named settling probe, "
            "contradiction/support edges, freshness stamp, snapshot sha256). "
            "G-1 measure does not schema-validate."
        ),
        "question": (
            "In replication research, what structural conditions make a "
            "reproduction independent (different team, different tooling, "
            "blind to the original conclusion), and which of those conditions "
            "can a same-vendor fresh-context agent actually satisfy?"
        ),
        "canonical_mechanism": (
            "Independence is a bundle of structural conditions (different "
            "team, different measuring system / independently developed "
            "artifacts, blindness to the original conclusion, and — for "
            "replicability rather than reproducibility — new data). A "
            "same-vendor fresh-context agent satisfies the context-reset "
            "condition and at most a narrow 'no author email' condition. "
            "It does not satisfy different-team or different-weights, which "
            "are cross-vendor-only. Treating the fresh context as a second "
            "signal is one signal, not two."
        ),
        "answer": {
            "summary": (
                "Eight structural conditions were scored. Same-vendor "
                "fresh-context SATISFIES C-CONTEXT, is PARTIAL on C-AUTHOR, "
                "and is NOT-SATISFIED on C-TEAM, C-WEIGHTS, C-TOOL, C-BLIND, "
                "C-DATA, and C-PREREG. Cross-vendor-only conditions named: "
                "C-TEAM and C-WEIGHTS."
            ),
            "same_vendor_fresh_context_verdicts": verdicts,
            "cross_vendor_only_conditions": cross_only,
            "uncomfortable_case": (
                "A fresh-context agent of the same model reading the same "
                "sources may be one signal, not two. C-CONTEXT can be "
                "SATISFIED while C-TEAM and C-WEIGHTS remain NOT-SATISFIED. "
                "Zheng's 85% vs 81% figure shows the same judge is stable, "
                "not that a second sample of it is independent. This unit's "
                "own two probes ran in the same vendor session on partitioned "
                "sources; that is not a cross-vendor review and is not "
                "claimed as one."
            ),
            "catalog_two_vendor_review_done": False,
        },
        "conditions": conditions,
        "mechanisms": mechanisms,
        "source_lineage": lineage,
        "evidence_tier_rule": (
            "A headline number without its baseline is recorded as E3 and "
            "cannot promote a mechanism. Every promoting mechanism below "
            "carries both."
        ),
        "confidence_band": {
            "structural_conditions_from_NASEM_Raff_ACM_policy": "high",
            "numeric_rates_from_fetched_papers": "high",
            "mapping_paper_teams_onto_same_vendor_agents": "medium",
            "caveat": (
                "The mapping from human independent labs to vendor/model "
                "identity is analogical. No paper in the captured set "
                "directly measures 'does a context reset restore independence "
                "for identical weights' (that is RES-0082's question; here it "
                "is marked NOT-ESTABLISHED as a measured rate, while the "
                "structural non-satisfaction of C-TEAM/C-WEIGHTS is still "
                "scored)."
            ),
        },
        "settling_probe": [
            (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0098/probe1_conditions.py"
            ),
            (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0098/probe2_overclaim.py"
            ),
        ],
        "edges": {
            "support": [
                {
                    "from": "M-NASEM-SPLIT",
                    "to": "C-DATA",
                    "note": (
                        "Same-source reread is reproducibility, not "
                        "replicability"
                    ),
                },
                {
                    "from": "M-OSC-ATTENUATION",
                    "to": "C-TEAM",
                    "note": (
                        "Independent human teams still attenuate; team "
                        "identity is load-bearing"
                    ),
                },
                {
                    "from": "M-ZHENG-STABLE-JUDGE",
                    "to": "C-WEIGHTS",
                    "note": "Same model is one stable instrument",
                },
                {
                    "from": "M-ESTATE-ANTI-ADOPTION-2",
                    "to": "C-TEAM",
                    "note": (
                        "Estate already rejects same-vendor-on-same-input "
                        "as independence"
                    ),
                },
            ],
            "contradiction": [
                {
                    "claim": (
                        "A same-vendor fresh context is an independent "
                        "reproduction"
                    ),
                    "refuted_by": [
                        "C-TEAM",
                        "C-WEIGHTS",
                        "C-BLIND",
                        "M-ZHENG-STABLE-JUDGE",
                    ],
                    "note": "Context reset is C-CONTEXT only",
                }
            ],
        },
        "freshness_stamp": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "snapshot_sha256": snapshot,
        "reviewers": [
            {
                "id": "RES-0098-partition-A-definitions",
                "evidence_half": ["nasem", "catalog-RES-0098"],
                "vendor": "this-session",
                "independent_of_executor": False,
                "note": (
                    "Mechanical probe1 over the definitional half. Same "
                    "vendor as the executor. Does not satisfy 05-ECO "
                    "anti-adoption #2."
                ),
            },
            {
                "id": "RES-0098-partition-B-rates",
                "evidence_half": [
                    "raff",
                    "gundersen",
                    "osc",
                    "camerer",
                    "zheng",
                ],
                "vendor": "this-session",
                "independent_of_executor": False,
                "note": (
                    "Mechanical probe2 over the measured-rate half. Disjoint "
                    "source ids from partition A. Still same vendor."
                ),
            },
        ],
        "tests": {
            "condition_by_condition_same_vendor_verdict": True,
            "at_least_one_cross_vendor_only_named": True,
            "control_cross_vendor_only": cross_only,
        },
        "residual_unknowns": [
            "command-center/schema/research-claim-record.schema.json is not on disk (RES-0001).",
            "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md and _USER-PROMPTS.md are not on disk; Phase 11 lines 11028-11041 are taken from catalog ADV-0005 spec_anchor and the RES-0098 inputs list.",
            "Direct experimental measure of identical-weight context-reset independence is NOT-ESTABLISHED (RES-0082); this unit scores structural conditions, not that missing rate.",
            "ACM badge HTML was Cloudflare-blocked from this host; ACM wording is used only as corroboration of NASEM/Raff team+artifact splits and is not a promoting mechanism.",
        ],
        "artifacts": [
            {
                "path": "command-center/research/RES-0098.json",
                "exists": True,
                "role": "primary",
            }
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=False, ensure_ascii=False) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={OUT.stat().st_size} sha256={sha_file(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
