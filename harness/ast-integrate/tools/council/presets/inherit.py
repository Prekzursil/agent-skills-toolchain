"""Preset inheritance and templating (IMP-0359).

A preset catalog is a mapping ``id -> record``.  A record may name a parent
with ``extends`` and declares its own dials either under ``overrides.dials``
(the templating form) or directly under ``dials`` (the root form).  Resolution
walks the chain root-first and lets the *child* win on every conflicting dial;
``parent_wins=True`` is the negative control, a merge order in which an
ancestor's declaration clobbers what the child declared.

Two dials are safety dials with an ordered strength scale
(:data:`SAFETY_RANKS`).  :func:`find_safety_weakenings` FIRES when a child
resolves to a weaker rank than its parent (``rank-regression``) or when the
merge silently hands a child a weaker value than the one it declared
(``silent-clobber-of-declared``).  :func:`resolve_strict` refuses such a child.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Mapping

MEASURED_COUNT = 72

SAFETY_RANKS: dict[str, tuple[str, ...]] = {
    "evidence_standard": (
        "anecdote",
        "secondary",
        "citation",
        "primary-source",
        "replication",
        "adversarial-replication",
    ),
    "anti_sycophancy": ("off", "advisory", "enforced"),
}

_MISSING = object()


class InheritError(Exception):
    """Raised on a missing parent, a cycle, or (strict mode) a safety weakening."""


@dataclass(frozen=True)
class Weakening:
    kind: str
    child_id: str
    base_id: str
    field: str
    child_value: Any
    base_value: Any
    child_rank: int
    base_rank: int
    declared_value: Any = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def rank(field: str, value: Any) -> int | None:
    """Position of ``value`` on the field's strength scale; None when unranked."""
    scale = SAFETY_RANKS.get(field)
    if scale is None or value is None:
        return None
    try:
        return scale.index(str(value))
    except ValueError:
        return None


def declared_overlay(node: Mapping[str, Any] | None) -> dict[str, Any]:
    """The dials a record declares for itself (templating form first, root form second)."""
    if not isinstance(node, Mapping):
        return {}
    overrides = node.get("overrides")
    if isinstance(overrides, Mapping) and isinstance(overrides.get("dials"), Mapping):
        return dict(overrides["dials"])
    if isinstance(node.get("dials"), Mapping):
        return dict(node["dials"])
    return {}


