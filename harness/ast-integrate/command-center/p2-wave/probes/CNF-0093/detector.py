"""Verbatim + paraphrase search over participant streams.

The same function is used for the partitioned canary hunt and for the
unpartitioned control. Silence is only trusted after the control hits.
"""
from __future__ import annotations

import re
from typing import Iterable

from canaries import (
    CONTROL_CANARY,
    FACT_COLOR,
    FACT_OBJECT,
    PARTITION_CANARY,
    PARAPHRASE_SERIAL,
    PARAPHRASE_TRIGRAM,
)

CREDENTIAL_SHAPED = re.compile(
    r"(?:sk-|AKIA|ghp_|xoxb-|xoxp-|-----BEGIN )",
    re.IGNORECASE,
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _window_has_trigram(norm: str, words: tuple[str, str, str]) -> bool:
    tokens = norm.split()
    need = {w.lower() for w in words}
    if not need:
        return False
    width = 12
    for i in range(len(tokens)):
        chunk = set(tokens[i : i + width])
        if need <= chunk:
            return True
    return False


def is_benign_token(value: str) -> bool:
    if not value or len(value) < 16:
        return False
    if CREDENTIAL_SHAPED.search(value):
        return False
    return value.startswith("CNF0093CANARY.")


def search_text(haystack: str, needle: str, paraphrase: bool) -> list[dict]:
    """Return hit dicts. Empty list means no leak of this needle in this haystack."""
    hits: list[dict] = []
    raw = haystack or ""
    if needle and needle in raw:
        idx = raw.index(needle)
        hits.append(
            {
                "kind": "verbatim",
                "needle": needle,
                "index": idx,
                "snippet": raw[max(0, idx - 24) : idx + len(needle) + 24],
            }
        )
    lowered = raw.lower()
    if needle and needle.lower() in lowered and needle not in raw:
        idx = lowered.index(needle.lower())
        hits.append(
            {
                "kind": "verbatim-casefold",
                "needle": needle,
                "index": idx,
                "snippet": raw[max(0, idx - 24) : idx + len(needle) + 24],
            }
        )
    if paraphrase:
        norm = _norm(raw)
        if PARAPHRASE_SERIAL.lower() in norm:
            hits.append(
                {
                    "kind": "paraphrase-serial",
                    "needle": PARAPHRASE_SERIAL,
                    "index": norm.find(PARAPHRASE_SERIAL.lower()),
                    "snippet": PARAPHRASE_SERIAL,
                }
            )
        if _window_has_trigram(norm, PARAPHRASE_TRIGRAM):
            hits.append(
                {
                    "kind": "paraphrase-trigram",
                    "needle": " ".join(PARAPHRASE_TRIGRAM),
                    "index": 0,
                    "snippet": f"{FACT_COLOR} {FACT_OBJECT} serial",
                }
            )
    # Dedup by kind.
    seen = set()
    out = []
    for h in hits:
        key = (h["kind"], h["needle"])
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


def search_streams(
    streams: Iterable[dict],
    needle: str,
    paraphrase: bool,
) -> list[dict]:
    rows = []
    for stream in streams:
        text = str(stream.get("text") or "")
        hits = search_text(text, needle, paraphrase=paraphrase)
        rows.append(
            {
                "stream": stream["stream"],
                "participant": stream["participant"],
                "haystack_bytes": len(text.encode("utf-8")),
                "hits": hits,
                "hit_count": len(hits),
            }
        )
    return rows


def any_hits(rows: list[dict]) -> bool:
    return any(r.get("hit_count") for r in rows)


def partition_needles() -> tuple[str, bool]:
    return PARTITION_CANARY, True


def control_needles() -> tuple[str, bool]:
    return CONTROL_CANARY, False
