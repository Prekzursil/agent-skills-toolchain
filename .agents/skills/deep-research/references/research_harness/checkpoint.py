"""Run ledger + resume-from-checkpoint for the deep-research harness.

Lens 12 find 1 (FS-Researcher, Anthropic's research system, ReSum). Per-run
progress is persisted to an **append-only JSONL ledger keyed by a plan hash**
(the normalized sub-questions + capabilities), so a run killed/OOM'd/context-
truncated at sub-question 5/8 restarts at 6/8 instead of from zero. Because
provider calls already flow through ``cache.fetch_with_cache``, most resumed
calls are cache hits.

Events (one JSON object per line, ``event`` key required)::

    {"event": "plan", "plan_hash": ..., "subquestions": [...], "capabilities": [...]}
    {"event": "subq_done", "index": 0, "subquestion": ..., "status": "answered"|"open",
     "sources": [...], "grades": [...]}
    {"event": "tool_output", "index": 0, "provider": ..., "query_hash": ..., "text": ...}
    {"event": "report_partial", "md": ...}
    {"event": "sealed", "status": "complete"|"partial:*"|"failed"}
    {"event": "corruption", "dropped_lines": N, "truncated_at": <byte offset>}

**Fail CLOSED on corruption**: the first undecodable / non-object / eventless /
torn (no trailing newline) line ends what the ledger is allowed to say. The
file is truncated back to the last good record, a ``corruption`` record is
appended so the repair is itself on the record, and every later line - even a
well-formed one - is dropped rather than trusted (the apache/maka reproduction
of the FS-Researcher durable-workspace contract).

The query cache is per-query and TTL'd; this ledger is per-run and ordered.
Distinct layers. Stdlib only (``json`` + ``pathlib``).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cache import DEFAULT_CACHE_DIR, normalize_query

DEFAULT_LEDGER_DIR = DEFAULT_CACHE_DIR.parent / "ledgers"

EVENT_PLAN = "plan"
EVENT_SUBQ_DONE = "subq_done"
EVENT_TOOL_OUTPUT = "tool_output"
EVENT_REPORT_PARTIAL = "report_partial"
EVENT_SEALED = "sealed"
EVENT_CORRUPTION = "corruption"

SUBQ_ANSWERED = "answered"
SUBQ_OPEN = "open"

_MAX_LEDGER_GENERATIONS = 1000


class LedgerCorruption(RuntimeError):
    """Raised by ``load_ledger(repair=False)`` on the first corrupt line."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def plan_hash(subquestions: Sequence[str], capabilities: Sequence[str] = ()) -> str:
    """SHA-256 of the normalized ``(sub-question, capability)`` sequence.

    Order-sensitive (the plan is a sequence), whitespace/case-insensitive per
    sub-question (via ``cache.normalize_query``). Capabilities are part of the
    identity: re-routing the same questions is a different plan.
    """
    caps = list(capabilities) + [""] * (len(subquestions) - len(capabilities))
    envelope = json.dumps(
        [
            [normalize_query(sq), cap]
            for sq, cap in zip(subquestions, caps, strict=True)
        ],
        ensure_ascii=False,
    )
    return hashlib.sha256(envelope.encode("utf-8")).hexdigest()


def ledger_path(ledger_dir: Path, phash: str, generation: int = 0) -> Path:
    """``{plan_hash}.jsonl`` (generation 0) or ``{plan_hash}.{n}.jsonl``."""
    if generation == 0:
        return ledger_dir / f"{phash}.jsonl"
    return ledger_dir / f"{phash}.{generation}.jsonl"


# --- writing (append-only) ----------------------------------------------------


def append_event(path: Path, event: dict[str, Any]) -> None:
    """Append one compact JSON line. The only write primitive in this module."""
    if not isinstance(event, dict) or not event.get("event"):
        raise ValueError("a ledger event must be a dict with a non-empty 'event'")
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def record_plan(
    path: Path,
    phash: str,
    subquestions: Sequence[str],
    capabilities: Sequence[str] = (),
    *,
    ts: str | None = None,
) -> None:
    append_event(
        path,
        {
            "event": EVENT_PLAN,
            "plan_hash": phash,
            "subquestions": list(subquestions),
            "capabilities": list(capabilities),
            "ts": ts or _now_iso(),
        },
    )


