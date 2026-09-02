#!/usr/bin/env python3
"""Charter completeness: every required council output must be present AND non-vacuous (IMP-0356).

A council charter names the outputs the council has to deliver -- by default
:data:`CHARTER_REQUIRED_OUTPUTS` (positions, idea_ledger, argument_graph, votes, dissent,
unknowns, experiments, recommendation, calibration); an artifact may narrow or extend the list
through ``artifact["charter"]["required_outputs"]``. Presence of the key is not delivery. A
value carries no content, and is scored *vacuous*, when it is

* ``null`` or a bare boolean (a checkbox is not a deliverable);
* a blank string, or a placeholder word such as ``TBD`` / ``TODO`` / ``n/a`` (:data:`PLACEHOLDER_MARKERS`);
* an empty list, or a list whose every item is vacuous;
* an empty object, an object that only carries presence/status/count bookkeeping keys
  (:data:`META_KEYS`, e.g. ``{"present": true}`` or ``{"ok": true, "status": "done"}``), or an
  object whose every content value is vacuous (``{"count": 0, "items": []}``).

Numbers are content (a calibration ``ece`` of ``0.0`` is a result, not a gap), and any object
with at least one non-vacuous content value passes.

:func:`check_artifact` scores one council: per required output it records ``present`` and
``vacuous``, lists the incomplete outputs (absent or vacuous) in charter order under ``missing``
and gives one reason per incomplete output in ``fail_reasons`` (``<output>:absent`` /
``<output>:vacuous``, with the vacuity kind under ``vacuity``). :func:`census` aggregates over a
corpus of recorded councils and ranks the required outputs by how often they are incomplete.
:func:`complete_artifact` builds a fully populated twin and :func:`vacuous_mutants` derives the
seven labelled empty-but-present mutants per section (:data:`VACUOUS_MUTANT_LABELS`) a reviewer
uses to show the checker fires on vacuity while staying silent on the twin.
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

CHARTER_REQUIRED_OUTPUTS: tuple[str, ...] = (
    "positions",
    "idea_ledger",
    "argument_graph",
    "votes",
    "dissent",
    "unknowns",
    "experiments",
    "recommendation",
    "calibration",
)

# Strings that announce content instead of carrying it. Compared after :func:`_normalise_text`.
PLACEHOLDER_MARKERS: frozenset[str] = frozenset(
    {
        "tbd",
        "tba",
        "todo",
        "fixme",
        "wip",
        "pending",
        "placeholder",
        "n/a",
        "na",
        "none",
        "null",
        "nil",
        "to be determined",
        "to be decided",
        "to be announced",
        "not yet",
        "later",
        "xxx",
        "lorem ipsum",
        "?",
        "???",
        "...",
    }
)

# Object keys that describe the container rather than deliver content. An object made of these
# keys alone is a presence-only checkbox; a count without the counted items is the same thing.
META_KEYS: frozenset[str] = frozenset(
    {
        "present",
        "ok",
        "status",
        "state",
        "checked",
        "complete",
        "completed",
        "done",
        "exists",
        "count",
        "n",
        "total",
        "size",
        "length",
    }
)

VACUOUS_MUTANT_LABELS: tuple[str, ...] = (
    "empty_list",
    "empty_object",
    "empty_string",
    "whitespace",
    "placeholder_tbd",
    "present_checkbox",
    "ok_status",
)

_MUTANT_VALUES: dict[str, Any] = {
    "empty_list": [],
    "empty_object": {},
    "empty_string": "",
    "whitespace": " \t\n ",
    "placeholder_tbd": "TBD",
    "present_checkbox": {"present": True},
    "ok_status": {"ok": True, "status": "done", "checked": True},
}

_PUNCT = ".:;,!-_*[](){}<>\"'`"


# --------------------------------------------------------------------------- vacuity
def _normalise_text(value: str) -> str:
    text = " ".join(value.casefold().split())
    return text.strip(_PUNCT + " ")


def vacuity_reason(value: Any) -> str | None:
    """Why ``value`` is vacuous (``None`` when it carries content).

    Reasons: ``null``, ``checkbox-bool``, ``blank``, ``placeholder:<word>``, ``empty-list``,
    ``all-items-vacuous``, ``empty-object``, ``presence-only-keys``, ``all-values-vacuous``.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "checkbox-bool"
    if isinstance(value, (int, float)):
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return "blank"
        normalised = _normalise_text(stripped)
        if not normalised or normalised in PLACEHOLDER_MARKERS:
            return f"placeholder:{stripped}"
        return None
    if isinstance(value, Mapping):
        if not value:
            return "empty-object"
        content = {k: v for k, v in value.items() if str(k).casefold() not in META_KEYS}
        if not content:
            return "presence-only-keys"
        if all(vacuity_reason(v) is not None for v in content.values()):
            return "all-values-vacuous"
        return None
    if isinstance(value, (list, tuple, set, frozenset)):
        if not value:
            return "empty-list"
        if all(vacuity_reason(item) is not None for item in value):
            return "all-items-vacuous"
        return None
    return None


