#!/usr/bin/env python3
"""Auto-install bar derived from unit inputs 10855-10858 and 11346.

Recomputed from captured listing + package bytes. A hub survey with zero
failing packages is treated as unsampled, not green.
"""
from __future__ import annotations

from typing import Any

REQUIREMENTS = [
    "artifact-provenance: Sigstore/npm provenance (or equivalent) over the exact installable bytes, not merely publisher namespace of metadata",
    "pinned-digest: hub record names a content digest of the bytes that would execute",
    "capability-declaration: machine-readable capabilities; unbounded shell/filesystem/network fails unless owner-allowlisted",
    "review-observed: published review policy AND a per-package review artifact for THIS version (scan report or human review record)",
    "revocation-of-fetched-bytes: hub can tombstone the listing AND consumers can detect that already-fetched copies are invalid (digest mismatch or signature revocation)",
]


def evaluate(pkg: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if not pkg.get("artifact_provenance"):
        reasons.append("missing-artifact-provenance")
    if not pkg.get("content_digest_in_hub_record"):
        reasons.append("missing-pinned-digest")
    if pkg.get("unbounded_exec") or str(pkg.get("capability") or "") in {
        "shell",
        "filesystem-unbounded",
        "remote-arbitrary",
    }:
        reasons.append("excessive-capability")
    depth = str(pkg.get("review_depth") or "NONE")
    if depth in {"NONE", "INFERRED"} and not pkg.get("per_package_review_record"):
        reasons.append("review-not-observed-for-this-version")
    if not pkg.get("revocation_invalidates_fetched_bytes"):
        reasons.append("revocation-metadata-only")
    return {
        "pass": len(reasons) == 0,
        "fail_reasons": reasons,
        "requirements": list(REQUIREMENTS),
    }


def package_from_captures(
    *,
    listing_text: str,
    listing_token: str,
    package_text: str,
    shell_markers: tuple[str, ...],
    provenance_markers: tuple[str, ...],
    review_record_markers: tuple[str, ...],
    digest_in_listing: bool,
) -> dict[str, Any]:
    if listing_token not in listing_text:
        raise AssertionError(f"package token {listing_token!r} not in listing capture")
    unbounded = any(m.lower() in package_text.lower() for m in shell_markers)
    provenance = any(m.lower() in package_text.lower() for m in provenance_markers)
    review_rec = any(m.lower() in listing_text.lower() for m in review_record_markers)
    return {
        "listed": True,
        "listing_token": listing_token,
        "artifact_provenance": provenance,
        "content_digest_in_hub_record": digest_in_listing,
        "unbounded_exec": unbounded,
        "capability": "shell" if unbounded else "unknown",
        "review_depth": "NONE",
        "per_package_review_record": review_rec,
        "revocation_invalidates_fetched_bytes": False,
    }
