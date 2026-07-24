"""``dbx_completion`` — the **versioned** C1 completion contract for dispatched work units.

WHY A NEW MODULE AND NOT AN EDIT
--------------------------------
``hooks/_shared/completion.py`` is the historical gate. It is deliberately left alone: this
module does not compete with it and does not restate its semantics. C1 is a *versioned*
contract — :data:`CONTRACT_VERSION` is stamped onto every :class:`Verdict`, so a consumer
always knows which ruleset produced a verdict and two rulesets can coexist during migration.

Two measured defects in the predecessors motivated the pins below; both are cited so a future
reader does not "simplify" them back:

* ``hooks/_shared/completion.py:85-86`` opens the artifact in **text** mode and slices
  ``fh.read()[-600:]`` — that is 600 **CHARACTERS**, while line 49 calls it "bytes of the
  tail" and line 88 reports "last 600B". On non-ASCII output the two disagree (400 two-byte
  characters occupy 800 bytes), so the same artifact can pass one reading and fail the other.
  **This module pins the window in BYTES** (:data:`SENTINEL_TAIL_BYTES`) and never decodes
  before matching.
* ``scratch/codex-auth-research-fanout/completion_predicate.py:75-76`` and ``:80-81`` map any
  probe exception to ``False``, converting a *detector failure* into an asserted *absence*.
  **Here every probe failure surfaces as** :attr:`State.UNKNOWN` **with the exception
  preserved** in ``Verdict.signals['detector_error']`` — never ``FAILED``, never ``DONE``.

THE SEVEN GATES — all must hold for :attr:`State.DONE`
-----------------------------------------------------
1. the expected artifact exists;
2. its size is >= the configured minimum (:data:`DEFAULT_MIN_BYTES`);
3. it passes its **declared** format check, when one is declared;
4. the ``logical_unit_id`` it carries matches the expectation;
5. the ``input_bundle_hash`` it carries matches the expectation;
6. the completion sentinel appears within the last :data:`SENTINEL_TAIL_BYTES` **BYTES**;
7. no *later* failure or cancellation event supersedes it.

Gates 4-6 are settled by ONE parse of the byte-window: the C1 sentinel line carries the
identity and the provenance it attests (``UNIT-COMPLETE: <unit> bundle=<hash>``), so identity
cannot be asserted by a party other than the producer that wrote the completion marker.

HARD RULES (each one is paid for in a real incident)
---------------------------------------------------
* **Exit code zero alone is NEVER success.** Exit 0 with no artifact is :attr:`State.SEVERED`.
* **An agent's self-report is NEVER success.** It is recorded as a signal and grants nothing;
  ``signals['agent_self_report_trusted']`` is always ``False``.
* **A detector failure returns** :attr:`State.UNKNOWN` — never ``FAILED``, never ``DONE``.
* **Exceptions are not swallowed into a boolean.** A probe or format check that *raises* is a
  broken instrument (``UNKNOWN``); one that *returns False* has rendered a verdict (``FAILED``).

Stdlib-only, so this vendors cleanly into a plain-Python skill alongside the rest of
``monitorcore``.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

__all__ = [
    "CONTRACT_VERSION",
    "DEFAULT_MIN_BYTES",
    "SENTINEL_TAIL_BYTES",
    "ArtifactProbe",
    "Event",
    "EventKind",
    "Expectation",
    "OsArtifactProbe",
    "State",
    "Verdict",
    "classify",
]

#: The contract revision stamped onto every :class:`Verdict`. Bump this — do not mutate the
#: rules in place — when the gate's semantics change, so historical verdicts stay readable.
CONTRACT_VERSION = "C1"

#: Minimum artifact size. Below this the stream is treated as truncated.
DEFAULT_MIN_BYTES = 1024

#: The sentinel search window, **in BYTES**.
#:
#: This is deliberately a byte count and the artifact is matched **without decoding**. A
#: 600-*character* window is a DIFFERENT measurement on non-ASCII content: 400 two-byte
#: characters occupy 800 bytes, so a sentinel can sit inside a 600-character window while
#: sitting outside a 600-byte one. Changing this constant, or decoding before matching,
#: silently redefines "done" for every non-ASCII artifact in the fleet.
SENTINEL_TAIL_BYTES = 600

#: The C1 sentinel: the producer's completion marker, carrying the identity and the input
#: provenance it attests. Matched against RAW BYTES (see :data:`SENTINEL_TAIL_BYTES`).
SENTINEL_RE = re.compile(rb"UNIT-COMPLETE:\s*(?P<uid>\S+)\s+bundle=(?P<bundle>\S+)")


class State(StrEnum):
    """The six terminal classifications of the C1 contract (a ``str`` at runtime).

    ``DONE`` — all seven gates hold · ``FAILED`` — the unit reached a non-success terminal
    state (explicit failure, non-zero exit with no artifact, or a *malformed* artifact) ·
    ``SEVERED`` — the output stream never reached a complete terminal state (missing,
    truncated, or sentinel-less artifact) · ``CANCELLED`` — a cancellation event applies ·
    ``QUARANTINED`` — a complete artifact that is not attributable to this (unit, bundle):
    contamination, not failure · ``UNKNOWN`` — the detector failed or the signals are
    insufficient. ``UNKNOWN`` is a refusal to guess, never a soft ``FAILED``.
    """

    DONE = "DONE"
    FAILED = "FAILED"
    SEVERED = "SEVERED"
    UNKNOWN = "UNKNOWN"
    CANCELLED = "CANCELLED"
    QUARANTINED = "QUARANTINED"


class EventKind(StrEnum):
    """Lifecycle events that can supersede an artifact (gate 7).

    ``SUCCESS_CLAIM`` is accepted for the record and **never grants** ``DONE`` — it is an
    agent self-report, which this contract does not trust.
    """

    FAILURE = "failure"
    CANCELLATION = "cancellation"
    SUCCESS_CLAIM = "success_claim"


@dataclass(frozen=True)
class Event:
    """A timestamped lifecycle event. ``at`` is epoch seconds, comparable to artifact mtime."""

    kind: EventKind
    at: float
    detail: str = ""


@dataclass(frozen=True)
class Expectation:
    """What a completed unit must look like — the caller's side of the contract.

    ``format_check`` receives the artifact's RAW BYTES and returns ``True``/``False``. If it
    *raises*, that is a broken instrument and the verdict is ``UNKNOWN`` (see module docstring).
    """

    logical_unit_id: str
    input_bundle_hash: str
    artifact_path: str
    min_bytes: int = DEFAULT_MIN_BYTES
    sentinel_tail_bytes: int = SENTINEL_TAIL_BYTES
    format_check: Callable[[bytes], bool] | None = None


@dataclass(frozen=True)
class Verdict:
    """A typed terminal-state result, stamped with the contract revision that produced it."""

    state: State
    reason: str
    contract_version: str = CONTRACT_VERSION
    logical_unit_id: str | None = None
    input_bundle_hash: str | None = None
    artifact_bytes: int = 0
    signals: Mapping[str, object] = field(default_factory=dict)

    @property
    def is_done(self) -> bool:
        return self.state is State.DONE

    def __str__(self) -> str:
        return f"{self.state}[{self.contract_version}]: {self.reason}"


class ArtifactProbe(Protocol):
    """The filesystem seam. Every method may RAISE; a raise is a detector failure.

    Injecting a probe is how a caller tests the broken-instrument path without corrupting a
    real filesystem, and how a remote/DBFS artifact store plugs in.
    """

    def exists(self, path: str) -> bool: ...
    def size(self, path: str) -> int: ...
    def read_tail(self, path: str, nbytes: int) -> bytes: ...
    def mtime(self, path: str) -> float: ...


@runtime_checkable
class _SupportsReadAll(Protocol):
    """Optional probe capability: read the WHOLE artifact, not just the tail.

    ``read_all`` is deliberately NOT part of :class:`ArtifactProbe` — a remote/DBFS
    store or a test double need not implement it. When a probe DOES provide it, the
    declared format check parses the full payload; when it does not, gate 3 falls
    back to the already-read tail window.
    """

    def read_all(self, path: str) -> bytes: ...


class OsArtifactProbe:
    """The default local-filesystem probe. Deliberately does NOT catch anything."""

    def exists(self, path: str) -> bool:
        return os.path.exists(path)

    def size(self, path: str) -> int:
        return os.path.getsize(path)

    def read_tail(self, path: str, nbytes: int) -> bytes:
        """Return the last ``nbytes`` BYTES — binary mode, no decoding (gate 6's pin)."""
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            start = max(0, fh.tell() - nbytes)
            fh.seek(start, os.SEEK_SET)
            return fh.read()

    def read_all(self, path: str) -> bytes:
        with open(path, "rb") as fh:
            return fh.read()

    def mtime(self, path: str) -> float:
        return os.path.getmtime(path)


def _verdict(
    state: State,
    reason: str,
    signals: dict[str, object],
    *,
    uid: str | None = None,
    bundle: str | None = None,
    size: int = 0,
) -> Verdict:
    return Verdict(
        state=state,
        reason=reason,
        contract_version=CONTRACT_VERSION,
        logical_unit_id=uid,
        input_bundle_hash=bundle,
        artifact_bytes=size,
        signals=dict(signals),
    )


def _first(events: Sequence[Event], kind: EventKind) -> Event | None:
    for event in events:
        if event.kind is kind:
            return event
    return None


def classify(
    expectation: Expectation,
    *,
    exit_code: int | None = None,
    events: Sequence[Event] = (),
    agent_self_report: str | None = None,
    prior: Verdict | None = None,
    probe: ArtifactProbe | None = None,
) -> Verdict:
    """Apply the seven C1 gates and return a typed :class:`Verdict`.

    ``exit_code`` and ``agent_self_report`` are accepted for the record and can only ever
    *withhold* ``DONE``, never grant it.
    """
    active_probe: ArtifactProbe = probe if probe is not None else OsArtifactProbe()
    path = expectation.artifact_path
    tail_bytes = expectation.sentinel_tail_bytes

    signals: dict[str, object] = {
        "contract_version": CONTRACT_VERSION,
        "sentinel_window": tail_bytes,
        "sentinel_window_unit": "bytes",  # NOT characters — see module docstring
        "exit_code": exit_code,
        "agent_self_report_trusted": False,
    }
    if agent_self_report is not None:
        signals["agent_self_report_chars"] = len(agent_self_report)

    # ---- the detector's own health outranks everything it reports -----------------------
    # A raise here is a BROKEN INSTRUMENT. The exception is carried into the verdict rather
    # than collapsed to a boolean, so a caller can tell "I could not look" from "not there".
    try:
        exists = active_probe.exists(path)
        size = active_probe.size(path) if exists else 0
        tail = active_probe.read_tail(path, tail_bytes) if exists else b""
        durable_at = active_probe.mtime(path) if exists else None
    except Exception as exc:  # noqa: BLE001 - re-surfaced as UNKNOWN, never swallowed
        signals["detector_error"] = exc
        return _verdict(
            State.UNKNOWN,
            f"detector failure while probing the artifact: {exc!r}",
            signals,
        )

    signals["artifact_exists"] = exists

    # ---- gate 1: existence --------------------------------------------------------------
    if not exists:
        # Nothing to supersede, so any cancellation/failure event stands on its own.
        if _first(events, EventKind.CANCELLATION) is not None:
            return _verdict(
                State.CANCELLED, "cancelled before an artifact was produced", signals
            )
        if _first(events, EventKind.FAILURE) is not None:
            return _verdict(State.FAILED, "failure event and no artifact", signals)
        if exit_code is None:
            # The producer has NOT been observed to exit: the artifact may still be
            # flushing. A success claim does not change this (self-reports grant nothing).
            return _verdict(
                State.UNKNOWN,
                "no artifact and the producer has not been observed to exit; refusing to guess",
                signals,
            )
        if exit_code == 0:
            return _verdict(
                State.SEVERED,
                "severed-stream: exit 0 but no artifact — exit code alone is never success",
                signals,
            )
        return _verdict(State.FAILED, f"exit={exit_code} and no artifact", signals)

    # ---- gate 2: minimum size -----------------------------------------------------------
    if size < expectation.min_bytes:
        if _first(events, EventKind.CANCELLATION) is not None:
            return _verdict(
                State.CANCELLED, "cancelled with a partial artifact", signals, size=size
            )
        return _verdict(
            State.SEVERED,
            f"truncated: {size}B < {expectation.min_bytes}B",
            signals,
            size=size,
        )

    # ---- gate 3: the declared format check ----------------------------------------------
    if expectation.format_check is not None:
        try:
            payload = (
                active_probe.read_all(path)
                if isinstance(active_probe, _SupportsReadAll)
                else tail
            )
            parsed_ok = expectation.format_check(payload)
        except Exception as exc:  # noqa: BLE001 - a crashing checker is a broken instrument
            signals["detector_error"] = exc
            return _verdict(
                State.UNKNOWN,
                f"detector failure in the declared format check: {exc!r}",
                signals,
                size=size,
            )
        signals["format_check"] = bool(parsed_ok)
        if not parsed_ok:
            # It finished and produced garbage: a terminal non-success, not a severed stream.
            return _verdict(
                State.FAILED,
                "artifact failed its declared format check",
                signals,
                size=size,
            )

    # ---- gate 6: the sentinel, inside the BYTE window -----------------------------------
    match = SENTINEL_RE.search(tail)
    if match is None:
        if _first(events, EventKind.CANCELLATION) is not None:
            return _verdict(
                State.CANCELLED, "cancelled before the sentinel", signals, size=size
            )
        return _verdict(
            State.SEVERED,
            f"sentinel absent from the last {tail_bytes} BYTES "
            f"(a {tail_bytes}-character window is a different measurement on non-ASCII)",
            signals,
            size=size,
        )

    found_uid = match.group("uid").decode("utf-8", errors="replace")
    found_bundle = match.group("bundle").decode("utf-8", errors="replace")
    signals["sentinel_offset_from_end"] = len(tail) - match.start()

    # ---- gates 4+5: identity and input provenance ---------------------------------------
    if found_uid != expectation.logical_unit_id:
        return _verdict(
            State.QUARANTINED,
            f"artifact attests unit {found_uid!r}, expected {expectation.logical_unit_id!r}",
            signals,
            uid=found_uid,
            bundle=found_bundle,
            size=size,
        )
    if found_bundle != expectation.input_bundle_hash:
        return _verdict(
            State.QUARANTINED,
            f"artifact was produced from bundle {found_bundle!r}, "
            f"expected {expectation.input_bundle_hash!r} (stale inputs)",
            signals,
            uid=found_uid,
            bundle=found_bundle,
            size=size,
        )

    # ---- duplicate attempts: idempotent if they agree, contamination if they do not ------
    if prior is not None and prior.state is State.DONE:
        if prior.input_bundle_hash == found_bundle:
            signals["duplicate_attempt"] = True
        else:
            return _verdict(
                State.QUARANTINED,
                f"a prior DONE for this unit attests bundle {prior.input_bundle_hash!r}, "
                f"this attempt attests {found_bundle!r}",
                signals,
                uid=found_uid,
                bundle=found_bundle,
                size=size,
            )

    # ---- gate 7: no LATER failure or cancellation supersedes the artifact -----------------
    later = [e for e in events if durable_at is not None and e.at > durable_at]
    signals["later_events"] = len(later)
    cancelled = _first(later, EventKind.CANCELLATION)
    if cancelled is not None:
        signals["superseded_by"] = EventKind.CANCELLATION
        return _verdict(
            State.CANCELLED,
            "a cancellation event supersedes the artifact",
            signals,
            uid=found_uid,
            bundle=found_bundle,
            size=size,
        )
    failed = _first(later, EventKind.FAILURE)
    if failed is not None:
        signals["superseded_by"] = EventKind.FAILURE
        return _verdict(
            State.FAILED,
            "a later failure event supersedes the artifact",
            signals,
            uid=found_uid,
            bundle=found_bundle,
            size=size,
        )

    # ---- all seven gates hold ------------------------------------------------------------
    return _verdict(
        State.DONE,
        f"all 7 C1 gates hold ({size}B, sentinel within the last {tail_bytes} BYTES)",
        signals,
        uid=found_uid,
        bundle=found_bundle,
        size=size,
    )
