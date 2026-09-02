#!/usr/bin/env python3
"""Probe 1: live five-scanner replay yields must match the artifact."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from measure import historical_replays, run_bundle  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / (
    "command-center/research/supply-chain/"
    "RES-0133-secret-scanner-coverage-on-prose-artifacts.json"
)
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0133-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print(f"FAILED:RES-0133-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:RES-0133" not in text:
        print("FAILED:RES-0133-probe1 sentinel-absent")
        return 1

    bundle = run_bundle()
    live = historical_replays(bundle)
    shutil.rmtree(bundle["tmp"], ignore_errors=True)
    art_rows = doc.get("historical_replays") or []
    if len(art_rows) != 5 or len(live) != 5:
        print(f"FAILED:RES-0133-probe1 expected 5 replays art={len(art_rows)} live={len(live)}")
        return 1
    by_id = {r["run_id"]: r for r in art_rows}
    for row in live:
        art = by_id.get(row["run_id"])
        if not art:
            print(f"FAILED:RES-0133-probe1 missing run {row['run_id']}")
            return 1
        for field in ("path", "n_sources", "fired", "fire_index", "yields", "file_sha256"):
            if art.get(field) != row[field]:
                print(
                    f"FAILED:RES-0133-probe1 mismatch {row['run_id']}.{field} "
                    f"art={art.get(field)!r} live={row[field]!r}"
                )
                return 1
        print(
            f"replay {row['run_id']} n={row['n_sources']} fired={row['fired']} "
            f"idx={row['fire_index']} recall={row['recall']}"
        )
    print("SUCCESS:RES-0133-probe1 five scanner replays match live extract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
