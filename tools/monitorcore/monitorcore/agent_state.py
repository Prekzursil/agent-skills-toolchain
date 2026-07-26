"""Transcript→coarse-state derivation (Fork C) + the unified agent state bucket.

Two pure, stdlib-only pieces the agent domain needs:

* :func:`bucket_agent` — the SINGLE source of truth for the coarse
  ``running`` / ``done`` / ``error`` / ``idle`` bucket that wfmon previously duplicated as
  ``model._state_bucket`` **and** ``workflow_monitor._bucket`` (identical logic in two
  places). Both now delegate here, killing the duplication. It maps a manifest agent row
  (its ``errored`` / ``state`` / ``running`` flags, plus an optional journal state) onto the
  bucket; ``journal_state=None`` reproduces the former ``_bucket`` exactly.

* :func:`agent_status` — the transcript-driven deriver ported from the retired agent-monitor
  Tkinter UI. It reads the tail of the transcript to distinguish ``running`` (fresh) /
  ``working`` (recently active or awaiting a long tool call) / ``done`` (the transcript shows
  the agent FINISHED) / ``stalled`` (frozen past its dead-man window).

TWO-SIGNAL STALL RULE
---------------------
``stalled`` is an INFERENCE, not a fact: a stalled agent and a long-FINISHED one are
indistinguishable from a single file-mtime reading. Deriving ``stalled`` from mtime age
alone was a MEASURED live defect — an 11-hour-old finished agent was reported as a live
stall, and re-measured on this box **66 of 1,283** transcripts older than 11 hours (i.e.
every one of them long finished) were labelled ``stalled`` by the single-signal oracle.

So this module now decides ``stalled`` only when TWO mechanically-independent signals
agree, and only when the transcript does not already say the agent finished:

1. **filesystem signal** — the file's mtime has not advanced past the dead-man window; AND
2. **content signal** — the tail's content fingerprint is unchanged across ``>= 2`` polls.

The AND-gate itself is NOT reimplemented here: :func:`classify_status` delegates it to
:func:`monitorcore.stall.is_corroborated_stall`, which is the one place that rule lives.
TERMINAL evidence outranks both — :func:`classify_status` answers ``done`` at ANY age when
the transcript shows the agent finished, so silence can never reclassify a finished agent
as a live stall.

The decision layer (:func:`classify_status` over an explicit :class:`StatusEvidence`) and
the tail parser (:func:`tail_evidence` over decoded text) are PURE — no clock, no
filesystem — so they reach 100% branch coverage on any platform. :func:`agent_status` is
the thin impure shim that reads the file, remembers the previous poll's fingerprint, and
calls them.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass

from .stall import StallSignals, is_corroborated_stall

__all__ = [
    "FRESH",
    "STALL",
    "StatusEvidence",
    "TailEvidence",
    "agent_status",
    "bucket_agent",
    "classify_status",
    "read_evidence",
    "reset_state",
    "tail_evidence",
]

FRESH = 45.0  # mtime age (s) under which an agent is definitely RUNNING
STALL = 600.0  # silence (s) after which a CONTENT-FROZEN agent may be inferred STALLED

_TAIL_BYTES = 40_000  # how much of the transcript tail one poll reads

# ``StatusEvidence.content_frozen`` means this poll's digest equals the previous poll's,
# i.e. at least TWO consecutive polls carried identical content — exactly the freeze
# threshold ``stall.is_corroborated_stall`` requires before a stall may be inferred.
_FROZEN_POLLS = 2

# The model's own end-of-turn declaration, persisted as ``message.stop_reason``. These two
# mean the turn COMPLETED; ``tool_use`` / ``max_tokens`` mean it was cut short mid-flight.
# Measured on 1,283 >11h-old transcripts on this box: only ``end_turn`` was observed among
# the mislabelled set; ``stop_sequence`` is its documented sibling and is treated the same.
_TERMINAL_STOP_REASONS = frozenset({"end_turn", "stop_sequence"})


def bucket_agent(
    *,
    errored: bool,
    state: str | None,
    running: bool,
    journal_state: str | None = None,
) -> str:
    """Collapse a manifest agent row into a coarse display bucket.

    ``error`` if the manifest marks the agent errored; else ``done`` if the journal recorded
    a ``result`` OR the manifest state is ``done``; else ``running`` if the agent is in a
    running state; else ``idle``. Passing ``journal_state=None`` reproduces the former
    ``workflow_monitor._bucket``; passing the journal state reproduces ``model._state_bucket``.
    """
    if errored:
        return "error"
    if journal_state == "result" or state == "done":
        return "done"
    if running:
        return "running"
    return "idle"


# ───────────────────────── tail evidence (PURE) ─────────────────────────
@dataclass(frozen=True)
class TailEvidence:
    """What ONE tail read observed. Pure data — no clock, no filesystem.

    ``last_type`` / ``role`` are the shape of the newest content-bearing block (the
    pre-existing signal). ``terminal`` is ``True`` when the transcript itself shows the agent
    FINISHED. ``fingerprint`` is a stable digest of the tail bytes — the CONTENT signal,
    mechanically independent of the file's mtime — or ``None`` when the tail was unreadable.
    """

    last_type: str | None
    role: str | None
    terminal: bool
    fingerprint: str | None


# The evidence an unreadable transcript yields: no shape, NOT terminal, and no fingerprint
# (so it can never satisfy the content half of the stall gate).
_UNREADABLE = TailEvidence(last_type=None, role=None, terminal=False, fingerprint=None)


def _records(text: str) -> list[dict[str, object]]:
    """Parse a JSONL tail NEWEST-FIRST, skipping blank / non-JSON / unparseable lines.

    The first line of a mid-file tail read is usually a fragment, so unparseable lines are
    dropped rather than raising.
    """
    out: list[dict[str, object]] = []
    for raw in reversed(text.splitlines()):
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _message_of(rec: dict[str, object]) -> dict[str, object]:
    """The record's ``message`` dict, or an empty dict when it is absent or not a dict."""
    msg = rec.get("message")
    return msg if isinstance(msg, dict) else {}


