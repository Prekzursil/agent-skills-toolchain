"""Cited-report assembly for the deep-research harness (M-16).

Extends the deep-research Step-5 markdown template with (a) inline *numbered*
citations + a tiered references section, and (b) grading + cache/preflight
provenance. The Methodology section reports routed providers, cache hit/miss,
and any provider that was DOWN at preflight - machine-checkable honesty for the
base skill's "acknowledge gaps" rule.

Terminal-state taxonomy (Lens 12 find 2): a run ends in exactly one of
``REPORT_STATUSES``. ``partial:*`` is *degraded success* - the renderer ALWAYS
emits whatever evidence exists plus an "Unanswered sub-questions" section - and
is counted apart from ``failed`` by ``summarize_statuses`` so a run that died
on the box is distinguishable from a run that answered wrongly.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

from .grading import Grade, Source, overall_confidence

STATUS_COMPLETE = "complete"
STATUS_PARTIAL_BUDGET = "partial:budget"  # call/token budget hit ``finalize``
STATUS_PARTIAL_SOURCES = "partial:sources"  # sufficiency gate left questions open
STATUS_PARTIAL_TIMEOUT = "partial:timeout"  # wall-clock axis was the binding one
STATUS_PARTIAL_LOOP = "partial:loop"  # loop guard tripped (repeated queries)
STATUS_FAILED = "failed"  # nothing usable; still rendered with its gaps
REPORT_STATUSES = frozenset(
    {
        STATUS_COMPLETE,
        STATUS_PARTIAL_BUDGET,
        STATUS_PARTIAL_SOURCES,
        STATUS_PARTIAL_TIMEOUT,
        STATUS_PARTIAL_LOOP,
        STATUS_FAILED,
    }
)
_PARTIAL_PREFIX = "partial:"


def status_family(status: str) -> str:
    """Collapse a status to ``complete`` / ``partial`` / ``failed``."""
    if status not in REPORT_STATUSES:
        raise ValueError(f"unknown report status: {status!r}")
    if status.startswith(_PARTIAL_PREFIX):
        return "partial"
    return status


@dataclass(frozen=True, slots=True)
class StatusSummary:
    """Run-outcome tallies with ``partial:*`` counted apart from ``failed``."""

    total: int
    complete: int
    partial: int
    failed: int
    partial_by_kind: dict[str, int]

    @property
    def complete_rate(self) -> float:
        return self.complete / self.total if self.total else 0.0

    @property
    def delivered_rate(self) -> float:
        """Share of runs that shipped a report (complete + partial)."""
        return (self.complete + self.partial) / self.total if self.total else 0.0

    @property
    def line(self) -> str:
        kinds = ", ".join(f"{k}={v}" for k, v in sorted(self.partial_by_kind.items()))
        detail = f" ({kinds})" if kinds else ""
        return (
            f"runs={self.total} complete={self.complete} "
            f"partial={self.partial}{detail} failed={self.failed}"
        )


def summarize_statuses(statuses: Iterable[str]) -> StatusSummary:
    """Tally terminal states; ``partial:*`` is never folded into ``failed``."""
    families = Counter()
    partial_kinds: Counter[str] = Counter()
    total = 0
    for status in statuses:
        family = status_family(status)
        families[family] += 1
        total += 1
        if family == "partial":
            partial_kinds[status] += 1
    return StatusSummary(
        total=total,
        complete=families["complete"],
        partial=families["partial"],
        failed=families["failed"],
        partial_by_kind=dict(partial_kinds),
    )


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
    # Terminal state of the run that produced this report (``REPORT_STATUSES``)
    # and the sub-questions it never answered. ``complete`` may not carry open
    # sub-questions; ``partial:*``/``failed`` may (and usually do).
    status: str = STATUS_COMPLETE
    open_subquestions: tuple[str, ...] = field(default_factory=tuple)
    # Rendered "Disputed" callouts (``conflicts.Dispute.callout``) for claims
    # whose sources quote incompatible values. Plain strings keep the renderer
    # data-only; a dispute is honest disagreement and does not change ``status``.
    disputes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.status not in REPORT_STATUSES:
            raise ValueError(f"unknown report status: {self.status!r}")
        if self.status == STATUS_COMPLETE and self.open_subquestions:
            raise ValueError("a complete report cannot carry open sub-questions")

    @property
    def is_partial(self) -> bool:
        return status_family(self.status) == "partial"


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
        f"Stale-allowed: {'yes' if report.methodology.stale_allowed else 'no'} | "
        f"Status: {report.status}*"
    )
    lines.append("")
    lines.append("## Executive Summary")
    lines.append(report.summary)
    lines.append("")

    # A partial/failed run still ships everything it has; the gaps are named
    # up front so a reader never mistakes degraded success for a full answer.
    if report.status != STATUS_COMPLETE:
        lines.append("## Unanswered sub-questions")
        lines.append(
            f"The run ended `{report.status}`; the following sub-questions were "
            "not answered (or not to the sufficiency bar):"
        )
        if report.open_subquestions:
            for sq in report.open_subquestions:
                lines.append(f"- {sq}")
        else:
            lines.append("- (none recorded)")
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

    # Contradicted claims are shown with BOTH values rather than silently
    # resolved to one; each callout names the grading-preferred citation.
    if report.disputes:
        lines.append("## Disputed claims")
        for callout in report.disputes:
            lines.append(f"> {callout}")
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
    lines.append(f"Terminal state: {report.status}.")

    return "\n".join(lines).rstrip() + "\n"
