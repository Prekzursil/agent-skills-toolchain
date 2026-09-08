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

# The nine fields that live in catalog `defaults` and may be overridden per unit.
# Measured: 0 of 103 legacy `items` override any of these; work_units may stamp
# them per-row. Precedence is enforced by `resolve_field` (IMP-0436), not prose.
OVERRIDEABLE_DEFAULT_FIELDS: tuple[str, ...] = (
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

# Slice authors use question_or_target / assigned_model_vendor_role spellings.
FIELD_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "assignment": ("assignment", "assigned_model_vendor_role"),
    "target": ("target", "question_or_target"),
}


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
    target = Path(path) if path else catalog_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(catalog, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    target.write_text(text, encoding="utf-8", newline="\n")
    return target


def items(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    raw = catalog.get("items")
    return list(raw) if isinstance(raw, list) else []


def by_id(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id", "")): item for item in items(catalog)}


def is_open(item: dict[str, Any]) -> bool:
    """Open == no final disposition. Deferral does NOT close an item."""
    return not item.get("disposition")


def open_items(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in items(catalog) if is_open(item)]


def dependencies(item: dict[str, Any]) -> list[str]:
    raw = item.get("dependencies")
    return [str(dep) for dep in raw] if isinstance(raw, list) else []


def field_keys(field: str) -> tuple[str, ...]:
    """JSON object keys that declare `field` on a unit (canonical + aliases)."""
    return FIELD_KEY_ALIASES.get(field, (field,))


def item_declares_field(item: dict[str, Any], field: str) -> bool:
    """True iff the unit object contains the field key — even when value is JSON null.

    Presence of the key is the override signal. A missing key falls through to
    defaults; a present key with value `null` is explicit-null, not fall-through.
    """
    return any(key in item for key in field_keys(field))


def item_field_value(item: dict[str, Any], field: str) -> Any:
    """Return the unit's declared value for `field` (may be None). Raises KeyError."""
    for key in field_keys(field):
        if key in item:
            return item[key]
    raise KeyError(field)


def resolve_field(
    item: dict[str, Any],
    defaults: dict[str, Any] | None,
    field: str,
) -> dict[str, Any]:
    """Resolve one field with enforced precedence and provenance.

    Precedence (enforced here, not merely described):
      1. Unit declares the key (including explicit JSON null) → unit wins.
      2. Else defaults declares the key → default wins.
      3. Else provenance=`unset`, value=None.

    Provenance values: `override` | `explicit-null` | `default` | `unset`.
    """
    if item_declares_field(item, field):
        value = item_field_value(item, field)
        if value is None:
            return {"field": field, "value": None, "provenance": "explicit-null"}
        return {"field": field, "value": value, "provenance": "override"}
    if isinstance(defaults, dict) and field in defaults:
        return {
            "field": field,
            "value": defaults[field],
            "provenance": "default",
        }
    return {"field": field, "value": None, "provenance": "unset"}


def resolve_unit(
    item: dict[str, Any],
    defaults: dict[str, Any] | None,
    *,
    fields: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Resolved view for one unit: effective value + provenance per field."""
    target_fields = fields or OVERRIDEABLE_DEFAULT_FIELDS
    resolved = {
        field: resolve_field(item, defaults, field) for field in target_fields
    }
    return {
        "id": str(item.get("id", "")),
        "fields": resolved,
    }


def defaults_block_violations(catalog: dict[str, Any]) -> list[dict[str, str]]:
    """Fail closed when the global defaults block is missing or incomplete.

    Deleting `defaults` (or a single overrideable default that items still rely
    on) must not silently leave nine fields unset — that silence was measured
    green under bare `validate.py` before IMP-0436.
    """
    findings: list[dict[str, str]] = []
    item_list = items(catalog)
    raw_defaults = catalog.get("defaults", None)

    if not isinstance(raw_defaults, dict):
        findings.append(
            {
                "check": "V-DEFAULTS",
                "id": "-",
                "detail": (
                    "catalog `defaults` block is missing or not an object — "
                    "overrideable fields cannot resolve; fail closed"
                ),
            }
        )
        return findings

    for field in OVERRIDEABLE_DEFAULT_FIELDS:
        if field in raw_defaults:
            continue
        reliant = [
            str(item.get("id", ""))
            for item in item_list
            if not item_declares_field(item, field)
        ]
        if not reliant:
            # Every item overrides this field; missing default is still a
            # contract gap for future items, but not an immediate unset.
            continue
        sample = ", ".join(reliant[:5])
        more = f" (+{len(reliant) - 5} more)" if len(reliant) > 5 else ""
        findings.append(
            {
                "check": "V-DEFAULTS",
                "id": "-",
                "detail": (
                    f"defaults.{field} missing while {len(reliant)} item(s) "
                    f"rely on it (e.g. {sample}{more})"
                ),
            }
        )
    return findings


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
