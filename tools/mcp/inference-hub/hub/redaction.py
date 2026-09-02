"""Outbound secret scanning and value-free log payloads for inference-hub.

Two questions are answered here, both without ever emitting a secret value:

* **Is a credential about to leave the box inside a prompt?** A
  :class:`Redactor` knows the exact VALUES of the credential environment
  variables named in the registry (only the ones set in the hub's own
  environment, only when at least eight characters long) plus the literal
  secret shapes every provider hands out (Hugging Face, GitHub, OpenRouter,
  Anthropic, OpenAI, DigitalOcean, AWS, Slack, PEM private keys, JWTs). It scans
  every message - string content and ``{"type": "text"}`` parts alike - and
  reports :class:`Finding` rows (message index, path, kind, length). The hub
  refuses the call (``REFUSED_SECRET_IN_PROMPT``) or, when the caller opted in,
  sends the masked copy produced by :meth:`Redactor.redact_messages`.
* **Is a log payload safe to write?** :meth:`Redactor.redact_obj` masks values
  under credential-bearing keys (``authorization``, ``api_key``, ``token``,
  ``secret``, ``password``, ``cookie``, ``x-api-key`` and their stems) and
  scrubs every string leaf. :meth:`Redactor.describe` renders a credential as
  ``NAME(len=N)`` - name and length, never the value.

Key-name matching and the recursive walk follow the idioms of
``tools/mcp/proxy-mcp/redaction.py`` (``_is_sensitive_key`` / ``redact_obj``).
Pure functions, stdlib only, no I/O.
"""

from __future__ import annotations

import copy
import json
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from typing import Any, NamedTuple

__all__ = [
    "MIN_ENV_VALUE_LENGTH",
    "SECRET_PATTERNS",
    "SENSITIVE_KEYS",
    "Finding",
    "Hit",
    "Redactor",
    "is_sensitive_key",
    "mask",
    "redact_obj",
    "redact_text",
]

MIN_ENV_VALUE_LENGTH = 8

_BOUNDARY = r"(?<![A-Za-z0-9_-])"
_DASHES = "-" * 5
_PEM_HEAD = _DASHES + r"BEGIN(?: [A-Z0-9]+)* PRIVATE KEY" + _DASHES
_PEM_TAIL = _DASHES + r"END(?: [A-Z0-9]+)* PRIVATE KEY" + _DASHES

# Ordered most-specific first: the combined alternation picks the first
# alternative that matches at a position, so ``sk-or-v1-`` wins over ``sk-``.
SECRET_PATTERNS: dict[str, str] = {
    "openrouter": _BOUNDARY + r"sk-or-v1-[A-Za-z0-9]{20,}",
    "anthropic": _BOUNDARY + r"sk-ant-[A-Za-z0-9_-]{20,}",
    "openai_project": _BOUNDARY + r"sk-proj-[A-Za-z0-9_-]{20,}",
    "openai": _BOUNDARY + r"sk-[A-Za-z0-9_-]{20,}",
    "huggingface": _BOUNDARY + r"hf_[A-Za-z0-9]{20,}",
    "github_pat": _BOUNDARY + r"github_pat_[A-Za-z0-9_]{20,}",
    "github_token": _BOUNDARY + r"gh[pousr]_[A-Za-z0-9]{20,}",
    "digitalocean": _BOUNDARY + r"do[op]_v1_[A-Za-z0-9]{20,}",
    "aws_access_key": r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])",
    "slack": _BOUNDARY + r"xox[abp]-[A-Za-z0-9-]{10,}",
    "private_key": _PEM_HEAD + r"[\s\S]*?(?:" + _PEM_TAIL + r"|\Z)",
    "jwt": _BOUNDARY + r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
}

SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "authorization",
        "proxy_authorization",
        "api_key",
        "apikey",
        "x_api_key",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "secret",
        "client_secret",
        "password",
        "passwd",
        "cookie",
        "set_cookie",
        "credential",
        "credentials",
        "private_key",
    }
)

_SENSITIVE_STEMS: tuple[str, ...] = (
    "authorization",
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "cookie",
    "private_key",
    "bearer",
)

_PATTERN_GROUP_PREFIX = "p_"
_ENV_GROUP_PREFIX = "e_"


class Hit(NamedTuple):
    """One match inside a single text: ``kind`` plus its half-open span."""

    kind: str
    start: int
    end: int


@dataclass(frozen=True)
class Finding:
    """One secret located inside a message list."""

    index: int
    path: str
    kind: str
    length: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalise_key(key: object) -> str:
    return str(key).strip().lower().replace("-", "_").replace(" ", "_")


def is_sensitive_key(key: object) -> bool:
    """True when ``key`` names a credential-bearing field or header."""
    norm = _normalise_key(key)
    if norm in SENSITIVE_KEYS:
        return True
    return any(stem in norm for stem in _SENSITIVE_STEMS)


