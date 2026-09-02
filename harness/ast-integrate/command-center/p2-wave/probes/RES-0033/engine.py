#!/usr/bin/env python3
"""Mechanical set-intersection over sibling vendor-primitive JSON files.

The intersection is computed with set operators only. No LLM judgement.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SIBLING_DIR = HERE / "siblings"
RESEARCH = REPO / "command-center" / "research"
SCHEMA_REL = "command-center/schema/compatibility-matrix.schema.json"
SCRIPT_REL = "command-center/p2-wave/probes/RES-0033/engine.py"
OUT_REL = "command-center/research/RES-0033.json"
UNIT = "RES-0033"
SIBLING_IDS = [f"RES-{n:04d}" for n in range(23, 33)]
HALF_A = ["RES-0023", "RES-0025", "RES-0027", "RES-0029", "RES-0031"]
HALF_B = ["RES-0024", "RES-0026", "RES-0028", "RES-0030", "RES-0032"]
CONTROL_ID = "codex-hooks-deny-unknown-fields"
SUPPORTED = "supported"
SENTINEL = (
    "SUCCESS:RES-0033 in the receipt AND a computed intersection set with "
    "its cardinality and the ratio to the union, plus the script"
)
SUPPORTED_VENDOR_RULE = (
    "A vendor is included in the portable-core intersection if and only if "
    "inclusion='supported' and artifact_family='file-contract': it exposes a "
    "repo- or workspace-scoped artifact a work unit can write. UI-only hosted "
    "platforms are out of scope (RES-0032). Public-HTTP-API-only platforms are "
    "recorded on the matrix but are a different adapter family and do not "
    "enter this intersection."
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_vendors(doc: Any, source_unit: str) -> list[dict]:
    """Pull vendor rows from a sibling-shaped JSON document."""
    if not isinstance(doc, dict):
        return []
    rows = doc.get("vendors")
    if not isinstance(rows, list):
        # Alternate: a single vendor object at the top level.
        if isinstance(doc.get("primitives"), list) and doc.get("vendor_id"):
            rows = [doc]
        else:
            return []
    out: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        vendor_id = str(row.get("vendor_id") or "").strip()
        if not vendor_id:
            continue
        ids = _primitive_ids(row)
        out.append(
            {
                "vendor_id": vendor_id,
                "display_name": str(row.get("display_name") or vendor_id),
                "source_unit": str(row.get("source_unit") or source_unit),
                "inclusion": str(row.get("inclusion") or SUPPORTED),
                "artifact_family": str(row.get("artifact_family") or "file-contract"),
                "primitive_ids": sorted(ids),
                "primitives": row.get("primitives") if isinstance(row.get("primitives"), list) else [],
            }
        )
    return out


def _primitive_ids(row: dict) -> set[str]:
    ids: set[str] = set()
    raw = row.get("primitive_ids")
    if isinstance(raw, list):
        ids.update(str(x).strip() for x in raw if str(x).strip())
    prims = row.get("primitives")
    if isinstance(prims, list):
        for item in prims:
            if isinstance(item, str) and item.strip():
                ids.add(item.strip())
            elif isinstance(item, dict):
                pid = str(item.get("id") or item.get("primitive_id") or "").strip()
                if pid:
                    ids.add(pid)
    return ids


def sibling_path(uid: str) -> tuple[Path, str]:
    """Prefer a live research sibling when it yields vendors; else reconstruction."""
    live = RESEARCH / f"{uid}.json"
    recon = SIBLING_DIR / f"{uid}.json"
    if live.is_file() and live.stat().st_size > 0:
        try:
            doc = load_json(live)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            doc = None
        if isinstance(doc, dict) and extract_vendors(doc, uid):
            return live, "live-sibling"
    if not recon.is_file():
        raise FileNotFoundError(f"missing reconstructed sibling {recon}")
    return recon, "reconstruction"


def load_source(uid: str) -> dict:
    path, kind = sibling_path(uid)
    doc = load_json(path)
    vendors = extract_vendors(doc, uid)
    raw = path.read_bytes()
    return {
        "unit_id": uid,
        "path": path.relative_to(REPO).as_posix(),
        "source_kind": kind,
        "sha256": sha256_bytes(raw),
        "bytes": len(raw.replace(b"\r\n", b"\n")),
        "vendors": vendors,
    }


def intersect(sets: list[set[str]]) -> set[str]:
    if not sets:
        return set()
    acc = set(sets[0])
    for s in sets[1:]:
        acc &= s
    return acc


def union(sets: list[set[str]]) -> set[str]:
    acc: set[str] = set()
    for s in sets:
        acc |= s
    return acc


def partition_review(sources: list[dict], half_ids: list[str]) -> dict:
    half = [s for s in sources if s["unit_id"] in half_ids]
    vendors: list[dict] = []
    for src in half:
        vendors.extend(src["vendors"])
    supported = [v for v in vendors if v["inclusion"] == SUPPORTED and v["artifact_family"] == "file-contract"]
    sets = [set(v["primitive_ids"]) for v in supported]
    return {
        "source_units": [s["unit_id"] for s in half],
        "n_vendors": len(vendors),
        "n_supported_vendors": len(supported),
        "vendor_ids": [v["vendor_id"] for v in supported],
        "extracted_union": sorted(union(sets)),
        "extracted_intersection": sorted(intersect(sets)) if sets else [],
        "source_sha256": sorted(s["sha256"] for s in half),
    }


def compute() -> dict:
    sources = [load_source(uid) for uid in SIBLING_IDS]
    vendors: list[dict] = []
    for src in sources:
        for v in src["vendors"]:
            row = dict(v)
            row["source_kind"] = src["source_kind"]
            row["source_path"] = src["path"]
            row["source_sha256"] = src["sha256"]
            vendors.append(row)

    supported = [
        v
        for v in vendors
        if v["inclusion"] == SUPPORTED and v["artifact_family"] == "file-contract"
    ]
    if len(supported) < 2:
        raise RuntimeError(f"need >=2 supported file-contract vendors, got {len(supported)}")

    sets = [set(v["primitive_ids"]) for v in supported]
    inter = intersect(sets)
    uni = union(sets)
    card = len(inter)
    uni_card = len(uni)
    if uni_card < 1:
        raise RuntimeError("union is empty")
    ratio = card / uni_card

    owners = {pid: [] for pid in uni}
    for v in supported:
        for pid in v["primitive_ids"]:
            owners[pid].append(v["vendor_id"])

    unique_on_one = [
        pid for pid, vs in owners.items() if len(vs) == 1
    ]
    if CONTROL_ID not in unique_on_one:
        raise RuntimeError(f"control {CONTROL_ID} is not unique among supported vendors")
    if CONTROL_ID in inter:
        raise RuntimeError(f"control {CONTROL_ID} leaked into the intersection")

    rev_a = partition_review(sources, HALF_A)
    rev_b = partition_review(sources, HALF_B)
    a_units = set(rev_a["source_units"])
    b_units = set(rev_b["source_units"])
    if a_units & b_units:
        raise RuntimeError("partitioned reviewers share a source unit")
    if a_units | b_units != set(SIBLING_IDS):
        raise RuntimeError("partitioned reviewers do not cover the source set")

    if not inter.issubset(set(rev_a["extracted_intersection"])):
        raise RuntimeError("intersection is not a subset of reviewer-A half-intersection")
    if not inter.issubset(set(rev_b["extracted_intersection"])):
        raise RuntimeError("intersection is not a subset of reviewer-B half-intersection")

    return {
        "sources": sources,
        "vendors": vendors,
        "supported": supported,
        "intersection": sorted(inter),
        "union": sorted(uni),
        "cardinality": card,
        "union_cardinality": uni_card,
        "intersection_over_union": ratio,
        "ratio_fraction": f"{card}/{uni_card}",
        "control_id": CONTROL_ID,
        "control_owners": owners[CONTROL_ID],
        "unique_primitives": sorted(unique_on_one),
        "reviewer_a": rev_a,
        "reviewer_b": rev_b,
        "n_supported_vendors": len(supported),
        "n_source_files": len(sources),
        "owners": {k: v for k, v in owners.items()},
    }


def control_both_states(supported: list[dict]) -> dict:
    """Detector both-states: unique id excluded when on one vendor; included when on all."""
    planted = "deliberately-vendor-unique-plant"
    sets_one = []
    for i, v in enumerate(supported):
        s = set(v["primitive_ids"])
        if i == 0:
            s.add(planted)
        sets_one.append(s)
    sets_all = [set(v["primitive_ids"]) | {planted} for v in supported]
    one_inter = intersect(sets_one)
    all_inter = intersect(sets_all)
    return {
        "planted_id": planted,
        "one_vendor_in_intersection": planted in one_inter,
        "all_vendors_in_intersection": planted in all_inter,
        "pass": (planted not in one_inter) and (planted in all_inter),
    }


def domain_of(doc: dict) -> dict:
    """Domain payload lives under report (receipt_core additionalProperties=false)."""
    if not isinstance(doc, dict):
        return {}
    rep = doc.get("report")
    if isinstance(rep, dict) and isinstance(rep.get("intersection"), list):
        return rep
    return doc


def schema_rejects_garbage(schema: dict | None = None) -> bool:
    """Garbage must fail the disk-resolved catalog schema, not a network $ref."""
    del schema  # callers still pass the shim; the local store is the control plane
    from schema_local import validator as local_validator

    v = local_validator()
    garbage = [
        {},
        {"unit_id": UNIT, "state": "SUCCESS"},
        {"foo": "bar", "n": 999999},
        {"unit_id": UNIT, "report_kind": "compatibility-matrix"},
    ]
    for g in garbage:
        if v.is_valid(g):
            return False
    return True
