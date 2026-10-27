"""Payload tokenizer. count_tokens is not a len//4 estimate."""
from __future__ import annotations

import re

TOKENIZER_ID = "whitespace-word-v1"
TOKENIZER_VERSION = "1"
_WORD = re.compile(r"\S+")


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_WORD.findall(text))


def char_quarter_estimate(text: str) -> int:
    return len(text) // 4
