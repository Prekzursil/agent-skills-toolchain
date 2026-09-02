#!/usr/bin/env python3
"""Pinned tokenizer for RES-0140 extraction-cost accounting.

Pin: res-0140-gpt2-regex-unigram/v1

Same mechanical rule as RES-0041 / ARC-0025: this is not a characters/4
estimate. Text is split with a stdlib approximation of the GPT-2 byte-pair
pre-tokenizer regex. Each match (and any unmatched gap) is one token. Byte
count and token count are therefore independent signals.
"""
from __future__ import annotations

import re

TOKENIZER_ID = "res-0140-gpt2-regex-unigram"
TOKENIZER_VERSION = "v1"
TOKENIZER_PIN = f"{TOKENIZER_ID}/{TOKENIZER_VERSION}"
TOKENIZER_SPEC = (
    "Unicode regex unigram: "
    r"'(?:[sdmt]|ll|ve|re)| ?[^\W\d_]+| ?\d+| ?[^\s\w]+|\s+(?!\S)|\s+ "
    "with unmatched gaps kept as their own tokens. Each piece counts as 1. "
    "Not len(text)//4."
)

_PAT = re.compile(
    r"'(?:[sdmt]|ll|ve|re)| ?[^\W\d_]+| ?\d+| ?[^\s\w]+|\s+(?!\S)|\s+",
    re.UNICODE,
)


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    tokens: list[str] = []
    pos = 0
    for m in _PAT.finditer(text):
        if m.start() > pos:
            tokens.append(text[pos : m.start()])
        tokens.append(m.group(0))
        pos = m.end()
    if pos < len(text):
        tokens.append(text[pos:])
    return tokens


def count_text(text: str) -> int:
    return len(tokenize(text))


def count_bytes(raw: bytes) -> int:
    norm = raw.replace(b"\r\n", b"\n")
    return count_text(norm.decode("utf-8", errors="replace"))


def pin_record() -> dict:
    return {
        "id": TOKENIZER_ID,
        "version": TOKENIZER_VERSION,
        "pin": TOKENIZER_PIN,
        "spec": TOKENIZER_SPEC,
        "not_chars_div_4": True,
        "module": "command-center/p2-wave/probes/RES-0140/tokenizer.py",
        "peer": "command-center/p2-wave/probes/RES-0041/tokenizer.py",
        "peer_algorithm": "identical regex unigram; distinct pin name for this unit",
    }