def _chain(node_id: str, catalog: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Records from ``node_id`` up to its root; raises on a missing link or a cycle."""
    seen: list[str] = []
    cur = str(node_id)
    chain: list[dict[str, Any]] = []
    while cur:
        if cur in seen:
            raise InheritError(f"cycle:{' -> '.join(seen + [cur])}")
        if cur not in catalog:
            raise InheritError(f"missing:{cur}")
        seen.append(cur)
        rec = dict(catalog[cur])
        rec.setdefault("id", cur)
        chain.append(rec)
        cur = str(rec.get("extends") or "")
    return chain


def resolve(
    node_id: str,
    catalog: Mapping[str, Mapping[str, Any]],
    parent_wins: bool = False,
) -> dict[str, Any]:
    """Resolve one preset: merged ``dials`` plus ``_trace`` (ancestor ids, root first)."""
    chain = _chain(node_id, catalog)
    dials: dict[str, Any] = {}
    if parent_wins:
        # Negative control: descendants first, then ancestors overwrite them.
        for node in chain:
            dials.update(declared_overlay(node))
    else:
        for node in reversed(chain):
            dials.update(declared_overlay(node))
    result = dict(chain[0])
    result["dials"] = dials
    result["_trace"] = [str(node["id"]) for node in reversed(chain[1:])]
    result["_declared"] = declared_overlay(chain[0])
    result["_parent_wins"] = bool(parent_wins)
    return result


def resolve_all(
    catalog: Mapping[str, Mapping[str, Any]],
    parent_wins: bool = False,
) -> dict[str, dict[str, Any]]:
    return {str(k): resolve(str(k), catalog, parent_wins=parent_wins) for k in catalog}


def check_weakening(
    child: Mapping[str, Any],
    base: Mapping[str, Any],
    declared: Mapping[str, Any] | None = None,
) -> list[Weakening]:
    """Compare two *resolved* presets on the safety dials.

    ``rank-regression``: the child resolved weaker than its base.
    ``silent-clobber-of-declared``: the child resolved weaker than what it
    declared for itself (only possible under a parent-wins merge).
    """
    child_dials = child.get("dials") or {}
    base_dials = base.get("dials") or {}
    child_id = str(child.get("id") or "")
    base_id = str(base.get("id") or "")
    declared = declared if declared is not None else (child.get("_declared") or {})
    findings: list[Weakening] = []
    for field in SAFETY_RANKS:
        cv = child_dials.get(field)
        cr = rank(field, cv)
        if cr is None:
            continue
        br = rank(field, base_dials.get(field))
        if br is not None and cr < br:
            findings.append(
                Weakening(
                    kind="rank-regression",
                    child_id=child_id,
                    base_id=base_id,
                    field=field,
                    child_value=cv,
                    base_value=base_dials.get(field),
                    child_rank=cr,
                    base_rank=br,
                )
            )
        if field in declared:
            dr = rank(field, declared[field])
            if dr is not None and cr < dr:
                findings.append(
                    Weakening(
                        kind="silent-clobber-of-declared",
                        child_id=child_id,
                        base_id=base_id,
                        field=field,
                        child_value=cv,
                        base_value=base_dials.get(field),
                        child_rank=cr,
                        base_rank=dr,
                        declared_value=declared[field],
                    )
                )
    return findings


def find_safety_weakenings(
    catalog: Mapping[str, Mapping[str, Any]],
    parent_wins: bool = False,
) -> list[Weakening]:
    """Every child/parent pair in the catalog, checked after resolution."""
    findings: list[Weakening] = []
    for nid in catalog:
        parent = str(catalog[nid].get("extends") or "")
        if not parent:
            continue
        child_res = resolve(str(nid), catalog, parent_wins=parent_wins)
        base_res = resolve(parent, catalog, parent_wins=parent_wins)
        findings.extend(
            check_weakening(child_res, base_res, declared=declared_overlay(catalog[nid]))
        )
    return findings


def resolve_strict(
    node_id: str,
    catalog: Mapping[str, Mapping[str, Any]],
    parent_wins: bool = False,
) -> dict[str, Any]:
    """Resolve, but refuse a preset that weakens a safety dial relative to its parent."""
    result = resolve(node_id, catalog, parent_wins=parent_wins)
    parent = str(catalog[node_id].get("extends") or "")
    if parent:
        base = resolve(parent, catalog, parent_wins=parent_wins)
        findings = check_weakening(result, base, declared=declared_overlay(catalog[node_id]))
        if findings:
            first = findings[0]
            raise InheritError(
                f"weakening:{node_id}:{first.field} {first.child_value!r} "
                f"(rank {first.child_rank}) < {first.base_value!r} (rank {first.base_rank}) "
                f"kind={first.kind}"
            )
    return result


def descendants(node_id: str, catalog: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """Transitive descendants of ``node_id`` in catalog order (cycle-safe)."""
    out: list[str] = []
    frontier = [str(node_id)]
    seen: set[str] = set()
    while frontier:
        cur = frontier.pop(0)
        for nid, node in catalog.items():
            if str(node.get("extends") or "") == cur and str(nid) not in seen:
                seen.add(str(nid))
                out.append(str(nid))
                frontier.append(str(nid))
    return out


def mutate_and_reresolve(
    catalog: Mapping[str, Mapping[str, Any]],
    base_id: str,
    patch: Any,
    value: Any = _MISSING,
) -> dict[str, dict[str, Any]]:
    """Mutate one record and re-resolve the whole catalog (live propagation).

    ``patch`` is a record patch such as ``{"dials": {"quorum": 99}}``; dials are
    merged into the record's own declaration slot so a descendant's override of
    the same dial still wins.  The legacy ``(field, value)`` spelling is kept.
    """
    if value is not _MISSING:
        patch = {"dials": {str(patch): value}}
    if not isinstance(patch, Mapping):
        raise InheritError(f"patch must be a mapping, got {type(patch).__name__}")
    if base_id not in catalog:
        raise InheritError(f"missing:{base_id}")
    cat = {str(k): deepcopy(dict(v)) for k, v in catalog.items()}
    node = cat[str(base_id)]
    for key, val in patch.items():
        if key == "dials" and isinstance(val, Mapping):
            overrides = node.get("overrides")
            if isinstance(overrides, dict) and isinstance(overrides.get("dials"), dict):
                overrides["dials"].update(val)
            else:
                dials = dict(node.get("dials") or {})
                dials.update(val)
                node["dials"] = dials
        else:
            node[key] = deepcopy(val)
    return resolve_all(cat)


def build_measured_72() -> dict[str, dict[str, Any]]:
    """A 72-preset catalog: one root, 8 families, 7 children each, 7 grandchildren.

    Overrides touch only non-safety dials, so the catalog resolves without a
    single weakening; ``root.07``'s children override ``quorum`` to exercise the
    child-wins path.
    """
    cat: dict[str, dict[str, Any]] = {
        "root": {
            "id": "root",
            "dials": {
                "evidence_standard": "primary-source",
                "anti_sycophancy": "enforced",
                "quorum": 4,
                "max_rounds": 8,
                "protocol": "deliberative",
            },
        }
    }
    for f in range(8):
        fam = f"root.{f:02d}"
        cat[fam] = {
            "id": fam,
            "extends": "root",
            "overrides": {"dials": {"label": fam, "max_rounds": 8 + f}},
        }
        for c in range(7):
            cid = f"{fam}.p{c}"
            dials: dict[str, Any] = {"label": cid}
            if f == 7:
                dials["quorum"] = 5
            cat[cid] = {"id": cid, "extends": fam, "overrides": {"dials": dials}}
    for g in range(7):
        gid = f"root.00.p0.q{g}"
        cat[gid] = {
            "id": gid,
            "extends": "root.00.p0",
            "overrides": {"dials": {"label": gid, "reviewer_count": 1 + g}},
        }
    if len(cat) != MEASURED_COUNT:
        raise InheritError(f"measured catalog has {len(cat)} presets, want {MEASURED_COUNT}")
    return cat
