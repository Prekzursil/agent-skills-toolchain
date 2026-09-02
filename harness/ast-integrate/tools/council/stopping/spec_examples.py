"""Executable stopping examples E1..E6 (spec lines 10937-10942, CNL-0078..CNL-0083).

The council spec names six stopping conditions in prose. This module carries each one
as an executable row in the grammar of :mod:`council.stopping.expr`, together with the
fixtures the TST-0281 probes drive through the evaluator. Row keys:

``id``
    ``E1`` .. ``E6``.
``spec_line``
    Line of the original spec text (``_USER-PROMPTS.md``) the expression was lifted from.
``cnl``
    The CNL catalog unit that made the example executable.
``source``
    The expression source.
``producers``
    Metric names a run must produce for the expression to bind (bare identifiers that
    denote enum states, such as ``PASS``, are literals and are not producers).
``fire``
    Bindings under which the expression is a definite ``True`` (the council may stop).
``silent``
    Bindings under which it is a definite ``False`` (the council continues).
``not_checked``
    Bindings with one metric ``NOT-CHECKED``: Kleene unknown, which never stops.
``fire_timer_arm`` (E3, E5 only)
    The disjunction fires on its ceiling / timer arm while the primary arm is false.
``unsuccessful_search`` (E6 only)
    A search that found no proof; it must not satisfy ``proof_of_impossibility``.

Bindings use the ``{"status": "CHECKED", "value": v}`` / ``{"status": "NOT-CHECKED"}``
shape read by :func:`council.stopping.expr.evaluate_source`.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

Binding = dict[str, Any]
Bindings = dict[str, Binding]

FIRST_SPEC_LINE = 10937
FIRST_CNL = 78


def checked(value: Any) -> Binding:
    """A metric that was measured this round and holds ``value``."""
    return {"status": "CHECKED", "value": value}


def unchecked() -> Binding:
    """A metric that was not measured this round (Kleene unknown)."""
    return {"status": "NOT-CHECKED"}


def _example(
    *,
    id: str,
    spec_line: int,
    cnl: str,
    source: str,
    producers: Iterable[str],
    fire: Bindings,
    silent: Bindings,
    not_checked: Bindings,
    **extra_fixtures: Bindings,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": id,
        "spec_line": spec_line,
        "cnl": cnl,
        "source": source,
        "producers": tuple(producers),
        "fire": fire,
        "silent": silent,
        "not_checked": not_checked,
    }
    row.update(extra_fixtures)
    return row


SPEC_EXAMPLES: tuple[dict[str, Any], ...] = (
    _example(
        id="E1",
        spec_line=10937,
        cnl="CNL-0078",
        source="unique_ideas >= 100 AND completeness_score >= 0.90",
        producers=("unique_ideas", "completeness_score"),
        fire={"unique_ideas": checked(100), "completeness_score": checked(0.90)},
        silent={"unique_ideas": checked(41), "completeness_score": checked(0.55)},
        not_checked={"unique_ideas": checked(100), "completeness_score": unchecked()},
    ),
    _example(
        id="E2",
        spec_line=10938,
        cnl="CNL-0079",
        source="consensus >= 0.95 AND no_new_objection_rounds >= 2",
        producers=("consensus", "no_new_objection_rounds"),
        fire={"consensus": checked(0.97), "no_new_objection_rounds": checked(2)},
        silent={"consensus": checked(0.62), "no_new_objection_rounds": checked(0)},
        not_checked={"consensus": checked(0.97), "no_new_objection_rounds": unchecked()},
    ),
    _example(
        id="E3",
        spec_line=10939,
        cnl="CNL-0080",
        source="unanimity == true OR max_rounds == 12",
        producers=("unanimity", "max_rounds"),
        fire={"unanimity": checked(True), "max_rounds": checked(7)},
        silent={"unanimity": checked(False), "max_rounds": checked(7)},
        not_checked={"unanimity": unchecked(), "max_rounds": checked(7)},
        fire_timer_arm={"unanimity": checked(False), "max_rounds": checked(12)},
    ),
    _example(
        id="E4",
        spec_line=10940,
        cnl="CNL-0081",
        source="quality_gate == PASS AND unresolved_load_bearing_counterexample == 0",
        producers=("quality_gate", "unresolved_load_bearing_counterexample"),
        fire={
            "quality_gate": checked("PASS"),
            "unresolved_load_bearing_counterexample": checked(0),
        },
        silent={
            "quality_gate": checked("FAIL"),
            "unresolved_load_bearing_counterexample": checked(2),
        },
        not_checked={
            "quality_gate": unchecked(),
            "unresolved_load_bearing_counterexample": checked(0),
        },
    ),
    _example(
        id="E5",
        spec_line=10941,
        cnl="CNL-0082",
        source="evidence_saturation == true OR time_minutes >= 180",
        producers=("evidence_saturation", "time_minutes"),
        fire={"evidence_saturation": checked(True), "time_minutes": checked(35)},
        silent={"evidence_saturation": checked(False), "time_minutes": checked(35)},
        not_checked={"evidence_saturation": unchecked(), "time_minutes": checked(35)},
        fire_timer_arm={"evidence_saturation": checked(False), "time_minutes": checked(180)},
    ),
    _example(
        id="E6",
        spec_line=10942,
        cnl="CNL-0083",
        source="proof_of_impossibility == true",
        producers=("proof_of_impossibility",),
        fire={"proof_of_impossibility": checked(True)},
        silent={"proof_of_impossibility": checked(False)},
        not_checked={"proof_of_impossibility": unchecked()},
        unsuccessful_search={"proof_of_impossibility": checked(False)},
    ),
)

SPEC_EXAMPLE_IDS: tuple[str, ...] = tuple(str(row["id"]) for row in SPEC_EXAMPLES)


def spec_example(example_id: str) -> dict[str, Any]:
    """Return the row for ``example_id`` (``E1`` .. ``E6``); ``KeyError`` otherwise."""
    for row in SPEC_EXAMPLES:
        if row["id"] == example_id:
            return row
    raise KeyError(f"no spec example {example_id!r}; known: {', '.join(SPEC_EXAMPLE_IDS)}")


def example_sources() -> dict[str, str]:
    """``{id: source}`` for every example, in spec order."""
    return {str(row["id"]): str(row["source"]) for row in SPEC_EXAMPLES}


def _fixture_names(row: Mapping[str, Any]) -> list[str]:
    return [key for key, value in row.items() if isinstance(value, dict)]


def check_examples() -> list[str]:
    """Cross-check every row against the expression module; return the problems found.

    An empty list means: ids are unique and in order, spec lines and CNL ids are
    consecutive, every metric the expression references is produced and bound in every
    fixture, and no fixture binds a metric the expression never reads.
    """
    from .expr import referenced_metrics

    problems: list[str] = []
    for index, row in enumerate(SPEC_EXAMPLES):
        rid = str(row["id"])
        if rid != f"E{index + 1}":
            problems.append(f"{rid}: expected id E{index + 1} at position {index}")
        if row["spec_line"] != FIRST_SPEC_LINE + index:
            problems.append(f"{rid}: spec_line {row['spec_line']} is out of sequence")
        if row["cnl"] != f"CNL-{FIRST_CNL + index:04d}":
            problems.append(f"{rid}: cnl {row['cnl']} is out of sequence")
        referenced = set(referenced_metrics(str(row["source"])))
        producers = set(row["producers"])
        if referenced != producers:
            problems.append(
                f"{rid}: producers {sorted(producers)} != referenced {sorted(referenced)}"
            )
        for fixture in _fixture_names(row):
            bound = set(row[fixture])
            if bound != referenced:
                problems.append(
                    f"{rid}.{fixture}: binds {sorted(bound)}, expression reads {sorted(referenced)}"
                )
    return problems


__all__ = [
    "FIRST_CNL",
    "FIRST_SPEC_LINE",
    "SPEC_EXAMPLES",
    "SPEC_EXAMPLE_IDS",
    "check_examples",
    "checked",
    "example_sources",
    "spec_example",
    "unchecked",
]
