"""Increment 1 NDJSON event contract: versioned envelope, writer, tailing reader.

Three pieces, in dependency order:

* **The envelope** (:class:`DbxEvent`, :data:`REQUIRED_FIELDS`) - a versioned,
  frozen record of the 30 contract fields plus an ``extra`` bag that preserves
  unknown keys verbatim, so a producer running a newer schema never has its
  fields silently dropped by an older reader.
* **The writer** (:func:`dump_event`) - emits exactly ONE NDJSON line, with a
  second redaction pass over every emitted string.
* **The monitor-adapter mapping** (:func:`normalize`) - the seam
  ``databricks_source.DatabricksSource`` probes for, translating one envelope
  into that adapter's fold vocabulary. Without it a *valid* envelope reached the
  fold under its native field names, matched none of them, and was silently
  dropped while the board still read reachable / fresh / idle.
* **The reader** (:class:`EventReader`) - incrementally tails an append-only
  NDJSON file in bounded memory and yields validated events, tolerating a torn
  final line, malformed JSON, duplicate ``event_id``, non-monotonic
  ``sequence``, unknown fields, oversize records and invalid UTF-8. It counts
  every anomaly and **never raises on data**.

Design rules this module is built to, each of which has a paired test:

1. **A partial final line is buffered, never yielded and never dropped.** The
   reader only ever emits newline-terminated records, so a writer that flushed
   half a line costs latency, not events.
2. **Anomalies are counted, never fatal.** A malformed line, an oversize record
   or a duplicate id increments a counter and the stream continues. A reader
   that dies on one bad byte is a monitor that goes blind exactly when the
   producer is misbehaving.
3. **Out-of-order is ACCEPTED but FLAGGED.** Dropping a late event loses data;
   silently accepting it hides a writer defect. Both are wrong, so the event is
   yielded *and* ``monotonic_violations`` is incremented.
4. **Memory is bounded by configuration, not by file length.** The partial-line
   buffer, the duplicate-suppression ring and the per-unit high-water map all
   carry explicit caps, so a 10 GB feed costs the same resident state as a 10 KB
   one.
5. **Redaction happens BEFORE the byte is written**, and tool arguments are
   emitted only as a digest - never as raw values.
"""

import hashlib
import json
import math
import os
import re
from collections import OrderedDict, deque
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from .redact import redact as _redact_text

__all__ = [
    "DEFAULT_CHUNK_BYTES",
    "DEFAULT_MAX_RECORD_BYTES",
    "DEFAULT_RECENT_EVENT_IDS",
    "DEFAULT_MAX_TRACKED_UNITS",
    "LIFECYCLE_STATES",
    "LIVENESS_STATES",
    "NULLABLE_FIELDS",
    "PROGRESS_KINDS",
    "REQUIRED_FIELDS",
    "SCHEMA_VERSION",
    "SENTINEL_STATES",
    "DbxEvent",
    "EventReader",
    "EventValidationError",
    "ReaderStats",
    "digest_tool_args",
    "dump_event",
    "load_event",
    "new_event",
    "normalize",
    "redact",
]

# --------------------------------------------------------------------------
# Contract constants
# --------------------------------------------------------------------------

SCHEMA_VERSION = 1

#: The 30 envelope fields, in wire order. Every one is REQUIRED to be PRESENT;
#: the subset in :data:`NULLABLE_FIELDS` may carry ``null``. Presence is
#: enforced rather than defaulted, because a silently-defaulted field is
#: indistinguishable from a measured one.
REQUIRED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "program_run_id",
    "databricks_run_id",
    "batch_id",
    "logical_unit_id",
    "attempt_id",
    "agent_id",
    "parent_agent_id",
    "sequence",
    "event_id",
    "emitted_at_utc",
    "observed_at_utc",
    "lifecycle_state",
    "liveness_state",
    "progress_kind",
    "message_summary",
    "tool_name",
    "tool_arg_digest",
    "artifact_uri",
    "artifact_bytes",
    "artifact_sha256",
    "sentinel_state",
    "retry_count",
    "error_class",
    "lease_expiry",
    "heartbeat_age_s",
    "source_node",
    "model",
    "reasoning_effort",
    "input_bundle_hash",
)

