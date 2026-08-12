"""Lawful academic-record normalization and deduplication.

The module consolidates discovery/resolver duplicates while preserving both
provider provenance and publication status.  It deliberately does not equate a
preprint, peer-reviewed primary study, review, standard, or dataset.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

PUBLICATION_TYPES = frozenset(
    {
        "peer_reviewed_primary",
        "systematic_review",
        "review",
        "preprint",
        "standard",
        "dataset",
        "unknown",
    }
)

_TYPE_ORDER = {
    "systematic_review": 0,
    "peer_reviewed_primary": 1,
    "review": 2,
    "standard": 3,
    "dataset": 4,
    "preprint": 5,
    "unknown": 6,
}


def normalize_doi(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    normalized = re.sub(r"^doi\s*:\s*", "", normalized)
    normalized = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", normalized)
    normalized = normalized.strip().rstrip(".,;)")
    return normalized or None


def normalize_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def canonical_url(value: str | None) -> str | None:
    if not value:
        return None
    parts = urlsplit(value.strip())
    if not parts.scheme or not parts.netloc:
        return value.strip()
    host = parts.netloc.casefold()
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.casefold(), host, path, "", ""))


@dataclass(frozen=True, slots=True)
class AcademicRecord:
    title: str
    provider: str
    doi: str | None = None
    url: str | None = None
    publication_type: str = "unknown"
    year: int | None = None
    authors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("academic record title is required")
        if not self.provider.strip():
            raise ValueError("academic record provider is required")
        if self.publication_type not in PUBLICATION_TYPES:
            raise ValueError(f"unknown publication_type: {self.publication_type}")


@dataclass(frozen=True, slots=True)
class ConsolidatedPaper:
    canonical_id: str
    title: str
    doi: str | None
    url: str | None
    year: int | None
    authors: tuple[str, ...]
    providers: tuple[str, ...]
    publication_types: tuple[str, ...]


def _completeness(record: AcademicRecord) -> tuple[int, int]:
    score = sum(
        (
            normalize_doi(record.doi) is not None,
            canonical_url(record.url) is not None,
            record.year is not None,
            bool(record.authors),
            record.publication_type != "unknown",
        )
    )
    return score, len(record.title.strip())


def _unique(values):
    return tuple(dict.fromkeys(value for value in values if value))


def consolidate_academic_records(
    records: tuple[AcademicRecord, ...],
) -> tuple[ConsolidatedPaper, ...]:
    """Deduplicate DOI/URL/title variants while preserving evidence classes."""
    # Strong identifiers merge first. A weak title may attach a title-only
    # discovery record to one unambiguous strong component, but it must never
    # collapse two different DOIs/URLs that happen to share a generic title.
    parents = list(range(len(records)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            return
        first, second = sorted((left_root, right_root))
        parents[second] = first

    by_doi: dict[str, list[int]] = {}
    for index, record in enumerate(records):
        doi = normalize_doi(record.doi)
        if doi:
            by_doi.setdefault(doi, []).append(index)
    for indexes in by_doi.values():
        for index in indexes[1:]:
            union(indexes[0], index)

    by_url: dict[str, list[int]] = {}
    for index, record in enumerate(records):
        url = canonical_url(record.url)
        if url:
            by_url.setdefault(url, []).append(index)

    def component_dois() -> dict[int, set[str]]:
        result: dict[int, set[str]] = {}
        for index, record in enumerate(records):
            doi = normalize_doi(record.doi)
            if doi:
                result.setdefault(find(index), set()).add(doi)
        return result

    for indexes in by_url.values():
        roots = tuple(dict.fromkeys(find(index) for index in indexes))
        if len(roots) < 2:
            continue
        dois_by_root = component_dois()
        distinct_dois = set().union(*(dois_by_root.get(root, set()) for root in roots))
        if len(distinct_dois) <= 1:
            for root in roots[1:]:
                union(roots[0], root)
        else:
            # The URL metadata conflicts. Preserve each DOI component and keep
            # any DOI-less records together as an explicit ambiguous group.
            doi_less = [root for root in roots if not dois_by_root.get(root)]
            for root in doi_less[1:]:
                union(doi_less[0], root)

    by_title: dict[str, list[int]] = {}
    for index, record in enumerate(records):
        by_title.setdefault(normalize_title(record.title), []).append(index)

    def component_has_strong_identity(root: int) -> bool:
        return any(
            find(index) == root
            and (
                normalize_doi(record.doi) is not None
                or canonical_url(record.url) is not None
            )
            for index, record in enumerate(records)
        )

    for indexes in by_title.values():
        roots = tuple(dict.fromkeys(find(index) for index in indexes))
        strong = [root for root in roots if component_has_strong_identity(root)]
        weak = [root for root in roots if root not in strong]
        if len(strong) == 1:
            for root in weak:
                union(strong[0], root)
        elif not strong and roots:
            for root in roots[1:]:
                union(roots[0], root)
        elif weak:
            for root in weak[1:]:
                union(weak[0], root)

    groups: dict[int, list[AcademicRecord]] = {}
    for index, record in enumerate(records):
        groups.setdefault(find(index), []).append(record)

    consolidated: list[ConsolidatedPaper] = []
    for group in groups.values():
        primary = max(group, key=_completeness)
        dois = _unique(normalize_doi(record.doi) for record in group)
        urls = _unique(canonical_url(record.url) for record in group)
        canonical_id = (
            f"doi:{dois[0]}"
            if dois
            else f"url:{urls[0]}"
            if urls
            else f"title:{normalize_title(primary.title)}"
        )
        years = [record.year for record in group if record.year is not None]
        authors = _unique(author for record in group for author in record.authors)
        providers = _unique(record.provider for record in group)
        publication_types = tuple(
            sorted(
                set(record.publication_type for record in group),
                key=lambda item: _TYPE_ORDER[item],
            )
        )
        consolidated.append(
            ConsolidatedPaper(
                canonical_id=canonical_id,
                title=primary.title.strip(),
                doi=dois[0] if dois else None,
                url=canonical_url(primary.url) or (urls[0] if urls else None),
                year=max(years) if years else None,
                authors=authors,
                providers=providers,
                publication_types=publication_types,
            )
        )
    return tuple(consolidated)