def record_subquestion_done(
    path: Path,
    index: int,
    subquestion: str,
    *,
    status: str = SUBQ_ANSWERED,
    sources: Sequence[str] = (),
    grades: Sequence[str] = (),
    ts: str | None = None,
) -> None:
    if status not in (SUBQ_ANSWERED, SUBQ_OPEN):
        raise ValueError(f"unknown sub-question status: {status!r}")
    append_event(
        path,
        {
            "event": EVENT_SUBQ_DONE,
            "index": index,
            "subquestion": subquestion,
            "status": status,
            "sources": list(sources),
            "grades": list(grades),
            "ts": ts or _now_iso(),
        },
    )


def record_tool_output(
    path: Path,
    index: int,
    provider: str,
    query_hash: str,
    text: str,
    *,
    ts: str | None = None,
) -> None:
    """Raw tool output, kept on disk so the working context can hold a digest."""
    append_event(
        path,
        {
            "event": EVENT_TOOL_OUTPUT,
            "index": index,
            "provider": provider,
            "query_hash": query_hash,
            "text": text,
            "ts": ts or _now_iso(),
        },
    )


def record_partial_report(path: Path, markdown: str, *, ts: str | None = None) -> None:
    """The evolving report (report-as-state); the renderer seeds from the last one."""
    append_event(
        path, {"event": EVENT_REPORT_PARTIAL, "md": markdown, "ts": ts or _now_iso()}
    )


def seal(path: Path, status: str, *, ts: str | None = None) -> None:
    """Close the run with its terminal status. A sealed ledger is never resumed."""
    append_event(
        path, {"event": EVENT_SEALED, "status": status, "ts": ts or _now_iso()}
    )


# --- reading (fail closed) ----------------------------------------------------


@dataclass(frozen=True, slots=True)
class Corruption:
    """What ``load_ledger`` had to cut: lines dropped from ``truncated_at`` on."""

    truncated_at: int
    dropped_lines: int


@dataclass(frozen=True, slots=True)
class Ledger:
    """Parsed ledger records (in order) plus any repair performed while loading."""

    path: Path
    records: tuple[dict[str, Any], ...]
    corruption: Corruption | None = None

    @property
    def plan(self) -> dict[str, Any] | None:
        return next((r for r in self.records if r["event"] == EVENT_PLAN), None)

    @property
    def sealed(self) -> bool:
        return any(r["event"] == EVENT_SEALED for r in self.records)

    @property
    def final_status(self) -> str | None:
        sealed = [r for r in self.records if r["event"] == EVENT_SEALED]
        return sealed[-1].get("status") if sealed else None

    def _done(self, status: str) -> list[dict[str, Any]]:
        return [
            r
            for r in self.records
            if r["event"] == EVENT_SUBQ_DONE
            and r.get("status", SUBQ_ANSWERED) == status
        ]

    @property
    def answered_indexes(self) -> tuple[int, ...]:
        return tuple(dict.fromkeys(int(r["index"]) for r in self._done(SUBQ_ANSWERED)))

    @property
    def answered_subquestions(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(str(r["subquestion"]) for r in self._done(SUBQ_ANSWERED))
        )

    @property
    def open_subquestions(self) -> tuple[str, ...]:
        answered = {normalize_query(sq) for sq in self.answered_subquestions}
        return tuple(
            dict.fromkeys(
                str(r["subquestion"])
                for r in self._done(SUBQ_OPEN)
                if normalize_query(str(r["subquestion"])) not in answered
            )
        )

    @property
    def last_partial_report(self) -> str | None:
        drafts = [r for r in self.records if r["event"] == EVENT_REPORT_PARTIAL]
        return str(drafts[-1]["md"]) if drafts else None

    @property
    def tool_outputs(self) -> tuple[dict[str, Any], ...]:
        return tuple(r for r in self.records if r["event"] == EVENT_TOOL_OUTPUT)


def _parse_line(raw: bytes) -> dict[str, Any] | None:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not data.get("event"):
        return None
    return data


