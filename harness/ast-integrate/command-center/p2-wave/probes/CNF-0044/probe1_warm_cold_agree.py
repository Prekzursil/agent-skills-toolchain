#!/usr/bin/env python3
"""Probe 1: after rollback WITH invalidation, warm and cold resolve the same restored version."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0044-rollback-cache-coherence.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    run = S.agree()
    printable = {k: run[k] for k in sorted(run) if k != "pass"}
    print(json.dumps(printable, sort_keys=True, default=str)[:4000])
    if not run.get("pass"):
        print("FAILED:CNF-0044-probe1 warm and cold did not agree on restored version")
        return 1
    layout = run.get("cache_paths_enumerated") or []
    if not layout:
        print("FAILED:CNF-0044-probe1 cache paths were not enumerated from implementation")
        return 1
    warm_v = (run.get("warm") or {}).get("version")
    cold_v = (run.get("cold") or {}).get("version")
    restored = run.get("restored_version")
    print(
        f"warm={warm_v} cold={cold_v} restored={restored} "
        f"enumerated_paths={len(layout)} agree=True"
    )
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            print(f"FAILED:CNF-0044-probe1 self-declared {doc.get('state')}")
            return 1
        if doc.get("warm_cold_agree") is not True:
            print("FAILED:CNF-0044-probe1 artifact warm_cold_agree is not true")
            return 1
        art_w = (doc.get("warm_client") or {}).get("resolved_version")
        art_c = (doc.get("cold_client") or {}).get("resolved_version")
        if art_w != art_c or art_w != restored:
            print(
                f"FAILED:CNF-0044-probe1 artifact versions disagree "
                f"warm={art_w} cold={art_c} restored={restored}"
            )
            return 1
        enum = doc.get("cache_paths_enumerated") or []
        if not enum:
            print("FAILED:CNF-0044-probe1 artifact did not record enumerated cache paths")
            return 1
    print("SUCCESS:CNF-0044-probe1 warm-cold agree after rollback invalidation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
