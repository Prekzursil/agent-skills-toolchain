"""Fixture discovery corpus: colliding catalogs + one rename alias.

Ten source files, eight frozen identities. Ground truth is known by construction
so a merge bug cannot hide behind an unknown estate registry.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MIGRATION_MAP = {
    "WF-ZETA-OLD": "WF-ZETA",
}

# Sweep order is filename order. Kill-after-4 lands between delta and epsilon.
SOURCES: list[dict[str, Any]] = [
    {
        "file": "01-alpha.json",
        "id": "WF-ALPHA",
        "source_uri": "catalog-a://workflows/alpha",
        "title": "Alpha discovery",
        "family": "skill",
        "mechanism": "hook-gate",
        "body": "stable text for alpha",
    },
    {
        "file": "02-beta.json",
        "id": "WF-BETA",
        "source_uri": "catalog-a://workflows/beta",
        "title": "Beta discovery",
        "family": "skill",
        "mechanism": "scheduler",
        "body": "stable text for beta",
    },
    {
        "file": "03-gamma.json",
        "id": "WF-GAMMA",
        "source_uri": "catalog-a://workflows/gamma",
        "title": "Gamma discovery",
        "family": "plugin",
        "mechanism": "adapter",
        "body": "stable text for gamma",
    },
    {
        "file": "04-delta.json",
        "id": "WF-DELTA",
        "source_uri": "catalog-a://workflows/delta",
        "title": "Delta discovery",
        "family": "rule",
        "mechanism": "lint",
        "body": "stable text for delta",
    },
    {
        "file": "05-epsilon.json",
        "id": "WF-EPSILON",
        "source_uri": "catalog-a://workflows/epsilon",
        "title": "Epsilon discovery",
        "family": "workflow",
        "mechanism": "fusion",
        "body": "stable text for epsilon",
    },
    {
        "file": "06-alpha-collision.json",
        "id": "WF-ALPHA",
        "source_uri": "catalog-b://workflows/alpha",
        "title": "Alpha discovery",
        "family": "skill",
        "mechanism": "hook-gate",
        "body": "stable text for alpha",
    },
    {
        "file": "07-zeta-old.json",
        "id": "WF-ZETA-OLD",
        "source_uri": "catalog-a://workflows/zeta",
        "title": "Zeta pipeline",
        "family": "workflow",
        "mechanism": "compose",
        "body": "stable text for zeta",
    },
    {
        "file": "08-zeta.json",
        "id": "WF-ZETA",
        "source_uri": "catalog-b://workflows/zeta",
        "title": "Zeta pipeline",
        "family": "workflow",
        "mechanism": "compose",
        "body": "stable text for zeta",
    },
    {
        "file": "09-eta.json",
        "id": "WF-ETA",
        "source_uri": "catalog-a://workflows/eta",
        "title": "Eta discovery",
        "family": "skill",
        "mechanism": "probe",
        "body": "stable text for eta",
    },
    {
        "file": "10-theta.json",
        "id": "WF-THETA",
        "source_uri": "catalog-a://workflows/theta",
        "title": "Theta discovery",
        "family": "plugin",
        "mechanism": "cache",
        "body": "stable text for theta",
    },
]

EXPECTED_STABLE_IDS = [
    "WF-ALPHA",
    "WF-BETA",
    "WF-DELTA",
    "WF-EPSILON",
    "WF-ETA",
    "WF-GAMMA",
    "WF-THETA",
    "WF-ZETA",
]

N_SOURCES = len(SOURCES)
N_UNIQUE = len(EXPECTED_STABLE_IDS)
KILL_AFTER = 4
EPSILON_UPDATE_BODY = "upstream epsilon body changed after first sweep"
BETA_UPDATE_BODY = "upstream beta body changed; adjudication must survive"
ADJUDICATION = {
    "disposition": "ADOPT-AS-IS",
    "adjudicator": "human-ops",
    "note": "manual keep across colliding-catalog re-runs",
    "locked": True,
}


def materialize(root: Path) -> tuple[Path, Path]:
    """Write corpus JSON files and the migration map. Returns (corpus_dir, map_path)."""
    corpus = root / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    for src in SOURCES:
        payload = {k: v for k, v in src.items() if k != "file"}
        (corpus / src["file"]).write_text(
            json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
    map_path = root / "migration_map.json"
    map_path.write_text(
        json.dumps({"aliases": MIGRATION_MAP}, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return corpus, map_path


def rewrite_source(corpus: Path, filename: str, **fields: Any) -> None:
    path = corpus / filename
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc.update(fields)
    path.write_text(json.dumps(doc, sort_keys=True, indent=2) + "\n", encoding="utf-8")