def load_ledger(path: Path, *, repair: bool = True) -> Ledger:
    """Parse a ledger, failing CLOSED at the first corrupt line.

    With ``repair=True`` (default) the file is truncated to the last good record
    and a ``corruption`` record is appended; with ``repair=False`` a
    ``LedgerCorruption`` is raised and the file is left untouched.
    """
    if not path.is_file():
        return Ledger(path=path, records=())
    blob = path.read_bytes()
    records: list[dict[str, Any]] = []
    good_end = 0
    dropped = 0
    offset = 0
    while offset < len(blob):
        newline = blob.find(b"\n", offset)
        if newline == -1:
            # Torn trailing write (killed before the newline): not trusted.
            dropped += 1
            break
        record = _parse_line(blob[offset:newline])
        if record is None:
            dropped = blob[offset:].count(b"\n")
            break
        records.append(record)
        offset = newline + 1
        good_end = offset
    if dropped == 0:
        return Ledger(path=path, records=tuple(records))

    if not repair:
        raise LedgerCorruption(
            f"{path}: corrupt ledger line after byte {good_end}; {dropped} line(s) untrusted"
        )
    with path.open("r+b") as fh:
        fh.truncate(good_end)
    corruption = Corruption(truncated_at=good_end, dropped_lines=dropped)
    repair_record = {
        "event": EVENT_CORRUPTION,
        "truncated_at": good_end,
        "dropped_lines": dropped,
        "ts": _now_iso(),
    }
    append_event(path, repair_record)
    records.append(repair_record)
    return Ledger(path=path, records=tuple(records), corruption=corruption)


# --- resuming -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ResumeState:
    """Which sub-questions still need work, and what the renderer can seed from."""

    fresh: bool
    pending: tuple[str, ...]
    completed: tuple[str, ...]
    open_subquestions: tuple[str, ...]
    seed_report: str | None


def resume(ledger: Ledger, subquestions: Sequence[str]) -> ResumeState:
    """Drop already-answered sub-questions (matched by normalized text).

    A sealed ledger, or one holding no progress yet (missing, or plan-only),
    yields a *fresh* state: everything is pending and nothing is seeded.
    ``open`` sub-questions stay pending (they were touched but never met the
    sufficiency bar) and are also reported so the renderer can list them if the
    resumed run cannot close them either.
    """
    progress = (EVENT_SUBQ_DONE, EVENT_REPORT_PARTIAL)
    has_progress = any(r["event"] in progress for r in ledger.records)
    if ledger.sealed or not has_progress:
        return ResumeState(
            fresh=True,
            pending=tuple(subquestions),
            completed=(),
            open_subquestions=(),
            seed_report=None,
        )
    answered = {normalize_query(sq) for sq in ledger.answered_subquestions}
    completed = tuple(sq for sq in subquestions if normalize_query(sq) in answered)
    pending = tuple(sq for sq in subquestions if normalize_query(sq) not in answered)
    return ResumeState(
        fresh=False,
        pending=pending,
        completed=completed,
        open_subquestions=ledger.open_subquestions,
        seed_report=ledger.last_partial_report,
    )


def active_ledger_path(ledger_dir: Path, phash: str) -> Path:
    """First ledger file for this plan that is missing or not yet sealed.

    Sealed runs are kept as an audit trail (append-only: nothing is renamed or
    deleted); a re-run of a sealed plan gets the next generation file.
    """
    for generation in range(_MAX_LEDGER_GENERATIONS):
        candidate = ledger_path(ledger_dir, phash, generation)
        if not candidate.is_file() or not load_ledger(candidate).sealed:
            return candidate
    raise RuntimeError(f"too many sealed ledgers for plan {phash}")


def open_run(
    ledger_dir: Path,
    subquestions: Sequence[str],
    capabilities: Sequence[str] = (),
) -> tuple[Ledger, ResumeState]:
    """Locate (or start) the ledger for a plan and compute what is left to do.

    Records the ``plan`` event exactly once per ledger file. Returns the loaded
    ledger (including that plan record) and the resume state.
    """
    phash = plan_hash(subquestions, capabilities)
    path = active_ledger_path(ledger_dir, phash)
    ledger = load_ledger(path)
    if ledger.plan is None:
        record_plan(path, phash, subquestions, capabilities)
        ledger = load_ledger(path)
    return ledger, resume(ledger, subquestions)
