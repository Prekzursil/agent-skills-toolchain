"""Runtime canary token. Never serialize the value; never print it."""
from __future__ import annotations

import hashlib
import math
import secrets
from collections import Counter

PREFIX = "sk-ant-"


def shannon_bits(text: str) -> float:
    if not text:
        return 0.0
    n = len(text)
    counts = Counter(text)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def mint() -> dict:
    """Zero-entropy prefix plus a random hex body. Value stays in `_token` only."""
    body = secrets.token_hex(16)
    token = PREFIX + body
    return {
        "prefix": PREFIX,
        "body_len": len(body),
        "body_entropy_bits": round(shannon_bits(body), 4),
        "token_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
        "shape": "anthropic-key (marketplace.lint SECRET_PATTERNS)",
        "_token": token,
    }


def public_meta(canary: dict) -> dict:
    return {k: v for k, v in canary.items() if not str(k).startswith("_")}


def token_of(canary: dict) -> str:
    tok = canary.get("_token")
    if not isinstance(tok, str) or not tok.startswith(PREFIX):
        raise RuntimeError("canary token missing; refusing to invent one")
    return tok
