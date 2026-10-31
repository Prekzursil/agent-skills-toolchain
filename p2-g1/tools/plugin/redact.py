"""Redact synthetic secret bodies; keep zero-entropy prefixes."""
from __future__ import annotations

from typing import Any

from canary import PREFIX, synthetic_body, synthetic_github_pat


def redact_text(text: str) -> str:
    body = synthetic_body()
    token = synthetic_github_pat()
    out = text.replace(token, PREFIX + "<redacted>")
    out = out.replace(body, "<redacted>")
    return out


def redact_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, list):
        return [redact_obj(x) for x in obj]
    if isinstance(obj, dict):
        return {redact_text(str(k)) if isinstance(k, str) else k: redact_obj(v) for k, v in obj.items()}
    return obj
