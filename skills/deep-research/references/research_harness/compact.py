"""Keep-latest-K compaction of tool outputs (Lens 12 find 4).

Raw search/fetch payloads are what blow the context (and RAM) on long runs.
The harness already keeps the raw payload on disk (query cache + run ledger);
the *working* context only needs the graded digest. Rule: keep the last
``KEEP_LATEST`` (3) tool outputs verbatim and replace everything older with a
compact, **deterministic** digest - a pure function over the ledger, no LLM
call. Compaction is triggered once the working context passes
``COMPACTION_TRIGGER_TOKENS`` (~32k, the Context Rot open-web setting).

``digest_sources`` is the per-sub-question form: <= N lines of
``URL | tier | confidence | provenance | one evidence sentence``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .budget import estimate_tokens
from .grading import Grade, Source

KEEP_LATEST = 3
COMPACTION_TRIGGER_TOKENS = 32_000
DIGEST_LEAD_CHARS = 160
DIGEST_MAX_URLS = 3
DIGEST_MAX_SOURCE_LINES = 8

_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class ToolOutput:
    """One raw provider payload as recorded in the ledger."""

    index: int  # sub-question index
    provider: str
    query_hash: str
    text: str


@dataclass(frozen=True, slots=True)
class Digest:
    """The compacted stand-in for an older ``ToolOutput``."""

    index: int
    provider: str
    query_hash: str
    text: str
    original_chars: int


def _lead_sentence(text: str, max_chars: int = DIGEST_LEAD_CHARS) -> str:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    sentence = _SENTENCE_END_RE.split(first_line, maxsplit=1)[0].strip()
    if len(sentence) > max_chars:
        sentence = sentence[: max(0, max_chars - 1)].rstrip() + "\u2026"
    return sentence


def digest_text(
    text: str, *, prefix: str = "[digest]", max_chars: int | None = None
) -> str:
    """Deterministic one-paragraph summary: lead sentence, size facts, URLs.

    With ``max_chars`` the lead sentence is shortened until the digest fits;
    a digest is never allowed to be longer than what it stands in for.
    """
    if not text.strip():
        return f"{prefix} empty output"
    lines = [line for line in text.splitlines() if line.strip()]
    urls = tuple(dict.fromkeys(u.rstrip(".,;") for u in _URL_RE.findall(text)))
    shown = ", ".join(urls[:DIGEST_MAX_URLS])
    more = (
        f" (+{len(urls) - DIGEST_MAX_URLS} more)" if len(urls) > DIGEST_MAX_URLS else ""
    )
    url_part = f"{len(urls)} URLs: {shown}{more}" if urls else "0 URLs"
    head = f"{prefix} {len(text)} chars, {len(lines)} lines, {url_part}"
    lead_budget = DIGEST_LEAD_CHARS
    if max_chars is not None:
        # head + ' | lead: ""' is the fixed overhead around the lead sentence.
        lead_budget = min(lead_budget, max_chars - len(head) - len(' | lead: ""'))
    if lead_budget <= 0:
        return head if max_chars is None or len(head) <= max_chars else text
    return f'{head} | lead: "{_lead_sentence(text, lead_budget)}"'


def digest_output(output: ToolOutput) -> Digest:
    prefix = f"[digest {output.provider} qh={output.query_hash}]"
    return Digest(
        index=output.index,
        provider=output.provider,
        query_hash=output.query_hash,
        text=digest_text(output.text, prefix=prefix, max_chars=len(output.text)),
        original_chars=len(output.text),
    )


def compact_outputs(
    outputs: Sequence[ToolOutput], *, keep_latest: int = KEEP_LATEST
) -> tuple[ToolOutput | Digest, ...]:
    """Last ``keep_latest`` outputs raw; every older one becomes its ``Digest``."""
    if keep_latest < 0:
        raise ValueError("keep_latest must be >= 0")
    items = tuple(outputs)
    cut = max(0, len(items) - keep_latest)
    return tuple(digest_output(o) for o in items[:cut]) + items[cut:]


def compact_ledger(
    records: Sequence[Mapping[str, Any]], *, keep_latest: int = KEEP_LATEST
) -> tuple[ToolOutput | Digest, ...]:
    """``compact_outputs`` over a ledger's ``tool_output`` records, in order."""
    outputs = [
        ToolOutput(
            index=int(r.get("index", 0)),
            provider=str(r.get("provider", "")),
            query_hash=str(r.get("query_hash", "")),
            text=str(r.get("text", "")),
        )
        for r in records
        if r.get("event") == "tool_output"
    ]
    return compact_outputs(outputs, keep_latest=keep_latest)


def working_context_tokens(items: Sequence[ToolOutput | Digest]) -> int:
    return sum(estimate_tokens(item.text) for item in items)


def should_compact(
    items: Sequence[ToolOutput | Digest],
    *,
    trigger_tokens: int = COMPACTION_TRIGGER_TOKENS,
) -> bool:
    """True once the estimated working-context size passes the trigger."""
    return working_context_tokens(items) > trigger_tokens


def digest_sources(
    sources: Sequence[Source],
    grades: Sequence[Grade],
    *,
    evidence: Mapping[str, str] | None = None,
    max_lines: int = DIGEST_MAX_SOURCE_LINES,
) -> str:
    """<= ``max_lines`` lines of ``URL | tier | confidence | provenance | sentence``."""
    if len(sources) != len(grades):
        raise ValueError("sources and grades must be parallel sequences")
    if max_lines < 1:
        raise ValueError("max_lines must be >= 1")
    evidence = evidence or {}
    lines: list[str] = []
    budget = max_lines if len(sources) <= max_lines else max_lines - 1
    for source, grade in list(zip(sources, grades, strict=True))[:budget]:
        sentence = _lead_sentence(evidence.get(source.url, ""))
        line = f"- {source.url} | tier {grade.tier} | {grade.confidence} | {grade.provenance}"
        if sentence:
            line += f" | {sentence}"
        lines.append(line)
    if len(sources) > max_lines:
        lines.append(f"- ... {len(sources) - budget} more sources (in cache)")
    return "\n".join(lines)