_REQUIRED_SET = frozenset(REQUIRED_FIELDS)

#: Fields that legitimately carry ``null``. Everything else must be non-null.
#: ``databricks_run_id`` is nullable because a unit exists locally before the
#: job is submitted; ``parent_agent_id`` is null at the root of the agent tree.
NULLABLE_FIELDS = frozenset(
    {
        "databricks_run_id",
        "parent_agent_id",
        "message_summary",
        "tool_name",
        "tool_arg_digest",
        "artifact_uri",
        "artifact_bytes",
        "artifact_sha256",
        "error_class",
        "lease_expiry",
        "heartbeat_age_s",
        "model",
        "reasoning_effort",
        "input_bundle_hash",
    }
)

#: Coarse durable-execution state of the unit (the state table's vocabulary).
LIFECYCLE_STATES = frozenset(
    {
        "PENDING",
        "ADMITTED",
        "STARTING",
        "RUNNING",
        "QUIET",
        "STALLED",
        "RETRYABLE",
        "QUARANTINED",
        "FAILED",
        "SEVERED",
        "CANCELLED",
        "DONE",
    }
)

#: Per-unit liveness as the monitor renders it.
LIVENESS_STATES = frozenset(
    {
        "STARTING",
        "THINKING",
        "WORKING",
        "QUIET",
        "STALLED",
        "FAILED",
        "SEVERED",
        "DONE",
    }
)

#: What KIND of progress this event reports.
PROGRESS_KINDS = frozenset(
    {
        "lifecycle",
        "reasoning",
        "message",
        "tool",
        "artifact",
        "error",
        "heartbeat",
        "terminal",
    }
)

#: ``ABSENT`` and ``UNKNOWN`` are deliberately distinct: "the producer emitted
#: no sentinel" and "the check could not be run" are different facts, and
#: collapsing them turns a missing gate into a passing one.
SENTINEL_STATES = frozenset({"PASS", "FAIL", "UNKNOWN", "ABSENT"})

_INT_FIELDS = frozenset(
    {"schema_version", "attempt_id", "sequence", "artifact_bytes", "retry_count"}
)
_FLOAT_FIELDS = frozenset(
    {"emitted_at_utc", "observed_at_utc", "lease_expiry", "heartbeat_age_s"}
)
_ENUM_FIELDS: dict[str, frozenset[str]] = {
    "lifecycle_state": LIFECYCLE_STATES,
    "liveness_state": LIVENESS_STATES,
    "progress_kind": PROGRESS_KINDS,
    "sentinel_state": SENTINEL_STATES,
}

# Reader defaults. MAX_RECORD_BYTES matches the writer-side line cap so a record
# the writer would truncate is also a record the reader refuses to buffer.
DEFAULT_MAX_RECORD_BYTES = 262_144
DEFAULT_CHUNK_BYTES = 65_536
DEFAULT_RECENT_EVENT_IDS = 512
DEFAULT_MAX_TRACKED_UNITS = 4_096


class EventValidationError(ValueError):
    """A payload does not satisfy the envelope contract."""


# --------------------------------------------------------------------------
# Redaction
# --------------------------------------------------------------------------

_FAILCLOSED = "[REDACTED:redaction-failed]"

# Key NAMES whose value is dropped wholesale regardless of shape. Matched as a
# substring (not anchored) so ``access_token`` and ``client_secret`` are caught,
# and biased fail-closed: a mildly over-broad drop costs a monitor field, an
# under-broad one costs a credential.
_SECRET_KEY_RE = re.compile(
    r"(?i)(auth|token|secret|api[_\-]?key|password|passwd|passphrase"
    r"|cookie|bearer|credential|private[_\-]?key|dapi"
    r"|(?:^|[_\-.])keys?(?:$|[_\-.]))"
)

# Databricks personal access tokens. Broader than the documented 32-hex body so
# a format change still masks.
_DAPI_RE = re.compile(r"dapi[A-Za-z0-9]{8,}")

