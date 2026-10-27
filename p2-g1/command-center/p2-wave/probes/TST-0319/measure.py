#!/usr/bin/env python3
"""Independent measurement of a written research run.

Reads notes.json and final_report.md from disk. Does not trust the workflow's
self-reported returned_proportion or survival fields. Quota is scored on the
BEGIN_SELECTED block of the final report. Survival is scored on contradiction
tokens that appear in notes.json and also in the BEGIN_CONTRADICTIONS block
of final_report.md. Intermediate notes never count as survival.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from tools.bench.deep_research import (
    MARK_CON_BEGIN,
    MARK_CON_END,
    MARK_SEL_BEGIN,
    MARK_SEL_END,
)

TOKEN_RE = re.compile(r"TOK-[A-Z]+-[A-Z]\d{2}")


def tokens_in_text(text: str) -> list[str]:
    return TOKEN_RE.findall(text)


def section_between(text: str, begin: str, end: str) -> str | None:
    start = text.find(begin)
    stop = text.find(end)
    if start < 0 or stop < 0 or stop <= start:
        return None
    return text[start + len(begin) : stop]


def token_index(corpus: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for src in corpus.get("sources") or []:
        if isinstance(src, dict) and isinstance(src.get("token"), str):
            out[src["token"]] = src
    return out


def ground_truth_from_file(corpus: Mapping[str, Any]) -> dict[str, Any]:
    """Recount stances from the seeded sources. Ignore the declared ground_truth object."""
    claim = corpus.get("query_claim_id") or corpus.get("claim_id")
    support = 0
    contradict = 0
    support_strength = 0.0
    contradict_strength = 0.0
    for src in corpus.get("sources") or []:
        if not isinstance(src, dict):
            continue
        if src.get("claim_id") != claim:
            continue
        stance = src.get("stance")
        strength = float(src.get("strength") or 0.0)
        if stance == "support":
            support += 1
            support_strength += strength
        elif stance == "contradict":
            contradict += 1
            contradict_strength += strength
    polar = support + contradict
    return {
        "query_claim_id": claim,
        "support": support,
        "contradict": contradict,
        "polar": polar,
        "support_ratio": (support / polar) if polar else 0.0,
        "contradict_ratio": (contradict / polar) if polar else 0.0,
        "support_strength": support_strength,
        "contradict_strength": contradict_strength,
        "contradict_stronger": contradict_strength > support_strength,
    }


def measure_run(out_dir: Path, corpus: Mapping[str, Any]) -> dict[str, Any]:
    notes_path = out_dir / "notes.json"
    final_md_path = out_dir / "final_report.md"
    final_json_path = out_dir / "final_report.json"
    notes_text = notes_path.read_text(encoding="utf-8") if notes_path.is_file() else ""
    final_md = final_md_path.read_text(encoding="utf-8") if final_md_path.is_file() else ""
    final_doc: dict[str, Any] = {}
    if final_json_path.is_file():
        try:
            loaded = json.loads(final_json_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                final_doc = loaded
        except json.JSONDecodeError:
            final_doc = {}

    index = token_index(corpus)
    gt = ground_truth_from_file(corpus)

    notes_tokens = [t for t in tokens_in_text(notes_text) if t in index]
    selected_block = section_between(final_md, MARK_SEL_BEGIN, MARK_SEL_END)
    contradict_block = section_between(final_md, MARK_CON_BEGIN, MARK_CON_END)
    selected_tokens = (
        [t for t in tokens_in_text(selected_block) if t in index]
        if selected_block is not None
        else []
    )
    appendix_tokens = (
        [t for t in tokens_in_text(contradict_block) if t in index]
        if contradict_block is not None
        else []
    )

    sel_support = [t for t in selected_tokens if index[t]["stance"] == "support"]
    sel_contradict = [t for t in selected_tokens if index[t]["stance"] == "contradict"]
    polar_n = len(sel_support) + len(sel_contradict)
    returned = {
        "support": (len(sel_support) / polar_n) if polar_n else 0.0,
        "contradict": (len(sel_contradict) / polar_n) if polar_n else 0.0,
        "polar_n": polar_n,
        "support_tokens": sel_support,
        "contradict_tokens": sel_contradict,
    }

    claim = gt["query_claim_id"]
    notes_contradict = [
        t
        for t in notes_tokens
        if index[t]["stance"] == "contradict" and index[t]["claim_id"] == claim
    ]
    # Unique, order-preserving.
    notes_contradict_u: list[str] = []
    for t in notes_contradict:
        if t not in notes_contradict_u:
            notes_contradict_u.append(t)
    appendix_u: list[str] = []
    for t in appendix_tokens:
        if t not in appendix_u:
            appendix_u.append(t)
    survived = [t for t in notes_contradict_u if t in set(appendix_u)]
    survival_rate = (
        len(survived) / len(notes_contradict_u) if notes_contradict_u else 1.0
    )

    verdict = str(final_doc.get("verdict") or "")
    if "Verdict: IMPOSSIBLE" in final_md:
        verdict = "IMPOSSIBLE"
    elif "Verdict:" in final_md and not verdict:
        for line in final_md.splitlines():
            if line.startswith("Verdict:"):
                verdict = line.split(":", 1)[1].strip()
                break

    impossibility_path = out_dir / "impossibility.json"
    impossibility: dict[str, Any] | None = None
    if impossibility_path.is_file():
        try:
            loaded_i = json.loads(impossibility_path.read_text(encoding="utf-8"))
            if isinstance(loaded_i, dict):
                impossibility = loaded_i
        except json.JSONDecodeError:
            impossibility = None

    return {
        "out_dir": str(out_dir),
        "markers_present": selected_block is not None and contradict_block is not None,
        "ground_truth": gt,
        "notes_token_count": len(notes_tokens),
        "notes_contradict_tokens": notes_contradict_u,
        "selected_tokens": selected_tokens,
        "appendix_tokens": appendix_u,
        "returned_proportion": returned,
        "contradiction_survival_rate": survival_rate,
        "survived_tokens": survived,
        "verdict": verdict,
        "impossibility": impossibility,
        "final_md_bytes": len(final_md.encode("utf-8")),
        "notes_bytes": len(notes_text.encode("utf-8")),
        "notes_is_not_final": notes_text != final_md,
    }
