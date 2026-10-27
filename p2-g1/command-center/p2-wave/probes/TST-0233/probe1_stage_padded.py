#!/usr/bin/env python3
"""TST-0233 probe 1: detector control - the stage-padded fusion is REJECTED.

fusion.padded carries wf.alpha's exact behaviour plus three noop stages; the
gate must REJECT with FC-11334. The more-stages complement fusion must be
ACCEPTED (stage count alone disqualifies nothing). fusion.degraded must be
REJECTED as FC-11333 and padded must NOT be classified as FC-11333.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from gate import evaluate_corpus  # noqa: E402


def verdict_of(report: dict, fusion_id: str) -> dict:
    for v in report["verdicts"]:
        if v["fusion_id"] == fusion_id:
            return v
    raise KeyError(fusion_id)


def main() -> int:
    report = evaluate_corpus()

    padded = verdict_of(report, "fusion.padded")
    degraded = verdict_of(report, "fusion.degraded")
    complement = verdict_of(report, "fusion.complement")

    checks = {
        "detector_control_stage_padded_rejected_FC_11334": padded["decision"] == "REJECT"
        and padded["failure_class"] == "FC-11334",
        "complement_more_stages_accepted": complement["decision"] == "ACCEPT"
        and complement["n_stages"] > max(
            report["results"][s]["n_stages"] for s in ("wf.alpha", "wf.beta")
        ),
        "degraded_rejected_FC_11333": degraded["decision"] == "REJECT"
        and degraded["failure_class"] == "FC-11333",
        "padded_not_classified_as_degraded": padded["failure_class"] != "FC-11333",
        "budget_parity_all": report["budget_parity"] is True,
        "stage_count_reported_not_scored": all(
            "n_stages" in v and v["failure_class"] != "FC-11334" or v["fusion_id"] != "fusion.complement"
            for v in report["verdicts"]
        ),
    }
    out = {
        "probe": "probe1_stage_padded",
        "unit": "TST-0233",
        "verdicts": report["verdicts"],
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe1_stage_padded.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
