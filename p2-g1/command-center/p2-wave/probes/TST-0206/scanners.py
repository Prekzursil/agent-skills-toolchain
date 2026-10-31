"""TST-0206 scanners: pattern + entropy, independent implementations.

(a) pattern_scanner  - literal/regex scan for the canary prefix and common
                       credential shapes.
(b) entropy_scanner  - tokenizes on non-secret-char boundaries and flags
                       high-Shannon-entropy base64ish tokens of secret-like
                       length; knows nothing about the canary's literal text
                       beyond what any random 40-hex-char token looks like.

Both must fire on a planted canary and agree on a clean tree.
"""
from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Any

CANARY_PREFIX = "SYNTHETIC_NOT_A_CREDENTIAL_TST0206_"

PATTERNS = [
    re.compile(r"SYNTHETIC_NOT_A_CREDENTIAL_TST0206_[0-9a-f]{16,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|secret[_-]?token)\s*[=:]\s*['\"][A-Za-z0-9_-]{16,}['\"]"),
]

_SECRETISH = re.compile(r"[A-Za-z0-9+/=_-]{20,}")


def _shannon(token: str) -> float:
    if not token:
        return 0.0
    freq: dict[str, int] = {}
    for ch in token:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(token)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def derive_canary() -> tuple[str, str]:
    """(token, sha256) - the body is derived fresh each run, never stored anywhere."""
    body = hashlib.sha256(b"TST-0206|wave3-resume|canary").hexdigest()[:40]
    token = CANARY_PREFIX + body
    return token, hashlib.sha256(token.encode("utf-8")).hexdigest()


def scan_text(text: str) -> dict[str, Any]:
    pattern_hits = []
    for pat in PATTERNS:
        for m in pat.finditer(text):
            pattern_hits.append(m.group(0)[:24] + "...")
    entropy_hits = []
    for tok in _SECRETISH.findall(text):
        if len(tok) >= 32 and _shannon(tok) >= 4.5 and re.search(r"[0-9]", tok) and re.search(r"[A-Za-z]", tok):
            entropy_hits.append(tok[:24] + "...")
    return {"pattern_hits": pattern_hits, "entropy_hits": entropy_hits}


def scan_tree(root: Path, limit_bytes: int = 64_000_000) -> dict[str, Any]:
    files = 0
    total_bytes = 0
    pattern_hits = []
    entropy_hits = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > limit_bytes:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        total_bytes += len(data)
        files += 1
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        res = scan_text(text)
        if res["pattern_hits"]:
            pattern_hits.append({"path": str(path), "hits": res["pattern_hits"]})
        if res["entropy_hits"]:
            entropy_hits.append({"path": str(path), "hits": res["entropy_hits"]})
    return {
        "root": str(root),
        "files": files,
        "bytes": total_bytes,
        "pattern_hits": pattern_hits,
        "entropy_hits": entropy_hits,
        "pattern_hit_count": sum(len(h["hits"]) for h in pattern_hits),
        "entropy_hit_count": sum(len(h["hits"]) for h in entropy_hits),
    }
