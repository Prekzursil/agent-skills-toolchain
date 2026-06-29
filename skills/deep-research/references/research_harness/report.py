"""Cited-report assembly for the deep-research harness (M-16).

Extends the deep-research Step-5 markdown template with (a) inline *numbered*
citations + a tiered references section, and (b) grading + cache/preflight
provenance. The Methodology section reports routed providers, cache hit/miss,
and any provider that was DOWN at preflight - machine-checkable honesty for the
base skill's "acknowledge gaps" rule.
"""

from dataclasses import dataclass, field

from .grading import Grade, Source, overall_confidence


@dataclass(frozen=True, slots=True)
class Citation:
    """A numbered reference: an index bound to a graded source."""

    index: int
    source: Source
    grade: Grade


@dataclass(frozen=True, slots=True)
class Claim:
    """One finding plus the citation indexes that back it."""

    text: str
    citation_indexes: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Theme:
    """A report section: a titled group of claims."""

    title: str
    claims: tuple[Claim, ...]


@dataclass(frozen=True, slots=True)
class Methodology:
    """Provenance facts surfaced in the report's Methodology section."""

    subquestions: tuple[str, ...] = ()
    providers_routed: tuple[str, ...] = ()
    cache_hits: int = 0
    cache_misses: int = 0
    providers_down: tuple[str, ...] = ()
    stale_allowed: bool = False


@dataclass(frozen=True, slots=True)
class Report:
    """Assembled report inputs (rendered to markdown by ``render``)."""

    topic: str
    generated: str
    summary: str
    themes: tuple[Theme, ...]
    citations: tuple[Citation, ...]
    methodology: Methodology
    takeaways: tuple[str, ...] = field(default_factory=tuple)


def build_citations(graded_sources: list[tuple[Source, Grade]]) -> tuple[Citation, ...]:
    """Assign sequential 1-based indexes to (source, grade) pairs."""
    return tuple(
        Citation(index=i, source=src, grade=grade)
        for i, (src, grade) in enumerate(graded_sources, start=1)
    )


def _citation_marker(indexes: tuple[int, ...]) -> str:
    return "".join(f"[{i}]" for i in indexes)


def _provenance_for(indexes: tuple[int, ...], by_index: dict[int, Citation]) -> str:
    tags = [by_index[i].grade.provenance for i in indexes if i in by_index]
    return " ".join(tags)


def render(report: Report) -> str:
    """Render the assembled report to a cited markdown string."""
    by_index = {c.index: c for c in report.citations}
    grades = [c.grade for c in report.citations]
    confidence = overall_confidence(grades) if grades else "Low"
    providers = ", ".join(report.methodology.providers_routed) or "none"

    lines: list[str] = []
    lines.append(f"# {report.topic}: Research Report")
    lines.append(
        f"*Generated: {report.generated} | Sources: {len(report.citations)} | "
        f"Providers: {providers} | Confidence: {confidence}*"
    )
    lines.append(
        f"*Cache: {report.methodology.cache_hits} hits / "
        f"{report.methodology.cache_misses} misses | "
        f"Stale-allowed: {'yes' if report.methodology.stale_allowed else 'no'}*"
    )
    lines.append("")
    lines.append("## Executive Summary")
    lines.append(report.summary)
    lines.append("")

    for n, theme in enumerate(report.themes, start=1):
        lines.append(f"## {n}. {theme.title}")
        for claim in theme.claims:
            marker = _citation_marker(claim.citation_indexes)
            provenance = _provenance_for(claim.citation_indexes, by_index)
            suffix = f" {marker}" if marker else ""
            if provenance:
                suffix += f" `{provenance}`"
            lines.append(f"- {claim.text}{suffix}")
        lines.append("")

    if report.takeaways:
        lines.append("## Key Takeaways")
        for takeaway in report.takeaways:
            lines.append(f"- {takeaway}")
        lines.append("")

    lines.append("## Sources")
    for citation in report.citations:
        src = citation.source
        year = src.published_year if src.published_year is not None else "n.d."
        lines.append(
            f"{citation.index}. [{src.title}]({src.url}) "
            f"- tier {citation.grade.tier} - {src.provider} ({year})"
        )
    lines.append("")

    lines.append("## Methodology")
    if report.methodology.subquestions:
        lines.append("Sub-questions investigated:")
        for sq in report.methodology.subquestions:
            lines.append(f"- {sq}")
    lines.append(f"Providers routed: {providers}.")
    lines.append(
        f"Cache: {report.methodology.cache_hits} hits, "
        f"{report.methodology.cache_misses} misses."
    )
    down = ", ".join(report.methodology.providers_down) or "none"
    lines.append(f"Providers down at preflight: {down}.")

    return "\n".join(lines).rstrip() + "\n"