def _as_str(value: object) -> str | None:
    """``value`` when it is a string, else ``None`` — transcript JSON fields are untyped."""
    return value if isinstance(value, str) else None


def _last_block(records: list[dict[str, object]]) -> tuple[str | None, str | None]:
    """``(block_type, role)`` of the newest content-bearing block in ``records``.

    ``records`` must be newest-first. A string ``content`` counts as one ``text`` block
    (that is how the retired agent-monitor treated it). ``(None, None)`` when no record
    carries a typed block.
    """
    for rec in records:
        msg = _message_of(rec)
        content = msg.get("content")
        blocks = (
            content
            if isinstance(content, list)
            else ([{"type": "text"}] if isinstance(content, str) else [])
        )
        for b in reversed(blocks):
            if isinstance(b, dict) and b.get("type"):
                return (_as_str(b.get("type")), _as_str(msg.get("role")))
    return (None, None)


def _turn_ended(records: list[dict[str, object]]) -> bool:
    """Whether the newest assistant record declared its turn COMPLETE.

    This is terminal evidence already present in the bytes that the single-signal oracle
    never read: the model records why it stopped in ``message.stop_reason``. ``records``
    must be newest-first; ``False`` when no assistant record is present.
    """
    for rec in records:
        msg = _message_of(rec)
        if msg.get("role") == "assistant":
            return msg.get("stop_reason") in _TERMINAL_STOP_REASONS
    return False


def tail_evidence(text: str) -> TailEvidence:
    """Fold one poll's decoded transcript tail into a :class:`TailEvidence`. PURE.

    Terminal evidence is the OR of the two signals the transcript already carries: the
    pre-existing trailing-assistant-``text`` turn, and the model's own ``stop_reason``
    end-of-turn declaration.
    """
    records = _records(text)
    last_type, role = _last_block(records)
    terminal = (last_type == "text" and role == "assistant") or _turn_ended(records)
    return TailEvidence(
        last_type=last_type,
        role=role,
        terminal=terminal,
        fingerprint=hashlib.sha256(text.encode("utf-8", "replace")).hexdigest(),
    )


def _read_tail(path: str, *, nbytes: int = _TAIL_BYTES) -> str | None:
    """The decoded last ``nbytes`` of ``path``, or ``None`` when unreadable.

    The ONLY filesystem read in the evidence path; everything downstream of it is pure.
    """
    try:
        sz = os.path.getsize(path)
        with open(path, "rb") as fh:
            fh.seek(max(0, sz - nbytes))
            return fh.read().decode("utf-8", "ignore")
    except OSError:
        return None


def read_evidence(path: str) -> TailEvidence:
    """Read ``path``'s tail once and fold it into evidence; unreadable → empty evidence."""
    text = _read_tail(path)
    return _UNREADABLE if text is None else tail_evidence(text)


# ───────────────────────── the decision (PURE) ─────────────────────────
@dataclass(frozen=True)
class StatusEvidence:
    """The explicit evidence record :func:`classify_status` decides from. Pure data.

    ``age`` is the mtime age in seconds (the FILESYSTEM signal) and ``fresh`` / ``stall``
    its two windows. ``terminal`` is whether the transcript shows the agent finished (a
    FACT). ``fingerprint`` is THIS poll's content digest and ``previous`` the PRIOR poll's
    (``None`` = never seen before) — together the CONTENT signal.
    """

    age: float
    fresh: float
    stall: float
    terminal: bool
    fingerprint: str | None
    previous: str | None

    @property
    def content_frozen(self) -> bool:
        """Whether this poll's digest is unchanged from the previous poll's.

        ``None`` never matches, so a first sighting (no previous poll) and an unreadable
        transcript both count as NOT frozen — one signal must never carry a stall.
        """
        return self.fingerprint is not None and self.fingerprint == self.previous