def is_vacuous(value: Any) -> bool:
    """True when ``value`` is present in form only (see the module docstring for the rules)."""
    return vacuity_reason(value) is not None


# --------------------------------------------------------------------------- one artifact
def required_outputs(doc: Mapping[str, Any]) -> list[str]:
    """The outputs ``doc``'s charter requires, in charter order; the default set when unset."""
    charter = doc.get("charter") if isinstance(doc, Mapping) else None
    declared = charter.get("required_outputs") if isinstance(charter, Mapping) else None
    names: list[str] = []
    if isinstance(declared, (list, tuple)):
        for item in declared:
            if isinstance(item, str) and item.strip() and item not in names:
                names.append(item)
    return names or list(CHARTER_REQUIRED_OUTPUTS)


def check_artifact(doc: Mapping[str, Any]) -> dict[str, Any]:
    """Score one council artifact against its charter.

    Returns ``council_id``, ``pass`` (every required output present and non-vacuous),
    ``missing`` (incomplete outputs in charter order), ``present`` / ``vacuous`` (one flag per
    required output), ``vacuity`` (the reason per vacuous output), ``fail_reasons``
    (``<output>:absent`` / ``<output>:vacuous``), ``required``, ``n_required``, ``n_complete``,
    ``completeness_score`` (complete / required) and ``extra_outputs`` (delivered but not required).
    """
    if not isinstance(doc, Mapping):
        raise TypeError(f"artifact must be an object, got {type(doc).__name__}")
    required = required_outputs(doc)
    raw_outputs = doc.get("outputs")
    outputs: Mapping[str, Any] = raw_outputs if isinstance(raw_outputs, Mapping) else {}
    present: dict[str, bool] = {}
    vacuous: dict[str, bool] = {}
    vacuity: dict[str, str] = {}
    missing: list[str] = []
    fail_reasons: list[str] = []
    for key in required:
        exists = key in outputs
        present[key] = exists
        reason = vacuity_reason(outputs[key]) if exists else None
        vacuous[key] = exists and reason is not None
        if not exists:
            missing.append(key)
            fail_reasons.append(f"{key}:absent")
        elif reason is not None:
            vacuity[key] = reason
            missing.append(key)
            fail_reasons.append(f"{key}:vacuous")
    n_complete = len(required) - len(missing)
    return {
        "council_id": doc.get("council_id"),
        "pass": not missing,
        "missing": missing,
        "present": present,
        "vacuous": vacuous,
        "vacuity": vacuity,
        "fail_reasons": fail_reasons,
        "required": required,
        "n_required": len(required),
        "n_complete": n_complete,
        "completeness_score": (n_complete / len(required)) if required else 1.0,
        "extra_outputs": sorted(str(k) for k in outputs if k not in required),
    }


def completeness_score(doc: Mapping[str, Any]) -> float:
    """Fraction of required outputs that are present and non-vacuous (the charter metric)."""
    return float(check_artifact(doc)["completeness_score"])


