#!/usr/bin/env python3
"""Extract cited source classes and research modes from an emitted record.

Coverage is read from citation-bearing fields on the OUTPUT, never from a
unit plan (catalog row, planned_*, source_policy, inputs, title).
"""
from __future__ import annotations

from typing import Any, Iterable

from canon import (
    CITATION_CONTAINERS,
    CITED_CLASS_KEYS,
    CITED_MODE_KEYS,
    CLASS_ALIASES,
    MODE_ALIASES,
    PLAN_KEYS,
    RESEARCH_MODES,
    SOURCE_CLASSES,
)


def _norm(value: str) -> str:
    return str(value).strip().lower().replace("_", "-").replace(" ", "-")


def _alias_table(kind: str) -> dict[str, str]:
    table = CLASS_ALIASES if kind == "class" else MODE_ALIASES
    out: dict[str, str] = {}
    for spec_id, aliases in table.items():
        for alias in aliases:
            out[_norm(alias)] = spec_id
    return out


_CLASS_MAP = _alias_table("class")
_MODE_MAP = _alias_table("mode")


def resolve_class(token: str) -> str | None:
    return _CLASS_MAP.get(_norm(token))


def resolve_mode(token: str) -> str | None:
    return _MODE_MAP.get(_norm(token))


def _tokens(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for item in value:
            out.extend(_tokens(item))
        return out
    return []


def _source_has_fetch_marker(obj: dict) -> bool:
    """A citation object counts when it carries a fetch address plus integrity."""
    has_addr = any(
        obj.get(k)
        for k in ("url", "permalink", "resolved_url", "final_url")
    )
    has_integrity = any(
        obj.get(k)
        for k in (
            "sha256",
            "snapshot_sha256",
            "bytes_sha256",
            "http_status",
            "fetch_timestamp",
            "fetched_at",
        )
    )
    return bool(has_addr and has_integrity)


def classify_url(url: str) -> str | None:
    """Map a fetched URL onto a spec source-class. Unknown hosts return None."""
    u = str(url).strip().lower()
    if not u.startswith(("http://", "https://")):
        return None
    if ".onion" in u or "onion." in u:
        return "public-tor"
    if "/issues/" in u or "/pull/" in u or "/issue/" in u:
        return "issue-tracker"
    if "arxiv.org" in u or "doi.org" in u or "jstor.org" in u:
        return "papers"
    if (
        "npmjs.org" in u
        or "npmjs.com" in u
        or "pypi.org" in u
        or "crates.io" in u
        or "packagist.org" in u
    ):
        return "package-registries"
    if "web.archive.org" in u or "softwareheritage.org" in u:
        return "archival"
    if "ietf.org" in u or "/rfc/" in u:
        return "standards-regulatory"
    if "/blog/" in u or "medium.com" in u or "substack.com" in u:
        return "blogs"
    if (
        "/docs/" in u
        or "developer." in u
        or "docs." in u
        or "code.claude.com/docs" in u
    ):
        return "official-docs"
    if (
        "github.com" in u
        or "githubusercontent.com" in u
        or "gitlab.com" in u
    ):
        return "source-code"
    return None


def cited_from_record(doc: Any, *, unit_id: str | None = None) -> dict[str, Any]:
    """Return spec-id sets actually cited in an emitted JSON record."""
    classes: set[str] = set()
    modes: set[str] = set()
    planned_ignored: list[str] = []

    def take_class(raw: Any) -> None:
        for tok in _tokens(raw):
            spec = resolve_class(tok)
            if spec in SOURCE_CLASSES:
                classes.add(spec)

    def take_mode(raw: Any) -> None:
        for tok in _tokens(raw):
            spec = resolve_mode(tok)
            if spec in RESEARCH_MODES:
                modes.add(spec)

    def walk(node: Any, *, in_citation: bool, parent_key: str | None) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item, in_citation=in_citation, parent_key=parent_key)
            return
        if not isinstance(node, dict):
            return
        if _source_has_fetch_marker(node):
            for addr_key in ("url", "permalink", "resolved_url", "final_url"):
                spec = classify_url(str(node.get(addr_key) or ""))
                if spec in SOURCE_CLASSES:
                    classes.add(spec)
        for key, val in node.items():
            if not isinstance(key, str):
                continue
            if key in PLAN_KEYS:
                # Record that a plan field existed so probes can prove it
                # did not increment coverage.
                for tok in _tokens(val):
                    spec = resolve_class(tok) or resolve_mode(tok)
                    if spec:
                        planned_ignored.append(f"{key}:{spec}")
                # Do not recurse into plan blobs (catalog-shaped objects).
                continue
            if key in CITED_CLASS_KEYS:
                # A sources[] stub with a class label but no fetch marker
                # is still a plan, not a citation.
                if parent_key == "sources" and isinstance(node, dict):
                    if not _source_has_fetch_marker(node):
                        continue
                take_class(val)
                continue
            if key in CITED_MODE_KEYS:
                take_mode(val)
                continue
            child_is_citation = in_citation or key in CITATION_CONTAINERS
            if child_is_citation and key in {"source_class", "cited_source_class"}:
                if parent_key == "sources" and isinstance(node, dict):
                    if not _source_has_fetch_marker(node):
                        continue
                take_class(val)
                continue
            if child_is_citation and key in {"research_mode", "cited_research_mode"}:
                take_mode(val)
                continue
            walk(val, in_citation=child_is_citation, parent_key=key)

    walk(doc, in_citation=False, parent_key=None)
    uid = unit_id
    if uid is None and isinstance(doc, dict):
        maybe = doc.get("unit_id") or doc.get("id")
        if isinstance(maybe, str) and maybe.startswith("RES-"):
            uid = maybe
    return {
        "unit_id": uid,
        "classes": sorted(classes),
        "modes": sorted(modes),
        "planned_fields_ignored": planned_ignored,
    }


def cited_from_records(records: Iterable[tuple[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for uid, doc in records:
        rows.append(cited_from_record(doc, unit_id=uid))
    return rows
