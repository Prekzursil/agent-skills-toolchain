# -*- coding: utf-8 -*-
"""Secret redaction for BLD-0051 (shipped-path redactor).

The receipt emitter runs this on its own artifact before write; the probes
verify both states (planted canary stripped; clean content untouched).

- redact_text(text, extra_needles=None, rewrite_json=False):
    extra_needles  - literal strings (e.g. the synthetic canary) replaced by
                     a [REDACTED:<label>] marker.
    rewrite_json   - additionally redact values of JSON-embedded secret keys
                     ("password", "apiKey", camelCase variants, token/secret
                     forms) - both shapes have bypassed a redactor on this
                     estate before.
- scrub_env_values(text, env_names): remove live VALUES of the named
    environment variables (names only are passed; values are never returned).
"""
from __future__ import annotations

import json
import os
import re
from typing import Iterable

MARKER_PREFIX = "[REDACTED:"

# JSON-embedded secret keys, snake_case and camelCase: "password": "v".
_JSON_SECRET_VALUE = re.compile(
    r'"([A-Za-z_][A-Za-z0-9_]*(?:passw(or)?d|passwd|secret|token|api[_-]?key|'
    r'credential)[A-Za-z0-9_]*)"\s*:\s*"([^"]*)"',
    re.IGNORECASE,
)


def _marker(label: str) -> str:
    return f"[REDACTED:{label}]"


def redact_text(
    text: str,
    extra_needles: Iterable[str] | None = None,
    rewrite_json: bool = False,
) -> str:
    for i, needle in enumerate(extra_needles or []):
        if needle:
            text = text.replace(needle, _marker(f"needle-{i}" if i else "canary"))
    if rewrite_json:
        def _sub(m: re.Match) -> str:
            key = m.group(1)
            return f'"{key}": "{_marker(key)}"'

        text = _JSON_SECRET_VALUE.sub(_sub, text)
    return text


def scrub_env_values(text: str, env_names: Iterable[str]) -> str:
    for name in env_names:
        val = os.environ.get(name)
        if val and len(val) >= 12:
            text = text.replace(val, _marker(f"env:{name}"))
    return text


def json_embedded_redact(data: str) -> str:
    """Redact secret-keyed values inside an arbitrary text containing JSON."""
    return _JSON_SECRET_VALUE.sub(
        lambda m: f'"{m.group(1)}": "{_marker(m.group(1))}"', data
    )


def scrub_obj(obj):  # pragma: no cover - helper for future writers
    if isinstance(obj, dict):
        return {
            k: (_marker(str(k)) if _JSON_SECRET_VALUE.match(f'"{k}": "x"') else scrub_obj(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [scrub_obj(v) for v in obj]
    return obj


def try_parse_json(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
