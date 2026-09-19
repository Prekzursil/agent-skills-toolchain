#!/usr/bin/env python3
"""CC-0017: provisional Phase-1 canonical claim-record contract.

PROVISIONAL — superseded by Phase-4 unit ARC-0085. This module validates claim
records against command-center/schema/claim-record.provisional.v1.schema.json,
rejects missing settling probes, duplicate-of cycles, and contradiction edges
to unknown claim ids, and migrates CLAIM-REGISTRY rows with no field loss.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
SCHEMA_REL = "command-center/schema/claim-record.provisional.v1.schema.json"
SCHEMA_PATH = REPO / SCHEMA_REL
REGISTRY_REL = "command-center/CLAIM-REGISTRY.json"

PROVISIONAL = True
SCHEMA_STATUS = "PROVISIONAL"
SUPERSEDED_BY_UNIT = "ARC-0085"
PHASE4_FORMALIZATION_UNIT = "ARC-0085"
SCHEMA_VERSION = 1

BANDS = {"almost-certain", "likely", "uncertain"}
VERDICTS = {
    "CONFIRMED",
    "REFUTED",
    "NOT-CHECKED",
    "PARTIAL",
    "UNVERIFIED",
}


class ClaimRecordError(ValueError):
    """Validation failure for a provisional claim record or registry graph."""


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def provisional_meta() -> dict[str, Any]:
    schema = load_schema()
    return {
        "provisional": True,
        "schema_status": SCHEMA_STATUS,
        "superseded_by_unit": SUPERSEDED_BY_UNIT,
        "phase4_formalization_unit": PHASE4_FORMALIZATION_UNIT,
        "schema_path": SCHEMA_REL,
        "schema_version": SCHEMA_VERSION,
        "schema_x_provisional": schema.get("x-provisional"),
        "schema_x_superseded_by_unit": schema.get("x-superseded-by-unit"),
    }


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_claim(
    record: dict[str, Any],
    *,
    known_ids: set[str] | None = None,
    check_edges: bool = True,
) -> list[str]:
    """Return a list of validation error strings (empty means OK)."""
    errs: list[str] = []
    if not isinstance(record, dict):
        return ["record must be an object"]

    if record.get("schema_version") != SCHEMA_VERSION:
        errs.append(f"schema_version must be {SCHEMA_VERSION}")
    if record.get("schema_status") != SCHEMA_STATUS:
        errs.append("schema_status must be PROVISIONAL")
    if record.get("superseded_by_unit") != SUPERSEDED_BY_UNIT:
        errs.append(f"superseded_by_unit must be {SUPERSEDED_BY_UNIT}")

    claim_id = record.get("claim_id")
    if not _nonempty_str(claim_id):
        errs.append("claim_id is required")

    if not _nonempty_str(record.get("canonical_mechanism")):
        errs.append("canonical_mechanism is required")

    for edge_key in ("duplicate_of", "supports", "contradicts"):
        edges = record.get(edge_key)
        if not isinstance(edges, list):
            errs.append(f"{edge_key} must be an array")
        else:
            for i, target in enumerate(edges):
                if not _nonempty_str(target):
                    errs.append(f"{edge_key}[{i}] must be a non-empty string")

    lineage = record.get("source_lineage")
    if not isinstance(lineage, list) or len(lineage) < 1:
        errs.append("source_lineage must be a non-empty array")
    else:
        for i, entry in enumerate(lineage):
            if not isinstance(entry, dict) or not _nonempty_str(entry.get("anchor")):
                errs.append(f"source_lineage[{i}].anchor is required")

    conf = record.get("confidence")
    if conf is not None and conf not in BANDS:
        errs.append(f"confidence must be null or one of {sorted(BANDS)}")

    status = record.get("verification_status")
    if status not in VERDICTS:
        errs.append(f"verification_status must be one of {sorted(VERDICTS)}")

    if not _nonempty_str(record.get("implementation_impact")):
        errs.append("implementation_impact is required")

    # Exact settling probe is mandatory (CC-0017 planted control).
    if not _nonempty_str(record.get("settling_probe")):
        errs.append("settling_probe is required (exact settling probe is mandatory)")

    if check_edges and known_ids is not None:
        present = set(known_ids)
        for edge_key in ("duplicate_of", "supports", "contradicts"):
            for target in record.get(edge_key) or []:
                if isinstance(target, str) and target not in present:
                    errs.append(
                        f"{edge_key} target {target!r} does not exist in claim id set"
                    )
    return errs


def find_duplicate_of_cycles(records: list[dict[str, Any]]) -> list[list[str]]:
    """Return list of cycles in the directed duplicate_of graph."""
    adj: dict[str, list[str]] = {}
    for rec in records:
        cid = rec.get("claim_id")
        if not isinstance(cid, str):
            continue
        adj.setdefault(cid, [])
        for target in rec.get("duplicate_of") or []:
            if isinstance(target, str):
                adj[cid].append(target)
                adj.setdefault(target, [])

    cycles: list[list[str]] = []
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in adj}
    for start in list(adj):
        if color[start] != WHITE:
            continue
        stack: list[tuple[str, int]] = [(start, 0)]
        path: list[str] = [start]
        color[start] = GRAY
        while stack:
            node, idx = stack[-1]
            children = adj[node]
            if idx < len(children):
                stack[-1] = (node, idx + 1)
                nxt = children[idx]
                if color.get(nxt, WHITE) == GRAY:
                    cyc_start = path.index(nxt)
                    cycles.append(path[cyc_start:] + [nxt])
                    continue
                if color.get(nxt, WHITE) == WHITE:
                    color[nxt] = GRAY
                    stack.append((nxt, 0))
                    path.append(nxt)
            else:
                stack.pop()
                path.pop()
                color[node] = BLACK
    return cycles


def validate_registry(records: list[dict[str, Any]]) -> list[str]:
    """Validate a set of provisional claims including graph constraints."""
    errs: list[str] = []
    ids: list[str] = []
    for i, rec in enumerate(records):
        cid = rec.get("claim_id")
        if isinstance(cid, str):
            ids.append(cid)
        else:
            errs.append(f"records[{i}]: missing claim_id")
    if len(ids) != len(set(ids)):
        errs.append("duplicate claim_id values in registry")

    known = set(ids)
    for i, rec in enumerate(records):
        for e in validate_claim(rec, known_ids=known, check_edges=True):
            errs.append(f"records[{i}]/{rec.get('claim_id')}: {e}")

    for cycle in find_duplicate_of_cycles(records):
        errs.append("duplicate_of cycle: " + " -> ".join(cycle))
    return errs


def assert_valid_registry(records: list[dict[str, Any]]) -> None:
    errs = validate_registry(records)
    if errs:
        raise ClaimRecordError("; ".join(errs[:20]))


def migrate_from_legacy(legacy: dict[str, Any]) -> dict[str, Any]:
    """Migrate one CLAIM-REGISTRY claim into the provisional record.

    Every original field is preserved under legacy_fields (no field loss).
    """
    if not isinstance(legacy, dict):
        raise ClaimRecordError("legacy claim must be an object")
    claim_id = legacy.get("id")
    if not _nonempty_str(claim_id):
        raise ClaimRecordError("legacy claim missing id")

    claim_text = legacy.get("claim")
    if not _nonempty_str(claim_text):
        claim_text = str(claim_id)

    settling = (
        legacy.get("settling_experiment")
        or legacy.get("verifier_probe")
        or legacy.get("source_probe")
    )
    if not _nonempty_str(settling):
        # Still emit a record shape, but validation will reject empty probes.
        settling = ""

    lineage: list[dict[str, Any]] = []
    if _nonempty_str(legacy.get("evidence")):
        lineage.append(
            {
                "anchor": legacy["evidence"],
                "probe": legacy.get("source_probe"),
                "sha256": None,
                "fetched_at": None,
                "note": "migrated from CLAIM-REGISTRY evidence",
            }
        )
    if _nonempty_str(legacy.get("source_probe")):
        lineage.append(
            {
                "anchor": f"source_probe:{legacy['source_probe']}",
                "probe": legacy.get("source_probe"),
                "sha256": None,
                "fetched_at": None,
                "note": "migrated source_probe",
            }
        )
    if not lineage:
        lineage.append(
            {
                "anchor": f"claim-registry:{claim_id}",
                "probe": None,
                "sha256": None,
                "fetched_at": None,
                "note": "placeholder lineage for legacy row without evidence",
            }
        )

    verdict = legacy.get("verdict") or "UNVERIFIED"
    if verdict not in VERDICTS:
        verdict = "UNVERIFIED"

    band = legacy.get("band")
    if band not in BANDS:
        band = None

    impact_bits = [
        f"verdict={legacy.get('verdict')}",
        f"band={legacy.get('band')}",
    ]
    if legacy.get("verifier_probe"):
        impact_bits.append("has_verifier_probe")

    return {
        "schema_version": SCHEMA_VERSION,
        "schema_status": SCHEMA_STATUS,
        "superseded_by_unit": SUPERSEDED_BY_UNIT,
        "claim_id": claim_id,
        "canonical_mechanism": claim_text,
        "claim_text": claim_text,
        "duplicate_of": list(legacy.get("duplicate_of") or []),
        "supports": list(legacy.get("supports") or []),
        "contradicts": list(legacy.get("contradicts") or []),
        "source_lineage": lineage,
        "confidence": band,
        "verification_status": verdict,
        "implementation_impact": (
            "Migrated CLAIM-REGISTRY row; impact inferred from "
            + ", ".join(impact_bits)
        ),
        "settling_probe": settling if isinstance(settling, str) else "",
        "legacy_fields": json.loads(json.dumps(legacy)),
    }


def migrate_registry_file(
    path: Path | None = None, *, claim_ids: list[str] | None = None
) -> list[dict[str, Any]]:
    data = json.loads((path or (REPO / REGISTRY_REL)).read_text(encoding="utf-8"))
    claims = data.get("claims") or []
    if claim_ids is not None:
        wanted = set(claim_ids)
        claims = [c for c in claims if c.get("id") in wanted]
    return [migrate_from_legacy(c) for c in claims]


def roundtrip_legacy_fields(legacy: dict[str, Any]) -> bool:
    migrated = migrate_from_legacy(legacy)
    return migrated.get("legacy_fields") == legacy


def recompute_schedule_after_soft_1_2(
    phase_graph_path: Path | None = None,
) -> dict[str, Any]:
    """Recompute schedule claim from PHASE-GRAPH edges after flipping 1->2 to SOFT.

    Does not mutate the on-disk phase graph. Returns before/after critical paths
    and B03 unit count measured from allocation_buckets.
    """
    path = phase_graph_path or (REPO / "command-center/PHASE-GRAPH.json")
    graph = json.loads(path.read_text(encoding="utf-8"))
    nodes = [str(p["id"]) for p in graph.get("phases", []) if isinstance(p, dict)]
    edges = [dict(e) for e in graph.get("edges", []) if isinstance(e, dict)]

    def longest_hard(edge_list: list[dict[str, Any]]) -> list[str]:
        hard = [(e["from"], e["to"]) for e in edge_list if e.get("type") == "HARD"]
        adj: dict[str, list[str]] = {n: [] for n in nodes}
        indeg = {n: 0 for n in nodes}
        for u, v in hard:
            if u in adj and v in adj:
                adj[u].append(v)
                indeg[v] += 1
        from collections import deque

        q = deque(n for n in nodes if indeg[n] == 0)
        topo: list[str] = []
        indeg_work = dict(indeg)
        while q:
            u = q.popleft()
            topo.append(u)
            for v in adj[u]:
                indeg_work[v] -= 1
                if indeg_work[v] == 0:
                    q.append(v)
        dist = {n: 1 for n in nodes}
        prev: dict[str, str | None] = {n: None for n in nodes}
        for u in topo:
            for v in adj[u]:
                if dist[u] + 1 > dist[v]:
                    dist[v] = dist[u] + 1
                    prev[v] = u
        end = max(nodes, key=lambda n: dist[n])
        chain: list[str] = []
        cur: str | None = end
        while cur is not None:
            chain.append(cur)
            cur = prev[cur]
        chain.reverse()
        return chain

    before_path = longest_hard(edges)
    soft_edges = []
    flipped = False
    for e in edges:
        ne = dict(e)
        if ne.get("from") == "1" and ne.get("to") == "2" and ne.get("type") == "HARD":
            ne["type"] = "SOFT"
            ne["reason"] = (
                (ne.get("reason") or "")
                + " [CC-0017 provisional claim-record schema authored; "
                "author proposes SOFT pending dual independent review]"
            )
            flipped = True
        soft_edges.append(ne)
    after_path = longest_hard(soft_edges)

    buckets = (graph.get("allocation_buckets") or {}).get("buckets") or []
    b03 = next((b for b in buckets if b.get("id") == "B03"), None)
    b03_units = int(b03["units"]) if b03 else None

    return {
        "provisional_schema": SCHEMA_REL,
        "schema_status": SCHEMA_STATUS,
        "superseded_by_unit": SUPERSEDED_BY_UNIT,
        "edge_1_2_flipped_hard_to_soft": flipped,
        "before": {
            "critical_path": before_path,
            "node_count": len(before_path),
        },
        "after": {
            "critical_path": after_path,
            "node_count": len(after_path),
        },
        "b03_units_released_if_soft": b03_units,
        "schedule_claim_recomputed": {
            "units_released": b03_units,
            "critical_path_before": len(before_path),
            "critical_path_after": len(after_path),
            "delta_nodes": len(before_path) - len(after_path),
        },
        "note": (
            "Schedule numbers recomputed from edges[] after in-memory 1->2 HARD->SOFT. "
            "Author schedule claim is not SUCCESS; dual reviewers must independently "
            "confirm the SOFT reclassification."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_meta = sub.add_parser("meta", help="Print PROVISIONAL metadata")
    p_meta.set_defaults(func=lambda _a: print(json.dumps(provisional_meta(), indent=2)))

    p_sched = sub.add_parser("schedule", help="Recompute schedule after soft 1->2")
    p_sched.set_defaults(
        func=lambda _a: print(json.dumps(recompute_schedule_after_soft_1_2(), indent=2))
    )

    p_mig = sub.add_parser("migrate", help="Migrate selected CLAIM-REGISTRY ids")
    p_mig.add_argument("--ids", nargs="+", required=True)
    p_mig.add_argument("--out", type=Path, default=None)

    def _migrate(args: argparse.Namespace) -> None:
        rows = migrate_registry_file(claim_ids=args.ids)
        payload = {
            "schema_status": SCHEMA_STATUS,
            "superseded_by_unit": SUPERSEDED_BY_UNIT,
            "claims": rows,
        }
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
            print(f"wrote {args.out} claims={len(rows)}")
        else:
            print(text)

    p_mig.set_defaults(func=_migrate)

    p_val = sub.add_parser("validate-file", help="Validate a migrated claims JSON")
    p_val.add_argument("path", type=Path)

    def _validate(args: argparse.Namespace) -> None:
        doc = json.loads(args.path.read_text(encoding="utf-8"))
        claims = doc if isinstance(doc, list) else doc.get("claims") or []
        errs = validate_registry(claims)
        if errs:
            print("INVALID")
            for e in errs:
                print(" ", e)
            raise SystemExit(1)
        print(f"VALID claims={len(claims)}")

    p_val.set_defaults(func=_validate)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
