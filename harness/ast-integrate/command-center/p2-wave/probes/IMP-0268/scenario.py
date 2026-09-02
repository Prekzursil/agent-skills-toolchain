#!/usr/bin/env python3
"""Shared loaders for IMP-0268 named probes. Does not import selector scores."""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MODULE = REPO / "tools/council/participants/select_calibrated.py"
ART = REPO / "command-center/receipts/IMP-0268.json"
WARM = HERE / "fixtures/warm-store.json"
EMPTY = HERE / "fixtures/empty-store.json"
ZERO = HERE / "fixtures/zero-history-store.json"
HAND = HERE / "fixtures/hand_computed.json"
CANDIDATES = ["alice", "bob", "cara"]
LOG_CLIP = 1e-15


def load_selector() -> ModuleType:
    spec = importlib.util.spec_from_file_location("select_calibrated_imp0268", MODULE)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {MODULE}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def independent_brier(forecasts: list[tuple[float, int]]) -> float:
    return sum((p - o) ** 2 for p, o in forecasts) / len(forecasts)


def independent_log(forecasts: list[tuple[float, int]]) -> float:
    total = 0.0
    for p, o in forecasts:
        q = min(1.0 - LOG_CLIP, max(LOG_CLIP, p))
        total += -(o * math.log(q) + (1 - o) * math.log(1.0 - q))
    return total / len(forecasts)


def forecasts_from_store(store: dict, pid: str) -> list[tuple[float, int]]:
    rec = (store.get("participants") or {}).get(pid) or {}
    out: list[tuple[float, int]] = []
    for item in rec.get("forecasts") or []:
        out.append((float(item["p"]), int(item["outcome"])))
    return out


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require_receipt() -> dict:
    if not ART.is_file() or ART.stat().st_size <= 0:
        raise SystemExit("FAILED:IMP-0268 receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise SystemExit("FAILED:IMP-0268 receipt not an object")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:IMP-0268 self-declared {st}")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0268" not in text:
        raise SystemExit("FAILED:IMP-0268 sentinel absent")
    if doc.get("unit_id") != "IMP-0268":
        raise SystemExit(f"FAILED:IMP-0268 unit_id {doc.get('unit_id')}")
    return doc
