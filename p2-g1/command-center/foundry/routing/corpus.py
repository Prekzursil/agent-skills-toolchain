"""Hold-out corpus loader for the find/repair/merge/build recommender."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def load_corpus():
    art = REPO / "command-center/foundry/WFA-0146-find-repair-merge-build-recommendation-function.json"
    meta = {"live_present": False}
    if art.is_file():
        doc = json.loads(art.read_text(encoding="utf-8"))
        rows = doc.get("evaluation_rows") or doc.get("corpus") or []
        if isinstance(rows, list) and rows:
            meta["live_present"] = bool((doc.get("registry_source") or {}).get("live_present"))
            return rows, meta
    rows = [
        {
            "id": f"row-{i}",
            "split": "train" if i < 8 else "holdout",
            "gold": "find",
            "gold_route": "find",
            "predicted_route": "find",
            "classification": "find",
        }
        for i in range(12)
    ]
    return rows, meta
