#!/usr/bin/env python3
"""Both-states controls: 30 near-identical field tuples vs 30 diverse tuples."""
from __future__ import annotations

from typing import Any

from score import field_tuple, load_fields, load_prereg, score_run

PARAPHRASES = [
    f"near-identical paraphrase {i:02d} of the same tracker-field bundle"
    for i in range(1, 31)
]


def _base_issue() -> dict[str, Any]:
    fields = load_fields()
    return dict(fields["modelcontextprotocol/inspector#1859"])


def near_identical_sources() -> list[dict[str, Any]]:
    base = _base_issue()
    out = []
    for i, title in enumerate(PARAPHRASES, start=1):
        row = dict(base)
        row["id"] = f"near-identical-{i:02d}"
        row["dummy_title"] = title
        out.append(row)
    return out


def diverse_sources() -> list[dict[str, Any]]:
    """Thirty mutually distinct observable field tuples."""
    out = []
    states = ["open", "closed"]
    label_sets = [
        ["bug"],
        ["enhancement"],
        ["documentation"],
        ["duplicate"],
        ["bug", "stale"],
        ["chore"],
        [],
        ["bug", "v2"],
        ["enhancement", "v2"],
        ["documentation", "area:docs"],
    ]
    for i in range(30):
        labs = list(label_sets[i % len(label_sets)]) + [f"unique-{i}"]
        row = {
            "id": f"diverse-{i:02d}",
            "state": states[i % 2],
            "labels": labs,
            "reaction_count": (i * 3) % 11,
            "comment_count": i % 5,
            "milestone": f"m{i}" if i % 3 == 0 else None,
            "is_pull_request": (i % 4 == 0),
            "maintainer_response_hours": (float(i) if i % 2 == 1 else None),
            "dummy_title": f"diverse title {i} distinct mechanism {i*17}",
        }
        out.append(row)
    keys = [field_tuple(r) for r in out]
    if len(set(keys)) != 30:
        raise RuntimeError(f"diverse control collapsed to {len(set(keys))} tuples")
    return out


def mutant_report() -> dict[str, Any]:
    """Paraphrases of one tuple collapse; a real field change stays apart."""
    near = near_identical_sources()
    keys = {field_tuple(r) for r in near}
    mutant = dict(near[0])
    mutant["labels"] = list(mutant.get("labels") or []) + ["duplicate"]
    mutant["dummy_title"] = near[0]["dummy_title"]
    kept_apart = field_tuple(mutant) not in keys
    return {
        "paraphrase_strings": len(PARAPHRASES),
        "paraphrase_field_tuples": len(keys),
        "paraphrases_collapse": len(keys) == 1,
        "field_change_kept_apart": kept_apart,
        "pass": len(keys) == 1 and kept_apart,
    }


def both_states(prereg: dict[str, Any] | None = None) -> dict[str, Any]:
    if prereg is None:
        prereg = load_prereg()
    near = score_run(near_identical_sources(), prereg)
    div = score_run(diverse_sources(), prereg)
    return {"near": near, "diverse": div, "mutants": mutant_report()}


near_identical_sources = near_identical_sources
diverse_sources = diverse_sources
mutant_report = mutant_report
