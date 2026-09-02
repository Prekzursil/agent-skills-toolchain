#!/usr/bin/env python3
"""Named probe 2: hybrid that file-count calls healthy must fail coherence.

Mechanically different from probe 1: does not roll back; leaves the
file_copy window in place and scores the two health implementations.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from trial import catalog_hybrid, run_hybrid_control  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0043-partial-upgrade-rollback.json"
SENTINEL = (
    "SUCCESS:CNF-0043 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and all three kill points were "
    "exercised and each has a recorded post-rollback health-check result. Any "
    "other terminal state is FAILED:CNF-0043 <classification> with the "
    "diagnostic tail attached."
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0043-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:CNF-0043-probe2 sentinel absent")
        return 1

    recorded = catalog_hybrid(doc)
    if not recorded.get("discriminated"):
        print("FAILED:CNF-0043-probe2 artifact hybrid not discriminated")
        return 1
    if recorded.get("naive_file_count", {}).get("kind") != "file-count-only":
        print("FAILED:CNF-0043-probe2 artifact missing file-count control")
        return 1
    if recorded.get("coherence_against_n", {}).get("ok") is not False:
        print("FAILED:CNF-0043-probe2 artifact coherence did not fail hybrid")
        return 1

    live = run_hybrid_control()
    if not live.get("kill_landed"):
        print("FAILED:CNF-0043-probe2 hybrid kill did not land")
        print(json.dumps(live, indent=2, default=str)[:2000])
        return 1
    if live.get("naive_file_count", {}).get("ok") is not True:
        print("FAILED:CNF-0043-probe2 file-count control was not healthy on hybrid")
        return 1
    if live.get("coherence_against_n", {}).get("ok") is not False:
        print("FAILED:CNF-0043-probe2 coherence reported healthy on hybrid")
        return 1
    if live.get("coherence_against_n", {}).get("hybrid") is not True:
        print("FAILED:CNF-0043-probe2 coherence missed hybrid flag")
        return 1
    if not live.get("discriminated"):
        print("FAILED:CNF-0043-probe2 control did not discriminate")
        return 1

    rec_obs = recorded.get("observed") or {}
    live_obs = live.get("observed") or {}
    if rec_obs != live_obs:
        print("FAILED:CNF-0043-probe2 observed-version drift")
        print("live", live_obs, "artifact", rec_obs)
        return 1

    out = {
        "probe": "probe2-hybrid",
        "unit_id": "CNF-0043",
        "naive_file_count_ok": True,
        "coherence_ok": False,
        "hybrid": True,
        "discriminated": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "hybrid files={files} manifest={manifest} cache={cache} "
        "file_count_ok=True coherence_ok=False".format(**live_obs)
    )
    print("SUCCESS:CNF-0043-probe2 hybrid false-healthy discriminated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
