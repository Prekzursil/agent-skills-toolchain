#!/usr/bin/env python3
"""Freeze the registry, then score every variant. Pin precedes measurement."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from corpus import CASES
from engine import run_variant, score_run
from registry import FIXTURES, freeze_registry, load_pinned_registry
from variants import GAMED_IDS, PRIMARY_GAMED_IDS, VARIANTS

HERE = Path(__file__).resolve().parent
RUNS = FIXTURES / "runs"


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, sort_keys=True) + "\n"
    path.write_text(text.replace("\r\n", "\n"), encoding="utf-8")


def run_campaign(*, freeze_first: bool = False) -> dict[str, Any]:
    """If freeze_first, write registry.json+pin then score. Else require pin."""
    freeze_order = []
    if freeze_first:
        _, pin = freeze_registry()
        freeze_order.append("write_registry_and_pin")
    else:
        _, pin = load_pinned_registry()
        freeze_order.append("load_existing_pin")
    freeze_order.append("score_variants")
    registry, live = load_pinned_registry(expected_sha=pin)
    if live != pin:
        raise RuntimeError("pin drifted between freeze and load")
    dump_json(FIXTURES / "cases.json", {"cases": CASES, "n": len(CASES)})
    traces: dict[str, list[dict]] = {}
    for name, fn in VARIANTS.items():
        traces[name] = run_variant(fn, CASES)
        dump_json(RUNS / f"{name}.json", {"variant": name, "trace": traces[name]})
    baseline = traces["honest_baseline"]
    scores = {
        name: score_run(name, tr, baseline, registry) for name, tr in traces.items()
    }
    gamed_naive_accept = [
        name
        for name in GAMED_IDS
        if scores[name]["naive_predicate"]["decision"] == "ACCEPT"
    ]
    gamed_fire = [
        name for name in GAMED_IDS if scores[name]["control"]["verdict"] == "FIRE"
    ]
    primary_fire = [
        name
        for name in PRIMARY_GAMED_IDS
        if scores[name]["control"]["verdict"] == "FIRE"
    ]
    honest_silent = scores["honest_baseline"]["control"]["verdict"] == "SILENT"
    genuine_gated = scores["genuine_improvement"]["gated_decision"] == "ACCEPT"
    return {
        "registry_sha256_before_first_run": pin,
        "freeze_order": freeze_order,
        "scores": scores,
        "gamed_naive_accept": gamed_naive_accept,
        "gamed_control_fire": gamed_fire,
        "primary_gamed_control_fire": primary_fire,
        "honest_control_silent": honest_silent,
        "genuine_gated_accept": genuine_gated,
        "n_cases": len(CASES),
        "n_visible": sum(1 for c in CASES if c["slice"] == "visible"),
        "n_heldout": sum(1 for c in CASES if c["slice"] == "held-out"),
    }
