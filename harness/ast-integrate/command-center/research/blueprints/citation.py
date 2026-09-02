"""Fact/citation audit: unfetchable citations are UNRESOLVED, never assumed valid."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

UNRESOLVED = "UNRESOLVED"
RESOLVED = "RESOLVED"
NAIVE_MUTANT = "NAIVE_ASSUME_UNFETCHABLE_VALID"

FetchFn = Callable[[Mapping[str, Any]], "FetchResult"]


@dataclass
class FetchResult:
    ok: bool
    reason: str
    body: str | None = None


@dataclass
class CitationVerdict:
    id: str
    url: str
    quoted_span: str
    status: str
    fetch_ok: bool
    fetch_reason: str
    quote_found: bool | None
    assumed_valid: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditResult:
    verdicts: list[CitationVerdict]
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def citation_count(self) -> int:
        return len(self.verdicts)

    @property
    def unresolved_ids(self) -> list[str]:
        return [v.id for v in self.verdicts if v.status == UNRESOLVED]

    @property
    def assumed_valid_count(self) -> int:
        return sum(1 for v in self.verdicts if v.assumed_valid)

    @property
    def coverage(self) -> float:
        if not self.verdicts:
            return 1.0
        scored = sum(1 for v in self.verdicts if v.status)
        return scored / len(self.verdicts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "assumed_valid_count": self.assumed_valid_count,
            "citation_count": self.citation_count,
            "coverage": self.coverage,
            "extra": dict(self.extra),
            "unresolved_ids": self.unresolved_ids,
            "verdicts": [v.to_dict() for v in self.verdicts],
        }


def fetch_citation(citation: Mapping[str, Any] | str) -> FetchResult:
    """Fetch a citation body. file:// only (hermetic). Missing path is not-found."""
    url = citation if isinstance(citation, str) else str(citation.get("url") or "")
    parsed = urlparse(url)
    if parsed.scheme not in {"file", ""}:
        return FetchResult(ok=False, reason="unsupported-scheme", body=None)
    if parsed.scheme == "file":
        path = Path(url2pathname(unquote(parsed.path)))
    else:
        path = Path(url)
    try:
        if not path.is_file():
            return FetchResult(ok=False, reason="not-found", body=None)
        return FetchResult(ok=True, reason="ok", body=path.read_text(encoding="utf-8"))
    except OSError:
        return FetchResult(ok=False, reason="not-found", body=None)


def _verdict_from_fetch(
    citation: Mapping[str, Any], fetched: FetchResult, *, assume_valid: bool
) -> CitationVerdict:
    cid = str(citation.get("id") or "")
    url = str(citation.get("url") or "")
    span = str(citation.get("quoted_span") or "")
    if not fetched.ok:
        if assume_valid:
            return CitationVerdict(
                id=cid,
                url=url,
                quoted_span=span,
                status=RESOLVED,
                fetch_ok=False,
                fetch_reason=fetched.reason,
                quote_found=None,
                assumed_valid=True,
            )
        status=UNRESOLVED
        return CitationVerdict(
            id=cid,
            url=url,
            quoted_span=span,
            status=status,
            fetch_ok=False,
            fetch_reason=fetched.reason,
            quote_found=None,
            assumed_valid=False,
        )
    body = fetched.body or ""
    found = span in body if span else False
    if found:
        return CitationVerdict(
            id=cid,
            url=url,
            quoted_span=span,
            status=RESOLVED,
            fetch_ok=True,
            fetch_reason=fetched.reason,
            quote_found=True,
            assumed_valid=False,
        )
    status=UNRESOLVED
    return CitationVerdict(
        id=cid,
        url=url,
        quoted_span=span,
        status=status,
        fetch_ok=True,
        fetch_reason=fetched.reason,
        quote_found=False,
        assumed_valid=False,
    )


def audit_citations(
    citations: Iterable[Mapping[str, Any]],
    fetch: FetchFn | None = None,
) -> AuditResult:
    """Honest auditor: a citation that cannot be fetched is UNRESOLVED."""
    fetch_fn = fetch or fetch_citation
    verdicts: list[CitationVerdict] = []
    for cite in citations:
        fetched = fetch_fn(cite)
        verdicts.append(_verdict_from_fetch(cite, fetched, assume_valid=False))
    return AuditResult(verdicts=verdicts, extra={})


def naive_assume_unfetchable_valid(
    citations: Iterable[Mapping[str, Any]],
    fetch: FetchFn | None = None,
) -> AuditResult:
    """Known-broken mutant: treat unfetchable citations as RESOLVED."""
    fetch_fn = fetch or fetch_citation
    verdicts: list[CitationVerdict] = []
    for cite in citations:
        fetched = fetch_fn(cite)
        verdicts.append(_verdict_from_fetch(cite, fetched, assume_valid=True))
    return AuditResult(
        verdicts=verdicts,
        extra={"mutant": NAIVE_MUTANT},
    )
