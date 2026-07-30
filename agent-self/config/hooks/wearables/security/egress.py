"""Fail-CLOSED egress chokepoint — the single most important security control.

ONE enforced function (:func:`egress_guard`) every third-party-LLM / external
call must pass through. Default-DENY allowlist of ``(model, endpoint,
source_class)`` triples. Any exception or unclassifiable input -> DENY.

Rules:
  * only ``source_class == "public_db"`` may reach a third-party LLM;
  * ``derived`` is sensitive-by-default — reaches a third-party LLM ONLY with
    an explicit ``allow_derived_egress=True`` downgrade;
  * ``unpublished`` always DENY to third-party (only loopback-local accepts it);
  * payloads are secret-scrubbed BEFORE any write/dump (assert-not-present);
  * any local-LLM ``base_url`` is loopback-pinned (host + scheme allowlist).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

# Models/endpoints we recognise as third-party (cloud) LLM egress.
_THIRD_PARTY_MODELS: frozenset[str] = frozenset(
    {"gemini-2.5-flash", "gemini-2.5-flash-lite"}
)
_THIRD_PARTY_ENDPOINTS: frozenset[str] = frozenset(
    {"https://generativelanguage.googleapis.com/v1/models"}
)
# Local / HF (Tier-3) models that may receive sensitive content over loopback.
_LOCAL_MODELS: frozenset[str] = frozenset({"qwen2.5-3b", "qwen2.5-3b-instruct"})

_LOOPBACK_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})
_ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

_REDACTED = "[REDACTED]"
# Each entry is (pattern, prefix-group-count). Patterns with a single capturing
# group preserve only a NON-secret prefix (group 1) and append _REDACTED. The
# bare hf_ token has NO prefix to keep, so it is a whole-match replacement to a
# constant — capturing the token and re-emitting it would leak the secret.
_PREFIX_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(GOOGLE_API_KEY\s*=\s*)\S+"),
    re.compile(r"(HF_TOKEN\s*=\s*)\S+"),
    re.compile(r"(Authorization\s*:\s*Bearer\s+)\S+", re.IGNORECASE),
    re.compile(r"(\bbearer\s+)\S+", re.IGNORECASE),
    re.compile(r"(\bapi[_-]?key\s*[=:]\s*)\S+", re.IGNORECASE),
    re.compile(r"(\bkey=)[^&\s]+"),
)
# Whole-match patterns: the entire match IS secret, so replace with a constant.
_WHOLE_MATCH_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"hf_[A-Za-z0-9]{8,}"),
)


@dataclass(frozen=True)
class EgressRequest:
    model: str
    endpoint: str
    source_class: str
    payload: object
    base_url: str
    allow_derived_egress: bool = False


@dataclass(frozen=True)
class EgressDecision:
    allowed: bool
    reason: str
    scrubbed_payload: str = field(default="")


def scrub_secrets(value: object) -> str:
    """Redact known secret patterns from ``value`` (coerced to str)."""
    text = value if isinstance(value, str) else str(value)
    for pattern in _PREFIX_SECRET_PATTERNS:
        text = pattern.sub(lambda m: m.group(1) + _REDACTED, text)
    for pattern in _WHOLE_MATCH_SECRET_PATTERNS:
        text = pattern.sub(_REDACTED, text)
    return text


def _is_loopback(base_url: str) -> bool:
    parts = urlsplit(base_url)
    if parts.scheme not in _ALLOWED_SCHEMES:
        return False
    host = parts.hostname
    if host is None:
        return False
    return host in _LOOPBACK_HOSTS


def _deny(reason: str) -> EgressDecision:
    return EgressDecision(allowed=False, reason=reason)


def egress_guard(request: object) -> EgressDecision:
    """Default-DENY gate. Returns an :class:`EgressDecision`; never raises."""
    try:
        if not isinstance(request, EgressRequest):
            return _deny("fail-closed: malformed or non-EgressRequest input")

        scrubbed = scrub_secrets(request.payload)

        if request.source_class not in {"public_db", "derived", "unpublished"}:
            return _deny(f"fail-closed: unknown source_class {request.source_class!r}")

        # A dataclass ANNOTATION is not a runtime check: EgressRequest(...,
        # allow_derived_egress="false") constructs fine, and the old raw-truthiness
        # gate (`not request.allow_derived_egress`) then read that string as an
        # affirmative downgrade -- the literal text "false" authorised derived
        # content to a third-party LLM. Unclassifiable input must DENY here, per
        # the fail-CLOSED contract in this package's __init__.
        if not isinstance(request.allow_derived_egress, bool):
            return _deny(
                "fail-closed: allow_derived_egress must be a bool, got "
                f"{type(request.allow_derived_egress).__name__}"
            )

        is_third_party = (
            request.model in _THIRD_PARTY_MODELS
            and request.endpoint in _THIRD_PARTY_ENDPOINTS
        )
        is_local = request.model in _LOCAL_MODELS

        if is_local:
            if not _is_loopback(request.base_url):
                return _deny("loopback-pin failed: local-LLM base_url not loopback")
            # Tier-3 loopback may receive any classification (incl. unpublished).
            return EgressDecision(
                allowed=True,
                reason="allow: loopback-local Tier-3 endpoint",
                scrubbed_payload=scrubbed,
            )

        if not is_third_party:
            return _deny("not on allowlist: unknown (model, endpoint) pair")

        # third-party LLM path: source_class gate
        if request.source_class == "unpublished":
            return _deny("source_class=unpublished may not reach a third-party LLM")
        if (
            request.source_class == "derived"
            and request.allow_derived_egress is not True
        ):
            return _deny(
                "source_class=derived is sensitive-by-default (no downgrade flag)"
            )
        # public_db, or derived + explicit downgrade
        return EgressDecision(
            allowed=True,
            reason="allow: public_db (or downgraded derived) to allowlisted third-party LLM",
            scrubbed_payload=scrubbed,
        )
    except Exception as exc:  # ANY failure -> DENY (fail-closed proof)
        return _deny(f"fail-closed: guard raised {type(exc).__name__}: {exc}")
