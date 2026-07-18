"""``report_doc`` — the generic document-IR the shared renderers consume.

A ``ReportDoc`` is a domain-neutral, immutable description of a report: a title, an
**injected** ``generated_at`` (never stamped at render time, so output is
deterministic), ordered provenance metadata, a coarse rollup, a redaction/active
notice pair, and a tree of :data:`Block` s. ``monitorcore.render_md`` /
``monitorcore.render_html`` turn a ``ReportDoc`` into Markdown / HTML; any monitor
source maps its native model to a ``ReportDoc`` (e.g. wfmon's ``export_model``) and
renders "for free" through the shared renderers.

The block vocabulary is intentionally **thin and non-speculative** — the six generic
primitives a report needs today: ``Heading``, ``Text``, ``Code``, ``KV``, ``Table``,
``Section``. ``Section`` doubles as a *group* (a titled container of child blocks —
wfmon's phase) and, when ``card=True``, as an *entity card* (a titled record with a
badge, a metadata row, an optional :class:`~monitorcore.timeline.TimelineEvent`
stream, a lead line, a quoted task, and an output body — wfmon's agent). No
FEP/training-specific block types are pre-added; PR-D/E grows the vocabulary against a
second real source shape.

Redaction, ANSI-stripping, base64 elision, truncation and fence/HTML-escaping are
applied by the renderers in their format-specific order (they differ between Markdown
and HTML), so blocks carry **raw** strings plus a ``redact`` opt-in flag; the renderer
threads a single ``Redactor`` and reports the final mask count in the audit banner.
"""

from __future__ import annotations

from dataclasses import dataclass

from .timeline import TimelineEvent


@dataclass(frozen=True)
class Heading:
    """A section heading at ``level`` (1-6) with an optional HTML ``anchor`` id."""

    text: str
    level: int = 2
    anchor: str = ""


@dataclass(frozen=True)
class Text:
    """A free-text run. ``variant`` ∈ {'', 'blockquote', 'emphasis'}; ``redact`` opts
    the content into the render-path secret pipeline (default off for structural text)."""

    text: str
    variant: str = ""
    redact: bool = False


@dataclass(frozen=True)
class Code:
    """A fenced (Markdown) / ``<pre>`` (HTML) code block. ``label`` prefixes it with an
    uppercase caption; ``redact`` (default on) routes the body through the secret pipeline."""

    text: str
    label: str = ""
    redact: bool = True


@dataclass(frozen=True)
class KV:
    """An ordered key/value list (a definition list in HTML, a bullet list in Markdown)."""

    pairs: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Table:
    """A simple header + rows table (GFM pipe table in Markdown, ``<table>`` in HTML)."""

    headers: tuple[str, ...] = ()
    rows: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class Section:
    """A titled document section.

    As a **group** (``card=False``): a ``title`` (+ optional ``index``/``anchor``) over
    ``children`` blocks — the renderers derive the table-of-contents and fan-out graph
    from a two-level group→card tree.

    As an **entity card** (``card=True``): a titled record with a ``badge`` state, a
    metadata row (``model``/``tokens``/``tool_calls``/``attempt``/``duration_ms``), an
    optional ``lead`` line, a quoted ``task``, a ``timeline`` event stream, and an
    ``output`` body — the raw fields the renderers format per target syntax.
    """

    title: str
    anchor: str = ""
    index: int = 0
    card: bool = False
    badge: str = ""
    model: str = ""
    tokens: int = 0
    tool_calls: int = 0
    attempt: int = 1
    duration_ms: int = 0
    lead: str = ""
    task: str = ""
    output: str = ""
    timeline: tuple[TimelineEvent, ...] = ()
    children: tuple["Block", ...] = ()


Block = Heading | Text | Code | KV | Table | Section


@dataclass(frozen=True)
class ReportDoc:
    """A rendered-ready, deterministic report.

    ``title``/``subtitle`` head the document; ``generated_at`` is INJECTED (pinnable for
    golden tests). ``meta`` is the ordered provenance surfaced as front-matter / head
    meta / a header list; ``rollup`` is the coarse count line; ``active`` and
    ``redaction_mode`` drive the notice banners (the redaction mask *count* is computed
    by the renderer while it walks the content). ``blocks`` is the body (top-level =
    group sections).
    """

    title: str
    generated_at: str
    blocks: tuple[Block, ...] = ()
    subtitle: str = ""
    meta: tuple[tuple[str, str], ...] = ()
    rollup: tuple[tuple[str, int], ...] = ()
    active: bool = False
    redaction_mode: str = "strict"
