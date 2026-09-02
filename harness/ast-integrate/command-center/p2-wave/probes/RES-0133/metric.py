"""Coverage-attained detector: rolling mean of per-plant detection bits."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PREREG_PATH = HERE / "prereg.json"


def load_prereg() -> dict[str, Any]:
    doc = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    if doc.get("recorded_before_any_replay_or_control") is not True:
        raise RuntimeError("preregistration was not frozen")
    if "early_max_index" not in doc and "early_max_index" in doc:
        doc["early_max_index"] = doc["early_max_index"]
    for key in ("window", "floor", "min_sources", "early_max_index"):
        if key not in doc:
            raise RuntimeError(f"prereg missing {key}")
    return doc


def fire_index(yields: list[int], window: int, floor: float, min_sources: int) -> int | None:
    """1-based index where rolling mean(detection) >= floor, else None."""
    n = len(yields)
    start = max(int(min_sources), int(window))
    for t in range(start, n + 1):
        chunk = yields[t - window : t]
        if len(chunk) < window:
            continue
        mean = sum(chunk) / float(window)
        if mean + 1e-12 >= float(floor):
            return t
    return None


def score_yields(yields: list[int], prereg: dict[str, Any] | None = None) -> dict[str, Any]:
    if prereg is None:
        prereg = load_prereg()
    window = int(prereg["window"])
    floor = float(prereg["floor"])
    min_sources = int(prereg["min_sources"])
    early_max = int(prereg["early_max_index"])
    idx = fire_index(yields, window, floor, min_sources)
    miss = sum(1 for y in yields if int(y) == 0)
    n = len(yields)
    return {
        "n_sources": n,
        "yields": [int(y) for y in yields],
        "fired": idx is not None,
        "fire_index": idx,
        "early": bool(idx is not None and idx <= early_max),
        "miss_count": miss,
        "miss_rate": (miss / n) if n else None,
        "recall": (1.0 - miss / n) if n else None,
        "window": window,
        "floor": floor,
        "min_sources": min_sources,
    }


def detection_bits(records: list[dict], hit_rels: set[str]) -> list[int]:
    bits = []
    for rec in records:
        rel = rec.get("relpath") or rec.get("filename")
        bits.append(1 if rel in hit_rels else 0)
    return bits


def precision_recall(plants: list[dict], decoys: list[dict], hit_rels: set[str]) -> dict:
    tp = sum(1 for p in plants if p["relpath"] in hit_rels)
    fn = len(plants) - tp
    fp = sum(1 for d in decoys if d["relpath"] in hit_rels)
    tn = len(decoys) - fp
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "true_positives": tp,
        "false_negatives": fn,
        "false_positives": fp,
        "true_negatives": tn,
        "n_plants": len(plants),
        "n_decoys": len(decoys),
        "precision": prec,
        "recall": rec,
        "decoy_classifications": [
            {
                "plant_id": d["plant_id"],
                "label": d.get("label"),
                "flagged": d["relpath"] in hit_rels,
                "class": "FP" if d["relpath"] in hit_rels else "TN",
            }
            for d in decoys
        ],
    }