# --------------------------------------------------------------------------- corpus census
def load_recorded_fixtures(folder: str | Path) -> list[dict[str, Any]]:
    """Load every ``rec-*.json`` council artifact under ``folder`` in name order."""
    root = Path(folder)
    if not root.is_dir():
        raise FileNotFoundError(f"recorded-council folder not found: {root}")
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("rec-*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            raise ValueError(f"{path}: recorded council is not a JSON object")
        rows.append(doc)
    return rows


def census(corpus: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Run :func:`check_artifact` over a corpus and rank the required outputs by incompleteness.

    ``per_output`` rows carry ``incomplete`` (absent or vacuous), ``absent`` and ``vacuous``
    counts and are ranked by ``incomplete`` descending, then by output name; the top-ranked
    output is ``missing_most_often`` (``None`` when every council is complete).
    """
    rows = [check_artifact(doc) for doc in corpus]
    keys = list(CHARTER_REQUIRED_OUTPUTS)
    for row in rows:
        for key in row["required"]:
            if key not in keys:
                keys.append(key)
    counts = {key: {"incomplete": 0, "absent": 0, "vacuous": 0} for key in keys}
    for row in rows:
        for key in row["missing"]:
            counts[key]["incomplete"] += 1
            if not row["present"].get(key):
                counts[key]["absent"] += 1
            else:
                counts[key]["vacuous"] += 1
    ranked = [{"output": key, **counts[key]} for key in keys]
    ranked.sort(key=lambda item: (-item["incomplete"], item["output"]))
    n_pass = sum(1 for row in rows if row["pass"])
    most = ranked[0]["output"] if ranked and ranked[0]["incomplete"] > 0 else None
    return {
        "n_councils": len(rows),
        "n_pass": n_pass,
        "n_fail": len(rows) - n_pass,
        "pass_rate": (n_pass / len(rows)) if rows else 0.0,
        "missing_most_often": most,
        "per_output": ranked,
        "required_outputs": keys,
        "rows": rows,
    }


# --------------------------------------------------------------------------- twin and mutants
def _generic_section(key: str, cid: str) -> dict[str, Any]:
    return {"items": [{"id": f"{key}-{cid}-1", "text": f"{cid}: live {key} content"}]}


def complete_artifact(council_id: str, required: Sequence[str] | None = None) -> dict[str, Any]:
    """A fully populated council artifact (every required output present with real content).

    The shapes mirror the recorded councils: positions as a list of claims, ledgers and graphs
    as objects with items/nodes/edges, votes with ballots and a tally, calibration with bins and
    an ECE. Outputs outside the default nine get a generic ``items`` section.
    """
    cid = str(council_id)
    names = [str(n) for n in required] if required else list(CHARTER_REQUIRED_OUTPUTS)
    canned: dict[str, Any] = {
        "positions": [
            {
                "author": f"role:architect:{cid}",
                "round": 1,
                "claim": f"{cid} prefers bounded replay over live store mutation.",
            },
            {
                "author": f"role:skeptic:{cid}",
                "round": 1,
                "claim": f"{cid}: replay must be verified byte-for-byte before adoption.",
            },
        ],
        "idea_ledger": {
            "ideas": [
                {
                    "id": f"I-{cid}-1",
                    "author": f"role:architect:{cid}",
                    "round": 1,
                    "mechanism": "append-only event log with derived views",
                }
            ],
            "unique_count": 1,
        },
        "argument_graph": {
            "nodes": [
                {"id": f"C-{cid}-1", "kind": "claim", "text": f"{cid}: replay is bounded by the event log."},
                {"id": f"C-{cid}-2", "kind": "claim", "text": f"{cid}: derived views can be rebuilt."},
            ],
            "edges": [{"src": f"C-{cid}-1", "dst": f"C-{cid}-2", "rel": "SUPPORTS", "turn": 4}],
        },
        "votes": {
            "round": 3,
            "rule": "majority",
            "ballots": [
                {"voter": f"architect-{cid}", "choice": "adopt", "weight": 1},
                {"voter": f"skeptic-{cid}", "choice": "adopt", "weight": 1},
            ],
            "tally": {"adopt": 2, "reject": 0},
        },
        "dissent": {
            "count": 1,
            "items": [
                {
                    "id": f"D-{cid}-1",
                    "author": f"skeptic-{cid}",
                    "claim": f"{cid}: calibration bins have no held-out labels.",
                    "carried_to_final": True,
                }
            ],
        },
        "unknowns": {
            "count": 1,
            "items": [{"id": f"U-{cid}-1", "question": f"{cid}: does event-store replay match byte-for-byte?"}],
        },
        "experiments": {
            "count": 1,
            "items": [
                {
                    "id": f"E-{cid}-1",
                    "hypothesis": f"{cid}: a presence-only checker accepts empty dissent.",
                    "method": "substitute [] and assert non-vacuity FAIL",
                }
            ],
        },
        "recommendation": {
            "action": f"{cid}: reject presence-only completeness; require non-vacuity.",
            "confidence": 0.72,
            "next_steps": ["wire completeness into the stop predicate"],
        },
        "calibration": {
            "method": "ten-bin ECE on held-out forecasts",
            "n_forecasts": 10,
            "bins": [{"p": 0.7, "n": 10, "hits": 6}],
            "ece": 0.08,
        },
    }
    outputs = {name: deepcopy(canned[name]) if name in canned else _generic_section(name, cid) for name in names}
    return {
        "council_id": cid,
        "charter": {"required_outputs": list(names)},
        "outputs": outputs,
    }


def vacuous_mutants(
    twin: Mapping[str, Any], section: str | None = None
) -> list[tuple[str, dict[str, Any]]]:
    """Derive the empty-but-present mutants of ``twin``: ``(label, mutant)`` pairs.

    For ``section`` the seven :data:`VACUOUS_MUTANT_LABELS` mutants are produced, each a deep
    copy of the twin with that section replaced by the labelled vacuous value (the twin is never
    modified). With ``section=None`` every required output is mutated and labels are prefixed
    ``<section>:``. Raises :class:`KeyError` when the section is not delivered by the twin.
    """
    if not isinstance(twin, Mapping) or not isinstance(twin.get("outputs"), Mapping):
        raise ValueError("twin must be a council artifact with an outputs object")
    outputs = twin["outputs"]
    sections = [section] if section is not None else required_outputs(twin)
    for name in sections:
        if name not in outputs:
            raise KeyError(f"section {name!r} is not delivered by the twin")
    base_id = str(twin.get("council_id") or "twin")
    mutants: list[tuple[str, dict[str, Any]]] = []
    for name in sections:
        for label in VACUOUS_MUTANT_LABELS:
            mutant = deepcopy(dict(twin))
            mutant["outputs"] = dict(mutant["outputs"])
            mutant["outputs"][name] = deepcopy(_MUTANT_VALUES[label])
            mutant["council_id"] = f"{base_id}:{name}:{label}"
            mutant["mutation"] = {"section": name, "label": label}
            tag = label if section is not None else f"{name}:{label}"
            mutants.append((tag, mutant))
    return mutants


# --------------------------------------------------------------------------- CLI
def _load_paths(paths: Sequence[str]) -> list[dict[str, Any]]:
    corpus: list[dict[str, Any]] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            corpus.extend(load_recorded_fixtures(path))
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            raise ValueError(f"{path}: council artifact is not a JSON object")
        corpus.append(doc)
    return corpus


def main(argv: Sequence[str] | None = None) -> int:
    """``completeness.py [--gate] PATH...`` -- census over artifacts or ``rec-*.json`` folders."""
    parser = argparse.ArgumentParser(description="charter completeness census (present AND non-vacuous)")
    parser.add_argument("paths", nargs="+", help="council artifact files or folders of rec-*.json")
    parser.add_argument("--gate", action="store_true", help="exit 1 when any council is incomplete")
    args = parser.parse_args(argv)
    report = census(_load_paths(args.paths))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.gate and report["n_fail"] else 0


__all__ = [
    "CHARTER_REQUIRED_OUTPUTS",
    "META_KEYS",
    "PLACEHOLDER_MARKERS",
    "VACUOUS_MUTANT_LABELS",
    "census",
    "check_artifact",
    "complete_artifact",
    "completeness_score",
    "is_vacuous",
    "load_recorded_fixtures",
    "required_outputs",
    "vacuity_reason",
    "vacuous_mutants",
]


if __name__ == "__main__":
    sys.exit(main())