# Only token-SHAPED strings are entropy candidates: no whitespace, no prose
# punctuation. This is what keeps an English sentence out of the entropy rule
# regardless of how varied its letters are.
_TOKENISH_RE = re.compile(r"[A-Za-z0-9+/=_\-.:]{24,}")

#: Entropy rule. 4.5 bits/char is chosen to sit ABOVE hex and BELOW base64:
#: hex maxes out at log2(16) = 4.0 bits/char, so content-addressed sha256/sha1
#: digests (measured 3.63-4.00) pass through untouched, while a real base64
#: credential (measured 5.10) is masked. Setting this at 4.0 would mask every
#: digest in the envelope; setting it at 5.5 would miss shorter tokens.
HIGH_ENTROPY_BITS = 4.5
HIGH_ENTROPY_MIN_LEN = 24

#: Envelope fields whose whole PURPOSE is to carry an opaque identifier. They
#: are exempt from the ENTROPY rule only - pattern masking and key-name drops
#: still apply to them, so a credential pasted into ``event_id`` is still
#: caught. Without this exemption a base64 ``input_bundle_hash`` would be
#: redacted as a false positive on every single event.
_ENTROPY_EXEMPT_FIELDS = frozenset(
    {
        "event_id",
        "program_run_id",
        "databricks_run_id",
        "batch_id",
        "logical_unit_id",
        "agent_id",
        "parent_agent_id",
        "artifact_sha256",
        "input_bundle_hash",
        "tool_arg_digest",
    }
)

#: Depth cap for the recursive walk, so a hostile deeply-nested payload cannot
#: exhaust the stack.
MAX_REDACT_DEPTH = 32


def _shannon_bits(text: str) -> float:
    """Shannon entropy of ``text`` in bits per character."""
    if not text:
        return 0.0
    counts: dict[str, int] = {}
    for char in text:
        counts[char] = counts.get(char, 0) + 1
    length = len(text)
    return -sum((n / length) * math.log2(n / length) for n in counts.values())


def _is_high_entropy(text: str) -> bool:
    if len(text) < HIGH_ENTROPY_MIN_LEN:
        return False
    if not _TOKENISH_RE.fullmatch(text):
        return False
    return _shannon_bits(text) >= HIGH_ENTROPY_BITS


def _redact_str(text: str, *, entropy_exempt: bool) -> str:
    """Mask one string. Fail-closed: on any error the raw text is NOT returned."""
    try:
        masked, _ = _redact_text(text)
        masked = _DAPI_RE.sub("[REDACTED:dapi]", masked)
    except Exception:
        return _FAILCLOSED
    try:
        if not entropy_exempt and _is_high_entropy(masked):
            return "[REDACTED:high-entropy]"
    except Exception:
        return _FAILCLOSED
    return masked


