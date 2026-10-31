"""Closed failure taxonomy and terminal-state result formatter (IMP-0449).

Every tool result is SUCCESS with an id, or FAILED with an id, a class, and a
reason. Open-ended prose is unrepresentable: TerminalResult rejects empty
FAILED reasons and SUCCESS-with-reason, and the JSON shape forbids extra
keys such as body/prose/message.

Unclassifiable input maps to FAILED UNCLASSIFIED. It never becomes SUCCESS
and never returns empty.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional

SEVERED_STREAM = "severed-stream"
ADAPTER_EXIT_N = "adapter-exit-n"
WIN_ARG_LIMIT = "win-arg-limit"
TIMEOUT = "timeout"
SCHEMA_INVALID = "schema-invalid"
PARTIAL_ARTIFACT = "partial-artifact"
DEGRADED = "degraded"
BLOCKED = "blocked"
UNCLASSIFIED = "UNCLASSIFIED"

TAXONOMY_CLASSES: tuple[str, ...] = (
    SEVERED_STREAM,
    ADAPTER_EXIT_N,
    WIN_ARG_LIMIT,
    TIMEOUT,
    SCHEMA_INVALID,
    PARTIAL_ARTIFACT,
    DEGRADED,
    BLOCKED,
)

_MISSING = object()

# Closed JSON shape for one formatter result. additionalProperties=false is
# the "prose is structurally impossible" gate: body/message/ok cannot appear.
TERMINAL_RESULT_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "oneOf": [
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["status", "id", "marker", "class"],
            "properties": {
                "status": {"const": "SUCCESS"},
                "id": {"type": "string", "minLength": 1},
                "marker": {"type": "string", "pattern": "^SUCCESS:"},
                "class": {"type": "null"},
            },
        },
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["status", "id", "marker", "reason", "class"],
            "properties": {
                "status": {"const": "FAILED"},
                "id": {"type": "string", "minLength": 1},
                "marker": {"type": "string", "pattern": "^FAILED:"},
                "reason": {"type": "string", "minLength": 1},
                "class": {
                    "type": "string",
                    "minLength": 1,
                    "enum": list(TAXONOMY_CLASSES) + [UNCLASSIFIED],
                },
            },
        },
    ],
}


class TaxonomyError(ValueError):
    """Raised when a TerminalResult would be an open or contradictory shape."""


@dataclass
class Observation:
    """Typed observation. Classify uses fields first, then text signatures."""

    text: str = ""
    winerror: Optional[int] = None
    timed_out: bool = False
    exit_code: Optional[int] = None
    schema_errors: int = 0
    artifact_present: Optional[bool] = None
    parseable: Optional[bool] = None
    artifact_bytes: Optional[int] = None
    progress_only: bool = False
    state: Optional[str] = None


@dataclass(frozen=True)
class TerminalResult:
    status: str
    id: str
    reason: Optional[str] = None
    class_: Optional[str] = None

    def __post_init__(self) -> None:
        status = (self.status or "").upper()
        if status not in {"SUCCESS", "FAILED"}:
            raise TaxonomyError(f"status must be SUCCESS or FAILED, got {self.status!r}")
        if not self.id:
            raise TaxonomyError("id is required")
        if status == "SUCCESS":
            if self.reason:
                raise TaxonomyError("SUCCESS must not carry a reason")
            if self.class_ is not None:
                raise TaxonomyError("SUCCESS class must be null")
        else:
            if not self.reason:
                raise TaxonomyError("FAILED requires a non-empty reason")
            if not self.class_:
                raise TaxonomyError("FAILED requires a class")

    @property
    def marker(self) -> str:
        if self.status == "SUCCESS":
            return f"SUCCESS:{self.id}"
        return f"FAILED:{self.id} {self.reason}"

    def to_json(self) -> dict[str, Any]:
        if self.status == "SUCCESS":
            return {
                "status": "SUCCESS",
                "id": self.id,
                "marker": self.marker,
                "class": None,
            }
        return {
            "status": "FAILED",
            "id": self.id,
            "marker": self.marker,
            "reason": self.reason,
            "class": self.class_,
        }


def result_to_json(result: TerminalResult) -> dict[str, Any]:
    return result.to_json()


def error_fingerprint(text: str, cls: str) -> str:
    norm = re.sub(r"\s+", " ", (text or "").strip().lower())
    payload = f"{cls}\n{norm}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _as_obs(raw: Any) -> Observation:
    if isinstance(raw, Observation):
        return raw
    if raw is None:
        return Observation(text="")
    if isinstance(raw, Mapping):
        text = raw.get("text")
        if text is None:
            text = raw.get("message")
        if text is None:
            text = raw.get("stderr")
        state = raw.get("state")
        return Observation(
            text="" if text is None else str(text),
            winerror=_maybe_int(raw.get("winerror")),
            timed_out=bool(raw.get("timed_out")),
            exit_code=_maybe_int(raw.get("exit_code")),
            schema_errors=int(raw.get("schema_errors") or 0),
            artifact_present=_maybe_bool(raw.get("artifact_present")),
            parseable=_maybe_bool(raw.get("parseable")),
            artifact_bytes=_maybe_int(raw.get("artifact_bytes")),
            progress_only=bool(raw.get("progress_only")),
            state=None if state is None else str(state),
        )
    if isinstance(raw, BaseException):
        return Observation(text=f"{type(raw).__name__}: {raw}")
    return Observation(text=str(raw))


def _maybe_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _maybe_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return None


def classify(raw: Any) -> str:
    """Map an observation to one closed class or UNCLASSIFIED.

    Never returns SUCCESS. Precedence is typed fields, then text signatures.
    """
    obs = _as_obs(raw)
    if obs.timed_out:
        return TIMEOUT
    if obs.schema_errors > 0 or obs.parseable is False:
        return SCHEMA_INVALID
    if obs.winerror == 206:
        return WIN_ARG_LIMIT
    state = (obs.state or "").strip().upper()
    if state == "BLOCKED":
        return BLOCKED
    if state == "DEGRADED":
        return DEGRADED
    if obs.artifact_present is True and obs.artifact_bytes == 0:
        return PARTIAL_ARTIFACT
    if obs.exit_code == 0 and (obs.artifact_present is False or obs.progress_only):
        return SEVERED_STREAM
    if obs.exit_code is not None and obs.exit_code != 0:
        return ADAPTER_EXIT_N
    return _classify_text(obs.text)


def _classify_text(text: str) -> str:
    t = text or ""
    if re.search(
        r"os error 206|winerror\s*=?\s*206|payload_len=|command line is too long",
        t,
        re.I,
    ):
        return WIN_ARG_LIMIT
    if re.search(r"\bTIMEOUT\b|timed[_ ]out", t, re.I):
        return TIMEOUT
    if re.search(r"schema-invalid|schema_errors", t, re.I):
        return SCHEMA_INVALID
    if re.search(r"zero-byte|partial-artifact|artifact_bytes\s*=\s*0", t, re.I):
        return PARTIAL_ARTIFACT
    if re.search(r"severed-stream|progress stream", t, re.I):
        return SEVERED_STREAM
    if re.search(
        r"current_launch_exit_code\"?\s*:\s*[1-9]|adapter-exit",
        t,
        re.I,
    ):
        return ADAPTER_EXIT_N
    # BLOCKED is case-sensitive so "blocking foreground" does not match.
    if re.search(r"self-declared:BLOCKED|\bBLOCKED\b", t):
        return BLOCKED
    if re.search(r"\bdegraded\b|contract check degraded", t, re.I):
        return DEGRADED
    return UNCLASSIFIED


def format_success(result_id: str) -> TerminalResult:
    return TerminalResult(status="SUCCESS", id=result_id, reason=None, class_=None)


def format_failure(result_id: str, raw: Any) -> TerminalResult:
    cls = classify(raw)
    obs = _as_obs(raw)
    snippet = (obs.text or "").strip()
    if cls == UNCLASSIFIED:
        reason = f"UNCLASSIFIED: {snippet or 'unclassifiable observation'}"
    elif snippet:
        reason = f"{cls}: {snippet[:240]}"
    else:
        reason = cls
    return TerminalResult(status="FAILED", id=result_id, reason=reason, class_=cls)


def format_tool_result(
    result_id: str,
    *,
    observation: Any = _MISSING,
    ok: bool = False,
) -> TerminalResult:
    """Emit an explicit terminal state. Missing observation is empty-return."""
    if ok:
        return format_success(result_id)
    if observation is _MISSING:
        return TerminalResult(
            status="FAILED",
            id=result_id,
            reason="empty-return: format_tool_result called with no observation",
            class_=UNCLASSIFIED,
        )
    return format_failure(result_id, observation)


def dumps(result: TerminalResult) -> str:
    return json.dumps(result.to_json(), sort_keys=True)
