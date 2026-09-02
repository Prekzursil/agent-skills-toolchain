#!/usr/bin/env python3
"""Classify a re-fetch against a citation-time snapshot and claimed passage."""
from __future__ import annotations

from fetch import FetchResult, is_onion_url, sha256_bytes

CLASSES = (
    "intact",
    "moved",
    "changed-but-still-supporting",
    "changed-and-no-longer-supporting",
    "dead",
    "source-unreachable",
    "blocked-external",
    "snapshot-missing",
    "tor-derived-corroborated",
    "tor-derived-uncorroborated",
    "vendor-529",
    "soft-error",
)


def passage_in(body: bytes, passage: str) -> bool:
    if not passage or not body:
        return False
    text = body.decode("utf-8", "replace")
    if passage in text:
        return True
    parts = [p.strip() for p in passage.split(";") if len(p.strip()) >= 8]
    if len(parts) > 1 and all(p in text for p in parts):
        return True
    norm_t = " ".join(text.split())
    norm_p = " ".join(passage.split())
    return bool(norm_p) and norm_p in norm_t


def support_verdict(classification: str, passage_found: bool, status: int | None) -> str:
    if classification in {
        "dead",
        "source-unreachable",
        "blocked-external",
        "snapshot-missing",
        "vendor-529",
        "soft-error",
        "tor-derived-uncorroborated",
    }:
        return "DOES-NOT-SUPPORT" if classification in {"dead", "changed-and-no-longer-supporting"} else "NOT-APPLICABLE"
    if classification == "changed-and-no-longer-supporting":
        return "DOES-NOT-SUPPORT"
    if classification in {
        "intact",
        "moved",
        "changed-but-still-supporting",
        "tor-derived-corroborated",
    }:
        return "SUPPORTS" if passage_found else "DOES-NOT-SUPPORT"
    if status is not None and 200 <= status < 400:
        return "SUPPORTS" if passage_found else "DOES-NOT-SUPPORT"
    return "NOT-APPLICABLE"


def classify(
    fetched: FetchResult,
    *,
    snapshot_sha256: str | None,
    passage: str,
    corroboration_hit: bool = False,
) -> dict:
    url = fetched.url
    passage_found = passage_in(fetched.body, passage) if fetched.body else False
    current = fetched.digest or (sha256_bytes(fetched.body) if fetched.body else None)

    if fetched.onion_skipped or is_onion_url(url):
        klass = "tor-derived-corroborated" if corroboration_hit else "tor-derived-uncorroborated"
        return _row(fetched, klass, snapshot_sha256, current, passage, passage_found)

    if fetched.blocked_third:
        return _row(fetched, "blocked-external", snapshot_sha256, current, passage, False)

    if fetched.status in {404, 410} or fetched.error_class in {"dead", "dead-dns"}:
        return _row(fetched, "dead", snapshot_sha256, current, passage, False)

    if fetched.status == 529 or fetched.error_class == "vendor-529":
        return _row(fetched, "vendor-529", snapshot_sha256, current, passage, False)

    if (fetched.status in {500, 502, 503, 504}) or fetched.error_class == "soft":
        return _row(fetched, "soft-error", snapshot_sha256, current, passage, False)

    if not fetched.ok_http:
        return _row(fetched, "source-unreachable", snapshot_sha256, current, passage, False)

    if fetched.redirected:
        klass = "moved" if passage_found else "changed-and-no-longer-supporting"
        return _row(fetched, klass, snapshot_sha256, current, passage, passage_found)

    if not snapshot_sha256:
        return _row(fetched, "snapshot-missing", snapshot_sha256, current, passage, passage_found)

    if current == snapshot_sha256 and passage_found:
        return _row(fetched, "intact", snapshot_sha256, current, passage, True)
    if current == snapshot_sha256 and not passage_found:
        return _row(
            fetched,
            "changed-and-no-longer-supporting",
            snapshot_sha256,
            current,
            passage,
            False,
        )
    if current != snapshot_sha256 and passage_found:
        return _row(
            fetched,
            "changed-but-still-supporting",
            snapshot_sha256,
            current,
            passage,
            True,
        )
    return _row(
        fetched,
        "changed-and-no-longer-supporting",
        snapshot_sha256,
        current,
        passage,
        False,
    )


def _row(
    fetched: FetchResult,
    klass: str,
    snapshot: str | None,
    current: str | None,
    passage: str,
    passage_found: bool,
) -> dict:
    support = support_verdict(klass, passage_found, fetched.status)
    if klass == "changed-and-no-longer-supporting":
        support = "DOES-NOT-SUPPORT"
    if klass in {"intact", "moved", "changed-but-still-supporting"} and not passage_found:
        support = "DOES-NOT-SUPPORT"
    if klass in {"intact", "moved", "changed-but-still-supporting"} and passage_found:
        support = "SUPPORTS"
    if klass == "tor-derived-corroborated":
        support = "SUPPORTS"
    if not (passage or "").strip() and klass not in {"dead", "blocked-external", "vendor-529", "soft-error"}:
        support = "NOT-APPLICABLE"
    http_status = fetched.status
    return {
        "url": fetched.url,
        "final_url": fetched.final_url,
        "classification": klass,
        "http_status": http_status,
        "snapshot_sha256": snapshot,
        "current_sha256": current,
        "passage": passage,
        "passage_found": passage_found,
        "support_verdict": support,
        "fetched_as_data": True,
        "tool_calls": list(fetched.tool_calls),
        "instruction_shaped": list(fetched.instruction_shaped),
        "onion_skipped": fetched.onion_skipped,
        "redirected": fetched.redirected,
        "redirect_chain": list(fetched.redirect_chain),
        "error": fetched.error,
        "error_class": fetched.error_class,
        "blocked_third": fetched.blocked_third,
        "prerequisite": fetched.prerequisite,
        "attempts": fetched.attempts,
        "slept_s": fetched.slept_s,
    }
