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
    # `ghr_` (refresh token) and `htk_` (HexStrike) only ever existed in the repo's
    # agent-self/harness mirror; this live tree has leaked both since the harness
    # trees diverged. Measured 2026-07-27 against this module BEFORE the fix:
    #   ghr_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345 -> returned byte-for-byte
    #   htk_ABCDEFGHIJKLMNOPQRSTUVWX         -> returned byte-for-byte
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bhtk_[A-Za-z0-9]{20,}\b", re.I),
    re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxox[a-z]-[A-Za-z0-9-]{20,}\b", re.I),
    re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b", re.I),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b", re.I),
    re.compile(r"\bnpm_[A-Za-z0-9]{20,}\b", re.I),
    re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b"),
    # `Basic` matters as much as `Bearer`: `Authorization: Basic <b64>` carries
    # user:password and was passing through untouched.
    re.compile(r"(?i)\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{20,}={0,2}"),
    # Measured 2026-07-26 against this module: `password=abcdefghijklmnopqr` was
    # caught but `{"password":"abcdefghijklmnopqr"}` was returned byte-for-byte,
    # because after the key comes a QUOTE, which is neither in [A-Za-z0-9_-] nor
    # \s, so the [:=] separator never matched. JSON is the dominant payload shape
    # and redact_text guards set_goal before it persists to the event ledger, so a
    # JSON credential was being written to durable storage in plaintext.
    #   ['\"]?\s* before the separator  -> quoted (JSON) keys now match
    #   [^\s'\"]{18,} as the value      -> the KEY is the discriminator, so any
    #                                      18+ non-space run counts; the old class
    #                                      excluded punctuation, letting
    #                                      `password=!CorrectHorseBattery...` pass.
    re.compile(
        r"(?i)\b[A-Za-z0-9_-]*(?:API[_-]?KEY|ACCESS[_-]?KEY|SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE[_-]?KEY)[A-Za-z0-9_-]*['\"]?\s*[:=]\s*['\"]?[^\s'\"]{18,}={0,2}"
    ),
    re.compile(
        r"(?i)(?:api[_-]?key|token|secret|password)['\"]?\s*[:=]\s*['\"]?[^\s'\"]{18,}={0,2}"
    ),
    # Preserve the existing sync-self.ps1 JSON heuristic when routing it through
    # this shared, value-redacting classifier. It intentionally accepts shorter
    # values only when a quoted credential-like key supplies strong context, so
    # `{"api_key":"abcdefghijkl"}` (12-char value, under the 18+ floor above) is
    # caught. Present in the repo's agent-self/harness; this live tree was stale.
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
