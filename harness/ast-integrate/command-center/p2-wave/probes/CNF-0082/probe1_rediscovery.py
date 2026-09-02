#!/usr/bin/env python3
"""Probe 1: every declared source class has a plant and a found-or-blind verdict.

Plants must be on disk as workflow documents (discoverable by the declared
file walk), not merely listed in index.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import control as C  # noqa: E402
import scenario as S  # noqa: E402
import schema_local as SL  # noqa: E402

ART = REPO / S.OUT_REL


def main() -> int:
    live = C.run(REPO)
    if live["missing_plant"]:
        print(f"FAILED:CNF-0082-probe1 missing plant {live['missing_plant']}")
        return 1
    if live["missing_verdict"]:
        print(
            f"FAILED:CNF-0082-probe1 missing found-or-blind {live['missing_verdict']}"
        )
        return 1
    if live["index_injection"]["verdict"] != "silent":
        print("FAILED:CNF-0082-probe1 index ghosts returned")
        return 1
    for row in live["class_rows"]:
        cls = row["source_class"]
        plant_path = REPO / row["plant"]["path"]
        print(
            f"class={cls} on_disk={plant_path.is_file()} "
            f"verdict={row['verdict']} rank={row['plant_rank']} "
            f"rebuild={row['rebuild_rank']} ghosts={row['ghosts_returned']}"
        )
        if not plant_path.is_file():
            print(f"FAILED:CNF-0082-probe1 plant missing {cls}")
            return 1
        if row["verdict"] not in {"found", "blind"}:
            print(f"FAILED:CNF-0082-probe1 bad verdict {cls}={row['verdict']}")
            return 1
        if row["ghosts_returned"]:
            print(f"FAILED:CNF-0082-probe1 ghosts in {cls}")
            return 1
        if row["verdict"] == "found" and not row["ranked_above_rebuild"]:
            print(f"FAILED:CNF-0082-probe1 found-but-below-rebuild {cls}")
            return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0082-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    pay = SL.payload(doc)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0082-probe1 self-declared {doc.get('state')}")
        return 1
    if S.SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0082-probe1 sentinel absent")
        return 1
    art_classes = {
        c.get("source_class")
        for c in pay.get("controls") or []
        if c.get("kind") == "source-class-plant"
    }
    if art_classes != set(S.SOURCE_CLASSES):
        print(f"FAILED:CNF-0082-probe1 artifact classes {art_classes}")
        return 1
    if not pay.get("every_declared_class_planted"):
        print("FAILED:CNF-0082-probe1 every_declared_class_planted false")
        return 1
    if not pay.get("every_declared_class_has_found_or_blind"):
        print("FAILED:CNF-0082-probe1 found-or-blind flag false")
        return 1
    print(
        f"found={live['found_classes']} blind={live['blind_classes']} "
        f"prod={live['census'].get('production_present', live['census'].get('production_present'))}"
    )
    print("SUCCESS:CNF-0082-probe1 rediscovery plants found-or-blind")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