def classify_status(ev: StatusEvidence) -> str:
    """Decide one transcript's state from explicit evidence. PURE — no clock, no I/O.

    The order is load-bearing:

    1. a transcript touched within ``fresh`` seconds is ``running`` (unchanged behaviour —
       freshness is checked before any content is read);
    2. TERMINAL evidence ⇒ ``done`` at ANY age. A finished agent is a fact, so no amount of
       silence may reclassify it as a live stall;
    3. ``stalled`` ONLY on the two-signal AND-gate — mtime stale past ``stall``
       (filesystem) AND content frozen across ``>= 2`` polls (content). The gate itself is
       :func:`monitorcore.stall.is_corroborated_stall`, so this module does not own a
       second copy of the rule;
    4. otherwise ``working`` — the honest answer when only one signal is present.
    """
    if ev.age < ev.fresh:
        return "running"
    if ev.terminal:
        return "done"
    signals = StallSignals(
        mtime_stale=ev.age > ev.stall,
        frozen_polls=_FROZEN_POLLS if ev.content_frozen else 1,
    )
    if is_corroborated_stall(signals):
        return "stalled"
    return "working"


# ───────────────────────── the impure shim ─────────────────────────
# path -> (mtime, terminal_status); avoids re-reading finished agents whose mtime is frozen.
_STATUS_CACHE: dict[str, tuple[float, str]] = {}
# path -> the PREVIOUS poll's content fingerprint; the cross-poll half of the stall gate.
# (``stall.StallTracker`` folds fingerprints down to a count; the explicit evidence record
# needs the fingerprint itself, so the per-path memory is kept here and the AND-gate reused.)
_FINGERPRINTS: dict[str, str | None] = {}


def reset_state() -> None:
    """Clear both module caches — the terminal-status cache and the fingerprint history."""
    _STATUS_CACHE.clear()
    _FINGERPRINTS.clear()


def agent_status(
    path: str,
    *,
    now: float | None = None,
    fresh: float = FRESH,
    stall: float = STALL,
    terminal: bool = False,
    fingerprints: dict[str, str | None] | None = None,
) -> tuple[str, float]:
    """Return ``(state, age_s)`` for one transcript: ``running`` | ``working`` | ``done`` | ``stalled``.

    A transcript touched within ``fresh`` seconds is ``running``. Otherwise the tail is read
    once and handed to :func:`classify_status`, which answers ``done`` whenever the
    transcript shows the agent finished (at any age) and ``stalled`` only when mtime
    staleness AND a content freeze across ``>= 2`` polls agree. The first poll of an
    unfamiliar silent transcript therefore reports ``working``, never ``stalled`` — one
    signal is not evidence.

    Terminal states (``done`` / ``stalled``) are cached by frozen mtime so a finished agent
    is not re-read; any mtime movement invalidates that cache. ``now`` is injectable for
    deterministic tests, as is ``fingerprints`` (the cross-poll fingerprint memory, which
    defaults to the module-level one).

    ``terminal`` lets a caller contribute terminal evidence the TRANSCRIPT DOES NOT CARRY —
    e.g. the manifest/journal ``done`` that :func:`bucket_agent` already models, or the
    parent transcript's completed ``Task`` tool result. It is OR-ed with the in-file signals,
    so ``terminal=True`` guarantees ``done`` at any age and any freeze depth. This matters:
    measured on this box, 64 of 66 long-finished transcripts that the single-signal oracle
    mislabelled carry NO end-of-turn evidence in their own bytes (they end mid-``tool_use``
    / ``tool_result``), so from the file alone they are genuinely indistinguishable from a
    wedged agent. Supplying that evidence here is the only sound way to resolve them; the
    two-signal gate alone downgrades them from an instant stall to a corroborated one.

    KNOWN RESIDUAL, disclosed rather than hidden: a missing or unreadable transcript still
    returns ``("stalled", 1e9)`` — absence reported as a stall, which is also single-signal.
    Changing it would change this function's state vocabulary for every caller, so it is
    left to the board layer, which has :class:`monitorcore.stall.Condition` values (and an
    UNREACHABLE row) that this 4-string return cannot express.
    """
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return ("stalled", 1e9)
    clock = time.time() if now is None else now
    age = clock - mtime
    if age < fresh:
        return ("running", age)
    cached = _STATUS_CACHE.get(path)
    if cached and cached[0] == mtime:
        return (cached[1], age)
    seen = _FINGERPRINTS if fingerprints is None else fingerprints
    ev = read_evidence(path)
    status = classify_status(
        StatusEvidence(
            age=age,
            fresh=fresh,
            stall=stall,
            terminal=ev.terminal or terminal,
            fingerprint=ev.fingerprint,
            previous=seen.get(path),
        )
    )
    seen[path] = ev.fingerprint
    if status in ("done", "stalled"):
        _STATUS_CACHE[path] = (mtime, status)
    return (status, age)
