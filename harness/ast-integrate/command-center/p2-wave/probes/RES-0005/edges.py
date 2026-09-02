#!/usr/bin/env python3
"""Mechanical edge types for two research sources that disagree (RES-0005).

Types: direct_contradiction, scope_mismatch, version_skew (stale_pointer),
measurement_artifact, independence_collapse, other.
A pair about different subjects yields no edge (None).
"""
from __future__ import annotations

from urllib.parse import urlparse

EDGE_TYPES = (
    "direct_contradiction",
    "scope_mismatch",
    "version_skew",
    "measurement_artifact",
    "independence_collapse",
    "other",
)
GOLD_OK = frozenset({"version_skew", "stale_pointer"})
NO_EDGE = None
DOCS_OLD = "docs.claude.com"
DOCS_NEW = "code.claude.com"


def host(url: str) -> str:
    if not url:
        return ""
    return urlparse(url).netloc.lower().split(":")[0]


def slug(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    if not path:
        return ""
    return path.split("/")[-1].lower()


def github_owner_repo(url: str) -> tuple[str, str] | None:
    parsed = urlparse(url)
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return None
    return parts[0].lower(), parts[1].lower()


def docs_ownership_redirect(url_a: str, url_b: str) -> bool:
    hosts = {host(url_a), host(url_b)}
    if hosts != {DOCS_OLD, DOCS_NEW}:
        return False
    sa, sb = slug(url_a), slug(url_b)
    return bool(sa) and sa == sb


def github_owner_redirect(url_a: str, url_b: str) -> bool:
    ga, gb = github_owner_repo(url_a), github_owner_repo(url_b)
    if not ga or not gb:
        return False
    return ga[1] == gb[1] and ga[0] != gb[0]


def signals(pair: dict) -> dict:
    raw = pair.get("signals")
    return raw if isinstance(raw, dict) else {}


def same_subject(pair: dict) -> bool:
    a = (pair.get("a") or {}).get("subject")
    b = (pair.get("b") or {}).get("subject")
    if a and b:
        return a == b
    subj = (pair.get("subject") or "").strip()
    return bool(subj)


def is_independence_collapse(pair: dict) -> bool:
    sig = signals(pair)
    if pair.get("shared_upstream") or pair.get("same_vendor_same_input") or pair.get("copied_from"):
        return True
    if sig.get("shared_upstream") or sig.get("same_vendor_same_input") or sig.get("copied_from"):
        return True
    sha_a = (pair.get("a") or {}).get("fetch_sha256")
    sha_b = (pair.get("b") or {}).get("fetch_sha256")
    return bool(sha_a) and sha_a == sha_b


def is_stale_pointer(pair: dict) -> bool:
    sig = signals(pair)
    if sig.get("http_redirect") in (301, 302, 307, 308):
        return True
    if sig.get("owner_changed") or sig.get("canonical_host_moved") or sig.get("superseded_tree"):
        return True
    url_a = (pair.get("a") or {}).get("url") or ""
    url_b = (pair.get("b") or {}).get("url") or ""
    return docs_ownership_redirect(url_a, url_b) or github_owner_redirect(url_a, url_b)


def is_scope_mismatch(pair: dict) -> bool:
    scope_a = pair.get("scope_a") or (pair.get("a") or {}).get("scope")
    scope_b = pair.get("scope_b") or (pair.get("b") or {}).get("scope")
    return bool(scope_a) and bool(scope_b) and scope_a != scope_b


def is_measurement_artifact(pair: dict) -> bool:
    sig = signals(pair)
    if pair.get("measurement_method_differs") or sig.get("measurement_method_differs"):
        return True
    for key in (
        "detector_inversion",
        "snapshot_decay_on_write",
        "inferred_not_extracted",
        "spec_derived_not_observed",
        "single_signal_double_count",
    ):
        if sig.get(key) or pair.get(key):
            return True
    return False


def is_direct_contradiction(pair: dict) -> bool:
    if pair.get("incompatible_values") is True:
        return True
    return signals(pair).get("incompatible_values") is True


def classify_edge(pair: dict) -> str | None:
    """Return an edge type, or None when claims must not be linked."""
    if not same_subject(pair):
        return NO_EDGE
    if is_independence_collapse(pair):
        return "independence_collapse"
    if is_stale_pointer(pair):
        return "version_skew"
    if is_scope_mismatch(pair):
        return "scope_mismatch"
    if is_measurement_artifact(pair):
        return "measurement_artifact"
    if is_direct_contradiction(pair):
        return "direct_contradiction"
    return "other"


def gold_classifies_ok(edge_type: str | None) -> bool:
    return edge_type in GOLD_OK


def residual_stats(edge_types: list[str | None]) -> dict:
    linked = [t for t in edge_types if t is not None]
    n = len(linked)
    other = sum(1 for t in linked if t == "other")
    rate = (other / n) if n else 1.0
    return {
        "linked": n,
        "other": other,
        "residual_rate": rate,
        "by_type": {k: sum(1 for t in linked if t == k) for k in EDGE_TYPES},
    }