def _redact_value(value: Any, exempt: frozenset[str], depth: int) -> Any:
    if depth > MAX_REDACT_DEPTH:
        return "[REDACTED:max-depth]"
    if isinstance(value, str):
        return _redact_str(value, entropy_exempt=False)
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for key, item in value.items():
            name = str(key)
            try:
                if _SECRET_KEY_RE.search(name):
                    out[key] = f"[DROPPED:{name}]"
                    continue
            except Exception:
                out[key] = _FAILCLOSED
                continue
            if isinstance(item, str) and name in exempt:
                out[key] = _redact_str(item, entropy_exempt=True)
            else:
                out[key] = _redact_value(item, exempt, depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [_redact_value(item, exempt, depth + 1) for item in value]
    # Unknown type: stringify, then redact. Never pass an opaque object through.
    try:
        return _redact_str(str(value), entropy_exempt=False)
    except Exception:
        return _FAILCLOSED


def redact(obj: Any, *, entropy_exempt_keys: frozenset[str] = frozenset()) -> Any:
    """Recursively strip secret-shaped values from ``obj``.

    Four ladders, applied to every string at every depth:

    1. **Key-name drop** - a key naming a token/key/password/secret/bearer/auth
       credential has its whole value replaced with ``[DROPPED:<key>]``, subtree
       included. The key NAME survives so the audit trail shows what was
       dropped.
    2. **Pattern masking** - the shared :mod:`monitorcore.redact` pattern set
       (``sk-``, ``ghp_``, ``AKIA``, ``xox*``, Bearer JWTs, PEM private-key
       blocks, home paths, ...).
    3. **``dapi`` prefix** - Databricks personal access tokens.
    4. **High entropy** - token-shaped strings at or above
       :data:`HIGH_ENTROPY_BITS`.

    ``entropy_exempt_keys`` suppresses rule 4 *only* for the named keys; rules
    1-3 always apply. Pure and fail-closed - a raising pattern degrades to a
    masked marker and the raw value is never returned.
    """
    return _redact_value(obj, entropy_exempt_keys, 0)


def digest_tool_args(obj: Any) -> str:
    """``sha256:``-prefixed digest of the REDACTED, canonicalised arguments.

    The digest is taken over the redacted form, so it is stable, comparable
    across calls, and carries no recoverable secret material even under
    brute-force. This is the ONLY representation of tool arguments that reaches
    the wire - raw values are never emitted.
    """
    scrubbed = redact(obj)
    try:
        canonical = json.dumps(
            scrubbed,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=str,
        )
    except Exception:
        canonical = repr(scrubbed)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# The envelope
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DbxEvent:
    """One versioned telemetry event.

    ``extra`` holds every key the current schema does not name, preserved
    verbatim so a newer producer's fields survive an older reader untouched
    (forward compatibility). Not hashable: ``extra`` is a mutable mapping.
    """

    schema_version: int
    program_run_id: str
    databricks_run_id: str | None
    batch_id: str
    logical_unit_id: str
    attempt_id: int
    agent_id: str
    parent_agent_id: str | None
    sequence: int
    event_id: str
    emitted_at_utc: float
    observed_at_utc: float
    lifecycle_state: str
    liveness_state: str
    progress_kind: str
    message_summary: str | None
    tool_name: str | None
    tool_arg_digest: str | None
    artifact_uri: str | None
    artifact_bytes: int | None
    artifact_sha256: str | None
    sentinel_state: str
    retry_count: int
    error_class: str | None
    lease_expiry: float | None
    heartbeat_age_s: float | None
    source_node: str
    model: str | None
    reasoning_effort: str | None
    input_bundle_hash: str | None
    extra: dict[str, Any] = field(default_factory=dict)


def _coerce(name: str, value: Any) -> Any:
    """Validate + normalise one field. Raises :class:`EventValidationError`."""
    if value is None:
        if name in NULLABLE_FIELDS:
            return None
        raise EventValidationError(f"field {name!r} may not be null")

    if name in _INT_FIELDS:
        # bool is a subclass of int; a boolean sequence number is a defect.
        if isinstance(value, bool) or not isinstance(value, int):
            raise EventValidationError(f"field {name!r} must be an integer")
        return value

    if name in _FLOAT_FIELDS:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise EventValidationError(f"field {name!r} must be a number")
        return float(value)

    if not isinstance(value, str):
        raise EventValidationError(f"field {name!r} must be a string")

    allowed = _ENUM_FIELDS.get(name)
    if allowed is not None and value not in allowed:
        raise EventValidationError(f"field {name!r} has unknown value {value!r}")
    return value


def new_event(
    *,
    program_run_id: str,
    batch_id: str,
    logical_unit_id: str,
    agent_id: str,
    sequence: int,
    event_id: str,
    emitted_at_utc: float,
    observed_at_utc: float,
    lifecycle_state: str,
    liveness_state: str,
    progress_kind: str,
    source_node: str,
    schema_version: int = SCHEMA_VERSION,
    databricks_run_id: str | None = None,
    attempt_id: int = 1,
    parent_agent_id: str | None = None,
    message_summary: str | None = None,
    tool_name: str | None = None,
    tool_args: Any = None,
    tool_arg_digest: str | None = None,
    artifact_uri: str | None = None,
    artifact_bytes: int | None = None,
    artifact_sha256: str | None = None,
    sentinel_state: str = "ABSENT",
    retry_count: int = 0,
    error_class: str | None = None,
    lease_expiry: float | None = None,
    heartbeat_age_s: float | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    input_bundle_hash: str | None = None,
    extra: dict[str, Any] | None = None,
) -> DbxEvent:
    """Build a validated :class:`DbxEvent`.

    ``tool_args`` accepts the RAW argument object and is never stored: it is
    redacted and reduced to ``tool_arg_digest`` here, at construction, so no
    caller can accidentally place raw arguments on the wire.
    """
    if tool_args is not None:
        tool_arg_digest = digest_tool_args(tool_args)

    values = {
        "schema_version": schema_version,
        "program_run_id": program_run_id,
        "databricks_run_id": databricks_run_id,
        "batch_id": batch_id,
        "logical_unit_id": logical_unit_id,
        "attempt_id": attempt_id,
        "agent_id": agent_id,
        "parent_agent_id": parent_agent_id,
        "sequence": sequence,
        "event_id": event_id,
        "emitted_at_utc": emitted_at_utc,
        "observed_at_utc": observed_at_utc,
        "lifecycle_state": lifecycle_state,
        "liveness_state": liveness_state,
        "progress_kind": progress_kind,
        "message_summary": message_summary,
        "tool_name": tool_name,
        "tool_arg_digest": tool_arg_digest,
        "artifact_uri": artifact_uri,
        "artifact_bytes": artifact_bytes,
        "artifact_sha256": artifact_sha256,
        "sentinel_state": sentinel_state,
        "retry_count": retry_count,
        "error_class": error_class,
        "lease_expiry": lease_expiry,
        "heartbeat_age_s": heartbeat_age_s,
        "source_node": source_node,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "input_bundle_hash": input_bundle_hash,
    }
    if values["schema_version"] > SCHEMA_VERSION:
        raise EventValidationError(
            f"unsupported schema_version {values['schema_version']}"
        )
    coerced = {name: _coerce(name, values[name]) for name in REQUIRED_FIELDS}
    return DbxEvent(**coerced, extra=dict(extra or {}))


def load_event(payload: dict[str, Any]) -> DbxEvent:
    """Validate a decoded JSON object into a :class:`DbxEvent`.

    Unknown keys are preserved into ``extra`` rather than dropped. A version
    ABOVE :data:`SCHEMA_VERSION` is refused loudly - this reader cannot honestly
    claim to understand a schema it predates.
    """
    if not isinstance(payload, dict):
        raise EventValidationError("payload must be a JSON object")

    version = payload.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise EventValidationError("schema_version must be an integer")
    if version > SCHEMA_VERSION:
        raise EventValidationError(
            f"unsupported schema_version {version} > {SCHEMA_VERSION}"
        )

    coerced: dict[str, Any] = {}
    for name in REQUIRED_FIELDS:
        if name not in payload:
            raise EventValidationError(f"missing required field: {name}")
        coerced[name] = _coerce(name, payload[name])

    extra = {k: v for k, v in payload.items() if k not in _REQUIRED_SET}
    return DbxEvent(**coerced, extra=extra)


def dump_event(event: DbxEvent) -> str:
    """Serialise to exactly ONE NDJSON line (no trailing newline).

    Two guarantees:

    * **One line.** ``ensure_ascii=True`` escapes every non-ASCII codepoint, so
      neither ``\\n``/``\\r`` nor the U+2028/U+2029 line separators can survive
      as raw characters in the output.
    * **Redacted.** Every emitted string is re-scrubbed here - the belt to the
      producer's braces. Redaction is deliberately LOSSY: a value carrying a
      secret or a home path does NOT round-trip, by design.

    Required fields are written last, so a hand-built ``extra`` cannot shadow or
    spoof a contract field.
    """
    payload: dict[str, Any] = dict(event.extra)
    for name in REQUIRED_FIELDS:
        payload[name] = getattr(event, name)

    scrubbed = redact(payload, entropy_exempt_keys=_ENTROPY_EXEMPT_FIELDS)
    return json.dumps(
        scrubbed,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )


# --------------------------------------------------------------------------
# The monitor-adapter mapping
# --------------------------------------------------------------------------

#: ``lifecycle_state`` values that ARE a state transition, mapped onto the
#: ``databricks_source`` fold vocabulary. Only these six transitions exist on the
#: adapter side; the executing states (``RUNNING`` / ``QUIET`` / ``STALLED``) are
#: NOT transitions and fall through to :data:`_KIND_BY_PROGRESS`.
_KIND_BY_LIFECYCLE: dict[str, str] = {
    "PENDING": "queued",
    "ADMITTED": "queued",
    "STARTING": "start",
    "RETRYABLE": "retry",
    "QUARANTINED": "error",
    "FAILED": "error",
    "SEVERED": "error",
    "CANCELLED": "cancel",
    "DONE": "done",
}

#: ``progress_kind`` → fold kind for an event that is pure in-flight motion.
#: ``lifecycle`` / ``reasoning`` / ``message`` / ``tool`` all collapse to ``event``
#: (they advance the last-arrival clock and nothing more) — see the ``normalize``
#: docstring for why ``tool`` deliberately does NOT become ``tool_start``.
_KIND_BY_PROGRESS: dict[str, str] = {
    "heartbeat": "heartbeat",
    "artifact": "artifact",
    "error": "error",
    "terminal": "done",
}


def normalize(rec: dict[str, Any]) -> dict[str, Any] | None:
    """Map ONE v1 envelope onto the ``databricks_source`` fold vocabulary.

    This is the adapter seam ``DatabricksSource._normalize`` probes for. Without it
    a *valid* envelope reached the fold under its native field names, matched none
    of them, and was dropped for having no ``unit_id`` — one ``events_seen`` and
    zero units, published as a reachable, non-stale, IDLE source with no error.

    Returns ``None`` for anything that is not a v1 envelope (detected by the two
    discriminating keys ``schema_version`` + ``logical_unit_id``, neither of which
    exists in the adapter's own record shape), so a legacy record passes through
    untouched — the caller's contract is "a dict, or fall back to the input".

    **Deliberately lossy, in the safe direction.** The envelope carries no
    start/end discriminator for a tool call, no remote-task id, and no lease
    event, so ``progress_kind == "tool"`` becomes a plain ``event`` rather than a
    ``tool_start``. Synthesising ``tool_active=True`` from a signal that can never
    say the call ENDED would pin the unit ``TOOL_ACTIVE`` forever and make it
    permanently ineligible for ``STALLED`` — a monitor that goes blind on exactly
    the unit that needs attention. ``started_ts`` likewise comes only from a real
    ``STARTING`` event: re-deriving it from every ``RUNNING`` record would keep
    resetting the starting-grace clock.
    """
    if not isinstance(rec, dict):
        return None
    if "schema_version" not in rec or "logical_unit_id" not in rec:
        return None
    unit_id = str(rec.get("logical_unit_id") or "")
    if not unit_id:
        return None

    lifecycle = str(rec.get("lifecycle_state") or "")
    progress = str(rec.get("progress_kind") or "")
    kind = _KIND_BY_LIFECYCLE.get(lifecycle) or _KIND_BY_PROGRESS.get(progress, "event")

    out: dict[str, Any] = {
        "kind": kind,
        "unit_id": unit_id,
        "run_id": str(rec.get("databricks_run_id") or ""),
        "ts": _as_float(rec.get("observed_at_utc")),
    }
    if kind == "start":
        # Two distinct PROGRAM runs claiming one databricks run id is the collision
        # the adapter looks for; ``attempt_id`` is deliberately excluded, because a
        # retry inside one program is not a second claimant.
        out["attempt_token"] = str(rec.get("program_run_id") or "")
    elif kind == "done":
        out["status"] = "SUCCESS" if lifecycle == "DONE" else "TERMINATED"
    elif kind == "error":
        out["message"] = str(rec.get("error_class") or lifecycle or "error")
    elif kind == "artifact":
        out["bytes"] = int(rec.get("artifact_bytes") or 0)
    return out


def _as_float(value: Any) -> float:
    """``value`` as a float, or ``0.0`` when it is not numeric (never raises)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


# --------------------------------------------------------------------------
# The reader
# --------------------------------------------------------------------------


@dataclass
class ReaderStats:
    """Anomaly counters. Every field is a measurement, never an estimate."""

    accepted: int = 0
    lines_seen: int = 0
    bytes_read: int = 0
    parse_errors: int = 0
    invalid: int = 0
    duplicates: int = 0
    monotonic_violations: int = 0
    oversize: int = 0
    io_errors: int = 0
    rotations: int = 0


class EventReader:
    """Incrementally tail an append-only NDJSON file in bounded memory.

    Call :meth:`read_new` repeatedly; each call resumes at the byte offset the
    previous one reached and yields only events completed since. Bounded state:

    * ``max_record_bytes`` caps the partial-line buffer **hard** - the buffer is
      never extended past the cap, so ``buffer_high_water <= max_buffer_bytes``
      holds by construction rather than by observation.
    * ``recent_event_ids`` caps the duplicate-suppression ring.
    * ``max_tracked_units`` caps the per-unit sequence high-water map (LRU).

    Documented limits, stated rather than left to be discovered:

    * A duplicate ``event_id`` reappearing MORE than ``recent_event_ids`` events
      after the original is NOT detected. The ring is a bounded-memory
      trade-off, not a global uniqueness proof.
    * Abandoning the :meth:`read_new` iterator mid-chunk discards that chunk's
      un-consumed events; the reader stays internally consistent but those
      events are not re-yielded. Consume the iterator fully.
    * An I/O failure yields nothing and increments ``stats.io_errors``. A failed
      read is a DETECTOR failure, not an absence of events - callers must
      surface it as unreachable rather than as a quiet feed.
    """

    def __init__(
        self,
        path: Any,
        *,
        max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES,
        chunk_bytes: int = DEFAULT_CHUNK_BYTES,
        recent_event_ids: int = DEFAULT_RECENT_EVENT_IDS,
        max_tracked_units: int = DEFAULT_MAX_TRACKED_UNITS,
    ) -> None:
        self._path = os.fspath(path)
        self._max_record_bytes = int(max_record_bytes)
        self._chunk_bytes = max(1, int(chunk_bytes))
        self._recent_event_ids = max(1, int(recent_event_ids))
        self._max_tracked_units = max(1, int(max_tracked_units))

        self.stats = ReaderStats()
        self._offset = 0
        self._partial = bytearray()
        self._skipping = False
        self._high_water = 0

        self._seen_ids: set[str] = set()
        self._seen_order: deque[str] = deque()
        self._high_seq: OrderedDict[tuple[str, int], int] = OrderedDict()
        self._violations: deque[str] = deque(maxlen=self._recent_event_ids)

    # -- introspection -----------------------------------------------------

    @property
    def path(self) -> str:
        return self._path

    @property
    def offset(self) -> int:
        """Byte offset of the last COMPLETE record consumed."""
        return self._offset

    @property
    def buffer_bytes(self) -> int:
        """Bytes currently held in the partial-line buffer."""
        return len(self._partial)

    @property
    def buffer_high_water(self) -> int:
        """Largest the partial-line buffer has ever been."""
        return self._high_water

    @property
    def max_buffer_bytes(self) -> int:
        """The explicit, hard cap on the partial-line buffer."""
        return self._max_record_bytes

    @property
    def max_tracked_units(self) -> int:
        return self._max_tracked_units

    @property
    def tracked_event_ids(self) -> int:
        return len(self._seen_ids)

    @property
    def tracked_units(self) -> int:
        return len(self._high_seq)

    @property
    def recent_monotonic_violations(self) -> tuple[str, ...]:
        """Event ids of the most recent sequence regressions (bounded)."""
        return tuple(self._violations)

    def high_water_sequence(self, unit_id: str, attempt_id: int) -> int | None:
        return self._high_seq.get((unit_id, attempt_id))

    # -- reading -----------------------------------------------------------

    def read_new(self) -> Iterator[DbxEvent]:
        """Yield every event completed since the previous call."""
        try:
            size = os.path.getsize(self._path)
        except OSError:
            self.stats.io_errors += 1
            return

        if size < self._offset:
            # Truncated or rotated: the file we were reading is gone. Restart
            # rather than seek past the end into permanent silence.
            self._offset = 0
            self._partial.clear()
            self._skipping = False
            self.stats.rotations += 1

        if size <= self._offset:
            return

        try:
            handle = open(self._path, "rb")
        except OSError:
            self.stats.io_errors += 1
            return

        try:
            handle.seek(self._offset)
            while True:
                chunk = handle.read(self._chunk_bytes)
                if not chunk:
                    return
                self._offset += len(chunk)
                self.stats.bytes_read += len(chunk)
                yield from self._feed(chunk)
        finally:
            handle.close()

    def _feed(self, chunk: bytes) -> Iterator[DbxEvent]:
        start = 0
        size = len(chunk)
        while start < size:
            newline = chunk.find(b"\n", start)
            if newline == -1:
                self._buffer(chunk[start:])
                return

            line = chunk[start:newline]
            start = newline + 1

            if self._skipping:
                # Tail of an oversize record: discard it and resync HERE, at the
                # first record boundary after the offending line.
                self._skipping = False
                self._partial.clear()
                continue

            if self._partial:
                if len(self._partial) + len(line) > self._max_record_bytes:
                    self.stats.oversize += 1
                    self._partial.clear()
                    continue
                line = bytes(self._partial) + line
                self._partial.clear()

            event = self._handle_line(line)
            if event is not None:
                yield event

    def _buffer(self, rest: bytes) -> None:
        """Hold an incomplete trailing line for the next read."""
        if self._skipping:
            return
        if len(self._partial) + len(rest) > self._max_record_bytes:
            # Refuse to grow past the cap. The record is abandoned and we skip
            # to the next newline, so one giant line cannot wedge the reader or
            # blow the memory ceiling.
            self.stats.oversize += 1
            self._partial.clear()
            self._skipping = True
            return
        self._partial.extend(rest)
        if len(self._partial) > self._high_water:
            self._high_water = len(self._partial)

    def _handle_line(self, raw: bytes) -> DbxEvent | None:
        self.stats.lines_seen += 1
        stripped = raw.strip()
        if not stripped:
            return None

        if len(stripped) > self._max_record_bytes:
            self.stats.oversize += 1
            return None

        # Invalid UTF-8 is REPLACED, never raised: a mangled byte costs one
        # unreadable character, not the whole stream.
        text = stripped.decode("utf-8", errors="replace")

        try:
            payload = json.loads(text)
        except Exception:
            self.stats.parse_errors += 1
            return None
        if not isinstance(payload, dict):
            self.stats.parse_errors += 1
            return None

        try:
            event = load_event(payload)
        except Exception:
            self.stats.invalid += 1
            return None

        if event.event_id in self._seen_ids:
            self.stats.duplicates += 1
            return None
        self._remember(event.event_id)
        self._check_monotonic(event)

        self.stats.accepted += 1
        return event

    def _remember(self, event_id: str) -> None:
        self._seen_ids.add(event_id)
        self._seen_order.append(event_id)
        while len(self._seen_order) > self._recent_event_ids:
            self._seen_ids.discard(self._seen_order.popleft())

    def _check_monotonic(self, event: DbxEvent) -> None:
        """Flag a sequence regression WITHOUT rejecting the event.

        Sequence is monotonic only within one writer process, so the key is
        ``(logical_unit_id, attempt_id)``: a retried attempt legitimately
        restarts at 0 and must not be reported as a violation.
        """
        key = (event.logical_unit_id, event.attempt_id)
        high = self._high_seq.get(key)
        if high is not None and event.sequence <= high:
            self.stats.monotonic_violations += 1
            self._violations.append(event.event_id)
            return
        self._high_seq[key] = event.sequence
        self._high_seq.move_to_end(key)
        while len(self._high_seq) > self._max_tracked_units:
            self._high_seq.popitem(last=False)
