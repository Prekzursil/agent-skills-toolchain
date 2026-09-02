#!/usr/bin/env python3
"""Quote-anchored adapter: paper-described protocol prose -> WorkflowIR subset.

Fills an IR field only when a source sentence is quoted. Unquoted fills are
forced to MISSING (never a plausible default). Missing any of participant
count, turn structure, stopping rule, or scoring yields UNDERSPECIFIED plus
the exact parameters an author would have to supply.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fields import (
    ALL_FIELDS,
    AUTHOR_MUST_SUPPLY,
    FIXTURES,
    PROTOCOL_VOCABULARY,
    REQUIRED_PARAMS,
    WORKFLOW_IR_CONSTRUCTS,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

# Patterns extract a VALUE from a sentence. The whole sentence is the quote.
# Order matters: first match wins. Keep these tight so vague prose stays MISSING.
FIELD_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "participant_count": (
        re.compile(r"(?i)\bexactly\s+(\d+)\s+participants?\b"),
        re.compile(r"(?i)\bN\s*=\s*(\d+)\s+agents?\b"),
        re.compile(r"(?i)\ba panel of\s+(\d+)\s+experts?\b"),
        re.compile(
            r"(?i)\bsamples\s+(\d+)\s+reasoning paths as the participant count\b"
        ),
        re.compile(r"(?i)\bhas exactly\s+(\d+)\s+participants?\b"),
    ),
    "turn_structure": (
        re.compile(r"(?i)^turn structure(?:\s+is)?\s*[: ]\s*(.+)$"),
    ),
    "stopping_rule": (
        re.compile(r"(?i)^the stopping rule is:\s*(.+)$"),
    ),
    "scoring": (
        re.compile(r"(?i)^scoring is\s+(.+)$"),
    ),
    "conflicts_of_interest": (
        re.compile(r"(?i)^conflicts of interest:\s*(.+)$"),
    ),
    "information_partitioning": (
        re.compile(r"(?i)^information partitioning:\s*(.+)$"),
    ),
    "role_mandates": (
        re.compile(r"(?i)^role mandates:\s*(.+)$"),
    ),
    "nested_subcouncil": (
        re.compile(r"(?i)^nested subcouncil:\s*(.+)$"),
    ),
    "deliberation_protocol": (
        re.compile(r"(?i)^deliberation protocol:\s*(.+)$"),
    ),
    "speaking_quotas": (
        re.compile(r"(?i)^speaking quotas:\s*(.+)$"),
    ),
    "minimum_engagement": (
        re.compile(r"(?i)^minimum engagement:\s*(.+)$"),
    ),
    "voting_aggregation": (
        re.compile(r"(?i)^voting and belief aggregation:\s*(.+)$"),
    ),
    "stopping_expression": (
        re.compile(r"(?i)\((ACCEPT OR rounds>=\d+)\)"),
        re.compile(r"(?i)(IQR is below [0-9.]+, or after \d+ rounds)"),
    ),
    "stages": (
        re.compile(r"(?i)^turn structure(?:\s+is)?\s*[: ]\s*(.+)$"),
    ),
    "roles": (
        re.compile(r"(?i)^role mandates:\s*(.+)$"),
        re.compile(r"(?i)\bexactly\s+\d+\s+participants?:\s*(.+)$"),
        re.compile(r"(?i)\bN\s*=\s*\d+\s+agents as (.+)$"),
        re.compile(r"(?i)\ba panel of\s+\d+\s+(experts)\b"),
    ),
    "gates": (
        re.compile(r"(?i)(stop when the judge issues ACCEPT)"),
    ),
    "fan_out_barriers": (
        re.compile(r"(?i)(critics speak in parallel, then the judge rules)"),
        re.compile(r"(?i)(until the round barrier)"),
        re.compile(r"(?i)(generated independently in parallel, then a majority vote)"),
    ),
    "loops_convergence": (
        re.compile(r"(?i)(that triple is one round)"),
        re.compile(r"(?i)(iterative anonymous rounds:.+)$"),
        re.compile(r"(?i)(in each round every agent writes a critique.+)"),
    ),
    "lineage": (
        re.compile(r"(?i)(local corpus fixture)"),
    ),
}

# These IR constructs stay MISSING unless a sentence uses the explicit label.
# Papers in this corpus do not pin them; filling them would be a default.
UNPINNED_UNLESS_LABELLED = (
    "tool_policy",
    "human_checkpoints",
    "retries",
    "resume",
)
LABELLED = {
    "tool_policy": re.compile(r"(?i)^tool policy:\s*(.+)$"),
    "human_checkpoints": re.compile(r"(?i)^human checkpoint:\s*(.+)$"),
    "retries": re.compile(r"(?i)^retries:\s*(.+)$"),
    "resume": re.compile(r"(?i)^resume:\s*(.+)$"),
}

KIND_FOR_FIELD = {
    "participant_count": "roles",
    "turn_structure": "stages",
    "stopping_rule": "stop",
    "scoring": "score",
    "conflicts_of_interest": "policy",
    "information_partitioning": "barrier",
    "role_mandates": "roles",
    "nested_subcouncil": "nesting",
    "deliberation_protocol": "stages",
    "speaking_quotas": "quota",
    "minimum_engagement": "quota",
    "voting_aggregation": "vote",
    "stopping_expression": "stop",
    "stages": "stages",
    "roles": "roles",
    "gates": "gate",
    "tool_policy": "policy",
    "fan_out_barriers": "barrier",
    "loops_convergence": "loop",
    "human_checkpoints": "checkpoint",
    "retries": "retry",
    "resume": "resume",
    "lineage": "lineage",
}


def iter_sentences(text: str, rel: str) -> list[dict[str, Any]]:
    rows = []
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        rows.append({"text": s, "anchor": f"{rel}:{i}", "line": i})
    return rows


def _match_field(field: str, sentence: str) -> str | None:
    if field in LABELLED:
        m = LABELLED[field].search(sentence)
        return m.group(1).strip() if m else None
    for pat in FIELD_PATTERNS.get(field, ()):
        m = pat.search(sentence)
        if m:
            if m.lastindex:
                return m.group(1).strip()
            return m.group(0).strip()
    return None


def extract_fields(text: str, rel: str) -> dict[str, dict[str, Any]]:
    """Quote-anchor every field. Unquoted candidates are MISSING."""
    body = text.replace("\r\n", "\n")
    sentences = iter_sentences(body, rel)
    out: dict[str, dict[str, Any]] = {}
    for field in ALL_FIELDS:
        hit: dict[str, Any] | None = None
        for sent in sentences:
            value = _match_field(field, sent["text"])
            if value is None:
                continue
            quote = sent["text"]
            if quote not in body:
                continue
            hit = {
                "name": field,
                "status": "FILLED",
                "value": value,
                "quote": quote,
                "source_anchor": sent["anchor"],
            }
            break
        if hit is None:
            out[field] = {
                "name": field,
                "status": "MISSING",
                "value": None,
                "quote": None,
                "source_anchor": None,
                "why_unpinned": (
                    AUTHOR_MUST_SUPPLY[field]
                    if field in AUTHOR_MUST_SUPPLY
                    else "no quoted source sentence pins this IR field"
                ),
            }
        else:
            out[field] = hit
    # Catalog test: an unquoted field is treated as MISSING.
    for field, rec in out.items():
        if rec["status"] != "FILLED":
            continue
        quote = rec.get("quote")
        if not isinstance(quote, str) or not quote or quote not in body:
            rec["status"] = "MISSING"
            rec["value"] = None
            rec["quote"] = None
            rec["source_anchor"] = None
            rec["forced_missing_reason"] = "unquoted-or-quote-not-in-source"
    return out


def _ir_nodes(fields: dict[str, dict[str, Any]], paper_id: str) -> list[dict[str, Any]]:
    nodes = []
    for name, rec in fields.items():
        if rec["status"] != "FILLED":
            continue
        nodes.append(
            {
                "id": f"{paper_id}:{name}",
                "kind": KIND_FOR_FIELD.get(name, "field"),
                "field": name,
                "value": rec["value"],
                "source_anchor": rec["source_anchor"],
                "quote": rec["quote"],
            }
        )
    return nodes


def translate(text: str, *, paper_id: str, rel: str, family: str = "") -> dict[str, Any]:
    fields = extract_fields(text, rel)
    missing_required = [p for p in REQUIRED_PARAMS if fields[p]["status"] != "FILLED"]
    if missing_required:
        verdict = "UNDERSPECIFIED"
        ir = None
        refusal = {
            "verdict": "UNDERSPECIFIED",
            "missing_required": missing_required,
            "required_from_author": [
                {
                    "parameter": p,
                    "why_unpinned": fields[p].get("why_unpinned")
                    or AUTHOR_MUST_SUPPLY[p],
                    "what_author_must_supply": AUTHOR_MUST_SUPPLY[p],
                }
                for p in missing_required
            ],
        }
    else:
        verdict = "TRANSLATED"
        ir = {
            "paper_id": paper_id,
            "family": family,
            "dialect": "paper-protocol-prose",
            "nodes": _ir_nodes(fields, paper_id),
            "lossy_unexpressed": [
                n
                for n in WORKFLOW_IR_CONSTRUCTS
                if fields[n]["status"] != "FILLED"
            ],
        }
        refusal = None
    filled = [n for n, r in fields.items() if r["status"] == "FILLED"]
    return {
        "paper_id": paper_id,
        "family": family,
        "source_path": rel,
        "verdict": verdict,
        "fields": fields,
        "filled_fields": filled,
        "missing_required": missing_required,
        "ir": ir,
        "refusal": refusal,
        "vocabulary_filled": [
            n for n in PROTOCOL_VOCABULARY if fields[n]["status"] == "FILLED"
        ],
    }


def load_fixture(rel: str, repo: Path | None = None) -> str:
    root = repo or REPO
    path = root / rel
    return path.read_text(encoding="utf-8")


def translate_fixture(meta: dict[str, Any], repo: Path | None = None) -> dict[str, Any]:
    text = load_fixture(meta["rel"], repo)
    return translate(
        text,
        paper_id=meta["paper_id"],
        rel=meta["rel"],
        family=str(meta.get("family") or ""),
    )


def translate_corpus(repo: Path | None = None) -> list[dict[str, Any]]:
    return [translate_fixture(meta, repo) for meta in FIXTURES]
