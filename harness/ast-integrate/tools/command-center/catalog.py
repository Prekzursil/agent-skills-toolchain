"""The machine-readable backlog: load, save, and derive the dependency graph.

WHY THIS EXISTS. The unified two-program contract requires that *every backlog
item is reachable from a final disposition* (`L14-unified-contract.md:615`,
quoting contract L2001). That check was never computable, because the backlog
existed only as a 4-column prose table carrying 4 of its 33 mandated per-item
fields and neither `10-DEPENDENCY-GRAPH.json` nor
`11-CAPABILITY-PRESERVATION-GRAPH.json` was ever written. A prose table cannot
answer a reachability question; a graph can. This module is the graph.

The catalog is the SOURCE OF TRUTH once seeded. `command-center/sources/REGISTER.md`
is a committed provenance snapshot of the human-authored register it was seeded
from -- kept so the seed is reproducible and auditable, not so it can be re-read
as authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

# The 19 mandatory per-work-unit fields, verbatim from Prompt Two
# (`_USER-PROMPTS.md:10607-10625`). Order preserved so a reader can diff the
# catalog against the prompt without re-reading the corpus.
WORK_UNIT_FIELDS: tuple[str, ...] = (
    "id",
    "title",
    "phase",
    "target",
    "inputs",
    "dependencies",
    "assignment",
    "tool_permissions",
    "execution_substrate",
    "timeout_seconds",
    "output_path",
    "output_schema",
    "evidence_requirement",
    "tests_required",
    "reviewer_requirement",
    "completion_sentinel",
    "retry_policy",
    "failure_classification",
    "owner_approval_required",
)

# The nine operational fields that today live in a single `defaults` block.
# A unit overrides one by setting the key on the item (JSON null, 0, False,
# and [] included). Zero of 103 live items currently do.
OVERRIDEABLE_FIELDS: tuple[str, ...] = (
    "assignment",
    "tool_permissions",
    "execution_substrate",
    "timeout_seconds",
    "output_schema",
    "tests_required",
    "reviewer_requirement",
    "retry_policy",
    "failure_classification",
)

PROVENANCE_OVERRIDE = "override"
PROVENANCE_DEFAULT = "default"
PROVENANCE_UNSET = "unset"
PROVENANCE_ITEM = "item"

OVERRIDE_SEMANTICS: dict[str, str] = {
    "precedence": (
        "item-key-present-wins-including-json-null; absent key uses defaults; "
        "both absent is unset"
    ),
    "enforced_by": "tools/command-center/catalog.py:resolve_field",
}

# Backlog fields the unified contract mandates on top of the work-unit set
# (`L14-unified-contract.md:129-134`) that the register actually determines.
REGISTER_FIELDS: tuple[str, ...] = (
    "program",
    "section",
    "status",
    "disposition",
    "disposition_evidence",
    "effort",
    "evidence",
    "sources",
    "reverse_dependencies",
    "owner_gate",
    "security_class",
    "next_smallest_action",
    "defer",
    "history",
)

# A disposition is FINAL. An item carrying one is out of the open set forever;
# an item carrying `null` is still live and must be reachable from one of these.
TERMINAL_DISPOSITIONS: tuple[str, ...] = (
    "DONE-VERIFIED",
    "DROPPED-BY-OWNER",
    "SUPERSEDED",
)

# The register's own section -> the disposition that section asserts.
SECTION_DISPOSITION = {
    "OUTSTANDING": None,
    "DELIBERATELY-SKIPPED": "DROPPED-BY-OWNER",
    "SUPERSEDED": "SUPERSEDED",
    "SETTLED": "DONE-VERIFIED",
}

UNKNOWN = "UNKNOWN - not yet determined"


def repo_root() -> Path:
    """The checkout root, derived from this file's location (tools/command-center/)."""
    return Path(__file__).resolve().parents[2]


def command_center_dir() -> Path:
    return repo_root() / "command-center"


def catalog_path() -> Path:
    return command_center_dir() / "WORK-UNIT-CATALOG.json"


def graph_path() -> Path:
    return command_center_dir() / "DEPENDENCY-GRAPH.json"


def events_path() -> Path:
    return command_center_dir() / "events" / "EVENTS.jsonl"


def load(path: Path | str | None = None) -> dict[str, Any]:
    target = Path(path) if path else catalog_path()
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"catalog root is {type(data).__name__}, expected object")
    return data


