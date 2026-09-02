"""Negative-control reducer: compute a result over present shards only.

This is the planted defect for TST-0148. It averages the present shards and
returns COMPLETE whenever at least one shard exists. It does not enumerate
missing ids. The production reducer must not behave like this; the probe
must reject this reducer on a 3-of-4 set.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def reduce_present_only(set_root: Path, manifest_path: Path) -> dict[str, Any]:
    """Average over whatever files exist. Missing shards are dropped, not named."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    scores: list[float] = []
    present_ids: list[str] = []
    for shard in manifest.get("shards") or []:
        if not isinstance(shard, dict):
            continue
        rel = str(shard.get("path") or "").replace("\\", "/")
        sid = str(shard.get("id") or "")
        path = Path(set_root) / Path(rel).name
        if path.is_file():
            present_ids.append(sid)
            scores.append(1.0)
    if not scores:
        return {
            "status": "INCOMPLETE",
            "score": 0.0,
            "present_ids": [],
            "computed_over_present": True,
            "evaluator": "present-only-average",
        }
    return {
        "status": "COMPLETE",
        "score": sum(scores) / len(scores),
        "present_ids": present_ids,
        "computed_over_present": True,
        "evaluator": "present-only-average",
    }
