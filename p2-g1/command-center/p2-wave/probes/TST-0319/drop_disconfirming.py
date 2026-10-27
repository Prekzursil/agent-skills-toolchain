#!/usr/bin/env python3
"""Planted drop-disconfirming synthesizer.

Writes contradictions into intermediate notes, then drops them from the
final report and reports CONSENSUS whenever any supporting source exists.
This is the failure TST-0319 exists to catch. Probe 2 requires this
synthesizer to fail quota, survival, and suppression contracts.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tools.bench.deep_research import (
    DEFAULT_CONFIG,
    STANCE_CONTRADICT,
    STANCE_SUPPORT,
    VERDICT_CONSENSUS,
    build_notes,
    corpus_sources,
    find_contradictions,
    query_claim_id,
    quota_counts,
    retrieve,
    write_artifacts,
)


def run_drop_disconfirming(
    corpus: Mapping[str, Any],
    config: Mapping[str, Any] | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if config:
        cfg.update(config)
    retrieved = retrieve(corpus)
    contradictions = find_contradictions(retrieved)
    notes = build_notes(corpus, retrieved, contradictions)
    if not retrieved:
        # Same silent-empty cheat: treat absence as consensus over nothing.
        report = {
            "kind": "final-report",
            "corpus_id": corpus.get("id"),
            "query_claim_id": query_claim_id(corpus),
            "verdict": VERDICT_CONSENSUS,
            "configured_quota": {
                "favourable": float(cfg.get("favourable_quota") or 0.0),
                "unfavourable": float(cfg.get("unfavourable_quota") or 0.0),
                "report_slot_budget": int(cfg.get("report_slot_budget") or 10),
            },
            "returned_proportion": {"support": 1.0, "contradict": 0.0, "polar_n": 0},
            "selected_ids": [],
            "selected_tokens": [],
            "contradiction_appendix_tokens": [],
            "contradiction_pair_count": 0,
            "preserve_negative": False,
            "code_path": "drop_disconfirming_empty_as_consensus",
        }
        result = {
            "verdict": VERDICT_CONSENSUS,
            "notes": notes,
            "final_report": report,
            "impossibility": None,
            "selected": [],
            "retrieved": [],
            "contradictions": contradictions,
        }
        if out_dir is not None:
            write_artifacts(Path(out_dir), result)
        return result

    budget, n_fav, _n_unfav = quota_counts(cfg)
    support = [s for s in retrieved if s["stance"] == STANCE_SUPPORT]
    support.sort(key=lambda s: (-float(s.get("strength") or 0.0), s["id"]))
    selected = support[: max(n_fav, budget)]
    report = {
        "kind": "final-report",
        "corpus_id": corpus.get("id"),
        "query_claim_id": query_claim_id(corpus),
        "verdict": VERDICT_CONSENSUS,
        "configured_quota": {
            "favourable": float(cfg.get("favourable_quota") or 0.0),
            "unfavourable": float(cfg.get("unfavourable_quota") or 0.0),
            "report_slot_budget": budget,
        },
        "returned_proportion": {
            "support": 1.0 if selected else 0.0,
            "contradict": 0.0,
            "polar_n": len(selected),
        },
        "selected_ids": [s["id"] for s in selected],
        "selected_tokens": [s["token"] for s in selected],
        "contradiction_appendix_tokens": [],
        "contradiction_pair_count": len(contradictions),
        "preserve_negative": False,
        "code_path": "drop_disconfirming_omit_appendix",
        "dropped_contradict_tokens": [
            s["token"] for s in retrieved if s["stance"] == STANCE_CONTRADICT
        ],
    }
    result = {
        "verdict": VERDICT_CONSENSUS,
        "notes": notes,
        "final_report": report,
        "impossibility": None,
        "selected": selected,
        "retrieved": list(retrieved),
        "contradictions": contradictions,
    }
    if out_dir is not None:
        write_artifacts(Path(out_dir), result)
    return result


def unused_corpus_sources(corpus: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Kept so a reviewer can see the planted synthesizer still reads the corpus."""
    return corpus_sources(corpus)
