"""Cron-refresh diff logic + quarantine (WU-K, PURE LOGIC ONLY).

Given a prior snapshot and a fresh pull (FAERS / literature), compute the
new/changed records. External free-text is sanitized + quarantined as inert,
delimited, untrusted data (memory-guard pattern) BEFORE any downstream use.
A FEP-running sentinel short-circuits the refresh (FEP critical-path guardrail).

The CronCreate registration and the live pipeline invocation are DEFERRED.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# Default sentinel that, when present, means an FEP run is in flight.
FEP_SENTINEL = Path.home() / ".fep-running"

# Inert delimiters wrapping quarantined untrusted text (never agent-readable
# instructions). Mirrors the memory-guard inbound-injection pattern.
QUARANTINE_OPEN = "<<UNTRUSTED_EXTERNAL_DATA>>"
QUARANTINE_CLOSE = "<</UNTRUSTED_EXTERNAL_DATA>>"

# Patterns that look like injected instructions in scraped free-text.
_INJECTION_MARKERS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore (all )?previous instructions", re.IGNORECASE),
    re.compile(r"system\s*:", re.IGNORECASE),
    re.compile(r"</?(system|assistant|user)>", re.IGNORECASE),
    re.compile(r"\bdisregard\b.*\binstructions\b", re.IGNORECASE),
)

# Cap on stored free-text length (response-size guard).
MAX_TEXT_LEN = 4000


@dataclass(frozen=True)
class DiffResult:
    """The outcome of diffing a prior snapshot against a fresh pull."""

    new: list[dict] = field(default_factory=list)
    changed: list[dict] = field(default_factory=list)
    unchanged_count: int = 0

    @property
    def has_changes(self) -> bool:
        return bool(self.new or self.changed)


def _record_id(record: dict, id_key: str) -> str | None:
    val = record.get(id_key)
    return None if val is None else str(val)


def _content_hash(record: dict, id_key: str) -> str:
    """Hash a record's content EXCLUDING its identity key (change detection)."""
    payload = {k: v for k, v in record.items() if k != id_key}
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def diff_snapshot(
    prior: list[dict], fresh: list[dict], id_key: str = "id"
) -> DiffResult:
    """Diff a prior snapshot against a fresh pull, keyed by ``id_key``.

    * records whose id is absent from prior -> ``new``;
    * records present in prior but whose content hash differs -> ``changed``;
    * identical records -> counted in ``unchanged_count``.

    Records missing ``id_key`` are treated as ``new`` (can't be matched).
    """
    prior_hashes: dict[str, str] = {}
    for rec in prior:
        rid = _record_id(rec, id_key)
        if rid is not None:
            prior_hashes[rid] = _content_hash(rec, id_key)

    new: list[dict] = []
    changed: list[dict] = []
    unchanged = 0
    for rec in fresh:
        rid = _record_id(rec, id_key)
        if rid is None or rid not in prior_hashes:
            new.append(rec)
            continue
        if _content_hash(rec, id_key) != prior_hashes[rid]:
            changed.append(rec)
        else:
            unchanged += 1
    return DiffResult(new=new, changed=changed, unchanged_count=unchanged)


def fep_running(sentinel: Path | None = None) -> bool:
    """True iff the FEP-running sentinel exists (refresh must then skip)."""
    path = sentinel if sentinel is not None else FEP_SENTINEL
    return Path(path).exists()


def quarantine_text(text: object) -> str:
    """Wrap untrusted external free-text as inert, delimited, length-capped data.

    Injection markers are neutralized (delimiters/markers defanged), the text is
    truncated to :data:`MAX_TEXT_LEN`, and the whole thing is wrapped in inert
    delimiters so it is NEVER interpreted as agent-readable instructions.
    """
    raw = text if isinstance(text, str) else str(text)
    if len(raw) > MAX_TEXT_LEN:
        raw = raw[:MAX_TEXT_LEN]
    # Defang any literal occurrence of our own delimiters in the payload.
    raw = raw.replace("<<", "&lt;&lt;").replace(">>", "&gt;&gt;")
    # Defang angle-bracket role tags so they can't be read as control tokens.
    raw = raw.replace("<", "&lt;").replace(">", "&gt;")
    return f"{QUARANTINE_OPEN}\n{raw}\n{QUARANTINE_CLOSE}"


def looks_like_injection(text: object) -> bool:
    """Heuristic: does the free-text contain prompt-injection markers?"""
    raw = text if isinstance(text, str) else str(text)
    return any(pat.search(raw) for pat in _INJECTION_MARKERS)


@dataclass(frozen=True)
class StagedRefresh:
    """Diff-before-merge staging payload (NOT merged until reviewed)."""

    diff: DiffResult
    quarantined: list[str]
    flagged_injection: list[dict]
    merged: bool = False


def stage_refresh(
    prior: list[dict],
    fresh: list[dict],
    id_key: str = "id",
    text_key: str = "text",
    sentinel: Path | None = None,
) -> StagedRefresh | None:
    """Stage a refresh: diff + quarantine, FEP-gated, diff-before-merge.

    Returns ``None`` when the FEP sentinel is present (skip). Otherwise returns
    a :class:`StagedRefresh` with ``merged=False`` — external free-text is
    quarantined and any injection-bearing record is flagged (NOT merged).
    """
    if fep_running(sentinel):
        return None

    diff = diff_snapshot(prior, fresh, id_key)
    quarantined: list[str] = []
    flagged: list[dict] = []
    for rec in diff.new + diff.changed:
        if text_key in rec:
            quarantined.append(quarantine_text(rec[text_key]))
            if looks_like_injection(rec[text_key]):
                flagged.append(rec)
    return StagedRefresh(diff=diff, quarantined=quarantined, flagged_injection=flagged)
