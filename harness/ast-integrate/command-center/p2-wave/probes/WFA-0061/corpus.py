"""Load the fixture corpus and materialize per-artifact bodies for body reads."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CORPUS_PATH = HERE / "fixtures" / "corpus.json"
BODIES_DIR = HERE / "fixtures" / "bodies"


def load_corpus() -> dict[str, Any]:
    doc = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("corpus is not an object")
    return doc


def materialize_bodies(corpus: dict[str, Any] | None = None) -> list[Path]:
    """Write one JSON body per artifact so spot-checks read files, not the matrix."""
    corpus = corpus if corpus is not None else load_corpus()
    BODIES_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for rec in list(corpus.get("candidates") or []) + list(corpus.get("blueprints") or []):
        if not isinstance(rec, dict) or not rec.get("id"):
            continue
        path = BODIES_DIR / f"{rec['id']}.json"
        path.write_text(
            json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        written.append(path)
    return written


def body_path(artifact_id: str) -> Path:
    return BODIES_DIR / f"{artifact_id}.json"


def read_body(artifact_id: str) -> dict[str, Any]:
    path = body_path(artifact_id)
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"body {artifact_id} is not an object")
    return doc
