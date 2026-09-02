"""Semantic + JSON-Schema validator for the PROVISIONAL claim-record contract.

JSON Schema cannot express duplicate-of acyclicity or contradiction
referential integrity. Those rules live here and are the named tests
CC-0017 requires.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/claim-record.schema.json"
SCHEMA_PATH = REPO / SCHEMA_REL

_SCHEMA_CACHE: dict[str, Any] | None = None


def load_schema() -> dict[str, Any]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        _SCHEMA_CACHE = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _SCHEMA_CACHE


def schema_is_provisional(schema: dict[str, Any] | None = None) -> tuple[bool, str]:
    doc = schema if schema is not None else load_schema()
    status = str(doc.get("schema_status") or "")
    title = str(doc.get("title") or "")
    comment = str(doc.get("$comment") or "")
    superseded = str(doc.get("superseded_by_phase4_unit") or "")
    blob = " ".join([status, title, comment, superseded])
    if "PROVISIONAL" not in blob:
        return False, "schema-missing-PROVISIONAL"
    if superseded != "ARC-0085":
        return False, f"schema-superseded-by:{superseded!r} want ARC-0085"
    return True, "ARC-0085"


def jsonschema_errors(record: dict[str, Any]) -> list[str]:
    validator = jsonschema.Draft7Validator(load_schema())
    out: list[str] = []
    for err in validator.iter_errors(record):
        path = ".".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{path}: {err.message}")
    return out


def _settling_ok(record: dict[str, Any]) -> bool:
    sp = record.get("settling_probe")
    if not isinstance(sp, dict):
        return False
    ident = str(sp.get("id") or "").strip()
    cmd = str(sp.get("command") or "").strip()
    return bool(ident) and bool(cmd)


def _edge_ids(record: dict[str, Any], key: str) -> list[str]:
    raw = record.get(key) or []
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if str(x).strip()]


def duplicate_of_cycle(records: list[dict[str, Any]]) -> str | None:
    graph: dict[str, list[str]] = {}
    for rec in records:
        cid = str(rec.get("claim_id") or "")
        if not cid:
            continue
        graph[cid] = _edge_ids(rec, "duplicate_of")
        if cid in graph[cid]:
            return f"self-loop:{cid}"
    GRAY, BLACK = 1, 2
    color: dict[str, int] = {}

    def dfs(node: str) -> str | None:
        color[node] = GRAY
        for nxt in graph.get(node, []):
            state = color.get(nxt, 0)
            if state == GRAY:
                return f"{node}->{nxt}"
            if state == 0:
                graph.setdefault(nxt, [])
                hit = dfs(nxt)
                if hit:
                    return hit
        color[node] = BLACK
        return None

    for node in list(graph):
        if color.get(node, 0) == 0:
            hit = dfs(node)
            if hit:
                return hit
    return None


def dangling_edges(
    records: list[dict[str, Any]], keys: tuple[str, ...] = ("contradiction",)
) -> list[str]:
    ids = {str(r.get("claim_id") or "") for r in records}
    ids.discard("")
    errors: list[str] = []
    for rec in records:
        cid = str(rec.get("claim_id") or "?")
        for key in keys:
            for target in _edge_ids(rec, key):
                if target not in ids:
                    errors.append(f"{cid}.{key}->{target} nonexistent")
    return errors


def validate_record(record: Any) -> list[str]:
    if not isinstance(record, dict):
        return ["record-not-object"]
    errors = jsonschema_errors(record)
    if not _settling_ok(record):
        errors.append("settling_probe-missing-or-empty")
    cid = str(record.get("claim_id") or "")
    if cid and cid in _edge_ids(record, "duplicate_of"):
        errors.append(f"duplicate_of-self-loop:{cid}")
    return errors


def validate_record_set(records: list[Any]) -> list[str]:
    if not isinstance(records, list) or not records:
        return ["record-set-empty"]
    errors: list[str] = []
    seen: dict[str, int] = {}
    typed: list[dict[str, Any]] = []
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            errors.append(f"records[{i}]-not-object")
            continue
        typed.append(rec)
        errors.extend(f"records[{i}]:{e}" for e in validate_record(rec))
        cid = str(rec.get("claim_id") or "")
        if cid in seen:
            errors.append(f"duplicate-claim_id:{cid}")
        seen[cid] = i
    cycle = duplicate_of_cycle(typed)
    if cycle:
        errors.append(f"duplicate_of-cycle:{cycle}")
    errors.extend(dangling_edges(typed, keys=("contradiction",)))
    return errors


def fixture_record(
    claim_id: str,
    mechanism: str,
    *,
    duplicate_of: list[str] | None = None,
    contradiction: list[str] | None = None,
    support: list[str] | None = None,
    settling: bool = True,
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "claim_id": claim_id,
        "canonical_mechanism": mechanism,
        "duplicate_of": list(duplicate_of or []),
        "support": list(support or []),
        "contradiction": list(contradiction or []),
        "source_lineage": [
            {
                "path": "command-center/schema/claim-record.schema.json",
                "line": 1,
                "snippet": "PROVISIONAL Phase-1 canonical claim record",
            }
        ],
        "confidence": "high",
        "verification_status": "CONFIRMED",
        "implementation_impact": "correctness",
        "schema_version": "0.1.0-provisional",
    }
    if settling:
        rec["settling_probe"] = {
            "id": f"{claim_id}-settle",
            "command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/CC-0017/probe1_validate.py"
            ),
        }
    return rec