def mask(kind: str) -> str:
    """The placeholder written in place of a detected secret."""
    return f"<redacted:{kind}>"


def _mask_value(key: str, value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return f"<redacted:key={_normalise_key(key)},len={len(text)}>"


class Redactor:
    """Scanner bound to one set of credential names and one environment."""

    def __init__(
        self,
        credential_env_names: Iterable[str],
        environ: Mapping[str, str] | None = None,
    ) -> None:
        env: Mapping[str, str] = os.environ if environ is None else environ
        self._environ = env
        values: dict[str, str] = {}
        for name in credential_env_names:
            value = env.get(name)
            if value is not None and len(value) >= MIN_ENV_VALUE_LENGTH:
                values[name] = value
        self._values = values
        self.env_names: tuple[str, ...] = tuple(values)
        self._matcher = self._compile()

    def _compile(self) -> re.Pattern[str]:
        # Exact values first (longest first so a value that contains another is
        # attributed to the longer name), then the shape patterns.
        alternatives = [
            f"(?P<{_ENV_GROUP_PREFIX}{name}>{re.escape(self._values[name])})"
            for name in sorted(self._values, key=lambda n: -len(self._values[n]))
        ]
        alternatives.extend(
            f"(?P<{_PATTERN_GROUP_PREFIX}{name}>{pattern})"
            for name, pattern in SECRET_PATTERNS.items()
        )
        return re.compile("|".join(alternatives))

    # -- description ----------------------------------------------------------
    def describe(self, name: str) -> str:
        """``NAME(len=N)`` or ``NAME(unset)`` - never the value."""
        value = self._environ.get(name)
        if value is None:
            return f"{name}(unset)"
        return f"{name}(len={len(value)})"

    # -- text ------------------------------------------------------------------
    def scan_text(self, text: str) -> list[Hit]:
        hits: list[Hit] = []
        for match in self._matcher.finditer(text):
            group = match.lastgroup or ""
            if group.startswith(_ENV_GROUP_PREFIX):
                kind = "env:" + group[len(_ENV_GROUP_PREFIX) :]
            else:
                kind = "pattern:" + group[len(_PATTERN_GROUP_PREFIX) :]
            hits.append(Hit(kind, match.start(), match.end()))
        return hits

    def redact_text(self, text: str) -> str:
        pieces: list[str] = []
        cursor = 0
        for hit in self.scan_text(text):
            pieces.append(text[cursor : hit.start])
            pieces.append(mask(hit.kind))
            cursor = hit.end
        pieces.append(text[cursor:])
        return "".join(pieces)

    # -- messages ----------------------------------------------------------------
    @staticmethod
    def _text_slots(message: Any) -> list[tuple[str, Any, Any]]:
        """``(path, container, key)`` for every scannable string in a message."""
        if not isinstance(message, dict):
            return []
        content = message.get("content")
        if isinstance(content, str):
            return [("content", message, "content")]
        slots: list[tuple[str, Any, Any]] = []
        if isinstance(content, list):
            for position, part in enumerate(content):
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    slots.append((f"content[{position}].text", part, "text"))
        return slots

    def scan_messages(self, messages: list[Any]) -> list[Finding]:
        if not isinstance(messages, list):
            return []
        findings: list[Finding] = []
        for index, message in enumerate(messages):
            for path, container, key in self._text_slots(message):
                for hit in self.scan_text(container[key]):
                    findings.append(Finding(index, path, hit.kind, hit.end - hit.start))
        return findings

    def redact_messages(self, messages: list[Any]) -> tuple[list[Any], int]:
        """A deep copy with every hit masked, plus the number of replacements."""
        if not isinstance(messages, list):
            return messages, 0
        redacted = copy.deepcopy(messages)
        count = 0
        for message in redacted:
            for _path, container, key in self._text_slots(message):
                hits = self.scan_text(container[key])
                if hits:
                    container[key] = self.redact_text(container[key])
                    count += len(hits)
        return redacted, count

    # -- log payloads ------------------------------------------------------------
    def redact_obj(self, obj: Any) -> Any:
        """A scrubbed copy of a JSON-like structure destined for a log."""
        if isinstance(obj, dict):
            out: dict[Any, Any] = {}
            for key, value in obj.items():
                if is_sensitive_key(key):
                    out[key] = _mask_value(str(key), value)
                else:
                    out[key] = self.redact_obj(value)
            return out
        if isinstance(obj, (list, tuple)):
            return [self.redact_obj(item) for item in obj]
        if isinstance(obj, str):
            return self.redact_text(obj)
        return obj


_PATTERNS_ONLY = Redactor((), {})


def redact_text(text: str) -> str:
    """Pattern-only scrub for callers without a registry-bound :class:`Redactor`."""
    return _PATTERNS_ONLY.redact_text(text)


def redact_obj(obj: Any) -> Any:
    """Pattern-only structural scrub (sensitive keys by name, values by shape)."""
    return _PATTERNS_ONLY.redact_obj(obj)
