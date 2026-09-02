#!/usr/bin/env python3
"""Named probe 1: capability-set difference, lineage set-membership, re-score.

Live best-of-breed fusion over licensed sources. Capability tokens are
computed from stage/tool declarations. Every fused stage must name its
source and license. Recovered sources are re-scored on the matched case
set; the fusion must cover every case any source covers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from workflow_forge.decompose import (  # noqa: E402
    decompose,
    fuse_and_record,
    fusion_covers_source_cases,
    score_on_cases,
)
import fixtures as F  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0317-probe1 {msg}")
    return 1


def main() -> int:
    srcs = F.sources()
    cases = F.cases()
    fusion = fuse_and_record(srcs, F.evidence())
    if not fusion.get("ok"):
        return fail(f"fusion refused {fusion}")

    caps = fusion["capability_report"]
    if caps["blocking_finding"] or not caps["empty_difference"]:
        return fail(f"non-empty capability difference {caps['difference']}")

    lin = fusion["lineage_integrity"]
    if not lin["ok"]:
        return fail(f"lineage set-membership failed {lin}")
    if set(lin["fused_stage_ids"]) != set(lin["named_stage_ids"]):
        return fail(f"fused {lin['fused_stage_ids']} != named {lin['named_stage_ids']}")
    if set(lin["licenses_present"]) != {"Apache-2.0", "MIT"}:
        return fail(f"licenses {lin['licenses_present']} want Apache-2.0 and MIT")
    if set(lin["sources_named"]) != {s["id"] for s in srcs}:
        return fail(f"sources named {lin['sources_named']}")

    dec = decompose(fusion)
    if not dec["ok"]:
        return fail(f"decompose failed {dec}")
    if set(dec["recovered_ids"]) != {s["id"] for s in srcs}:
        return fail(f"recovered {dec['recovered_ids']}")

    source_scores = []
    for sid, component in dec["components"].items():
        scored = score_on_cases(component, cases)
        if scored["workflow_id"] != sid:
            return fail(f"score id {scored['workflow_id']} != {sid}")
        if any(not r["standalone_ok"] for r in scored["runs"]):
            return fail(f"recovered {sid} failed standalone {scored['runs']}")
        source_scores.append(scored)

    fusion_score = score_on_cases(fusion["workflow"], cases)
    if any(not r["standalone_ok"] for r in fusion_score["runs"]):
        return fail(f"fusion standalone failed {fusion_score['runs']}")
    cover = fusion_covers_source_cases(fusion_score, source_scores)
    if not cover["ok"]:
        return fail(f"fusion dropped source cases {cover['missing_from_fusion']}")

    if "tool:LicenseScan" not in caps["fusion"]:
        return fail("fusion dropped LicenseScan (cite capability)")
    if "tool:Glob" not in caps["fusion"]:
        return fail("fusion dropped Glob (retrieve capability)")

    payload = {
        "probe": "probe1-capability-and-lineage",
        "unit_id": "TST-0317",
        "difference": caps["difference"],
        "empty_difference": caps["empty_difference"],
        "per_source_sizes": {k: len(v) for k, v in caps["per_source"].items()},
        "fusion_size": len(caps["fusion"]),
        "lineage_ok": lin["ok"],
        "licenses": lin["licenses_present"],
        "recovered_ids": dec["recovered_ids"],
        "fusion_cases": cover["fusion_cases"],
        "union_source_cases": cover["union_source_cases"],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "difference=[] lineage_ok=True recovered="
        f"{dec['recovered_ids']} fusion_covers_union=True"
    )
    print(
        "SUCCESS:TST-0317-probe1 capability-set difference empty; "
        "lineage names source and license; recovered sources re-scored"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
