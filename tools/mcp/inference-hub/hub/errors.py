"""Tool-error taxonomy for inference-hub (BUILD-CONTRACT section 4).

Every failure the hub reports to a caller is a *tool execution* error, never a
protocol error: it carries ``{"error": {"class", "message", "retryable",
"endpoint", "model"}}``. Messages are passed through :func:`safe_message`, which
strips control characters and truncates, and by construction they never carry
prompt text or credential values - callers must only ever put identifiers,
status codes and short reasons into them.
"""

from __future__ import annotations

import re
from typing import Any

REGISTRY_UNAVAILABLE = "REGISTRY_UNAVAILABLE"
UNKNOWN_MODEL = "UNKNOWN_MODEL"
MODEL_DISABLED = "MODEL_DISABLED"
ENDPOINT_DISABLED = "ENDPOINT_DISABLED"
CALLER_DENIED = "CALLER_DENIED"
CREDENTIAL_MISSING = "CREDENTIAL_MISSING"
REFUSED_SECRET_IN_PROMPT = "REFUSED_SECRET_IN_PROMPT"
UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
INVALID_ARGUMENT = "INVALID_ARGUMENT"
BACKEND_AUTH = "BACKEND_AUTH"
BACKEND_RATE_LIMITED = "BACKEND_RATE_LIMITED"
BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"
BACKEND_ERROR = "BACKEND_ERROR"
MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
TIMEOUT_NO_OUTPUT = "TIMEOUT_NO_OUTPUT"
TIMEOUT_PARTIAL = "TIMEOUT_PARTIAL"
BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
CONCURRENCY_SATURATED = "CONCURRENCY_SATURATED"
HALTED = "HALTED"

ERROR_CLASSES: tuple[str, ...] = (
    REGISTRY_UNAVAILABLE,
    UNKNOWN_MODEL,
    MODEL_DISABLED,
    ENDPOINT_DISABLED,
    CALLER_DENIED,
    CREDENTIAL_MISSING,
    REFUSED_SECRET_IN_PROMPT,
    UNSUPPORTED_CAPABILITY,
    INVALID_ARGUMENT,
    BACKEND_AUTH,
    BACKEND_RATE_LIMITED,
    BACKEND_UNAVAILABLE,
    BACKEND_ERROR,
    MALFORMED_RESPONSE,
    TIMEOUT_NO_OUTPUT,
    TIMEOUT_PARTIAL,
    BUDGET_EXCEEDED,
    CONCURRENCY_SATURATED,
    HALTED,
)

RETRYABLE: frozenset[str] = frozenset(
    {
        BACKEND_RATE_LIMITED,
        BACKEND_UNAVAILABLE,
        TIMEOUT_NO_OUTPUT,
        CONCURRENCY_SATURATED,
    }
)

DEFAULT_MESSAGE_LIMIT = 300

# C0/C1 controls, DEL, zero-width and bidi/format characters, line/paragraph
# separators: none of them belong in a one-line diagnostic.
_CONTROL_RE = re.compile(
    "[\x00-\x1f\x7f-\x9f\u200b-\u200f\u2028-\u202f\u2060-\u206f\ufeff]"
)


def safe_message(text: object, limit: int = DEFAULT_MESSAGE_LIMIT) -> str:
    """Return ``text`` as a single line of at most ``limit`` characters."""
    cleaned = " ".join(_CONTROL_RE.sub(" ", str(text)).split())
    if len(cleaned) <= limit:
        return cleaned
    if limit < 3:
        return cleaned[:limit]
    return cleaned[: limit - 3].rstrip() + "..."


def classify_http_status(status: int) -> str:
    """Map an upstream HTTP status to a ``BACKEND_*`` class."""
    if status in (401, 403):
        return BACKEND_AUTH
    if status == 429:
        return BACKEND_RATE_LIMITED
    if 500 <= status <= 599:
        return BACKEND_UNAVAILABLE
    return BACKEND_ERROR


class HubError(Exception):
    """A classified tool-execution error.

    ``retryable`` defaults to membership in :data:`RETRYABLE` and may be forced
    either way for a specific occurrence (a 503 with ``Retry-After: 3600`` is
    not worth retrying now).
    """

    klass: str
    message: str
    retryable: bool
    endpoint: str | None
    model: str | None

    def __init__(
        self,
        klass: str,
        message: object = "",
        *,
        endpoint: str | None = None,
        model: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        if klass not in ERROR_CLASSES:
            raise ValueError(f"unknown error class: {klass!r}")
        self.klass = klass
        self.message = safe_message(message)
        self.retryable = (klass in RETRYABLE) if retryable is None else bool(retryable)
        self.endpoint = endpoint
        self.model = model
        super().__init__(f"{klass}: {self.message}")

    def to_payload(self) -> dict[str, dict[str, Any]]:
        """The wire shape every error result carries."""
        return {
            "error": {
                "class": self.klass,
                "message": self.message,
                "retryable": self.retryable,
                "endpoint": self.endpoint,
                "model": self.model,
            }
        }
