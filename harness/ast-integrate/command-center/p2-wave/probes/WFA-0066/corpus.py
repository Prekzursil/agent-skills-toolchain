"""Load the WFA-0066 mechanism vocabulary + incidence corpus.

Live WFA-0058 / WFA-0059 catalog artifacts are used when both exist and
carry definitions, held-out examples, and per-artifact incidence. Otherwise
the closed fixture is the input. The fixture is not a forged WFA-0058 receipt.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE = HERE / "fixtures" / "vocabulary.json"
LIVE_VOCAB = REPO / "command-center" / "wfa" / "WFA-0058-mechanism-vocabulary.json"
LIVE_EXTRACT = REPO / "command-center" / "wfa" / "WFA-0059-mechanism-extraction.json"
LIVE_VOCAB = LIVE_VOCAB
LIVE_EXTRACT = LIVE_EXTRACT


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _mechanisms_ok(rows: list) -> bool:
    if len(rows) < 2:
        return False
    for row in rows:
        if not isinstance(row, dict):
            return False
        if not str(row.get("id") or "").strip():
            return False
        if len(str(row.get("definition") or "")) < 24:
            return False
        examples = row.get("examples") or row.get("held_out_examples") or []
        if not isinstance(examples, list) or len(examples) < 1:
            return False
    return True


def _from_live() -> dict | None:
    if not LIVE_VOCAB.is_file() or not LIVE_EXTRACT.is_file():
        return None
    try:
        vocab = _load_json(LIVE_VOCAB)
        extract = _load_json(LIVE_EXTRACT)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(vocab, dict) or not isinstance(extract, dict):
        return None
    mechs = vocab.get("mechanisms") or vocab.get("vocabulary") or []
    if not isinstance(mechs, list) or not _mechanisms_ok(mechs):
        return None
    artifacts = extract.get("artifacts") or []
    if not isinstance(artifacts, list) or len(artifacts) < 2:
        matrix = extract.get("incidence") or extract.get("matrix")
        if isinstance(matrix, dict):
            artifacts = []
            for mid, arts in matrix.items():
                if not isinstance(arts, list):
                    continue
                for aid in arts:
                    artifacts.append(
                        {
                            "id": str(aid),
                            "upstream": "SOURCE-UNKNOWN",
                            "mechanisms": [str(mid)],
                        }
                    )
        elif isinstance(matrix, list):
            artifacts = []
            for row in matrix:
                if not isinstance(row, dict):
                    continue
                aid = str(row.get("artifact_id") or row.get("id") or "")
                mids = row.get("mechanisms") or row.get("mechanism_ids") or []
                if aid and isinstance(mids, list):
                    artifacts.append(
                        {
                            "id": aid,
                            "upstream": str(row.get("upstream") or "SOURCE-UNKNOWN"),
                            "mechanisms": [str(m) for m in mids],
                        }
                    )
    if not isinstance(artifacts, list) or len(artifacts) < 2:
        return None
    normalised = []
    for m in mechs:
        examples = m.get("examples") or m.get("held_out_examples") or []
        normalised.append(
            {
                "id": str(m["id"]),
                "name": str(m.get("name") or m["id"]),
                "definition": str(m["definition"]),
                "severity": int(m.get("severity") or 1),
                "decision_impact": int(m.get("decision_impact") or m.get("impact") or 1),
                "examples": [str(x) for x in examples if str(x).strip()],
            }
        )
    arts = []
    for a in artifacts:
        if not isinstance(a, dict):
            continue
        aid = str(a.get("id") or "")
        mids = a.get("mechanisms") or []
        if not aid or not isinstance(mids, list) or not mids:
            continue
        arts.append(
            {
                "id": aid,
                "upstream": str(a.get("upstream") or "SOURCE-UNKNOWN"),
                "mechanisms": [str(x) for x in mids],
            }
        )
    if len(normalised) < 2 or len(arts) < 2:
        return None
    return {
        "version": str(vocab.get("version") or "WFA-0058-live"),
        "source": "live-WFA-0058-WFA-0059",
        "live_vocab_present": True,
        "live_extract_present": True,
        "mechanisms": normalised,
        "artifacts": arts,
        "incidence_suspect_threshold": float(
            vocab.get("incidence_suspect_threshold") or 0.7
        ),
        "discrimination_accuracy_floor": float(
            vocab.get("discrimination_accuracy_floor") or 0.7
        ),
    }


def load_corpus() -> dict:
    live = _from_live()
    if live is not None:
        return live
    doc = _load_json(FIXTURE)
    if not isinstance(doc, dict):
        raise RuntimeError("WFA-0066 fixture unparseable")
    doc = dict(doc)
    doc["source"] = "closed-fixture"
    doc["live_vocab_present"] = LIVE_VOCAB.is_file()
    doc["live_extract_present"] = LIVE_EXTRACT.is_file()
    return doc


def mechanism_index(corpus: dict) -> dict[str, dict]:
    return {str(m["id"]): m for m in corpus["mechanisms"]}


def incidence_sets(corpus: dict) -> dict[str, set[str]]:
    sets: dict[str, set[str]] = {str(m["id"]): set() for m in corpus["mechanisms"]}
    for art in corpus["artifacts"]:
        aid = str(art["id"])
        for mid in art.get("mechanisms") or []:
            key = str(mid)
            if key in sets:
                sets[key].add(aid)
    return sets


def upstream_map(corpus: dict) -> dict[str, str]:
    return {str(a["id"]): str(a.get("upstream") or "SOURCE-UNKNOWN") for a in corpus["artifacts"]}
