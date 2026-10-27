"""SSE parsing and terminal classification contract for CRCP writes."""

from __future__ import annotations

import json
from typing import Any


COMPLETE = "COMPLETE"
UNCERTAIN_ACCEPTED = "UNCERTAIN_ACCEPTED"
ERROR = "ERROR"


def parse_sse(text: str) -> list[dict[str, Any]]:
    """Parse SSE records, joining multiple data fields per the SSE format."""
    records: list[dict[str, Any]] = []
    event_name = "message"
    data_lines: list[str] = []

    def flush() -> None:
        nonlocal event_name, data_lines
        if not data_lines:
            event_name = "message"
            return
        raw = "\n".join(data_lines)
        record: dict[str, Any] = {"event": event_name, "raw": raw}
        if raw == "[DONE]":
            record["done"] = True
        else:
            try:
                record["data"] = json.loads(raw)
            except (TypeError, ValueError):
                record["malformed"] = True
        records.append(record)
        event_name = "message"
        data_lines = []

    for line in text.splitlines():
        if not line:
            flush()
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            event_name = line[6:].lstrip()
        elif line.startswith("data:"):
            value = line[5:]
            data_lines.append(value[1:] if value.startswith(" ") else value)
    flush()
    return records


def _contains_terminal(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("status") in {"finished_successfully", "complete", "completed"}:
            return True
        if value.get("end_turn") is True:
            return True
        return any(_contains_terminal(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_terminal(item) for item in value)
    return False


def classify_sse(status: int, text: str) -> str:
    """Classify transport failure, terminal completion, or uncertain acceptance."""
    if status < 200 or status >= 300:
        return ERROR
    records = parse_sse(text)
    if any(record.get("malformed") for record in records):
        return ERROR
    for record in records:
        if record.get("event") == "error":
            return ERROR
        data = record.get("data")
        if isinstance(data, dict) and (
            data.get("error") or data.get("type") == "error"
        ):
            return ERROR
    if any(
        record.get("done") or _contains_terminal(record.get("data"))
        for record in records
    ):
        return COMPLETE
    return UNCERTAIN_ACCEPTED
