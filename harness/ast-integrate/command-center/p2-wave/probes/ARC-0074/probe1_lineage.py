#!/usr/bin/env python3
"""Probe 1: lineage completeness, both-states, live artifact re-extract.

Good fusion: every borrowed id is in the source extract; justified NEW allowed.
Bad fusion: planted orphan fires; unjustified NEW fires.
Live WINNING-ARCHITECTURE.json is re-checked against live DESIGN extracts.
Losing-entry reviewer: A1-sourced fusion rows are a subset of A1 extract.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import compose as C  # noqa: E402

ART = REPO / C.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0074-probe1 {msg}")
    return 1


def main() -> int:
    good, good_src = C.fixture_fusion_good()
    good_lin = C.lineage_check(good, good_src)
    if not good_lin["ok"] or good_lin["orphan_count"] != 0:
        return fail(f"good-fixture lineage {good_lin}")

    orphan, orphan_src = C.fixture_fusion_orphan()
    orphan_lin = C.lineage_check(orphan, orphan_src)
    orphan_ids = {o["id"] for o in orphan_lin["orphans"]}
    if orphan_lin["ok"] or "SA:ghost-not-extracted" not in orphan_ids:
        return fail(f"orphan-fixture silent {orphan_lin}")

    unjust, unjust_src = C.fixture_fusion_unjustified_new()
    unjust_lin = C.lineage_check(unjust, unjust_src)
    unjust_ids = {u["id"] for u in unjust_lin["unjustified_new"]}
    if unjust_lin["ok"] or "H-SA-SB:unjustified" not in unjust_ids:
        return fail(f"unjustified-new silent {unjust_lin}")

    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("winning architecture missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:ARC-0074" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    if doc.get("unit_id") != "ARC-0074":
        return fail(f"unit_id {doc.get('unit_id')}")

    fusion = doc.get("mechanisms") or []
    if len(fusion) < 4:
        return fail(f"fusion too small {len(fusion)}")

    live = C.load_live_dossiers()
    sources = C.source_rows_from_live(live)
    live_lin = C.lineage_check(fusion, sources)
    if not live_lin["ok"]:
        return fail(f"live lineage {live_lin}")

    # Losing-entry architect (A1 lost capability-ssot): A1 rows ⊆ A1 extract.
    a1_ids = {m["id"] for m in sources.get("A1") or []}
    a1_fusion = [
        str(r["id"])
        for r in fusion
        if r.get("kind") == "borrowed" and r.get("source_architecture") == "A1"
    ]
    if not a1_fusion:
        return fail("no A1-sourced rows for losing-entry reviewer")
    extra = [i for i in a1_fusion if i not in a1_ids]
    if extra:
        return fail(f"A1 reviewer mismatch {extra}")

    recorded = (doc.get("tests") or {})
    if isinstance(recorded, list):
        t1 = next((t for t in recorded if "lineage" in str(t.get("id") or "")), None)
        if t1 is None:
            return fail("artifact missing lineage test row")

    print(
        json.dumps(
            {
                "good_ok": True,
                "orphan_fires": True,
                "unjustified_new_fires": True,
                "live_orphan_count": live_lin["orphan_count"],
                "live_borrowed": live_lin["borrowed"],
                "live_new": live_lin["new"],
                "a1_subset": True,
                "a1_rows": len(a1_fusion),
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"good_ok=True orphan_fires=True unjustified_new_fires=True "
        f"live_orphans={live_lin['orphan_count']} a1_subset=True"
    )
    print("SUCCESS:ARC-0074-probe1 lineage both-states live-reextract A1-subset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
