"""Collect declared triples, filed refutations, and subtract."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from normalize import as_triple, triple_from_mapping

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLANTED = HERE / "fixtures" / "planted_filed.json"

TABLE_ROW = re.compile(
    r"^\|\s*(U-[A-Z0-9-]+)\s*\|\s*([A-Za-z0-9_-]+)\s*\|\s*`([^`]+)`",
    re.MULTILINE,
)


def _add(
    bag: set[tuple[str, str, str]],
    triple: tuple[str, str, str] | None,
) -> None:
    if triple is not None:
        bag.add(triple)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def declared_from_catalog_items(catalog: dict[str, Any]) -> set[tuple[str, str, str]]:
    """The triples DEPENDENCY-GRAPH.json would contain (catalog.py:build_graph)."""
    out: set[tuple[str, str, str]] = set()
    for item in catalog.get("items") or []:
        if not isinstance(item, dict):
            continue
        node = item.get("id")
        for dep in item.get("dependencies") or []:
            _add(out, as_triple(node, "blocked_by", dep))
    return out


def declared_from_work_units(catalog: dict[str, Any]) -> set[tuple[str, str, str]]:
    out: set[tuple[str, str, str]] = set()
    for unit in catalog.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        node = unit.get("id")
        for dep in unit.get("dependencies") or []:
            _add(out, as_triple(node, "depends_on", dep))
    return out


def declared_from_graph_file(path: Path) -> set[tuple[str, str, str]]:
    out: set[tuple[str, str, str]] = set()
    doc = load_json(path)
    if not isinstance(doc, dict):
        return out
    edges = doc.get("edges")
    if isinstance(edges, list):
        for edge in edges:
            if isinstance(edge, dict):
                _add(out, triple_from_mapping(edge))
    return out


def declared_from_claim_registry(path: Path) -> set[tuple[str, str, str]]:
    out: set[tuple[str, str, str]] = set()
    doc = load_json(path)
    if not isinstance(doc, dict):
        return out
    claims: Iterable[Any]
    if isinstance(doc.get("claims"), list):
        claims = doc["claims"]
    elif isinstance(doc.get("records"), list):
        claims = doc["records"]
    else:
        claims = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        cid = claim.get("id") or claim.get("claim_id")
        for key, rel in (
            ("duplicate_of", "duplicate_of"),
            ("duplicate-of", "duplicate_of"),
            ("contradicts", "contradicts"),
            ("contradiction", "contradicts"),
            ("supports", "supports"),
            ("support", "supports"),
        ):
            target = claim.get(key)
            if isinstance(target, list):
                for item in target:
                    _add(out, as_triple(cid, rel, item))
            elif target:
                _add(out, as_triple(cid, rel, target))
        _add(out, triple_from_mapping(claim))
    return out


def declared_from_unknowns(path: Path) -> set[tuple[str, str, str]]:
    out: set[tuple[str, str, str]] = set()
    if not path.is_file():
        return out
    text = path.read_text(encoding="utf-8")
    for match in TABLE_ROW.finditer(text):
        uid, claim_id, prereq = match.group(1), match.group(2), match.group(3)
        _add(out, as_triple(uid, "prerequisite_of", claim_id))
        _add(out, as_triple(uid, "blocked_by", prereq))
    return out


def declared_from_risk_register(path: Path) -> set[tuple[str, str, str]]:
    out: set[tuple[str, str, str]] = set()
    if not path.is_file():
        return out
    text = path.read_text(encoding="utf-8")
    for match in re.finditer(
        r"^\|\s*(R(?:ISK)?-[A-Z0-9-]+)\s*\|[^|]*\|\s*`?([^`|\n]+)`?",
        text,
        re.MULTILINE,
    ):
        _add(out, as_triple(match.group(1), "covers", match.group(2).strip()))
    return out


def collect_declared(repo: Path | None = None) -> tuple[set[tuple[str, str, str]], list[dict]]:
    root = repo or REPO
    catalog_path = root / "command-center" / "WORK-UNIT-CATALOG.json"
    catalog = load_json(catalog_path)
    if not isinstance(catalog, dict):
        catalog = {}

    item_triples = declared_from_catalog_items(catalog)
    wu_triples = declared_from_work_units(catalog)

    sources_spec = [
        (
            "command-center/DEPENDENCY-GRAPH.json",
            root / "command-center" / "DEPENDENCY-GRAPH.json",
            "graph",
        ),
        (
            "command-center/PHASE-GRAPH.json",
            root / "command-center" / "PHASE-GRAPH.json",
            "graph",
        ),
        (
            "command-center/CLAIM-REGISTRY.json",
            root / "command-center" / "CLAIM-REGISTRY.json",
            "claims",
        ),
        (
            "command-center/RISK-REGISTER.md",
            root / "command-center" / "RISK-REGISTER.md",
            "risk",
        ),
        (
            "command-center/UNKNOWNS-REGISTER.md",
            root / "command-center" / "UNKNOWNS-REGISTER.md",
            "unknowns",
        ),
    ]

    declared: set[tuple[str, str, str]] = set()
    declared |= item_triples
    declared |= wu_triples
    rows: list[dict] = [
        {
            "path": "command-center/WORK-UNIT-CATALOG.json#items",
            "present": catalog_path.is_file(),
            "triple_count": len(item_triples),
            "role": "dependency-graph-substitute",
            "note": (
                "command-center/DEPENDENCY-GRAPH.json is absent; triples are "
                "derived from catalog items with the catalog.py:build_graph rule "
                "(from, blocked_by)."
            ),
        },
        {
            "path": "command-center/WORK-UNIT-CATALOG.json#work_units",
            "present": catalog_path.is_file(),
            "triple_count": len(wu_triples),
            "role": "unit-dependency-edges",
        },
    ]

    for rel, path, kind in sources_spec:
        if kind == "graph":
            triples = declared_from_graph_file(path)
        elif kind == "claims":
            triples = declared_from_claim_registry(path)
        elif kind == "risk":
            triples = declared_from_risk_register(path)
        else:
            triples = declared_from_unknowns(path)
        declared |= triples
        rows.append(
            {
                "path": rel,
                "present": path.is_file(),
                "triple_count": len(triples),
                "role": "declared-source",
            }
        )

    return declared, rows


def harvest_b10(repo: Path, catalog: dict[str, Any]) -> tuple[list[dict], dict]:
    """Pull typed triples from live B10 output_path files if any exist."""
    records: list[dict] = []
    missing = 0
    present = 0
    adversarial = repo / "command-center" / "adversarial"
    seen_paths: set[str] = set()
    skip_rel = {
        "command-center/adversarial/ADV-0130-novelty-accounting.json",
    }
    for unit in catalog.get("work_units") or []:
        if not isinstance(unit, dict) or unit.get("bucket") != "B10":
            continue
        if unit.get("id") == "ADV-0130":
            continue
        rel = str(unit.get("output_path") or "").replace("\\", "/")
        if not rel or rel in skip_rel:
            continue
        path = repo / rel
        if not path.is_file():
            missing += 1
            continue
        present += 1
        seen_paths.add(rel)
        records.extend(_records_from_json(path, rel, source="b10-output"))
    if adversarial.is_dir():
        for path in sorted(adversarial.glob("*.json")):
            rel = path.relative_to(repo).as_posix()
            if rel in seen_paths or rel in skip_rel:
                continue
            if path.name.startswith("ADV-0130"):
                continue
            records.extend(_records_from_json(path, rel, source="adversarial-dir"))
    inventory = {
        "b10_units": sum(
            1
            for u in (catalog.get("work_units") or [])
            if isinstance(u, dict) and u.get("bucket") == "B10"
        ),
        "b10_output_present": present,
        "b10_output_absent": missing,
        "harvested_records": len(records),
        "adversarial_dir_present": adversarial.is_dir(),
    }
    return records, inventory


def _records_from_json(path: Path, rel: str, source: str) -> list[dict]:
    doc = load_json(path)
    out: list[dict] = []
    candidates: list[Any] = []
    if isinstance(doc, dict):
        if doc.get("unit_id") == "ADV-0130" or doc.get("kind") == "novelty-ledger":
            return []
        for key in ("filed", "refutations", "records", "edges", "triples", "claims"):
            val = doc.get(key)
            if isinstance(val, list):
                candidates.extend(val)
        if any(k in doc for k in ("subject_id", "from", "relation")):
            candidates.append(doc)
    elif isinstance(doc, list):
        candidates.extend(doc)
    for i, row in enumerate(candidates, 1):
        if not isinstance(row, dict):
            continue
        nested = row.get("triple") if isinstance(row.get("triple"), dict) else None
        triple = triple_from_mapping(nested) if nested else None
        if triple is None:
            triple = triple_from_mapping(row)
        rid = str(row.get("id") or f"{path.stem}-{i}")
        out.append(
            {
                "id": rid,
                "source": source,
                "path": rel,
                "raw": row,
                "plant_class": None,
                "triple": triple,
            }
        )
    return out


def load_plants() -> list[dict]:
    doc = json.loads(PLANTED.read_text(encoding="utf-8"))
    records = []
    for row in doc.get("records") or []:
        rec = dict(row)
        rec["triple"] = as_triple(
            rec.get("subject_id"), rec.get("relation"), rec.get("object_id")
        )
        records.append(rec)
    return records


def classify_filed(
    records: list[dict], declared: set[tuple[str, str, str]]
) -> list[dict]:
    out = []
    for rec in records:
        triple = rec.get("triple")
        if triple is None:
            classification = "UNNORMALISABLE"
        elif triple in declared:
            classification = "SUBTRACTED"
        else:
            classification = "NOVEL"
        item = dict(rec)
        item["classification"] = classification
        if triple is not None:
            item["triple"] = {
                "subject_id": triple[0],
                "relation": triple[1],
                "object_id": triple[2],
            }
            item["_tuple"] = triple
        else:
            item["triple"] = None
            item["_tuple"] = None
        out.append(item)
    return out


def subtract(
    classified: list[dict],
) -> tuple[set[tuple[str, str, str]], set[tuple[str, str, str]], list[dict]]:
    novel = {rec["_tuple"] for rec in classified if rec["classification"] == "NOVEL"}
    subtracted = {
        rec["_tuple"] for rec in classified if rec["classification"] == "SUBTRACTED"
    }
    unnorm = []
    for rec in classified:
        if rec["classification"] != "UNNORMALISABLE":
            continue
        raw = rec.get("raw_text") or rec.get("prose") or ""
        if not raw and rec.get("raw") is not None:
            raw = json.dumps(rec.get("raw"), ensure_ascii=False)[:500]
        unnorm.append(
            {"id": rec["id"], "raw_text": raw or "(empty)", "source": rec.get("source")}
        )
    return novel, subtracted, unnorm


def naive_text_would_subtract(rec: dict, declared: set[tuple[str, str, str]]) -> bool:
    """Payload-text matcher: true if prose mentions a declared (s,o) pair."""
    prose = str(rec.get("prose") or rec.get("raw_text") or "")
    if not prose:
        return False
    for s, _rel, o in declared:
        if s and o and s in prose and o in prose:
            return True
    return False


def run(repo: Path | None = None) -> dict:
    root = repo or REPO
    catalog = load_json(root / "command-center" / "WORK-UNIT-CATALOG.json")
    if not isinstance(catalog, dict):
        catalog = {}
    declared, sources = collect_declared(root)
    plants = load_plants()
    harvested, inventory = harvest_b10(root, catalog)
    filed_raw = plants + harvested
    classified = classify_filed(filed_raw, declared)
    novel, subtracted, unnorm = subtract(classified)
    filed_norm = {rec["_tuple"] for rec in classified if rec.get("_tuple")}
    collapse = (len(subtracted) / len(filed_norm)) if filed_norm else 0.0

    reassert_ids = [r["id"] for r in plants if r.get("plant_class") == "reassertion"]
    novelty_ids = [r["id"] for r in plants if r.get("plant_class") == "novelty"]
    uvm_ids = [r["id"] for r in plants if r.get("plant_class") == "use_vs_mention"]
    plant_classified = [r for r in classified if r.get("source") == "plant"]
    by_id = {r["id"]: r for r in plant_classified}

    re_ok = all(by_id[i]["classification"] == "SUBTRACTED" for i in reassert_ids)
    nov_ok = all(by_id[i]["classification"] == "NOVEL" for i in novelty_ids)
    uvm_id = uvm_ids[0] if uvm_ids else ""
    uvm_ok = bool(uvm_id) and by_id[uvm_id]["classification"] == "NOVEL"
    uvm_naive = bool(uvm_id) and naive_text_would_subtract(by_id[uvm_id], declared)
    detector_failure = not (re_ok and nov_ok)

    return {
        "declared": declared,
        "declared_sources": sources,
        "classified": classified,
        "novel": novel,
        "subtracted": subtracted,
        "unnormalisable": unnorm,
        "harvest": inventory,
        "counts": {
            "filed_records": len(classified),
            "filed_normalisable": len(filed_norm),
            "declared": len(declared),
            "novel": len(novel),
            "subtracted": len(subtracted),
            "unnormalisable": len(unnorm),
            "collapse_ratio": collapse,
        },
        "planted_controls": {
            "reassertion_ids": reassert_ids,
            "novelty_ids": novelty_ids,
            "use_vs_mention_id": uvm_id,
            "reassertion_all_subtracted": re_ok,
            "novelty_all_novel": nov_ok,
            "use_vs_mention_survived": uvm_ok,
            "naive_text_matcher_false_subtracts_uvm": uvm_naive,
            "detector_failure": detector_failure,
        },
    }
