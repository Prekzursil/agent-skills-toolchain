#!/usr/bin/env python3
"""Declared hold-out inventory for SYN-0012.

Catalog inputs (SYN-0011 adjudications, CLAIM-REGISTRY, ARTIFACT-MANIFEST)
are merged when present. When they are absent, the fixture corpus plus any
live corroborating files IS the declared inventory. A census of that
inventory is COMPLETE relative to what was declared, not a 40-source sample.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

ADJUDICATIONS = "command-center/synthesis/SYN-0011.adjudications.json"
CLAIM_REGISTRY = "command-center/CLAIM-REGISTRY.json"
ARTIFACT_MANIFEST = "command-center/ARTIFACT-MANIFEST.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
MEASURE = "command-center/p2-wave/_measure_one_delivered.py"
CORPUS = HERE / "fixtures" / "corpus.json"

SRC_LIVE_CATALOG = "SRC-LIVE-CATALOG"
SRC_LIVE_MEASURE = "SRC-LIVE-MEASURE"
C_G1_CONTRACT = "C-G1-CONTRACT"
C_CATALOG_ONLY = "C-CATALOG-ONLY"
C_PLANTED_FRAGILE = "C-PLANTED-FRAGILE"
C_ROBUST_TRIPLE = "C-ROBUST-TRIPLE"
C_PROBE_WINS_FLIP = "C-PROBE-WINS-FLIP"
C_PROBE_PAIR_ROBUST = "C-PROBE-PAIR-ROBUST"
SRC_FABRICATED = "SRC-ART-FABRICATED"


def _present(rel: str) -> bool:
    return (REPO / rel).is_file() and (REPO / rel).stat().st_size > 0


def input_status() -> dict:
    return {
        "adjudications_path": ADJUDICATIONS,
        "adjudications_present": _present(ADJUDICATIONS),
        "claim_registry_path": CLAIM_REGISTRY,
        "claim_registry_present": _present(CLAIM_REGISTRY),
        "artifact_manifest_path": ARTIFACT_MANIFEST,
        "artifact_manifest_present": _present(ARTIFACT_MANIFEST),
    }


def label_completeness(swept: int, declared: int) -> str:
    if declared <= 0:
        raise ValueError("declared inventory size must be positive")
    if swept < declared:
        return "SAMPLE"
    return "COMPLETE"


def _load_json(rel_or_path) -> object | None:
    path = rel_or_path if isinstance(rel_or_path, Path) else REPO / rel_or_path
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _as_source(row: dict) -> dict:
    sid = str(row.get("id") or "").strip()
    kind = str(row.get("kind") or "artifact").strip()
    if kind not in {"artifact", "agent", "probe"}:
        kind = "artifact"
    path = str(row.get("path") or "").replace("\\", "/")
    return {
        "id": sid,
        "kind": kind,
        "path": path,
        "fabricated": bool(row.get("fabricated")),
        "role": str(row.get("role") or "declared"),
        "present": bool(path) and _present(path) if kind == "artifact" else True,
    }


def _as_conclusion(row: dict) -> dict:
    keep = [str(x) for x in (row.get("keep") or []) if str(x).strip()]
    oppose = [str(x) for x in (row.get("oppose") or []) if str(x).strip()]
    return {
        "id": str(row.get("id") or "").strip(),
        "text": str(row.get("text") or "").strip(),
        "keep": keep,
        "oppose": oppose,
        "planted": str(row.get("planted") or ""),
        "origin": str(row.get("origin") or "fixture"),
    }


def _iter_manifest_paths(doc) -> list[str]:
    out: list[str] = []
    if isinstance(doc, list):
        rows = doc
    elif isinstance(doc, dict):
        rows = doc.get("artifacts") or doc.get("entries") or doc.get("sources") or []
    else:
        return out
    for a in rows:
        if isinstance(a, str) and a.strip():
            out.append(a.replace("\\", "/").strip())
        elif isinstance(a, dict):
            rel = str(a.get("path") or a.get("source") or a.get("id") or "").replace("\\", "/")
            if rel.strip():
                out.append(rel.strip())
    return out


def _iter_registry_claims(doc) -> list[dict]:
    if isinstance(doc, list):
        rows = doc
    elif isinstance(doc, dict):
        rows = (
            doc.get("claims")
            or doc.get("entries")
            or doc.get("records")
            or doc.get("settled")
            or []
        )
    else:
        return []
    return [r for r in rows if isinstance(r, dict)]


def _iter_adjudications(doc) -> list[dict]:
    if isinstance(doc, list):
        rows = doc
    elif isinstance(doc, dict):
        rows = (
            doc.get("adjudications")
            or doc.get("conclusions")
            or doc.get("settled")
            or doc.get("records")
            or []
        )
    else:
        return []
    return [r for r in rows if isinstance(r, dict)]


def _lineage_ids(claim: dict, path_to_id: dict[str, str]) -> list[str]:
    raw = (
        claim.get("source_lineage")
        or claim.get("sources")
        or claim.get("source_ids")
        or claim.get("anchors")
        or []
    )
    ids: list[str] = []
    if isinstance(raw, dict):
        raw = raw.get("sources") or raw.get("paths") or list(raw.values())
    if isinstance(raw, str):
        raw = [raw]
    for item in raw or []:
        if isinstance(item, dict):
            sid = str(item.get("id") or "").strip()
            rel = str(item.get("path") or "").replace("\\", "/").strip()
            if sid:
                ids.append(sid)
            elif rel and rel in path_to_id:
                ids.append(path_to_id[rel])
        elif isinstance(item, str) and item.strip():
            token = item.replace("\\", "/").strip()
            if token in path_to_id:
                ids.append(path_to_id[token])
            else:
                ids.append(token)
    seen: set[str] = set()
    out: list[str] = []
    for sid in ids:
        if sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out


def build_universe() -> dict:
    corpus = _load_json(CORPUS)
    if not isinstance(corpus, dict):
        raise RuntimeError("SYN-0012 fixture corpus missing or unparseable")

    sources: list[dict] = []
    seen: set[str] = set()

    def add_source(row: dict) -> None:
        src = _as_source(row)
        if not src["id"] or src["id"] in seen:
            return
        seen.add(src["id"])
        sources.append(src)

    for row in corpus.get("sources") or []:
        if isinstance(row, dict):
            add_source(row)

    status = input_status()
    manifest_doc = _load_json(ARTIFACT_MANIFEST) if status["artifact_manifest_present"] else None
    registry_doc = _load_json(CLAIM_REGISTRY) if status["claim_registry_present"] else None
    adj_doc = _load_json(ADJUDICATIONS) if status["adjudications_present"] else None

    if _present(CATALOG):
        add_source(
            {
                "id": SRC_LIVE_CATALOG,
                "kind": "artifact",
                "path": CATALOG,
                "fabricated": False,
                "role": "live-catalog",
            }
        )
    if _present(MEASURE):
        add_source(
            {
                "id": SRC_LIVE_MEASURE,
                "kind": "artifact",
                "path": MEASURE,
                "fabricated": False,
                "role": "live-g1-measure",
            }
        )

    manifest_added = 0
    if isinstance(manifest_doc, (dict, list)):
        for i, rel in enumerate(_iter_manifest_paths(manifest_doc)):
            sid = f"SRC-MANIFEST-{i:04d}"
            add_source(
                {
                    "id": sid,
                    "kind": "artifact",
                    "path": rel,
                    "fabricated": False,
                    "role": "artifact-manifest",
                }
            )
            manifest_added += 1

    conclusions: list[dict] = []
    cid_seen: set[str] = set()

    def add_conclusion(row: dict) -> None:
        con = _as_conclusion(row)
        if not con["id"] or con["id"] in cid_seen:
            return
        cid_seen.add(con["id"])
        conclusions.append(con)

    for row in corpus.get("conclusions") or []:
        if isinstance(row, dict):
            add_conclusion(row)

    if SRC_LIVE_CATALOG in seen and SRC_LIVE_MEASURE in seen:
        add_conclusion(
            {
                "id": C_G1_CONTRACT,
                "text": (
                    "G-1 delivery for a unit requires live named probes, a "
                    "non-BLOCKED catalog artifact, and a per-unit manifest row "
                    "whose sha256 matches the live artifact."
                ),
                "keep": [SRC_LIVE_CATALOG, SRC_LIVE_MEASURE],
                "oppose": [],
                "planted": "",
                "origin": "live",
            }
        )
    if SRC_LIVE_CATALOG in seen:
        add_conclusion(
            {
                "id": C_CATALOG_ONLY,
                "text": (
                    "WORK-UNIT-CATALOG.json names SYN-0012 as leave-one-source-out "
                    "sensitivity over the source inventory."
                ),
                "keep": [SRC_LIVE_CATALOG],
                "oppose": [],
                "planted": "",
                "origin": "live",
            }
        )

    path_to_id = {s["path"]: s["id"] for s in sources if s.get("path")}

    registry_added = 0
    if isinstance(registry_doc, (dict, list)):
        for i, claim in enumerate(_iter_registry_claims(registry_doc)):
            cid = str(claim.get("id") or claim.get("claim_id") or f"C-REGISTRY-{i:04d}")
            keep = _lineage_ids(claim, path_to_id)
            if not keep:
                continue
            text = str(claim.get("text") or claim.get("claim") or claim.get("statement") or cid)
            add_conclusion(
                {
                    "id": cid if cid.startswith("C-") else f"C-REG-{cid}",
                    "text": text[:400],
                    "keep": keep,
                    "oppose": [],
                    "planted": "",
                    "origin": "claim-registry",
                }
            )
            registry_added += 1

    adj_added = 0
    if isinstance(adj_doc, (dict, list)):
        for i, rec in enumerate(_iter_adjudications(adj_doc)):
            cid = str(rec.get("id") or rec.get("conclusion_id") or f"C-ADJ-{i:04d}")
            keep = _lineage_ids(rec, path_to_id)
            if not keep:
                anchors = rec.get("raw_anchor") or rec.get("anchor") or rec.get("anchors")
                keep = _lineage_ids({"anchors": anchors}, path_to_id) if anchors else []
            if not keep:
                continue
            text = str(rec.get("conclusion") or rec.get("verdict_text") or rec.get("text") or cid)
            add_conclusion(
                {
                    "id": cid if cid.startswith("C-") else f"C-ADJ-{cid}",
                    "text": text[:400],
                    "keep": keep,
                    "oppose": [],
                    "planted": "",
                    "origin": "syn-0011",
                }
            )
            adj_added += 1

    sources.sort(key=lambda s: s["id"])
    conclusions.sort(key=lambda c: c["id"])
    return {
        "sources": sources,
        "conclusions": conclusions,
        "input_status": status,
        "merge": {
            "manifest_sources_added": manifest_added,
            "registry_conclusions_added": registry_added,
            "adjudication_conclusions_added": adj_added,
        },
    }
