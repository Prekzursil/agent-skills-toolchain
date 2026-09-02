#!/usr/bin/env python3
"""Workflow-scout discovery step under test for WFA-0145.

Walks source-class directories and parses workflow JSON on disk. Plants are
ordinary files in the corpus; they are not injected into an in-memory index.
plants.json is never loaded here.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CORPUS = HERE / "fixtures" / "corpus"
SKIP_NAMES = frozenset({"plants.json", "goals.json"})
SOURCE_CLASSES = (
    "local",
    "repository",
    "marketplace",
    "public",
    "registry",
    "distractors",
)
SUPERIOR_MIN = 80
UNKNOWN_CLASS = "UNKNOWN-NEEDS-PROBE"


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def anchor_for(path: Path, token: str) -> dict:
    rel = _rel(path)
    text = path.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if token and token in line:
            return {
                "path": rel,
                "line": i,
                "anchor": f"{rel}:{i}",
                "snippet": line.strip()[:200],
                "ok": True,
            }
    return {
        "path": rel,
        "line": 1,
        "anchor": f"{rel}:1",
        "snippet": "",
        "ok": False,
    }


def _source_class_of(path: Path, corpus_root: Path) -> str:
    try:
        rel = path.resolve().relative_to(corpus_root.resolve())
    except ValueError:
        return "unknown"
    parts = rel.parts
    if parts and parts[0] in SOURCE_CLASSES:
        return parts[0]
    return "unknown"


def _quality(raw: dict) -> int:
    if "quality_score" in raw:
        return int(raw["quality_score"])
    classification = str(raw.get("classification") or "")
    if classification == UNKNOWN_CLASS:
        return 0
    if classification == "ADOPT-AS-IS":
        return 50
    return 40


def _normalize(raw: dict, path: Path, source_class: str) -> dict:
    wid = str(raw.get("id") or "")
    token = str(raw.get("recall_token") or wid)
    loc = anchor_for(path, token if token else wid)
    license_name = raw.get("license")
    if not license_name:
        license_name = "UNKNOWN"
    return {
        "id": wid,
        "name": str(raw.get("name") or wid),
        "mechanisms": [str(m) for m in (raw.get("mechanisms") or [])],
        "does": str(raw.get("does") or ""),
        "classification": str(raw.get("classification") or "ADOPT-AS-IS"),
        "quality_score": _quality(raw),
        "license": str(license_name),
        "maintenance": str(raw.get("maintenance") or "UNKNOWN"),
        "recall_token": token,
        "source_class": source_class,
        "source_path": _rel(path),
        "evidence_anchor": loc["anchor"],
        "evidence": loc,
        "superior": bool(raw.get("superior")),
        "raw_provenance": raw.get("provenance") or {},
    }


def parse_workflow_file(path: Path, corpus_root: Path) -> list[dict]:
    if path.name in SKIP_NAMES:
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    source_class = _source_class_of(path, corpus_root)
    rows: list[dict] = []
    if isinstance(data, dict) and isinstance(data.get("candidates"), list):
        for cand in data["candidates"]:
            if isinstance(cand, dict) and cand.get("id"):
                rows.append(_normalize(cand, path, source_class))
        return rows
    if isinstance(data, dict) and data.get("id") and "mechanisms" in data:
        return [_normalize(data, path, source_class)]
    return []


def load_workflows(
    corpus_root: Path | None = None,
    exclude_ids: frozenset[str] | None = None,
) -> list[dict]:
    root = corpus_root or CORPUS
    skip = exclude_ids or frozenset()
    found: list[dict] = []
    seen: set[str] = set()
    for path in sorted(root.rglob("*.json")):
        if not path.is_file():
            continue
        if path.name in SKIP_NAMES:
            continue
        for wf in parse_workflow_file(path, root):
            if not wf["id"] or wf["id"] in skip or wf["id"] in seen:
                continue
            seen.add(wf["id"])
            found.append(wf)
    return found


def covers(workflow: dict, required: list[str]) -> bool:
    if not required:
        return False
    have = set(workflow.get("mechanisms") or [])
    return set(required) <= have


def _rank_key(workflow: dict) -> tuple:
    return (-int(workflow.get("quality_score") or 0), str(workflow.get("id") or ""))


def recommend(ranked: list[dict]) -> dict:
    if not ranked:
        return {
            "route": "BUILD",
            "cite": None,
            "reason": "empty-ranked-set",
        }
    top = ranked[0]
    if int(top.get("quality_score") or 0) >= SUPERIOR_MIN:
        return {
            "route": "ADOPT",
            "cite": top["id"],
            "reason": "superior-existing-present",
        }
    return {
        "route": "BUILD",
        "cite": None,
        "reason": "no-superior-existing",
    }


def scout(
    goal: dict,
    workflows: list[dict] | None = None,
    mode: str = "live",
    corpus_root: Path | None = None,
    exclude_ids: frozenset[str] | None = None,
) -> dict:
    """Return ranked hits plus a route. mode=live|always-empty|always-same."""
    required = [str(m) for m in (goal.get("required_mechanisms") or [])]
    loaded = workflows if workflows is not None else load_workflows(
        corpus_root=corpus_root, exclude_ids=exclude_ids
    )
    if mode == "always-empty":
        ranked: list[dict] = []
        unknown: list[dict] = []
    elif mode == "always-same":
        pool = sorted(loaded, key=lambda w: str(w.get("id") or ""))
        ranked = [pool[0]] if pool else []
        unknown = []
    else:
        unknown = []
        ranked = []
        for wf in loaded:
            if not covers(wf, required):
                continue
            if wf.get("classification") == UNKNOWN_CLASS:
                unknown.append(wf)
                continue
            ranked.append(wf)
        ranked.sort(key=_rank_key)
    rec = recommend(ranked)
    return {
        "goal_id": goal.get("id"),
        "required_mechanisms": required,
        "ranked": [
            {
                "id": h["id"],
                "name": h["name"],
                "quality_score": h["quality_score"],
                "license": h["license"],
                "maintenance": h["maintenance"],
                "source_class": h["source_class"],
                "source_path": h["source_path"],
                "evidence_anchor": h["evidence_anchor"],
                "mechanisms": h["mechanisms"],
                "recall_token": h.get("recall_token"),
            }
            for h in ranked
        ],
        "unknown_needs_probe": [u["id"] for u in unknown],
        "recommendation": rec["route"],
        "cited_existing": rec["cite"],
        "recommendation_reason": rec["reason"],
        "mode": mode,
        "workflows_scanned": len(loaded),
    }


if __name__ == "__main__":
    import sys

    wfs = load_workflows()
    print(json.dumps({"scanned": len(wfs), "ids": [w["id"] for w in wfs]}, indent=2))
    raise SystemExit(0 if wfs else 1)
