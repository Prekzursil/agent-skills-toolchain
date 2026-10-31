"""Bench cases: TST-0297 load_cases plus TST-0309 overlap corpus."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CORPUS_REL = "command-center/p2-wave/probes/TST-0309/fixtures/overlap-corpus.json"
N_OVERLAP = 50


def load_cases() -> list[dict]:
    return [
        {"id": "c1", "weight": 1.0},
        {"id": "c2", "weight": 1.0},
        {"id": "c3", "weight": 2.0},
        {"id": "c4", "weight": 3.0},
        {"id": "c5", "weight": 0.5},
    ]


def _cases() -> list[dict[str, Any]]:
    rows = []
    for i in range(N_OVERLAP):
        oracle = "match" if i < 25 else "mismatch"
        if i < 25:
            judge = "match"
        elif i < 32:
            judge = "match"
        else:
            judge = "mismatch"
        rows.append(
            {
                "id": f"C{i:02d}",
                "overlap": True,
                "oracle": oracle,
                "judge_a": judge,
                "judge_b": "mismatch" if 25 <= i < 32 else judge,
                "text": f"case-{i:02d} {oracle}",
            }
        )
    for i in range(10):
        rows.append(
            {
                "id": f"J{i:02d}",
                "overlap": False,
                "oracle": "match" if i % 2 == 0 else "mismatch",
                "judge_a": "match" if i % 2 == 0 else "mismatch",
                "judge_b": "mismatch" if i % 2 == 0 else "match",
                "text": f"judged-only-{i:02d}",
            }
        )
    return rows


def materialize_corpus(repo: Path | None = None, *args, **kwargs) -> Path:
    root = Path(repo) if repo is not None else Path(".")
    path = root / CORPUS_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"unit_id": "TST-0309", "n": N_OVERLAP, "cases": _cases()}
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return path


def load_corpus(repo: Path | None = None, *args, **kwargs) -> list[dict[str, Any]]:
    root = Path(repo) if repo is not None else Path(".")
    path = root / CORPUS_REL
    if path.is_file():
        doc = json.loads(path.read_text(encoding="utf-8"))
        cases = doc.get("cases") if isinstance(doc, dict) else doc
        if isinstance(cases, list) and len(cases) >= N_OVERLAP:
            return cases
    return _cases()


def overlap_only(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = [c for c in cases if c.get("overlap") is not False]
    if len(out) >= N_OVERLAP:
        return out[:N_OVERLAP]
    return [c for c in _cases() if c.get("overlap") is not False]


def judged_only(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in cases if c.get("overlap") is False]


def cases_by_id(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(c.get("id")): c for c in cases}
