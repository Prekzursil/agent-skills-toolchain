"""Constraint solver for same-seat incompatible roles and declared COI.

Incompatibility is discharged from capability predicates over artifact
kinds, not from a named-pair if-ladder. A seat is structurally
incompatible when the union of its role capabilities both authors and
adjudicates (judge/vote/veto) the same kind.

Declared COI is a second constraint family: an interest tag overlapping
the matter fires only when the seat also holds an adjudicate capability.
Absence of declared_interests is a hard fail (uncontrolled silence).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
TEMPLATES_PATH = FIXTURES / "templates.json"
ROSTERS_PATH = FIXTURES / "rosters.json"

CAP_KEYS = ("author", "judge", "vote", "veto", "chair")
ADJUDICATE = ("judge", "vote", "veto")
STRUCTURAL = "SAME-SEAT-AUTHOR-ADJUDICATE"
COI = "DECLARED-INTEREST-OVERLAP-ON-ADJUDICATE"
MISSING_INTERESTS = "UNDECLARED-INTEREST-FIELD"
MISSING_CAPS = "UNDECLARED-CAPABILITIES"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_library(path: Path | None = None) -> dict[str, Any]:
    return load_json(path or TEMPLATES_PATH)


def empty_caps() -> dict[str, set[str]]:
    return {k: set() for k in CAP_KEYS}


def _as_caps(obj: dict[str, Any]) -> dict[str, set[str]] | None:
    if not all(k in obj for k in CAP_KEYS):
        return None
    out = empty_caps()
    for k in CAP_KEYS:
        vals = obj.get(k) or []
        if not isinstance(vals, list) or any(not isinstance(x, str) for x in vals):
            return None
        out[k] = set(vals)
    return out


def resolve_role(spec: Any, templates: dict[str, Any]) -> tuple[str, dict[str, set[str]] | None]:
    if isinstance(spec, str):
        row = (templates.get("templates") or {}).get(spec)
        if not isinstance(row, dict):
            return spec, None
        caps = _as_caps(row)
        return spec, caps
    if isinstance(spec, dict):
        rid = str(spec.get("id") or spec.get("name") or "custom")
        return rid, _as_caps(spec)
    return "invalid", None


def union_caps(roles: list[dict[str, set[str]]]) -> dict[str, set[str]]:
    out = empty_caps()
    for role in roles:
        for k in CAP_KEYS:
            out[k].update(role[k])
    return out


def structural_hits(caps: dict[str, set[str]]) -> list[dict[str, Any]]:
    authored = set(caps["author"])
    adjudicated: set[str] = set()
    by_cap: dict[str, set[str]] = {}
    for cap in ADJUDICATE:
        kinds = set(caps[cap])
        by_cap[cap] = kinds
        adjudicated.update(kinds)
    overlap = sorted(authored & adjudicated)
    hits = []
    for kind in overlap:
        caps_hit = [c for c in ADJUDICATE if kind in by_cap[c]]
        hits.append(
            {
                "constraint": STRUCTURAL,
                "kind": kind,
                "adjudicate_caps": caps_hit,
            }
        )
    return hits


def check_seat(
    seat: dict[str, Any],
    library: dict[str, Any],
    matter: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    templates = library.get("templates") or {}
    wrapped = {"templates": templates, **{k: v for k, v in library.items() if k != "templates"}}
    seat_id = str(seat.get("id") or "?")
    violations: list[dict[str, Any]] = []
    resolved: list[tuple[str, dict[str, set[str]]]] = []
    for spec in seat.get("roles") or []:
        rid, caps = resolve_role(spec, wrapped)
        if caps is None:
            violations.append(
                {
                    "constraint": MISSING_CAPS,
                    "seat": seat_id,
                    "role": rid,
                    "detail": "role lacks author/judge/vote/veto/chair predicates",
                }
            )
            continue
        resolved.append((rid, caps))
    if "declared_interests" not in seat:
        violations.append(
            {
                "constraint": MISSING_INTERESTS,
                "seat": seat_id,
                "detail": "declared_interests field absent; silence is not allowed",
            }
        )
        interests: set[str] = set()
    else:
        raw = seat.get("declared_interests")
        if not isinstance(raw, list) or any(not isinstance(x, str) for x in raw):
            violations.append(
                {
                    "constraint": MISSING_INTERESTS,
                    "seat": seat_id,
                    "detail": "declared_interests must be a list of strings",
                }
            )
            interests = set()
        else:
            interests = set(raw)
    if not resolved and any(v["constraint"] == MISSING_CAPS for v in violations):
        return violations
    caps = union_caps([c for _, c in resolved])
    role_ids = [r for r, _ in resolved]
    for hit in structural_hits(caps):
        violations.append(
            {
                "constraint": STRUCTURAL,
                "seat": seat_id,
                "roles": role_ids,
                "kind": hit["kind"],
                "adjudicate_caps": hit["adjudicate_caps"],
            }
        )
    tags = set((matter or {}).get("tags") or [])
    overlap = sorted(interests & tags)
    adjudicate_kinds = set()
    for cap in ADJUDICATE:
        adjudicate_kinds.update(caps[cap])
    if overlap and adjudicate_kinds:
        violations.append(
            {
                "constraint": COI,
                "seat": seat_id,
                "roles": role_ids,
                "interests": overlap,
                "detail": "declared interest overlaps matter tags while seat adjudicates",
            }
        )
    return violations


def check_roster(roster: dict[str, Any], library: dict[str, Any] | None = None) -> dict[str, Any]:
    lib = library if library is not None else load_library()
    matter = roster.get("matter") if isinstance(roster.get("matter"), dict) else {}
    violations: list[dict[str, Any]] = []
    for seat in roster.get("seats") or []:
        if isinstance(seat, dict):
            violations.extend(check_seat(seat, lib, matter))
    return {
        "roster_id": roster.get("id"),
        "fired": bool(violations),
        "silent": not violations,
        "violation_count": len(violations),
        "violations": violations,
    }


def enumerate_ordered_pairs(library: dict[str, Any] | None = None) -> dict[str, Any]:
    lib = library if library is not None else load_library()
    names = sorted((lib.get("templates") or {}).keys())
    rows = []
    incompatible = []
    compatible = []
    for a in names:
        for b in names:
            roster = {
                "id": f"pair:{a}+{b}",
                "matter": {"id": "pair-scan", "tags": []},
                "seats": [
                    {
                        "id": "seat-0",
                        "roles": [a, b],
                        "declared_interests": [],
                    }
                ],
            }
            result = check_roster(roster, lib)
            fired = bool(result["fired"])
            kinds = sorted(
                {
                    v["kind"]
                    for v in result["violations"]
                    if v.get("constraint") == STRUCTURAL and "kind" in v
                }
            )
            row = {
                "a": a,
                "b": b,
                "incompatible": fired,
                "kinds": kinds,
                "constraints": sorted({v["constraint"] for v in result["violations"]}),
            }
            rows.append(row)
            if fired:
                incompatible.append(row)
            else:
                compatible.append(row)
    unordered = {}
    for row in rows:
        key = tuple(sorted([row["a"], row["b"]]))
        unordered.setdefault(key, False)
        unordered[key] = unordered[key] or row["incompatible"]
    unordered_inc = sorted(["+".join(k) for k, v in unordered.items() if v])
    return {
        "template_count": len(names),
        "ordered_pair_count": len(rows),
        "incompatible_ordered": len(incompatible),
        "compatible_ordered": len(compatible),
        "incompatible_unordered": unordered_inc,
        "incompatible_unordered_count": len(unordered_inc),
        "rows": rows,
        "names": names,
    }


def load_rosters(path: Path | None = None) -> dict[str, Any]:
    return load_json(path or ROSTERS_PATH)
