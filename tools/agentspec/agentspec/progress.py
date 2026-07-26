"""A progress/status stream is NEVER a result — enforced at the TYPE level.

MEASURED FAILURES THIS EXISTS FOR:
* an agent's ENTIRE final answer was a receipt reading "started in the background as task-…",
  and its real finding then completed on disk and was discarded unread;
* another forwarded a raw ``[codex] …`` progress stream as its terminal result.

:func:`classify` returns :class:`ResultText` **or** :class:`ProgressLog`. Only a
:class:`ResultText` can be turned into a result by :func:`as_result`; handing it a
:class:`ProgressLog` raises. A caller cannot accidentally return the progress stream, because
the two are different types.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

BACKGROUND_PHRASES: tuple[str, ...] = (
    "check /codex:status",
    "check the job status",
    "launched in the background",
    "running in the background",
    "started in the background",
)
"""Sorted and closed. Each is a receipt phrase observed on a real fire-and-forget return."""

PROGRESS_LINE_RE = re.compile(r"^\s*\[[A-Za-z0-9_.-]+\]\s")
"""A bracketed-tag progress line, e.g. ``[codex] reading files``."""


class ProgressStreamRejected(ValueError):
    """Raised when a progress payload is asked to act as a result."""

    reason = "progress-stream"

    def __init__(self, marker: str) -> None:
        super().__init__(f"progress-stream: payload matched {marker!r} and is not a result")
        self.marker = marker


@dataclass(frozen=True, slots=True)
class ResultText:
    """A payload that may be returned as a work-unit result."""

    text: str


@dataclass(frozen=True, slots=True)
class ProgressLog:
    """A payload that is progress/status only. It can never become a result."""

    text: str
    marker: str


def classify(payload: str) -> ResultText | ProgressLog:
    """Split ``payload`` into the result variant or the progress variant."""
    lowered = payload.lower()
    for phrase in BACKGROUND_PHRASES:
        if phrase in lowered:
            return ProgressLog(text=payload, marker=phrase)
    lines = [line for line in payload.splitlines() if line.strip()]
    if lines and all(PROGRESS_LINE_RE.match(line) for line in lines):
        return ProgressLog(text=payload, marker="progress-line-only")
    return ResultText(text=payload)


def as_result(classified: ResultText | ProgressLog) -> str:
    """Unwrap a :class:`ResultText`. A :class:`ProgressLog` raises; anything else is a bug."""
    if isinstance(classified, ResultText):
        return classified.text
    if isinstance(classified, ProgressLog):
        raise ProgressStreamRejected(classified.marker)
    raise TypeError(f"expected ResultText or ProgressLog, got {type(classified).__name__}")


def looks_like_progress(payload: str) -> bool:
    """Boolean shorthand over :func:`classify`, for call sites that only need the flag."""
    return isinstance(classify(payload), ProgressLog)
