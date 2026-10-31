"""Redact canaries and named env values before writing artifacts."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Iterable

# JSON-embedded secret keys, snake_case and camelCase: "password": "v".
# Both shapes have bypassed a redactor on this estate before (unit evidence:
# BLD-0051 shape control), so the value form is redacted regardless of key
# spelling.
_JSON_SECRET_VALUE = re.compile(
    r'"([A-Za-z_][A-Za-z0-9_]*(?:passw(or)?d|passwd|secret|token|api[_-]?key|'
    r'credential)[A-Za-z0-9_]*)"\s*:\s*"([^"]*)"',
    re.IGNORECASE,
)


def scrub_env_values(text: str, env_names: Iterable[str] | None = None) -> str:
    names = list(env_names or [])
    out = text
    for name in names:
        val = os.environ.get(name)
        if val:
            out = out.replace(val, f"[REDACTED:{name}]")
    return out


def redact_text(
    text: str,
    extra_needles: Iterable[str] | None = None,
    env_names: Iterable[str] | None = None,
    rewrite_json: bool = False,
) -> str:
    """Redact literal needles, named env values, KEY=VALUE pairs and, when
    rewrite_json is set, values of JSON-embedded secret keys (snake_case and
    camelCase). Markers carry a label: [REDACTED:canary], [REDACTED:<NAME>],
    [REDACTED:<key>]."""
    out = scrub_env_values(text, env_names)
    if rewrite_json:
        def _sub(m: "re.Match[str]") -> str:
            key = m.group(1)
            return f'"{key}": "[REDACTED:{key}]"'

        out = _JSON_SECRET_VALUE.sub(_sub, out)
    for i, needle in enumerate(extra_needles or []):
        if needle:
            label = "canary" if i == 0 else f"needle-{i}"
            out = out.replace(str(needle), f"[REDACTED:{label}]")
    out = re.sub(
        r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*[^\s\"]+",
        r"\1=[REDACTED]",
        out,
    )
    return out


def safe_write(
    path: str | Path,
    body: str,
    extra_needles: Iterable[str] | None = None,
    env_names: Iterable[str] | None = None,
    **kwargs: Any,
) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    redacted = redact_text(
        body, extra_needles=extra_needles, env_names=env_names, **kwargs
    )
    if not redacted.endswith("\n"):
        redacted += "\n"
    dest.write_text(redacted, encoding="utf-8")
