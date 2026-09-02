"""Extract canonical mechanism ids from definition fields, not self-description.

Definition fields: does, stages, gates, stop, code.
Prose/self-description fields: mechanisms, name.
Notes are documentation: a mention there is not an implementation.

Unmapped free-text is recorded as a vocabulary gap, never minted as an id.
An artifact with no matching needles yields an empty set — never a default.
"""
from __future__ import annotations

import json
from typing import Any

from vocabulary import MECHANISMS, CLOSED_IDS, MECH_BY_ID


def _norm(text: str) -> str:
    return " ".join(str(text).lower().replace("_", "-").split())


def _blob(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, default=str)


def definition_text(art: dict[str, Any], *, include_notes: bool = False) -> str:
    parts = [
        _blob(art.get("does")),
        _blob(art.get("stages")),
        _blob(art.get("gates")),
        _blob(art.get("stop")),
        _blob(art.get("code")),
        _blob(art.get("runtime")),
    ]
    if include_notes:
        parts.append(_blob(art.get("notes")))
    return _norm(" ".join(parts))


def prose_text(art: dict[str, Any]) -> str:
    mechs = art.get("mechanisms") or []
    if isinstance(mechs, str):
        mechs = [mechs]
    return _norm(" ".join(str(x) for x in mechs) + " " + _blob(art.get("name")))


def notes_text(art: dict[str, Any]) -> str:
    return _norm(_blob(art.get("notes")))


def _hits(blob: str, field: str) -> list[str]:
    found: list[str] = []
    for mech in MECHANISMS:
        needles = mech["impl_needles"] if field == "impl" else mech["prose_aliases"]
        if any(_norm(n) in blob for n in needles):
            found.append(mech["id"])
    return found


def extract_from_definition(
    art: dict[str, Any], *, include_notes: bool = False
) -> list[str]:
    blob = definition_text(art, include_notes=include_notes)
    if not blob.strip():
        return []
    return _hits(blob, "impl")


def extract_from_prose(art: dict[str, Any]) -> list[str]:
    blob = prose_text(art)
    if not blob.strip():
        return []
    return _hits(blob, "prose")


def vocabulary_gaps(art: dict[str, Any]) -> list[str]:
    """Free-text mechanism strings that did not map to a closed id."""
    mechs = art.get("mechanisms") or []
    if isinstance(mechs, str):
        mechs = [mechs]
    mapped = set(extract_from_prose(art))
    gaps: list[str] = []
    for raw in mechs:
        text = str(raw).strip()
        if not text:
            continue
        hit = _hits(_norm(text), "prose")
        if not hit:
            gaps.append(text)
        else:
            mapped.update(hit)
    return gaps


def extract_artifact(art: dict[str, Any]) -> dict[str, Any]:
    definition_ids = extract_from_definition(art)
    prose_ids = extract_from_prose(art)
    notes_ids = _hits(notes_text(art), "impl") + _hits(notes_text(art), "prose")
    # Use-versus-mention: notes-only hits are not credited as implementation.
    mention_only = sorted(set(notes_ids) - set(definition_ids))
    return {
        "artifact_id": art.get("id"),
        "kind": art.get("kind"),
        "family": art.get("family"),
        "definition_ids": definition_ids,
        "prose_ids": prose_ids,
        "mention_only_ids": mention_only,
        "implemented_ids": definition_ids,  # incidence uses definition, not prose
        "agrees": set(definition_ids) == set(prose_ids),
        "zero_extractable": definition_ids == [],
        "vocabulary_gaps": vocabulary_gaps(art),
        "extraction_rule": (
            "implemented := impl_needles in {does,stages,gates,stop,code}; "
            "prose := aliases in {mechanisms,name}; "
            "notes mention is not implementation; "
            "empty match => [] never a default"
        ),
        "planted": art.get("planted"),
    }


def mention_only_fixture() -> dict[str, Any]:
    """Standalone use-versus-mention control, independent of the 284-set."""
    return {
        "id": "ctrl-mention-only-fan-in-doc",
        "kind": "control",
        "family": "CONTROL",
        "name": "operator-handbook.md",
        "does": (
            "The stage blocks until a named human records a decision; owner "
            "accept required (human-gate)."
        ),
        "stages": [{"id": "human-gate", "kind": "human-gate", "role": "implement"}],
        "mechanisms": ["human checkpoint"],
        "notes": (
            "This handbook documents a blocking fan-in barrier and a "
            "wait-for-all barrier so operators can recognise the pattern. "
            "The workflow itself does not run one."
        ),
        "planted": "use-versus-mention",
    }


def zero_fixture() -> dict[str, Any]:
    return {
        "id": "ctrl-zero-extractable",
        "kind": "control",
        "family": "CONTROL",
        "name": "empty.json",
        "does": "",
        "stages": [],
        "mechanisms": [],
        "notes": "",
        "planted": "zero-extractable",
    }


def extract_all(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [extract_artifact(a) for a in artifacts]


def incidence_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_artifact: dict[str, list[str]] = {}
    by_mechanism: dict[str, list[str]] = {m: [] for m in sorted(CLOSED_IDS)}
    for row in rows:
        aid = str(row["artifact_id"])
        ids = list(row["implemented_ids"])
        by_artifact[aid] = ids
        for mid in ids:
            by_mechanism.setdefault(mid, []).append(aid)
    for mid in by_mechanism:
        by_mechanism[mid] = sorted(set(by_mechanism[mid]))
    empty = sorted(aid for aid, ids in by_artifact.items() if ids == [])
    return {
        "n_artifacts": len(by_artifact),
        "n_mechanisms": len(CLOSED_IDS),
        "n_nonzero_cells": sum(len(v) for v in by_artifact.values()),
        "zero_mechanism_artifact_ids": empty,
        "by_artifact": by_artifact,
        "by_mechanism": by_mechanism,
        "per_cell_rule": (
            "cell (artifact, mechanism) is 1 iff an impl_needle of that "
            "mechanism occurs in the artifact's definition fields"
        ),
    }


def compare_sample(
    rows: list[dict[str, Any]], sample_ids: list[str]
) -> dict[str, Any]:
    index = {str(r["artifact_id"]): r for r in rows}
    disagreements = []
    missing = []
    for sid in sample_ids:
        row = index.get(sid)
        if row is None:
            missing.append(sid)
            continue
        if set(row["definition_ids"]) != set(row["prose_ids"]):
            disagreements.append(
                {
                    "artifact_id": sid,
                    "definition_ids": row["definition_ids"],
                    "prose_ids": row["prose_ids"],
                    "only_definition": sorted(
                        set(row["definition_ids"]) - set(row["prose_ids"])
                    ),
                    "only_prose": sorted(
                        set(row["prose_ids"]) - set(row["definition_ids"])
                    ),
                }
            )
    n = len(sample_ids)
    n_dis = len(disagreements)
    return {
        "sampling_rule": (
            "first two candidates of each of 9 families (18) plus first "
            "twelve blueprints in id order (12); frozen before extraction"
        ),
        "n": n,
        "n_disagreements": n_dis,
        "disagreement_rate": (n_dis / n) if n else None,
        "missing_from_rows": missing,
        "disagreements": disagreements,
    }


__all__ = [
    "CLOSED_IDS",
    "MECH_BY_ID",
    "compare_sample",
    "extract_all",
    "extract_artifact",
    "extract_from_definition",
    "extract_from_prose",
    "incidence_from_rows",
    "mention_only_fixture",
    "zero_fixture",
]
