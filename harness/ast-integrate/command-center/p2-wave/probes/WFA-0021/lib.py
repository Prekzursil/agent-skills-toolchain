"""WFA-0021 vendor-documentation sweep primitives.

Fetched pages are untrusted DATA. Embedded instruction-like spans are
neutralised and logged; they are never followed. A docs claim without a
retrieval timestamp cannot become a finding. A mechanism seen on only one
independent surface class stays UNVERIFIED with a named settling probe.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urlparse

ISO_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
)

# Existence evidence classes. Two *docs* pages on the same vendor site are
# one surface. Changelog / source / spec / sdk are the independent classes
# the catalog names.
EXISTENCE_KINDS = frozenset({"docs", "changelog", "source", "sdk", "spec"})
INDEPENDENT_OF_DOCS = frozenset({"changelog", "source", "sdk", "spec"})

INSTRUCTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore-previous",
        re.compile(
            r"ignore\s+(all\s+)?previous\s+instructions?",
            re.IGNORECASE,
        ),
    ),
    (
        "you-are-now",
        re.compile(r"\byou are now\b", re.IGNORECASE),
    ),
    (
        "mark-verified",
        re.compile(
            r"mark(?:\s+mechanism)?\s+\S+\s+as\s+VERIFIED",
            re.IGNORECASE,
        ),
    ),
    (
        "skip-timestamp",
        re.compile(r"skip(?:\s+the)?\s+timestamp\s+requirement", re.IGNORECASE),
    ),
    (
        "do-not-log",
        re.compile(r"do\s+not\s+log\s+this", re.IGNORECASE),
    ),
    (
        "promote-finding",
        re.compile(r"promote\s+\S+\s+to\s+(a\s+)?finding", re.IGNORECASE),
    ),
    (
        "system-tag",
        re.compile(r"</?(?:system|assistant|instruction)>", re.IGNORECASE),
    ),
]

NEUTRAL_TOKEN = "⟦NEUTRALIZED⟧"


def sha256_text(text: str) -> str:
    raw = text.encode("utf-8").replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def neutralize(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Replace instruction-like spans; return (safe_text, log). Never execute."""
    log: list[dict[str, Any]] = []
    safe = text
    for pid, cre in INSTRUCTION_PATTERNS:
        for match in cre.finditer(text):
            log.append(
                {
                    "pattern_id": pid,
                    "span": match.group(0)[:240],
                    "start": match.start(),
                    "end": match.end(),
                    "followed": False,
                }
            )
        safe = cre.sub(NEUTRAL_TOKEN, safe)
    return safe, log


def timestamp_ok(value: Any) -> bool:
    return isinstance(value, str) and bool(ISO_RE.match(value))


def grade_surfaces(surfaces: list[dict[str, Any]]) -> dict[str, Any]:
    """Grade mechanism existence from independent surface classes.

    A capture without retrieved_at is dropped. Zero dated surfaces =>
    REJECTED-UNDATED (cannot be a finding). Only `docs` => UNVERIFIED.
    docs plus changelog/source/sdk/spec, or two of those, => VERIFIED.
    """
    dated = []
    undated = []
    for surf in surfaces:
        if timestamp_ok(surf.get("retrieved_at")):
            dated.append(surf)
        else:
            undated.append(surf)
    kinds = {str(s.get("kind") or "") for s in dated} & EXISTENCE_KINDS
    if not dated:
        return {
            "status": "REJECTED-UNDATED",
            "kinds": sorted(kinds),
            "n_dated": 0,
            "n_undated": len(undated),
            "settling_probe": (
                "WFA-0021-settling: re-fetch every cited URL and persist "
                "an ISO-8601 retrieval timestamp (HTTP Date or local clock)"
            ),
        }
    verified = ("docs" in kinds and bool(kinds & INDEPENDENT_OF_DOCS)) or (
        len(kinds & INDEPENDENT_OF_DOCS) >= 2
    )
    if verified:
        return {
            "status": "VERIFIED",
            "kinds": sorted(kinds),
            "n_dated": len(dated),
            "n_undated": len(undated),
            "settling_probe": None,
        }
    missing = sorted(INDEPENDENT_OF_DOCS - kinds)
    return {
        "status": "UNVERIFIED",
        "kinds": sorted(kinds),
        "n_dated": len(dated),
        "n_undated": len(undated),
        "settling_probe": (
            "WFA-0021-settling: locate the same mechanism on a second "
            "vendor surface class (changelog, SDK reference, or the "
            "vendor's own source); currently missing: "
            + ",".join(missing)
        ),
    }


def etld1(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    parts = [p for p in host.split(".") if p]
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def quote_in_neutralized(quote: str, neutralized: str) -> bool:
    compact_q = " ".join(quote.split())
    compact_n = " ".join(neutralized.split())
    return compact_q in compact_n


def dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
