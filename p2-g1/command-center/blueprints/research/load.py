"""Load research blueprint library and mixed corpora."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

FLAGSHIP_IDS = ("deep-research", "gem-hunt")


def _bp(bp_id: str, *, quota: int, stages: int, flagship: bool = False) -> dict[str, Any]:
    st = [{"id": f"s{i}", "kind": "stage", "params": {"i": i}} for i in range(stages)]
    edges = [[st[i]["id"], st[i + 1]["id"]] for i in range(len(st) - 1)]
    return {
        "id": bp_id,
        "tier": "flagship" if flagship else "standard",
        "declared_parameters": {"source_quota": quota, "depth": stages},
        "workflow": {"id": bp_id + "-wf", "stages": st, "edges": edges},
        "stopping_rules": {"mechanism": "quota-exhausted", "documented": "stop when quota is spent"},
        "example": {"question": f"example for {bp_id}"},
    }


def load_library() -> dict[str, dict[str, Any]]:
    return {
        "deep-research": _bp("deep-research", quota=12, stages=4, flagship=True),
        "gem-hunt": _bp("gem-hunt", quota=6, stages=3, flagship=True),
        "systematic-literature-review": _bp("systematic-literature-review", quota=20, stages=5),
        "rapid-literature-review": _bp("rapid-literature-review", quota=5, stages=3),
    }


def register_library(lib: dict[str, Any]) -> dict[str, Any]:
    failed = []
    from contract import register

    for bp_id, bp in lib.items():
        rec = register(bp)
        if not rec["ok"]:
            failed.append({"id": bp_id, "code": rec["code"]})
    return {"ok": not failed, "failed": failed, "n": len(lib)}


def load_corpus(kind: str = "mixed") -> list[dict[str, Any]]:
    rows = [
        {"id": "fav-1", "label": "favorable", "text": "positive prior art"},
        {"id": "neg-1", "label": "negative", "text": "contradicting result"},
        {"id": "fav-2", "label": "favorable", "text": "replication"},
    ]
    if kind == "all_favorable":
        return [r for r in rows if r["label"] == "favorable"]
    return rows