def save(catalog: dict[str, Any], path: Path | str | None = None) -> Path:
    """Write the catalog deterministically (sorted keys, trailing newline, LF).

    `newline="\\n"` is not cosmetic on this box: a CRLF working-tree copy and the
    LF blob git stores are different bytes, and a formatter/parity gate run
    against the wrong one verifies nothing (`rules/common/windows-shell.md` 8b)."""
    import path_guard as pg

    if path is not None:
        pg.reject_unc(path)
    target = Path(path) if path else catalog_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(catalog, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if path is not None:
        pg.guarded_write_text(path, text)
        return Path(path)
    target.write_text(text, encoding="utf-8", newline="\n")
    return target


def items(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    raw = catalog.get("items")
    return list(raw) if isinstance(raw, list) else []


def work_units(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """The `work_units` array (the 2007 P2 units), distinct from `items`."""
    raw = catalog.get("work_units")
    return list(raw) if isinstance(raw, list) else []


def _id_normalize() -> Any:
    """Sibling module `id_normalize` (this directory is not an importable package)."""
    try:
        import id_normalize as inn  # type: ignore[import-not-found]

        return inn
    except ImportError:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "id_normalize", Path(__file__).resolve().with_name("id_normalize.py")
        )
        if spec is None or spec.loader is None:
            raise
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def _canonical_index(rows: list[dict[str, Any]]) -> Any:
    """Index rows by id behind the NFC boundary (`id_normalize.CanonicalIdMap`).

    An NFC and an NFD spelling of the same id resolve to one entity; a plain dict
    would treat them as two keys (the mixed-resolver hazard TST-0057 measures).
    Later rows with the same canonical id still win, as the plain dict did."""
    index = _id_normalize().CanonicalIdMap()
    for row in rows:
        index[str(row.get("id", ""))] = row
    return index


def by_id(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """`items` indexed by NFC-canonical id (a `CanonicalIdMap`, dict-compatible)."""
    return _canonical_index(items(catalog))


def work_units_by_id(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """`work_units` indexed by NFC-canonical id (a `CanonicalIdMap`, dict-compatible)."""
    return _canonical_index(work_units(catalog))


def is_open(item: dict[str, Any]) -> bool:
    """Open == no final disposition. Deferral does NOT close an item."""
    return not item.get("disposition")


def open_items(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in items(catalog) if is_open(item)]


def dependencies(item: dict[str, Any]) -> list[str]:
    raw = item.get("dependencies")
    return [str(dep) for dep in raw] if isinstance(raw, list) else []


def build_graph(catalog: dict[str, Any]) -> dict[str, Any]:
    """Derive DEPENDENCY-GRAPH.json from the catalog.

    Fully derived on purpose: a hand-maintained graph beside a hand-maintained
    catalog is two sources of truth that drift, and the validator asserts the
    committed graph still equals this function's output."""
    index = by_id(catalog)
    reverse: dict[str, list[str]] = {node: [] for node in index}
    edges: list[dict[str, str]] = []
    for node in sorted(index):
        for dep in sorted(set(dependencies(index[node]))):
            edges.append({"from": node, "blocked_by": dep})
            if dep in reverse:
                reverse[dep].append(node)
    nodes = []
    for node in sorted(index):
        item = index[node]
        nodes.append(
            {
                "id": node,
                "program": item.get("program", ""),
                "disposition": item.get("disposition"),
                "open": is_open(item),
                "effort": item.get("effort", ""),
                "owner_gate": item.get("owner_gate") or None,
                "blocked_by": sorted(set(dependencies(item))),
                "blocks": sorted(set(reverse.get(node, []))),
            }
        )
    order, residual = topological_order(catalog)
    return {
        "schema_version": SCHEMA_VERSION,
        "derived_from": "WORK-UNIT-CATALOG.json",
        "derivation": "tools/command-center/catalog.py:build_graph",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "acyclic": not residual,
        "cycle_nodes": find_cycle_nodes(catalog),
        "unorderable_nodes": residual,
        "topological_order": order,
        "nodes": nodes,
        "edges": edges,
    }


def _edge_map(catalog: dict[str, Any]) -> dict[str, set[str]]:
    """node -> the set of IN-CATALOG ids it is blocked by. Dangling ids are dropped
    here on purpose: referential integrity is REACH-1's job, and letting a typo'd
    id masquerade as a cycle would report one defect as two."""
    index = by_id(catalog)
    return {
        node: {dep for dep in dependencies(index[node]) if dep in index}
        for node in index
    }


def topological_order(catalog: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Kahn peel in dependency order.

    Returns `(order, residual)`. `order` lists ids such that every dependency
    precedes its dependent -- a legal execution sequence. `residual` is whatever
    could not be peeled, which is exactly the set of nodes lying on, or
    downstream of, a cycle. `residual == []` is the DAG proof."""
    blocked_by = _edge_map(catalog)
    remaining = dict(blocked_by)
    order: list[str] = []
    while True:
        ready = sorted(node for node, deps in remaining.items() if not deps)
        if not ready:
            break
        order.extend(ready)
        for node in ready:
            del remaining[node]
        done = set(ready)
        for deps in remaining.values():
            deps -= done
    return order, sorted(remaining)


def find_cycle_nodes(catalog: dict[str, Any]) -> list[str]:
    """The ids that actually sit ON a cycle.

    `topological_order`'s residual also contains innocent nodes merely blocked BY
    a cycle, which would misattribute the defect. Peeling the residual a second
    time from the other end (dropping nodes nothing in the residual depends on)
    removes those, leaving only mutually-blocking members."""
    _, residual = topological_order(catalog)
    alive = set(residual)
    blocked_by = {
        node: set(deps) & alive
        for node, deps in _edge_map(catalog).items()
        if node in alive
    }
    while True:
        blockers = {dep for deps in blocked_by.values() for dep in deps}
        dead = {node for node in blocked_by if node not in blockers}
        if not dead:
            break
        for node in dead:
            del blocked_by[node]
        for deps in blocked_by.values():
            deps -= dead
    return sorted(blocked_by)


def catalog_defaults(catalog: dict[str, Any]) -> dict[str, Any] | None:
    """The catalog `defaults` object, or None when missing / not an object."""
    raw = catalog.get("defaults")
    return raw if isinstance(raw, dict) else None


def defaults_block_problems(catalog: dict[str, Any]) -> list[str]:
    """Structural problems in the defaults block (empty list = usable)."""
    defaults = catalog_defaults(catalog)
    if defaults is None:
        return ["defaults block is missing or not an object"]
    return [
        f"defaults missing {field}"
        for field in OVERRIDEABLE_FIELDS
        if field not in defaults
    ]


def resolve_field(
    item: dict[str, Any],
    defaults: dict[str, Any] | None,
    field: str,
) -> dict[str, Any]:
    """Effective value + provenance for one of the nine overridable fields.

    Precedence is `field in item`, not a truthiness `or`: JSON null, 0, False,
    and [] on the unit are overrides. An absent key falls through to defaults.
    """
    defaults = defaults or {}
    if field in item:
        return {
            "field": field,
            "value": item[field],
            "provenance": PROVENANCE_OVERRIDE,
        }
    if field in defaults:
        return {
            "field": field,
            "value": defaults[field],
            "provenance": PROVENANCE_DEFAULT,
        }
    return {"field": field, "value": None, "provenance": PROVENANCE_UNSET}


def resolve_contract_field(
    item: dict[str, Any],
    defaults: dict[str, Any] | None,
    field: str,
) -> dict[str, Any]:
    """Same rule as resolve_field; provenance token is `item` not `override`."""
    view = resolve_field(item, defaults, field)
    if view["provenance"] == PROVENANCE_OVERRIDE:
        return {**view, "provenance": PROVENANCE_ITEM}
    return view


def resolve_item(
    item: dict[str, Any],
    defaults: dict[str, Any] | None,
) -> dict[str, Any]:
    """Resolved view of all nine overridable fields on one item."""
    fields = [resolve_field(item, defaults, field) for field in OVERRIDEABLE_FIELDS]
    return {
        "id": item.get("id"),
        "fields": fields,
        "override_count": sum(
            1 for row in fields if row["provenance"] == PROVENANCE_OVERRIDE
        ),
        "default_count": sum(
            1 for row in fields if row["provenance"] == PROVENANCE_DEFAULT
        ),
        "unset_count": sum(
            1 for row in fields if row["provenance"] == PROVENANCE_UNSET
        ),
    }


def items_overriding(catalog: dict[str, Any]) -> list[str]:
    """Ids of items that set at least one of the nine overridable fields."""
    hits: list[str] = []
    for item in items(catalog):
        if any(field in item for field in OVERRIDEABLE_FIELDS):
            hits.append(str(item.get("id", "")))
    return hits
