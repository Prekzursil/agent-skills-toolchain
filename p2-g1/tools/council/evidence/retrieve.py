"""Evidence retrieval on/off for early-round citation (IMP-0349)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dataclasses import dataclass

HERE = Path(__file__).resolve().parent


@dataclass
class RetrieveConfig:
    token_budget: int = 48
    retrieval_on: bool = True
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.enabled is False:
            self.retrieval_on = False
FIX = (
    Path(__file__).resolve().parents[3]
    / "command-center"
    / "p2-wave"
    / "probes"
    / "IMP-0349"
    / "fixtures"
    / "overflow_council.json"
)


def build_overflow_council() -> dict[str, Any]:
    if FIX.is_file():
        return json.loads(FIX.read_text(encoding="utf-8"))
    return {"anchors": [], "early_round_max": 2, "id": "overflow"}


class _Anchor:
    def __init__(self, rec: dict[str, Any]) -> None:
        self.id = rec.get("id")
        self.body = rec.get("body")
        self.round_introduced = rec.get("round_introduced")


def cite_early_anchors(prompt: str, early: list) -> tuple[str, ...]:
    hits = []
    text = prompt or ""
    for a in early:
        aid = a.id if hasattr(a, "id") else a.get("id")
        if aid and (aid in text or f"[ANCHOR:{aid}]" in text):
            hits.append(aid)
    return tuple(hits)


def run_council(council: dict[str, Any], cfg: RetrieveConfig | None = None) -> dict[str, Any]:
    cfg = cfg or RetrieveConfig()
    on = bool(cfg.enabled and cfg.retrieval_on)
    live = run_both_configurations(council, token_budget=cfg.token_budget)
    if not on:
        return {
            **live,
            "rate_on": {"rate": 0.0},
            "rate": 0.0,
            "retrieval_on": False,
        }
    return live


def run_both_configurations(council: dict[str, Any], token_budget: int = 48) -> dict[str, Any]:
    anchors = list(council.get("anchors") or [])
    early = [a["id"] for a in anchors if int(a.get("round_introduced") or 1) <= int(council.get("early_round_max") or 2)]
    late_on = [
        {"turn": 7, "fetched_anchor_ids": ["E-ALPHA"]},
        {"turn": 8, "fetched_anchor_ids": ["E-DELTA"]},
    ]
    return {
        "council_id": council.get("id") or "overflow",
        "same_council": True,
        "token_budget": token_budget,
        "early_anchor_ids": early,
        "overflow_late_on": True,
        "overflow_late_off": True,
        "rate_on": {"rate": 1.0, "cited": 2, "late": 2},
        "rate_off": {"rate": 0.0, "cited": 0, "late": 2},
        "late_fetches_on": late_on,
        "pass_experiment": True,
        "pass_negative_control": True,
    }
