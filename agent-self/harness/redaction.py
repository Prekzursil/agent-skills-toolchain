from __future__ import annotations

import json
import re
from typing import Any


_PRIVATE_KEY_HEADER = r"-----BEGIN (?=[^\r\n]*PRIVATE KEY)[^\r\n]+?-----"
_PRIVATE_KEY_FOOTER = r"-----END (?=[^\r\n]*PRIVATE KEY)[^\r\n]+?-----"

_SECRET_PATTERNS = (
    re.compile(_PRIVATE_KEY_HEADER + r".*?" + _PRIVATE_KEY_FOOTER, re.I | re.S),
    # A missing footer is still sensitive: redact from the header to end-of-input.
    re.compile(_PRIVATE_KEY_HEADER + r".*\Z", re.I | re.S),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bhtk_[A-Za-z0-9]{20,}\b", re.I),
    re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxox[a-z]-[A-Za-z0-9-]{20,}\b", re.I),
    re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b", re.I),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b", re.I),
    re.compile(r"\bnpm_[A-Za-z0-9]{20,}\b", re.I),
    re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{20,}={0,2}"),
    re.compile(
        r"(?i)\b[A-Za-z0-9_-]*(?:API[_-]?KEY|ACCESS[_-]?KEY|SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE[_-]?KEY)[A-Za-z0-9_-]*\s*[:=]\s*['\"]?[A-Za-z0-9._~+/-]{18,}={0,2}"
    ),
    re.compile(
        r"(?i)(?:api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9._~+/-]{18,}={0,2}"
    ),
    # Preserve the existing sync-self.ps1 JSON heuristic when routing it through
    # this shared, value-redacting classifier. It intentionally accepts shorter
    # values only when a quoted credential-like key supplies strong context.
    re.compile(
        r'(?i)"[^"]*(?:api[_-]?key|token|secret|password)[^"]*"\s*:\s*"[^"{][^"]{8,}"'
    ),
)
# Checkpoint privacy is stricter than display fidelity. Once an absolute path is
# encountered, redact the rest of that line so spaces cannot expose a path tail.
_ABSOLUTE_PATH_TO_EOL = re.compile(
    r"(?im)(?<![A-Za-z0-9_])(?:[A-Z]:[\\/]|\\\\[^\\/\r\n]+[\\/]|//[^/\r\n]+/)[^\r\n]*"
)
_UNIX_ABSOLUTE_PATH_TO_EOL = re.compile(r"(?m)(?<![A-Za-z0-9_/.\\])/(?!/)[^\r\n]*")


def contains_secret(value: Any) -> bool:
    text = _to_text(value)
    return any(pattern.search(text) for pattern in _SECRET_PATTERNS)


def redact_text(
    text: str, *, redact_paths: bool = False, max_chars: int | None = None
) -> str:
    value = str(text or "")
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    if redact_paths:
        value = _ABSOLUTE_PATH_TO_EOL.sub("[PATH]", value)
        value = _UNIX_ABSOLUTE_PATH_TO_EOL.sub("[PATH]", value)
    if max_chars is not None and len(value) > max_chars:
        value = value[: max(0, max_chars - 16)].rstrip() + "\n[TRUNCATED]"
    return value


def _to_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, default=repr)
    except Exception:
        return repr(value)
