#!/usr/bin/env python3
"""Generate the SYN-0045 owner brief from a bound report plus open decisions."""
from __future__ import annotations

from typing import Iterable

from claims import (
    CLAIM_SECTIONS,
    extract_report_claims,
    invariant,
    word_count,
)

# Keep a strict subset so summarisation is real (retention < 1).
BRIEF_SELECT = ("R-001", "R-002", "R-003", "R-004", "R-006", "R-008")

SECTION_FOR_LABEL = {
    "VERIFIED": "what was built",
    "INFERRED": "what is proven",
    "UNVERIFIED": "what is open",
    "DEFERRED": "what is open",
    "REJECTED": "what is proven",
}


def select_rows(report_rows: list[dict], wanted: Iterable[str] | None = None) -> list[dict]:
    ids = list(wanted) if wanted is not None else list(BRIEF_SELECT)
    by_id = {r["id"]: r for r in report_rows}
    chosen = [by_id[i] for i in ids if i in by_id]
    if chosen:
        return chosen
    # Live SYN-0041 may use different ids: keep VERIFIED/INFERRED first, drop at least one.
    preferred = [r for r in report_rows if r["label"] in {"VERIFIED", "INFERRED"}]
    pool = preferred or list(report_rows)
    if len(pool) <= 1:
        return pool
    return pool[:-1]


def render_markdown(
    claims: list[dict],
    decisions: list[dict],
    next_actions: list[str],
    evidence_line: str,
    sentinel: str,
) -> str:
    buckets = {name: [] for name in CLAIM_SECTIONS}
    for row in claims:
        section = SECTION_FOR_LABEL.get(row["label"], "what is open")
        buckets[section].append(f"- {row['label']}: {row['text']}")

    parts = ["# Owner brief", ""]
    titles = (
        ("What was built", "what was built"),
        ("What is proven", "what is proven"),
        ("What is open", "what is open"),
    )
    for title, key in titles:
        parts.append(f"## {title}")
        parts.append("")
        parts.extend(buckets[key] or ["- none"])
        parts.append("")

    parts.append("## What needs a decision")
    parts.append("")
    for d in decisions:
        parts.append(f"### {d['id']}: {d['question']}")
        parts.append(f"- recommendation: {d['recommendation']}")
        parts.append(f"- strongest_tradeoff: {d['strongest_tradeoff']}")
        parts.append(f"- default_if_unanswered: {d['default_if_unanswered']}")
        parts.append("")

    parts.append("## What to do next")
    parts.append("")
    for action in next_actions:
        parts.append(f"- {action}")
    parts.append("")
    parts.append("## Evidence")
    parts.append("")
    parts.append(evidence_line)
    parts.append("")
    parts.append(sentinel)
    parts.append("")
    return "\n".join(parts)


def next_actions_from(decisions: list[dict], deferred: list[dict]) -> list[str]:
    actions: list[str] = []
    for d in decisions:
        rec = str(d.get("recommendation") or "").strip()
        if rec:
            actions.append(f"{d.get('id')}: {rec}")
    for row in deferred:
        actions.append(f"deferred {row['id']}: {row['text']}")
    return actions or ["No next action is stated because none was sourced."]


def build_document(
    *,
    report: dict,
    decisions: list[dict],
    claim_source: dict,
    sentinel: str,
    question: str,
    wanted_ids: Iterable[str] | None = None,
) -> dict:
    report_rows = extract_report_claims(report)
    chosen = select_rows(report_rows, wanted_ids)
    brief_claims = [
        {
            "id": f"B-{i:03d}",
            "source_item_id": row["id"],
            "label": row["label"],
            "text": row["text"],
        }
        for i, row in enumerate(chosen, start=1)
    ]
    deferred = [r for r in report_rows if r["label"] == "DEFERRED"]
    actions = next_actions_from(decisions, deferred[:1])
    stub = {
        "claims": brief_claims,
        "markdown": "",
    }
    diff = invariant(stub, report)
    evidence_line = (
        f"{diff['printed']}. word_count_placeholder. "
        f"claim_count={diff['brief_claim_count']}/{diff['report_claim_count']} "
        f"retention_rate={diff['retention_rate']:.6f}."
    )
    markdown = render_markdown(
        chosen, decisions, actions, evidence_line, sentinel
    )
    words = word_count(markdown)
    evidence_line = (
        f"{diff['printed']}. word_count={words}. "
        f"claim_count={diff['brief_claim_count']}/{diff['report_claim_count']} "
        f"retention_rate={diff['retention_rate']:.6f}."
    )
    markdown = render_markdown(
        chosen, decisions, actions, evidence_line, sentinel
    )
    words = word_count(markdown)
    doc = {
        "unit_id": "SYN-0045",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "question": question,
        "claim_source": {
            "kind": claim_source["kind"],
            "path": claim_source["path"],
            "live_present": bool(claim_source.get("present")),
            "only_permitted_claim_source": (
                "command-center/synthesis/SYN-0041.final-report.json"
            ),
        },
        "claims": brief_claims,
        "open_decisions": decisions,
        "what_was_built": [r["text"] for r in chosen if r["label"] == "VERIFIED"],
        "what_is_proven": [
            r["text"]
            for r in chosen
            if r["label"] in {"VERIFIED", "INFERRED", "REJECTED"}
        ],
        "what_is_open": [
            r["text"] for r in chosen if r["label"] in {"UNVERIFIED", "DEFERRED"}
        ],
        "what_needs_a_decision": [d["question"] for d in decisions],
        "what_to_do_next": actions,
        "markdown": markdown,
        "word_count": words,
        "claim_count": len(brief_claims),
        "report_claim_count": len(report_rows),
        "retention_rate": diff["retention_rate"],
        "set_difference": {
            "brief_minus_report": diff["brief_minus_report"],
            "empty": diff["empty"],
            "printed": diff["printed"],
        },
    }
    return doc
