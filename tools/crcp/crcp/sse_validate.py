"""Classify ChatGPT SSE responses by terminal stream evidence.

An HTTP success only establishes that the server accepted the request.  A turn
is successful when the response stream also contains an explicit terminal
marker and contains no explicit error.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

SUCCESS = "SUCCESS"
UNCERTAIN_ACCEPTED = "UNCERTAIN_ACCEPTED"
FAILED = "FAILED"

_FINISHED_STATUSES = {"finished", "finished_successfully", "complete", "completed"}
_ERROR_STATUSES = {"error", "failed", "failed_error", "cancelled", "canceled"}


def _sse_payloads(text: str) -> list[Any]:
    """Decode SSE data fields while retaining malformed payloads as strings."""
    payloads: list[Any] = []
    data_lines: list[str] = []
    event_name: str | None = None

    def flush() -> None:
        nonlocal data_lines, event_name
        if not data_lines and event_name is None:
            return
        payload = "\n".join(data_lines).strip()
        if payload == "[DONE]":
            item: Any = {"done": True}
        elif payload:
            try:
                item = json.loads(payload)
            except (TypeError, ValueError):
                item = {"raw": payload[:200], "malformed": True}
        else:
            item = {}
        if event_name:
            if isinstance(item, dict):
                item = dict(item)
                item.setdefault("event", event_name)
            else:
                item = {"event": event_name, "data": item}
        payloads.append(item)
        data_lines = []
        event_name = None

    for line in text.splitlines():
        if not line.strip():
            flush()
        elif line.startswith("data:"):
            value = line[5:]
            value = value[1:] if value.startswith(" ") else value
            # Be tolerant of captures that dropped the blank SSE record
            # separator.  Preserve real multi-line data when the accumulated
            # payload is not independently decodable yet.
            if data_lines:
                prior = "\n".join(data_lines).strip()
                try:
                    json.loads(prior)
                    prior_complete = True
                except (TypeError, ValueError):
                    prior_complete = prior == "[DONE]"
                if prior_complete:
                    flush()
            data_lines.append(value)
        elif line.startswith("event:"):
            event_name = line[6:].strip()
    flush()

    if not payloads and text.strip():
        stripped = text.strip()
        if stripped == "[DONE]":
            payloads.append({"done": True})
        else:
            try:
                payloads.append(json.loads(stripped))
            except (TypeError, ValueError):
                payloads.append({"raw": stripped[:200], "malformed": True})
    return payloads


def _normalise_events(text_or_events: Any) -> list[Any]:
    if isinstance(text_or_events, str):
        return _sse_payloads(text_or_events)
    if isinstance(text_or_events, Mapping):
        return [text_or_events]
    if isinstance(text_or_events, Iterable):
        events: list[Any] = []
        for item in text_or_events:
            events.extend(_sse_payloads(item) if isinstance(item, str) else [item])
        return events
    return [text_or_events]


def _has_error(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_lower = str(key).lower()
            if key_lower in {"error", "errors"} and child not in (None, False, "", [], {}):
                return True
            if key_lower in {"event", "type", "status"}:
                marker = str(child).lower()
                if marker in _ERROR_STATUSES or marker.endswith("_error"):
                    return True
            if _has_error(child):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(_has_error(item) for item in value)
    return False


def _is_finished_assistant(value: Any) -> bool:
    if isinstance(value, Mapping):
        author = value.get("author")
        role = author.get("role") if isinstance(author, Mapping) else value.get("role")
        status = str(value.get("status", "")).lower()
        if role == "assistant" and (
            status in _FINISHED_STATUSES or value.get("end_turn") is True
        ):
            return True
        return any(_is_finished_assistant(child) for child in value.values())
    if isinstance(value, (list, tuple)):
        return any(_is_finished_assistant(item) for item in value)
    return False


def classify_sse_stream(text_or_events: Any) -> str:
    """Return SUCCESS, UNCERTAIN_ACCEPTED, or FAILED for an SSE response.

    Explicit errors take precedence over terminal markers.  Missing, truncated,
    empty, or malformed responses remain uncertain because HTTP acceptance is
    not proof that the assistant turn completed.
    """
    events = _normalise_events(text_or_events)
    if any(_has_error(event) for event in events):
        return FAILED
    terminal = any(
        (isinstance(event, Mapping) and event.get("done") is True)
        or _is_finished_assistant(event)
        for event in events
    )
    return SUCCESS if terminal else UNCERTAIN_ACCEPTED
