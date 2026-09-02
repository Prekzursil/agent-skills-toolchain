#!/usr/bin/env python3
"""Reconstruct the selected capability ids from an explanation JSON only.

Does not load the labelled corpus or re-run fusion/overrides.  The only input
is the explanation record written by ``tools/router/explain.py`` (or a receipt
that embeds such records under ``explanations``); the output is one block per
explanation::

    query_id=<id>
    count=<n>
    <capability_id>        (one per line, in selection order)

An owner who reads the explanation and this printout has the whole decision.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def explanations_in(doc: Any, fallback_id: str) -> list[dict[str, Any]]:
    """Explanation records carried by ``doc``: itself, or its ``explanations``."""
    if isinstance(doc, list):
        return [d for d in doc if isinstance(d, dict) and "selected" in d]
    if not isinstance(doc, dict):
        return []
    if isinstance(doc.get("selected"), list):
        if not doc.get("query_id"):
            doc = {**doc, "query_id": fallback_id}
        return [doc]
    nested = doc.get("explanations")
    if isinstance(nested, list):
        return [d for d in nested if isinstance(d, dict) and "selected" in d]
    report = doc.get("report")
    if isinstance(report, dict) and isinstance(report.get("explanations"), list):
        return [d for d in report["explanations"] if isinstance(d, dict) and "selected" in d]
    return []


def selected_ids(expl: dict[str, Any]) -> list[str]:
    return [
        str(row.get("capability_id") or "")
        for row in (expl.get("selected") or [])
        if isinstance(row, dict) and row.get("capability_id")
    ]


def render(expl: dict[str, Any]) -> str:
    ids = selected_ids(expl)
    lines = [f"query_id={expl.get('query_id')}", f"count={len(ids)}"]
    lines.extend(ids)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 1:
        print("usage: reconstruct.py <explanation.json | receipt-with-explanations.json>", file=sys.stderr)
        return 2
    path = Path(args[0])
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"reconstruct: cannot read {path}: {exc}", file=sys.stderr)
        return 2
    records = explanations_in(doc, path.stem)
    if not records:
        print(f"reconstruct: no explanation record in {path}", file=sys.stderr)
        return 1
    for expl in records:
        print(render(expl))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
