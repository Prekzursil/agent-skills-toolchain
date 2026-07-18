"""/biopull rendering LOGIC (WU-1E) — VERBATIM 8-column table + footer.

PURE function (NOT the live skill wiring). Contract is PINNED:

  columns (exact order):
    Source | Target/Assay context | Metric | Value(normalized) |
    Value(as-reported) | n | Confidence | Ref
  default sort: Target (alphabetical), then ascending normalized affinity;
  inline ``!`` disagreement flag (from J) with a footnoted spread;
  footer VERBATIM:
    sources hit: <list> | accessed YYYY-MM-DD | n rows, m flagged
  ``--raw`` escape -> full JSON via :func:`render_raw`.
"""

from __future__ import annotations

import dataclasses
import json

from .datum import Datum

HEADER: list[str] = [
    "Source",
    "Target/Assay context",
    "Metric",
    "Value(normalized)",
    "Value(as-reported)",
    "n",
    "Confidence",
    "Ref",
]

_DISAGREEMENT_PREFIX = "disagreement:"


def _ref(datum: Datum) -> str:
    prov = datum.provenance
    if prov.pmid:
        return prov.pmid
    return f"{prov.db}:{prov.accession}"


def _disagreement(datum: Datum) -> str | None:
    for flag in datum.flags:
        if flag.startswith(_DISAGREEMENT_PREFIX):
            return flag[len(_DISAGREEMENT_PREFIX) :].strip()
    return None


def _fmt_value(value: float | None, unit: str) -> str:
    if value is None:
        return "-"
    return f"{value} {unit}"


def _sort_key(datum: Datum):
    # Target alphabetical, then ascending normalized affinity (None last).
    value = datum.value if datum.value is not None else float("inf")
    return (datum.target_context, value)


def render_table(data, accessed: str) -> str:
    """Render the VERBATIM 8-column markdown table + footer for ``data``."""
    rows = sorted(data, key=_sort_key)

    footnotes: list[str] = []
    table_lines = [
        "| " + " | ".join(HEADER) + " |",
        "| " + " | ".join("---" for _ in HEADER) + " |",
    ]

    flagged_count = 0
    for idx, datum in enumerate(rows, start=1):
        spread = _disagreement(datum)
        metric_cell = datum.metric
        if spread is not None:
            flagged_count += 1
            metric_cell = f"{datum.metric} !"
            footnotes.append(f"[{idx}] {datum.metric} {spread}")

        cells = [
            datum.source,
            datum.target_context,
            metric_cell,
            _fmt_value(datum.value, datum.unit),
            _fmt_value(datum.value_as_reported, datum.unit_as_reported or ""),
            str(datum.n) if datum.n is not None else "-",
            datum.confidence,
            _ref(datum),
        ]
        table_lines.append("| " + " | ".join(cells) + " |")

    sources = ", ".join(dict.fromkeys(d.source for d in rows))
    footer = (
        f"sources hit: {sources} | accessed {accessed} | "
        f"{len(rows)} rows, {flagged_count} flagged"
    )

    parts = ["\n".join(table_lines)]
    if footnotes:
        parts.append("\n".join(footnotes))
    parts.append(footer)
    return "\n\n".join(parts)


def render_raw(data) -> str:
    """``--raw`` escape: full JSON dump of every Datum (nested dataclasses)."""
    return json.dumps([dataclasses.asdict(d) for d in data], indent=2, default=str)
