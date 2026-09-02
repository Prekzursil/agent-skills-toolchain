"""Mechanical disconfirming-query generator for any claim string.

Accepts a raw string (or a dict with text/claim/statement). Never requires
pre-parsed subject/capability/competitor/issue_repo fields.
"""
from __future__ import annotations

import json
import re
from typing import Any

TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[+._/-][A-Za-z0-9]+)*")
OPERATOR_RE = re.compile(r"\b(?:site|is|label|reason):\S+", re.I)

STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "and",
        "or",
        "to",
        "in",
        "on",
        "for",
        "with",
        "by",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "as",
        "at",
        "that",
        "this",
        "it",
        "its",
        "into",
        "over",
        "than",
        "then",
        "via",
        "may",
        "must",
        "should",
        "without",
        "never",
        "no",
        "not",
        "only",
        "all",
        "any",
        "can",
        "cannot",
        "like",
        "using",
        "used",
        "use",
        "has",
        "have",
        "had",
        "does",
        "do",
        "did",
        "still",
        "every",
        "same",
        "such",
        "those",
        "these",
        "their",
        "them",
    }
)

# Cue tokens stripped from "subject" but kept on generated queries.
CUE_TOKENS = frozenset(
    {
        "false",
        "wrong",
        "incorrect",
        "failed",
        "broken",
        "bug",
        "wontfix",
        "regression",
        "myth",
        "disprove",
        "counterevidence",
        "alternative",
        "migrated",
        "instead",
        "work",
        "works",
        "doesnt",
        "don't",
        "cannot",
        "never",
    }
)


def claim_text(claim: Any) -> str:
    """Normalize any claim-shaped input to a string. Never raises KeyError."""
    if claim is None:
        return ""
    if isinstance(claim, str):
        return claim.strip()
    if isinstance(claim, dict):
        for key in ("text", "claim", "statement", "raw", "sentence"):
            val = claim.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        return json.dumps(claim, sort_keys=True)
    return str(claim).strip()


def tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in TOKEN_RE.finditer(text or "")]


def content_tokens(text: str) -> list[str]:
    kept = [t for t in tokens(text) if t not in STOP and len(t) > 1]
    return kept if kept else tokens(text) or ["claim"]


def subject_phrase(claim: Any, n: int = 6) -> str:
    text = claim_text(claim)
    toks = [t for t in content_tokens(text) if t not in CUE_TOKENS]
    if not toks:
        toks = content_tokens(text)
    return " ".join(toks[:n])


def _rows(family: str, queries: list[str]) -> list[dict[str, str]]:
    out = []
    seen: set[str] = set()
    for q in queries:
        q = " ".join(q.split())
        if not q or q.lower() in seen:
            continue
        seen.add(q.lower())
        out.append({"family": family, "query": q})
    return out


def generate(claim: Any) -> list[dict[str, str]]:
    """Primary mechanical generator (probe 1)."""
    text = claim_text(claim)
    subj = subject_phrase(text)
    quoted = f'"{subj}"'
    rows: list[dict[str, str]] = []
    rows += _rows(
        "negation",
        [
            f"{quoted} does not work",
            f"{subj} not true",
            f"{subj} never",
            f"{quoted} cannot",
        ],
    )
    rows += _rows(
        "failure_vocabulary",
        [
            f"{subj} failed",
            f"{subj} broken",
            f"{subj} incorrect",
            f"{subj} bug",
            f"{subj} regression",
        ],
    )
    rows += _rows(
        "x_does_not_work",
        [
            f"{subj} does not work",
            f"{quoted} doesn't work",
        ],
    )
    rows += _rows(
        "competitor_framing",
        [
            f"alternative to {subj}",
            f"migrated away from {subj}",
            f"{subj} vs",
            f"instead of {subj}",
        ],
    )
    rows += _rows(
        "issue_tracker",
        [
            f"site:github.com {subj} is:closed",
            f"{subj} wontfix",
            f"{subj} label:wontfix",
            f"{subj} reason:not-planned",
            f"{subj} is:issue is:closed",
        ],
    )
    return rows


def generate_independent(claim: Any) -> list[dict[str, str]]:
    """Second template expansion: same families, different wording (probe 2)."""
    text = claim_text(claim)
    subj = subject_phrase(text, n=5)
    rows: list[dict[str, str]] = []
    rows += _rows(
        "negation",
        [
            f"{subj} is not correct",
            f"{subj} is false",
            f"{subj} no such",
        ],
    )
    rows += _rows(
        "failure_vocabulary",
        [
            f"{subj} is broken",
            f"{subj} failure",
            f"{subj} is a bug",
        ],
    )
    rows += _rows(
        "x_does_not_work",
        [
            f"{subj} does not work",
            f"{subj} will not work",
        ],
    )
    rows += _rows(
        "competitor_framing",
        [
            f"replacement for {subj}",
            f"moved off {subj}",
            f"{subj} compared to",
        ],
    )
    rows += _rows(
        "issue_tracker",
        [
            f"site:github.com/issues {subj} closed",
            f"{subj} wontfix",
            f"{subj} not-planned issue",
        ],
    )
    return rows


def baseline_queries(claim: Any) -> list[dict[str, str]]:
    """Unstructured counter-search: paste the claim plus generic dissent words."""
    text = claim_text(claim)
    return _rows(
        "unstructured",
        [
            text,
            f"counterevidence {text}",
            f"{text} false",
            f"{text} wrong",
            f"disprove {text}",
            f"is {text} a myth",
        ],
    )


def query_strings(rows: list[dict[str, str]]) -> list[str]:
    return [r["query"] for r in rows]


def lexical_terms(query: str) -> list[str]:
    stripped = OPERATOR_RE.sub(" ", query)
    stripped = stripped.replace('"', " ")
    return [t for t in tokens(stripped) if t not in STOP and len(t) > 1]
