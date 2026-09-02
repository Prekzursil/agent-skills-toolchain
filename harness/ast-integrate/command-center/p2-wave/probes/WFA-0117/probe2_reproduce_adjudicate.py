#!/usr/bin/env python3
"""Named probe 2: reproduce three runs end to end and adjudicate splits.

Opens the sealed fusion-lane only after independent verdicts exist. Split
resolution must ignore votes. Insufficient evidence must default to REFUTED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import pipeline as P  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0117-fusion-independent-review.json"
UNIT = "WFA-0117"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:WFA-0117" not in json.dumps(doc):
        return fail("sentinel absent")

    live = P.live_independent()
    reproduced = P.reproduce_triple(live["records"])
    if len(reproduced) < 3:
        return fail("fewer than three reproductions", reproduced)
    if not all(r["input_hash_match"] and r["oracle_match"] for r in reproduced):
        return fail("reproduction mismatch", reproduced)

    art_runs = doc.get("reproduced_runs") or []
    if len(art_runs) < 3:
        return fail("artifact reproduced_runs < 3")
    art_ids = {r["run_id"] for r in art_runs}
    live_ids = {r["run_id"] for r in reproduced}
    if art_ids != live_ids:
        return fail("run_id set mismatch", {"art": sorted(art_ids), "live": sorted(live_ids)})

    flipped = dict(reproduced[0])
    flipped["recorded_oracle_pass"] = not flipped["recorded_oracle_pass"]
    if flipped["recorded_oracle_pass"] == flipped["live_oracle_pass"]:
        return fail("flipped-oracle control did not create a mismatch")

    sealed_pack = P.open_sealed_and_adjudicate(live)
    chosen = sealed_pack["chosen"]
    if chosen["fused_gaming"]["chosen"] != "VOID":
        return fail("gaming not VOID after adjudication", chosen["fused_gaming"])
    if chosen["fused_gaming"]["which_side_right"] != "independent":
        return fail("split not awarded to independent", chosen["fused_gaming"])
    if chosen["fused_gaming"]["resolved_by"] != "read-both-probes-not-vote":
        return fail("split not resolved by reading probes", chosen["fused_gaming"])
    if not chosen["fused_gaming"]["votes_ignored"]:
        return fail("votes were consulted")
    if chosen["fused_absent"]["chosen"] != "REFUTED":
        return fail("insufficient evidence did not default to REFUTED")
    if chosen["fused_complement"]["chosen"] != "PASS":
        return fail("complement not PASS")
    if chosen["fused_worse"]["chosen"] != "FAIL":
        return fail("worse not FAIL")

    art_split = {
        row["workflow_id"]: row["chosen"]
        for row in (doc.get("split_resolution") or {}).get("rows") or []
    }
    live_split = {wf: row["chosen"] for wf, row in chosen.items()}
    if art_split != live_split:
        return fail("artifact split != live", {"art": art_split, "live": live_split})

    print(
        json.dumps(
            {
                "probe": "probe2-reproduce-adjudicate",
                "reproduced": len(reproduced),
                "chosen": live_split,
                "pass": True,
            }
        )
    )
    print("SUCCESS:WFA-0117-probe2 reproduce and adjudicate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
