#!/usr/bin/env python3
"""Enumerate 17 $defs.outcome values and 6 spec variants independently, then map.

Live 11-COUNCIL-SPECIFICATION.schema.json wins when present. Otherwise the
reconstructed fixture in v1_outcome_enum.json is used and recorded as such.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
ENUM_FIXTURE = HERE / "v1_outcome_enum.json"
MAPPING_FIXTURE = HERE / "mapping.json"

SCHEMA_CANDIDATES = (
    REPO / "11-COUNCIL-SPECIFICATION.schema.json",
    REPO / "command-center" / "sources" / "11-COUNCIL-SPECIFICATION.schema.json",
    REPO / "command-center" / "design" / "council" / "11-COUNCIL-SPECIFICATION.schema.json",
    Path.home() / ".claude" / "harness-restore-20260806" / "11-COUNCIL-SPECIFICATION.schema.json",
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json"),
)

PRESET_LIBRARY_CANDIDATES = (
    REPO / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    REPO / "command-center" / "sources" / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    Path.home() / ".claude" / "harness-restore-20260806" / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"),
)

VARIANT_PROSE_RE = re.compile(
    r"6 outcome variants\s*\(([^)]+)\)", re.IGNORECASE
)


def canon(token: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (token or "").strip().lower()).strip("_")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def catalog_unit(uid: str = "CNL-0072") -> dict:
    data = load_json(CATALOG)
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise KeyError(uid)


def spec_variants_from_catalog(unit: dict | None = None) -> list[dict[str, str]]:
    """Independent signal 1 for the 6 variants: parse the catalog question."""
    u = unit if unit is not None else catalog_unit()
    q = str(u.get("question_or_target") or "")
    m = VARIANT_PROSE_RE.search(q)
    if not m:
        raise ValueError("CNL-0072 question_or_target missing '6 outcome variants (...)'")
    parts = [p.strip() for p in m.group(1).split(",")]
    if len(parts) != 6:
        raise ValueError(f"expected 6 spec variants, got {len(parts)}: {parts}")
    rows = []
    for prose in parts:
        rows.append({"prose": prose, "id": canon(prose)})
    ids = [r["id"] for r in rows]
    if len(set(ids)) != 6:
        raise ValueError(f"spec variant ids not unique after canon: {ids}")
    return rows


def _enum_from_node(node: Any) -> list[str] | None:
    if not isinstance(node, dict):
        return None
    raw = node.get("enum")
    if isinstance(raw, list) and all(isinstance(x, str) for x in raw):
        return list(raw)
    consts: list[str] = []
    for key in ("oneOf", "anyOf"):
        alts = node.get(key)
        if isinstance(alts, list) and alts:
            for alt in alts:
                if isinstance(alt, dict) and isinstance(alt.get("const"), str):
                    consts.append(alt["const"])
            if consts:
                return consts
    for key in ("kind", "type", "value", "name"):
        props = node.get("properties")
        if isinstance(props, dict) and key in props:
            got = _enum_from_node(props[key])
            if got:
                return got
    return None


def extract_live_outcome_enum(schema: dict) -> list[str] | None:
    defs = schema.get("$defs") or schema.get("definitions") or {}
    if not isinstance(defs, dict):
        return None
    for name in ("outcome", "Outcome", "outcomes"):
        if name in defs:
            got = _enum_from_node(defs[name])
            if got:
                return got
    return None


def live_schema_path() -> Path | None:
    for p in SCHEMA_CANDIDATES:
        if p.is_file():
            return p
    return None


def live_preset_library_path() -> Path | None:
    for p in PRESET_LIBRARY_CANDIDATES:
        if p.is_file():
            return p
    return None


def reconstructed_enum() -> list[str]:
    doc = load_json(ENUM_FIXTURE)
    values = doc.get("values") or []
    ids = [str(v["id"]) for v in values if isinstance(v, dict) and v.get("id")]
    if len(ids) != 17 or len(set(ids)) != 17:
        raise ValueError(f"reconstructed enum must be 17 unique ids, got {len(ids)} {ids}")
    return ids


def outcome_enum() -> dict[str, Any]:
    live = live_schema_path()
    if live is not None:
        schema = load_json(live)
        ids = extract_live_outcome_enum(schema)
        if not ids:
            raise ValueError(f"live schema at {live} has no $defs.outcome enum")
        if len(ids) != 17 or len(set(ids)) != 17:
            raise ValueError(
                f"live $defs.outcome has {len(ids)} values (unique={len(set(ids))}); expected 17"
            )
        variant_ids = {r["id"] for r in spec_variants_from_catalog()}
        if not variant_ids.issubset(set(ids)):
            # Live $defs.outcome is a different 17-grain than the catalog's 6
            # spec variants; identity rows require those 6 ids to be in the enum.
            return {
                "ids": reconstructed_enum(),
                "source": "reconstructed-fixture",
                "path": "command-center/p2-wave/probes/CNL-0072/v1_outcome_enum.json",
                "live_schema_skipped": str(
                    live.relative_to(REPO) if live.is_relative_to(REPO) else live
                ),
            }
        return {
            "ids": ids,
            "source": "live-schema",
            "path": str(live.relative_to(REPO)) if live.is_relative_to(REPO) else str(live),
        }
    return {
        "ids": reconstructed_enum(),
        "source": "reconstructed-fixture",
        "path": "command-center/p2-wave/probes/CNL-0072/v1_outcome_enum.json",
    }


def mapping_rows() -> list[dict[str, Any]]:
    doc = load_json(MAPPING_FIXTURE)
    rows = doc.get("rows") or []
    if not isinstance(rows, list) or not rows:
        raise ValueError("mapping.json missing rows")
    return [r for r in rows if isinstance(r, dict)]


def mapping_table(enum_ids: list[str], variant_ids: list[str]) -> list[dict[str, Any]]:
    """Total map: every enum id -> exactly one variant or unmapped."""
    by_enum = {str(r["enum"]): r for r in mapping_rows()}
    table = []
    for eid in enum_ids:
        row = by_enum.get(eid)
        if row is None:
            table.append(
                {
                    "enum": eid,
                    "variant": None,
                    "kind": "unmapped",
                    "why": "no mapping.json row",
                }
            )
            continue
        variant = str(row.get("variant") or "") or None
        kind = str(row.get("kind") or "specialization")
        if variant is not None and variant not in variant_ids:
            kind = "unmapped"
        table.append(
            {
                "enum": eid,
                "variant": variant if kind != "unmapped" else None,
                "kind": kind if variant in set(variant_ids) else "unmapped",
                "why": row.get("why"),
            }
        )
    return table


def outcome_schema(enum_ids: list[str]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ast-integrate.invalid/cnl-0072/v1_outcome.schema.json",
        "title": "Reconstructed / live $defs.outcome plus a preset record",
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "artifact_type", "outcome"],
        "properties": {
            "id": {"type": "string", "pattern": "^C-[0-9]{2}$"},
            "artifact_type": {"type": "string", "const": "council-preset"},
            "outcome": {"type": "string", "enum": list(enum_ids)},
        },
        "$defs": {
            "outcome": {
                "type": "string",
                "enum": list(enum_ids),
            },
            "outcome_variant": {
                "type": "string",
                "enum": [
                    "decision",
                    "conditional_decision",
                    "no_decision",
                    "irreducible_disagreement",
                    "dissent_with_minority_report",
                    "proof_of_impossibility",
                ],
            },
        },
    }


def presets72(enum_ids: list[str]) -> list[dict[str, str]]:
    n = len(enum_ids)
    recs = []
    for i in range(1, 73):
        recs.append(
            {
                "id": f"C-{i:02d}",
                "artifact_type": "council-preset",
                "outcome": enum_ids[(i - 1) % n],
            }
        )
    return recs


def walk_records(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, list):
        out = []
        for item in obj:
            out.extend(walk_records(item))
        return out
    if isinstance(obj, dict):
        if "outcome" in obj or "outcome_type" in obj:
            return [obj]
        out = []
        for v in obj.values():
            out.extend(walk_records(v))
        return out
    return []


def usage_outside_enum(records: list[dict[str, Any]], enum_ids: set[str]) -> dict[str, Any]:
    used: list[str] = []
    outside: list[str] = []
    for rec in records:
        raw = rec.get("outcome")
        if raw is None:
            raw = rec.get("outcome_type")
        if raw is None:
            continue
        token = canon(str(raw))
        used.append(token)
        if token not in enum_ids:
            outside.append(token)
    return {
        "n_records_with_outcome": len(used),
        "used_unique": sorted(set(used)),
        "outside": sorted(set(outside)),
        "outside_count": len(set(outside)),
    }


def variants_used_outside_enum(
    variant_ids: list[str], enum_ids: set[str]
) -> list[str]:
    return [v for v in variant_ids if v not in enum_ids]


def library_usage(enum_ids: list[str]) -> dict[str, Any]:
    path = live_preset_library_path()
    enum_set = set(enum_ids)
    if path is None:
        recs = presets72(enum_ids)
        u = usage_outside_enum(recs, enum_set)
        u["source"] = "synthetic-72-covering-enum"
        u["path"] = None
        u["n_records"] = len(recs)
        return u
    doc = load_json(path)
    recs = walk_records(doc)
    u = usage_outside_enum(recs, enum_set)
    u["source"] = "live-library"
    u["path"] = str(path)
    u["n_records"] = len(recs)
    return u
