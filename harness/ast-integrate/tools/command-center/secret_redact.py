"""Redact canaries and named env values before writing artifacts."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

# Key names whose VALUE is a credential by construction (case-insensitive, camelCase included:
# ``apiKey`` / ``passWord`` / ``access_token`` all match).
SECRET_KEY_RE = re.compile(r"(?i)(api[_-]?key|token|passw(?:or)?d|secret|credential|authorization)")

# ``NAME=value`` / ``name: value`` assignments inside free text, redacted value-side only. The
# value token stops at a quote so a JSON string ``"K=v",`` keeps its closing delimiter.
_ASSIGNMENT_RE = re.compile(r"""(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*[^\s"']+""")


def scrub_env_values(text: str, env_names: Iterable[str] | None = None) -> str:
    names = list(env_names or [])
    out = text
    for name in names:
        val = os.environ.get(name)
        if val:
            out = out.replace(val, f"[REDACTED:{name}]")
    return out


def _redact_string(text: str, extra_needles: Iterable[str] | None, env_names: Iterable[str] | None) -> str:
    """Text-mode redaction of one string: env values, explicit needles, then assignments."""
    out = scrub_env_values(text, env_names)
    for needle in extra_needles or []:
        if needle:
            out = out.replace(str(needle), "[REDACTED]")
    out = _ASSIGNMENT_RE.sub(r"\1=[REDACTED]", out)
    return out


def _redact_json_value(value: Any, extra_needles: list[str], env_names: list[str], key: str | None = None) -> Any:
    """Walk a decoded JSON document, redacting credential-named keys and needle-bearing strings.

    The document SHAPE is preserved (same keys, same nesting, same non-string scalars) so the
    result re-serialises as valid JSON that a downstream ``json.loads`` still accepts.
    """
    if isinstance(value, dict):
        return {str(k): _redact_json_value(v, extra_needles, env_names, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_json_value(v, extra_needles, env_names, key=key) for v in value]
    if isinstance(value, str):
        if key is not None and SECRET_KEY_RE.search(key):
            return f"[REDACTED:{key}]"
        out = scrub_env_values(value, env_names)
        for needle in extra_needles:
            if needle and needle in out:
                out = out.replace(needle, f"[REDACTED:{key}]" if key is not None else "[REDACTED]")
        return _ASSIGNMENT_RE.sub(r"\1=[REDACTED]", out)
    return value


def redact_text(
    text: str,
    extra_needles: Iterable[str] | None = None,
    env_names: Iterable[str] | None = None,
    *,
    rewrite_json: bool = False,
) -> str:
    """Redact ``text``; with ``rewrite_json`` a JSON document is rewritten JSON-safely.

    Text mode (default) replaces named env values with ``[REDACTED:<name>]``, explicit needles
    with ``[REDACTED]`` and ``key=value`` credential assignments value-side. That mode splices
    ``key=[REDACTED]`` into ``"apiKey": "..."`` and so breaks a JSON body; ``rewrite_json=True``
    instead parses the body, redacts values under credential-named keys as ``[REDACTED:<key>]``,
    scrubs needles/env values inside every string and re-serialises, so the output still
    parses. A body that is not JSON falls back to text mode — never returned unredacted.
    """
    if rewrite_json:
        try:
            doc = json.loads(text)
        except (TypeError, ValueError):
            doc = None
        if isinstance(doc, (dict, list)):
            needles = [str(n) for n in (extra_needles or []) if n]
            names = [str(n) for n in (env_names or [])]
            return json.dumps(_redact_json_value(doc, needles, names), ensure_ascii=False)
    return _redact_string(text, extra_needles, env_names)


def safe_write(
    path: str | Path,
    body: str,
    extra_needles: Iterable[str] | None = None,
    env_names: Iterable[str] | None = None,
    rewrite_json: bool = False,
    **kwargs: Any,
) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    redacted = redact_text(body, extra_needles=extra_needles, env_names=env_names, rewrite_json=rewrite_json)
    if not redacted.endswith("\n"):
        redacted += "\n"
    dest.write_text(redacted, encoding="utf-8")
