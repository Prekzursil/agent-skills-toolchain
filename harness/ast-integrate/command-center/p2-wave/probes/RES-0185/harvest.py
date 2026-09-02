"""Harvest this program's recorded conclusions and their recorded lineage.

CLAIM-REGISTRY.json is absent. Support is taken from lineage fields on live
research artifacts, never by re-reading cited bodies. Distinct from RES-0128
(bucket source-class touch census).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lineage import locators_from_node, locators_from_top_level_lineage
from plants import plants

CLAIM_ARRAYS = (
    "claims",
    "bias_by_correction_table",
    "mechanisms",
)

HEADLINE_TEXT_KEYS = (
    "answer",
    "canonical_mechanism",
    "question_or_target",
    "question",
)

CLAIM_TEXT_KEYS = (
    "claim",
    "canonical_mechanism",
    "text",
    "correction",
    "question",
    "answer",
)

RESEARCH_GLOBS = (
    "command-center/research/*.json",
    "command-center/research/evidence-quality/*.json",
    "command-center/research/teardown/*.json",
    "command-center/research/gem-hunt/*.json",
    "command-center/research/deep-research-design/*.json",
)

SKIP_NAMES = {
    "RES-0185-evidence-map-coverage-holes.json",
}


def _unit_id(doc: dict, path: Path) -> str:
    for k in ("unit_id", "id", "unit"):
        v = doc.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return path.stem


def _text_from(obj: dict, keys: tuple[str, ...]) -> str:
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _claim_id(item: dict, unit: str, idx: int) -> str:
    for k in ("id", "claim_id"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return f"{unit}:{v.strip()}"
    return f"{unit}:claim-{idx:03d}"


def harvest_research(repo: Path) -> list[dict]:
    rows: list[dict] = []
    paths: list[Path] = []
    for pattern in RESEARCH_GLOBS:
        paths.extend(sorted(repo.glob(pattern)))
    seen: set[str] = set()
    for path in paths:
        if path.name in SKIP_NAMES:
            continue
        rel = path.relative_to(repo).as_posix()
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        unit = _unit_id(doc, path)
        children: list[dict] = []
        for arr_name in CLAIM_ARRAYS:
            items = doc.get(arr_name)
            if not isinstance(items, list):
                continue
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                text = _text_from(item, CLAIM_TEXT_KEYS)
                if not text:
                    continue
                cid = _claim_id(item, unit, idx)
                if cid in seen:
                    continue
                seen.add(cid)
                rec = {
                    "id": cid,
                    "unit_id": unit,
                    "kind": "nested-claim",
                    "plant": False,
                    "text": text[:800],
                    "origin_path": rel,
                    "lineage_records": locators_from_node(item),
                }
                children.append(rec)
                rows.append(rec)
        headline = _text_from(doc, HEADLINE_TEXT_KEYS)
        hid = f"{unit}:HEADLINE"
        if headline and hid not in seen:
            seen.add(hid)
            locs = locators_from_top_level_lineage(doc)
            if not locs:
                locs = [loc for c in children for loc in c["lineage_records"]]
            rows.append(
                {
                    "id": hid,
                    "unit_id": unit,
                    "kind": "headline",
                    "plant": False,
                    "text": headline[:800],
                    "origin_path": rel,
                    "lineage_records": locs,
                }
            )
    return rows


def harvest_claim_registry(repo: Path) -> tuple[bool, list[dict]]:
    path = repo / "command-center/CLAIM-REGISTRY.json"
    if not path.is_file():
        return False, []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True, []
    claims = doc
    if isinstance(doc, dict):
        claims = doc.get("claims") or doc.get("entries") or []
    if not isinstance(claims, list):
        return True, []
    rows: list[dict] = []
    for idx, item in enumerate(claims):
        if not isinstance(item, dict):
            continue
        text = _text_from(item, CLAIM_TEXT_KEYS + ("statement", "conclusion"))
        cid = str(item.get("id") or f"CLAIM-REGISTRY:{idx:03d}")
        rows.append(
            {
                "id": cid,
                "unit_id": "CLAIM-REGISTRY",
                "kind": "registry-claim",
                "plant": False,
                "text": (text or cid)[:800],
                "origin_path": "command-center/CLAIM-REGISTRY.json",
                "lineage_records": locators_from_node(item),
            }
        )
    return True, rows


def harvest(repo: Path) -> dict[str, Any]:
    registry_present, registry_rows = harvest_claim_registry(repo)
    research_rows = harvest_research(repo)
    plant_rows = plants()
    if registry_present and registry_rows:
        program = registry_rows + research_rows
        frame = "claim-registry-plus-research"
    else:
        program = research_rows
        frame = "research-artifacts-recorded-lineage"
    return {
        "frame": frame,
        "claim_registry_present": registry_present,
        "program_conclusions": program,
        "plants": plant_rows,
        "all_conclusions": program + plant_rows,
    }
