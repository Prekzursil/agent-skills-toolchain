#!/usr/bin/env python3
"""Seeded corpora for TST-0319. True support/contradict ratios known by construction."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CASES = REPO / "command-center" / "bench" / "cases" / "TST-0319"

CONFIG = {
    "favourable_quota": 0.70,
    "unfavourable_quota": 0.30,
    "contradiction_search": True,
    "preserve_negative": True,
    "report_slot_budget": 10,
}


def _source(
    *,
    corpus_tag: str,
    stance_letter: str,
    n: int,
    claim_id: str,
    stance: str,
    strength: float,
    source_class: str,
    body: str,
) -> dict[str, Any]:
    sid = f"{corpus_tag}-{stance_letter}{n:02d}"
    token = f"TOK-{corpus_tag}-{stance_letter}{n:02d}"
    return {
        "id": sid,
        "claim_id": claim_id,
        "stance": stance,
        "strength": strength,
        "source_class": source_class,
        "token": token,
        "body": f"{body} {token}",
    }


def quota_corpus() -> dict[str, Any]:
    """14 support / 6 contradict = 0.70 / 0.30 by construction."""
    claim = "CLAIM-ALPHA"
    sources: list[dict[str, Any]] = []
    classes = ("seeded-paper", "seeded-web", "seeded-archive")
    for i in range(1, 15):
        sources.append(
            _source(
                corpus_tag="Q",
                stance_letter="S",
                n=i,
                claim_id=claim,
                stance="support",
                strength=0.50,
                source_class=classes[(i - 1) % 3],
                body="Seeded supporting observation for CLAIM-ALPHA.",
            )
        )
    for i in range(1, 7):
        sources.append(
            _source(
                corpus_tag="Q",
                stance_letter="C",
                n=i,
                claim_id=claim,
                stance="contradict",
                strength=0.50,
                source_class=classes[(i - 1) % 3],
                body="Seeded contradicting observation for CLAIM-ALPHA.",
            )
        )
    return {
        "id": "TST-0319-Q-70-30",
        "claim_id": claim,
        "query_claim_id": claim,
        "query": "Does CLAIM-ALPHA hold under the seeded evidence?",
        "role": "quota-adherence",
        "ground_truth": {
            "support": 14,
            "contradict": 6,
            "support_ratio": 0.70,
            "contradict_ratio": 0.30,
            "construction": "14 support + 6 contradict sources authored into this file",
        },
        "sources": sources,
    }


def survival_corpus() -> dict[str, Any]:
    """Contradictions planted in notes must survive into the final appendix."""
    claim = "CLAIM-BETA"
    sources: list[dict[str, Any]] = []
    for i in range(1, 9):
        sources.append(
            _source(
                corpus_tag="V",
                stance_letter="S",
                n=i,
                claim_id=claim,
                stance="support",
                strength=0.40 + 0.02 * i,
                source_class="seeded-paper",
                body="Seeded support for CLAIM-BETA.",
            )
        )
    for i in range(1, 5):
        sources.append(
            _source(
                corpus_tag="V",
                stance_letter="C",
                n=i,
                claim_id=claim,
                stance="contradict",
                strength=0.45,
                source_class="seeded-web",
                body="Seeded contradiction for CLAIM-BETA that must reach the final report.",
            )
        )
    return {
        "id": "TST-0319-V-SURVIVAL",
        "claim_id": claim,
        "query_claim_id": claim,
        "query": "Preserve contradictions for CLAIM-BETA into the final report.",
        "role": "contradiction-survival",
        "ground_truth": {
            "support": 8,
            "contradict": 4,
            "support_ratio": 8 / 12,
            "contradict_ratio": 4 / 12,
            "construction": "8 support + 4 contradict; all 4 contradict tokens must survive",
        },
        "sources": sources,
    }


def suppression_corpus() -> dict[str, Any]:
    """Contradicting evidence is stronger. Must not be reported as consensus."""
    claim = "CLAIM-GAMMA"
    sources: list[dict[str, Any]] = []
    for i in range(1, 5):
        sources.append(
            _source(
                corpus_tag="P",
                stance_letter="S",
                n=i,
                claim_id=claim,
                stance="support",
                strength=0.20,
                source_class="seeded-web",
                body="Weak supporting anecdote for CLAIM-GAMMA.",
            )
        )
    for i in range(1, 4):
        sources.append(
            _source(
                corpus_tag="P",
                stance_letter="C",
                n=i,
                claim_id=claim,
                stance="contradict",
                strength=0.90,
                source_class="seeded-paper",
                body="Strong contradicting measurement for CLAIM-GAMMA.",
            )
        )
    return {
        "id": "TST-0319-P-SUPPRESSION",
        "claim_id": claim,
        "query_claim_id": claim,
        "query": "Is CLAIM-GAMMA a consensus given stronger contradictions?",
        "role": "suppression-control",
        "ground_truth": {
            "support": 4,
            "contradict": 3,
            "support_ratio": 4 / 7,
            "contradict_ratio": 3 / 7,
            "support_strength_sum": 0.80,
            "contradict_strength_sum": 2.70,
            "construction": "4 x 0.20 support vs 3 x 0.90 contradict; contradict dominates",
        },
        "sources": sources,
    }


def impossibility_corpus() -> dict[str, Any]:
    """Asked-for claim is absent. Only CLAIM-OTHER sources exist."""
    sources: list[dict[str, Any]] = []
    for i in range(1, 4):
        sources.append(
            _source(
                corpus_tag="I",
                stance_letter="S",
                n=i,
                claim_id="CLAIM-OTHER",
                stance="support",
                strength=0.80,
                source_class="seeded-paper",
                body="Evidence about CLAIM-OTHER, not the asked-for claim.",
            )
        )
    return {
        "id": "TST-0319-I-IMPOSSIBLE",
        "claim_id": "CLAIM-OTHER",
        "query_claim_id": "CLAIM-GHOST",
        "query": "Produce supporting evidence that CLAIM-GHOST holds.",
        "role": "proof-of-impossibility",
        "ground_truth": {
            "support": 0,
            "contradict": 0,
            "support_ratio": 0.0,
            "contradict_ratio": 0.0,
            "asked_for": "CLAIM-GHOST",
            "present_claim": "CLAIM-OTHER",
            "construction": "zero sources match query_claim_id CLAIM-GHOST",
        },
        "sources": sources,
    }


CORPORA = {
    "quota": quota_corpus,
    "survival": survival_corpus,
    "suppression": suppression_corpus,
    "impossibility": impossibility_corpus,
}

FILENAMES = {
    "quota": "quota-70-30.json",
    "survival": "survival.json",
    "suppression": "suppression-stronger-contradict.json",
    "impossibility": "impossibility-ghost.json",
}


def materialize() -> dict[str, Path]:
    CASES.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    (CASES / "config.json").write_text(
        json.dumps(CONFIG, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    written["config"] = CASES / "config.json"
    for key, builder in CORPORA.items():
        path = CASES / FILENAMES[key]
        path.write_text(
            json.dumps(builder(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        written[key] = path
    return written


def load_case(name: str) -> dict[str, Any]:
    materialize()
    path = CASES / FILENAMES[name]
    return json.loads(path.read_text(encoding="utf-8"))


def load_config() -> dict[str, Any]:
    materialize()
    return json.loads((CASES / "config.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    paths = materialize()
    for key, path in paths.items():
        print(f"{key} {path}")
