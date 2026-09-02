#!/usr/bin/env python3
"""Probe 2: sealed mapping lives outside the judge tree; residual is measured."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pipeline as P  # noqa: E402
from leakage import scan_tree  # noqa: E402
from residual import score as residual_score  # noqa: E402


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def main() -> int:
    if not P.MAP_PATH.is_file() or not P.ENTRIES_ROOT.is_dir():
        P.build()
    mapping = json.loads(P.MAP_PATH.read_text(encoding="utf-8"))
    live_hash = P.sha256_file(P.MAP_PATH)
    recorded = P.MAP_HASH_PATH.read_text(encoding="utf-8").strip()
    if live_hash != recorded:
        print(f"FAILED:ARC-0067-probe2 hash mismatch {live_hash} != {recorded}")
        return 1
    if is_under(P.MAP_PATH, P.JUDGE_ROOT):
        print("FAILED:ARC-0067-probe2 mapping is inside the judge-visible tree")
        return 1
    if list(P.JUDGE_ROOT.rglob("MAPPING.json")):
        print("FAILED:ARC-0067-probe2 MAPPING.json found under judge-visible tree")
        return 1
    labels = mapping.get("labels") or {}
    if len(labels) != 9:
        print(f"FAILED:ARC-0067-probe2 expected 9 labels, got {len(labels)}")
        return 1
    label_to_arch = {lab: meta["architecture_id"] for lab, meta in labels.items()}
    judge_scan = scan_tree(P.JUDGE_ROOT)
    if judge_scan["hit_count"] != 0:
        print(f"FAILED:ARC-0067-probe2 judge tree still leaks {judge_scan['hits'][:8]}")
        return 1
    sample = sorted(label_to_arch)[:3]
    residual = residual_score(P.ENTRIES_ROOT, label_to_arch, sample)
    if residual["attempts"] != 3:
        print("FAILED:ARC-0067-probe2 expected 3 residual attempts")
        return 1
    print(
        json.dumps(
            {
                "mapping_sha256": live_hash,
                "mapping_outside_judge_tree": True,
                "judge_leak_hits": 0,
                "residual_attempts": residual["attempts"],
                "residual_hits": residual["hits"],
                "residual_hit_rate": residual["hit_rate"],
                "blindness_claimed": False,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:ARC-0067-probe2 sealed-mapping and residual-identifiability")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
