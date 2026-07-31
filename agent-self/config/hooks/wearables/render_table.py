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

Both renderers are a WRITE/DUMP boundary, so both pass their output through
:func:`~wearables.security.egress.scrub_secrets` — the package invariant is
"payloads are secret-scrubbed BEFORE any write/dump" (``security/egress.py``).
A Datum string field (``confidence`` and friends) carries provider text
verbatim (``datum.py``), so an unscrubbed renderer emits any bearer token /
API key it was handed.
"""

from __future__ import annotations

import dataclasses
import json

from .datum import Datum
from .security.egress import scrub_secrets

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
    # Scrub at the RETURN boundary (same chokepoint shape as ``egress_guard``):
    # one call covers every cell, every footnote and the footer, so no field
    # added later can silently bypass the guard.
    return scrub_secrets("\n\n".join(parts))


def _scrub_tree(value):
    """Recursively scrub every string LEAF of an ``asdict`` tree.

    MEASURED: scrubbing the serialized JSON instead corrupts it. Every prefix
    pattern in ``egress.py`` ends in ``\\S+``, which is greedy over non-space —
    so on ``"confidence": "Authorization: Bearer sk-x",`` it also eats the
    closing quote and the comma, leaving an unterminated string literal
    (``JSONDecodeError: Invalid control character``). Scrub before dumping.
    """
    if isinstance(value, str):
        return scrub_secrets(value)
    if isinstance(value, dict):
        return {k: _scrub_tree(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_tree(v) for v in value]
    return value


def render_raw(data) -> str:
    """``--raw`` escape: full JSON dump of every Datum (nested dataclasses)."""
    scrubbed = _scrub_tree([dataclasses.asdict(d) for d in data])
    return json.dumps(scrubbed, indent=2, default=str)
