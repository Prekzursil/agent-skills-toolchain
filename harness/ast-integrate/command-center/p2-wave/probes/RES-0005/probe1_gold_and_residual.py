#!/usr/bin/env python3
"""Probe 1: 30-pair graph, residual other < 10%, five gold pairs version_skew."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import edges as E  # noqa: E402

ART = REPO / "command-center/research/RES-0005.json"
SENTINEL = (
    "SUCCESS:RES-0005 in the receipt AND an edge-typed graph over 30 pairs "
    "with a printed residual rate and the five gold pairs correct"
)


def classify_pair(pair: dict) -> str | None:
    payload = {k: v for k, v in pair.items() if k != "gold"}
    return E.classify_edge(payload)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0005-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:RES-0005-probe1 sentinel-absent")
        return 1
    doc = json.loads(text)
    live_types = []
    live_by_id = {}
    for pair in C.PAIRS:
        et = classify_pair(pair)
        live_types.append(et)
        live_by_id[pair["id"]] = et
        stripped = classify_pair({**pair, "gold": False})
        if stripped != et:
            print(f"FAILED:RES-0005-probe1 gold-flag leaked into classifier id={pair['id']}")
            return 1
    if len(C.PAIRS) != 30:
        print(f"FAILED:RES-0005-probe1 corpus size {len(C.PAIRS)}")
        return 1
    stats = E.residual_stats(live_types)
    printed = (
        f"residual_other={stats['other']}/{stats['linked']} "
        f"residual_rate={stats['residual_rate']:.4f}"
    )
    print(printed)
    print(f"by_type={stats['by_type']}")
    if stats["linked"] != 30:
        print(f"FAILED:RES-0005-probe1 linked={stats['linked']} want 30")
        return 1
    if stats["residual_rate"] >= 0.10:
        print(f"FAILED:RES-0005-probe1 residual {stats['residual_rate']:.4f} not < 0.10")
        return 1
    gold_wrong = []
    for pid in C.GOLD_IDS:
        et = live_by_id[pid]
        ok = E.gold_classifies_ok(et)
        print(f"gold {pid} edge_type={et} ok={ok}")
        if not ok:
            gold_wrong.append(pid)
    if gold_wrong:
        print(f"FAILED:RES-0005-probe1 gold misclassified {gold_wrong}")
        return 1
    graph = doc.get("graph") or {}
    rec_edges = graph.get("edges") or []
    if len(rec_edges) != 30:
        print(f"FAILED:RES-0005-probe1 artifact graph size {len(rec_edges)}")
        return 1
    for row in rec_edges:
        live = live_by_id.get(row.get("id"))
        if live != row.get("edge_type"):
            print(
                f"FAILED:RES-0005-probe1 artifact drift id={row.get('id')} "
                f"live={live} recorded={row.get('edge_type')}"
            )
            return 1
    rec_printed = str(doc.get("printed_residual_rate") or graph.get("printed_residual_rate") or "")
    if "residual_rate=" not in rec_printed:
        print("FAILED:RES-0005-probe1 printed residual rate missing")
        return 1
    if not graph.get("five_gold_pairs_correct") or not doc.get("five_gold_pairs_correct"):
        print("FAILED:RES-0005-probe1 five_gold_pairs_correct not true")
        return 1
    print(
        "SUCCESS:RES-0005-probe1 edge-typed graph over 30 pairs "
        f"{printed} five gold pairs correct"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
