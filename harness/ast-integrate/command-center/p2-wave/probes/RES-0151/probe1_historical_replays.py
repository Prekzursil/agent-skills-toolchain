#!/usr/bin/env python3
"""Probe 1: live replay of five prior documents must match the artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpora import load_historical_runs  # noqa: E402
from metric import load_prereg, score_run  # noqa: E402

ART = REPO / (
    "command-center/research/evidence-quality/"
    "RES-0151-evidence-saturation-stopping-metric.json"
)
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0151-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print(f"FAILED:RES-0151-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:RES-0151" not in text:
        print("FAILED:RES-0151-probe1 sentinel-absent")
        return 1

    prereg = load_prereg()
    live = []
    for run in load_historical_runs():
        scored = score_run(run["sources"], prereg)
        live.append(
            {
                "run_id": run["run_id"],
                "path": run["path"],
                "n_sources": scored["n_sources"],
                "fired": scored["fired"],
                "fire_index": scored["fire_index"],
                "miss_count": scored["miss_count"],
                "total_distinct": scored["total_distinct"],
                "yields": scored["yields"],
                "file_sha256": run["file_sha256"],
            }
        )
    art_rows = doc.get("historical_replays") or []
    if len(art_rows) != 5 or len(live) != 5:
        print(f"FAILED:RES-0151-probe1 expected 5 replays art={len(art_rows)} live={len(live)}")
        return 1
    by_id = {r["run_id"]: r for r in art_rows}
    for row in live:
        art = by_id.get(row["run_id"])
        if not art:
            print(f"FAILED:RES-0151-probe1 missing run {row['run_id']}")
            return 1
        for field in ("path", "n_sources", "fired", "fire_index", "miss_count", "yields", "file_sha256"):
            if art.get(field) != row[field]:
                print(
                    f"FAILED:RES-0151-probe1 mismatch {row['run_id']}.{field} "
                    f"art={art.get(field)!r} live={row[field]!r}"
                )
                return 1
        if not art.get("resolved_url") or not art.get("fetch_timestamp"):
            print(f"FAILED:RES-0151-probe1 lineage missing on {row['run_id']}")
            return 1
        if not isinstance(art.get("sha256") or art.get("file_sha256"), str):
            print(f"FAILED:RES-0151-probe1 sha missing on {row['run_id']}")
            return 1
        print(
            f"replay {row['run_id']} n={row['n_sources']} fired={row['fired']} "
            f"idx={row['fire_index']} miss={row['miss_count']} "
            f"distinct={row['total_distinct']}"
        )
    print("SUCCESS:RES-0151-probe1 five historical replays match live extract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
