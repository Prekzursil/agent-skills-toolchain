"""Reachability + integrity validator for the command-center backlog.

The one question this answers, which the prose backlog could not:
**is every item reachable from a final disposition?**

That is the unified contract's own completeness rule (L2001, quoted at
`L14-unified-contract.md:615`) and it was NOT COMPUTABLE for the whole life of
the program, because the backlog was a 4-column markdown table and neither
dependency graph was ever written. An item that no path can carry to a
disposition is precisely the "deferred, drafted, then forgotten" shape.

Checks, each independently falsifiable:

  REACH-1  referential integrity - every dependency id resolves to a real item.
  REACH-2  acyclicity            - no set of items mutually blocks itself.
  REACH-3  actionability         - every OPEN item has a next smallest action, or
                                   an owner gate, or at least one still-open
                                   dependency. An open item with none of the
                                   three is a DEAD END: nothing will ever move it.
  REACH-4  gate resolvability    - every owner_gate names a question that exists
                                   and is still open. A gate pointing at nothing
                                   is a dead end wearing a blocker's clothes.
  REACH-5  disposition evidence  - a terminal item names a terminal disposition
                                   AND cites evidence. "DONE" with no evidence is
                                   the DONE-CLAIMED failure this register exists
                                   to keep visible.
  REACH-6  no silent drop        - every id in the committed register snapshot is
                                   still in the catalog, and the snapshot is the
                                   one the catalog was seeded from (sha256).
  V-GRAPH  derived-graph parity  - the committed DEPENDENCY-GRAPH.json equals
                                   build_graph(catalog) byte for byte.
  V-FIELDS work-unit completeness- all 19 Prompt Two fields resolve per item,
                                   from the item or from the declared defaults.

FAIL CLOSED. An empty item list, an unreadable catalog, or a missing register
snapshot is a FAILURE, never "nothing found -> pass" (`rules/common/ci-hygiene.md`
section 1: a gate that cannot fail is indistinguishable from a no-op).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # pragma: no cover - import shim for direct runs
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalog as cat
import register_parse as rp

_ID_RE = re.compile(r"^(?:R|D|S|T)-[A-Z]?\d+$")


class Violation(dict):
    """A single finding. `dict` so the JSON report needs no encoder."""

    def __init__(self, check: str, item_id: str, detail: str) -> None:
        super().__init__(check=check, id=item_id, detail=detail)

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return f"{self['check']} {self['id']}: {self['detail']}"


def _resolved(item: dict[str, Any], defaults: dict[str, Any], field: str) -> bool:
    value = item.get(field, defaults.get(field))
    if value is None:
        return field == "disposition"
    if isinstance(value, str):
        return bool(value.strip()) and not value.strip().startswith("UNKNOWN")
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def validate(
    catalog: dict[str, Any],
    *,
    register_path: Path | None = None,
    graph: dict[str, Any] | None = None,
    require_complete: bool = False,
) -> tuple[list[Violation], dict[str, Any]]:
    """Run every check. Returns (violations, stats). Never raises on bad data."""
    violations: list[Violation] = []
    items = cat.items(catalog)
    defaults = (
        catalog.get("defaults", {}) if isinstance(catalog.get("defaults"), dict) else {}
    )

    if not items:
        violations.append(
            Violation("V-EMPTY", "-", "catalog holds zero items (fail closed)")
        )
        return violations, {"items": 0}

    index: dict[str, dict[str, Any]] = {}
    for item in items:
        item_id = str(item.get("id", "")).strip()
        if not _ID_RE.match(item_id):
            violations.append(
                Violation(
                    "V-ID",
                    item_id or "<blank>",
                    "id does not match ^(R|D|S|T)-[A-Z]?[0-9]+$",
                )
            )
            continue
        if item_id in index:
            violations.append(Violation("V-ID", item_id, "duplicate id"))
            continue
        index[item_id] = item

    open_ids = {node for node, item in index.items() if cat.is_open(item)}
    questions = {
        str(entry.get("id", "")): entry
        for entry in catalog.get("owner_questions", [])
        if isinstance(entry, dict)
    }

    # REACH-1 + the closed-depends-on-open contradiction.
    for node in sorted(index):
        item = index[node]
        for dep in cat.dependencies(item):
            if dep not in index:
                violations.append(
                    Violation("REACH-1", node, f"dependency {dep!r} does not exist")
                )
            elif not cat.is_open(item) and dep in open_ids:
                violations.append(
                    Violation(
                        "REACH-1",
                        node,
                        f"item is closed but depends on still-open {dep}",
                    )
                )

    # REACH-2
    for node in cat.find_cycle_nodes(catalog):
        violations.append(
            Violation(
                "REACH-2",
                node,
                "lies on a dependency cycle; can never reach a disposition",
            )
        )

    # REACH-3 + REACH-4
    for node in sorted(open_ids):
        item = index[node]
        action = str(item.get("next_smallest_action", "") or "").strip()
        has_action = bool(action) and not action.startswith("UNKNOWN")
        gates = [str(gate) for gate in item.get("owner_gate", []) or []]
        open_deps = [dep for dep in cat.dependencies(item) if dep in open_ids]
        live_gates = []
        for gate in gates:
            entry = questions.get(gate)
            if entry is None:
                violations.append(
                    Violation(
                        "REACH-4", node, f"owner_gate {gate!r} names no known question"
                    )
                )
            elif str(entry.get("state", "")).upper() != "OPEN":
                violations.append(
                    Violation(
                        "REACH-4",
                        node,
                        f"owner_gate {gate} is already {entry.get('state')}",
                    )
                )
            else:
                live_gates.append(gate)
        if not (has_action or live_gates or open_deps):
            violations.append(
                Violation(
                    "REACH-3",
                    node,
                    "DEAD END - open with no next smallest action, no live owner gate, and no open dependency",
                )
            )

    # REACH-5
    for node in sorted(index):
        item = index[node]
        disposition = item.get("disposition")
        if disposition is None:
            continue
        if disposition not in cat.TERMINAL_DISPOSITIONS:
            violations.append(
                Violation(
                    "REACH-5", node, f"disposition {disposition!r} is not terminal"
                )
            )
        if not str(item.get("disposition_evidence", "") or "").strip():
            violations.append(
                Violation(
                    "REACH-5", node, f"{disposition} with no disposition_evidence"
                )
            )

    # REACH-6
    provenance = (
        catalog.get("provenance", {})
        if isinstance(catalog.get("provenance"), dict)
        else {}
    )
    snapshot = register_path or (cat.repo_root() / str(provenance.get("register", "")))
    if not snapshot.is_file():
        violations.append(
            Violation("REACH-6", "-", f"register snapshot missing at {snapshot}")
        )
    else:
        # LF-NORMALISE BEFORE HASHING — the register snapshot is text, git stores it
        # with LF, and a Windows checkout under core.autocrlf=true materialises CRLF.
        # Hashing raw working-tree bytes made REACH-6 unsatisfiable on ANY Windows
        # checkout while passing on Linux CI (measured 2026-08-10: worktree digest
        # 1a404a91d819 vs the recorded 8b3e44cc3813, which is exactly the committed
        # blob). That is not a data defect, it is a portability defect in this gate.
        #
        # It was not cosmetic: render_status() embeds validate()'s violations, so the
        # phantom Windows violation was baked into the COMMITTED STATUS.md and then
        # showed up on CI as `cc-render drift=1` — a local-only measurement artifact
        # leaking into a tracked artifact. Same root cause as render_manifest.
        raw = snapshot.read_bytes().replace(b"\r\n", b"\n")
        digest = hashlib.sha256(raw).hexdigest()
        recorded = str(provenance.get("register_sha256", ""))
        if recorded and digest != recorded:
            violations.append(
                Violation(
                    "REACH-6",
                    "-",
                    f"register snapshot sha256 {digest[:12]} != recorded {recorded[:12]}",
                )
            )
        for row in rp.parse_text(raw.decode("utf-8")).rows:
            if row.row_id not in index:
                violations.append(
                    Violation(
                        "REACH-6",
                        row.row_id,
                        "present in the register snapshot, dropped from the catalog",
                    )
                )

    # V-GRAPH
    expected = cat.build_graph(catalog)
    if graph is not None and graph != expected:
        violations.append(
            Violation(
                "V-GRAPH",
                "-",
                "committed DEPENDENCY-GRAPH.json != build_graph(catalog); re-run seed/close",
            )
        )

    # V-FIELDS
    unresolved: list[str] = []
    default_only = 0
    for node in sorted(index):
        item = index[node]
        for field in cat.WORK_UNIT_FIELDS:
            if field in ("dependencies", "inputs") and not item.get(field):
                continue  # legitimately empty: a root item has neither
            if not _resolved(item, defaults, field):
                unresolved.append(f"{node}.{field}")
            elif field not in item and field in defaults:
                default_only += 1
    if unresolved and require_complete:
        for entry in unresolved:
            node, _, field = entry.partition(".")
            violations.append(
                Violation("V-FIELDS", node, f"work-unit field {field!r} unresolved")
            )

    stats = {
        "items": len(index),
        "open": len(open_ids),
        "closed": len(index) - len(open_ids),
        "edges": expected["edge_count"],
        "acyclic": expected["acyclic"],
        "owner_questions_open": sum(
            1 for q in questions.values() if str(q.get("state", "")).upper() == "OPEN"
        ),
        "work_unit_fields_unresolved": len(unresolved),
        "work_unit_fields_from_defaults": default_only,
        "by_program": _count(index, "program"),
        "by_status": _count(index, "status"),
    }
    return violations, stats


def _count(index: dict[str, dict[str, Any]], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in index.values():
        key = str(item.get(field, "") or "-")
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the command-center backlog.")
    parser.add_argument("--catalog", default=str(cat.catalog_path()))
    parser.add_argument("--graph", default=str(cat.graph_path()))
    parser.add_argument("--register", default=None)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument(
        "--json", action="store_true", help="emit the machine-readable report"
    )
    args = parser.parse_args(argv)

    try:
        catalog = cat.load(args.catalog)
    except Exception as exc:  # fail closed: an unreadable catalog is a failure
        print(f"FAILED:cc-validate cannot read {args.catalog}: {exc}")
        return 1
    graph: dict[str, Any] | None = None
    graph_path = Path(args.graph)
    if graph_path.is_file():
        try:
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"FAILED:cc-validate cannot read {graph_path}: {exc}")
            return 1
    else:
        print(f"FAILED:cc-validate dependency graph missing at {graph_path}")
        return 1

    violations, stats = validate(
        catalog,
        register_path=Path(args.register) if args.register else None,
        graph=graph,
        require_complete=args.require_complete,
    )
    if args.json:
        print(
            json.dumps(
                {"violations": violations, "stats": stats}, indent=2, sort_keys=True
            )
        )
    else:
        for violation in violations:
            print(f"  {violation}")
        print(
            "cc-validate "
            + " ".join(
                f"{key}={value}"
                for key, value in stats.items()
                if not isinstance(value, dict)
            )
        )
    if violations:
        print(f"FAILED:cc-validate violations={len(violations)}")
        return 1
    print(
        f"SUCCESS:cc-validate items={stats['items']} open={stats['open']} reachable=all"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
