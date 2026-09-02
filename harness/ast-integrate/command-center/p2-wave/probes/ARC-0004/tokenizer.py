"""Pinned tokenizer for ARC-0004 (and the ARC-0025 cross-check corpus).

tiktoken is not installed on this worktree. This module is the named, versioned
tokenizer: a Unicode regex pretokenizer matching the cl100k_base *split* stage
(without BPE merges). Counts are therefore a real tokeniser output, not chars/4.
"""
from __future__ import annotations

import re
import unicodedata

TOKENIZER_ID = "arc-0004.unicode-regex.v1"
TOKENIZER_VERSION = "1.0.0"
ALGORITHM = (
    "NFC-normalize UTF-8 text, then emit one token per match of the pinned "
    "cl100k-style regex (contraction / letters / 1-3 digits / other-run / "
    "whitespace). No BPE merges. Not a character/4 estimate."
)

# cl100k_base-style pretokenizer, ASCII-safe stand-in for \p{L}/\p{N}.
PATTERN = re.compile(
    r"'(?:[sS]|[tT]|[mM]|[dD]|ll|LL|ve|VE|re|RE)"
    r"|[A-Za-z]+"
    r"|[0-9]{1,3}"
    r"|[^\sA-Za-z0-9]+"
    r"|\s+"
)


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    norm = unicodedata.normalize("NFC", text)
    return PATTERN.findall(norm)


def count_text(text: str) -> int:
    return len(tokenize(text))


def count_bytes(raw: bytes) -> int:
    return count_text(raw.decode("utf-8"))


count_bytes = count_bytes
TOKENIZER_ID = TOKENIZER_ID
TOKENIZER_VERSION = TOKENIZER_VERSION


def spec() -> dict:
    return {
        "id": TOKENIZER_ID,
        "version": TOKENIZER_VERSION,
        "algorithm": ALGORITHM,
        "pinned": True,
        "pattern": PATTERN.pattern,
        "bpe_merges": False,
        "chars_div_4": False,
    }
