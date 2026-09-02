"""Pinned regex-unigram tokenizer for injected capability blocks (TST-0240).

The router must *measure* the tokens of the block it actually injects instead
of estimating ``len(text) // 4``. This module is that measurement: a GPT-2
style pre-tokenizer expressed as a Unicode regex. Every regex piece counts as
one token; any byte span the regex does not cover (for example a bare
underscore, which is ``\\w`` but neither a letter nor a digit) is kept as its
own token so the count never silently drops text.

The tokenizer identity is pinned (``TOKENIZER_PIN``) so receipts can record
which counting rule produced a number and detect a swap later.
"""

from __future__ import annotations

import re
from typing import Iterator

TOKENIZER_ID = "router-gpt2-regex-unigram"
TOKENIZER_VERSION = "v1"
TOKENIZER_PIN = f"{TOKENIZER_ID}/{TOKENIZER_VERSION}"
TOKENIZER_MODULE = "tools/router/tokens.py"

# GPT-2 pre-tokenizer, restricted to the ``re`` module's Unicode classes:
#   contractions | optional-space + letters | optional-space + digits |
#   optional-space + punctuation run | whitespace not followed by non-space |
#   whitespace run.
TOKEN_PATTERN = (
    r"'(?:[sdmt]|ll|ve|re)"
    r"| ?[^\W\d_]+"
    r"| ?\d+"
    r"| ?[^\s\w]+"
    r"|\s+(?!\S)"
    r"|\s+"
)
TOKENIZER_SPEC = (
    "Unicode regex unigram: '(?:[sdmt]|ll|ve|re)| ?[^\\W\\d_]+| ?\\d+| ?[^\\s\\w]+"
    "|\\s+(?!\\S)|\\s+ with unmatched gaps kept as their own tokens. "
    "Each piece counts as 1. Not len(text)//4."
)
_TOKEN_RE = re.compile(TOKEN_PATTERN, re.UNICODE)


def iter_tokens(text: str) -> Iterator[str]:
    """Yield every token of ``text`` in order, including uncovered gaps.

    ``text`` must be a ``str``; bytes are rejected because the count would
    depend on the encoding rather than on the injected block.
    """
    if not isinstance(text, str):
        raise TypeError(f"count_tokens expects str, got {type(text).__name__}")
    pos = 0
    for match in _TOKEN_RE.finditer(text):
        start, end = match.span()
        if start > pos:
            # A span the pattern cannot describe (e.g. "_") is still content.
            yield text[pos:start]
        if end > start:
            yield match.group(0)
        pos = end
    if pos < len(text):
        yield text[pos:]


def tokenize(text: str) -> list[str]:
    """Return the token pieces of ``text``; ``"".join(pieces) == text``."""
    return list(iter_tokens(text))


def count_tokens(text: str) -> int:
    """Measured token count of ``text`` under the pinned tokenizer.

    Deterministic and stable: the same block always yields the same count.
    """
    return sum(1 for _ in iter_tokens(text))


def chars_div_4(text: str) -> int:
    """The naive estimate the measurement is *not* allowed to collapse onto."""
    if not isinstance(text, str):
        raise TypeError(f"chars_div_4 expects str, got {type(text).__name__}")
    return len(text) // 4


def tokenizer_pin() -> dict[str, object]:
    """Identity record embedded in injection results and receipts."""
    return {
        "id": TOKENIZER_ID,
        "version": TOKENIZER_VERSION,
        "pin": TOKENIZER_PIN,
        "module": TOKENIZER_MODULE,
        "spec": TOKENIZER_SPEC,
        "not_chars_div_4": True,
    }


__all__ = [
    "TOKENIZER_ID",
    "TOKENIZER_MODULE",
    "TOKENIZER_PIN",
    "TOKENIZER_SPEC",
    "TOKENIZER_VERSION",
    "TOKEN_PATTERN",
    "chars_div_4",
    "count_tokens",
    "iter_tokens",
    "tokenize",
    "tokenizer_pin",
]
