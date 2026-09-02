#!/usr/bin/env python3
"""Probe 2: configured rate records zero 429s; 529 must not cut concurrency."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scheduler as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0011-scheduler-report.json"


def main() -> int:
    cfg = S.SchedulerConfig()
    jobs = S.load_cohort(REPO)["jobs"]
    configured = S.run_scheduler(jobs, cfg, mode="configured")
    burst = S.run_scheduler(jobs, cfg, mode="burst")
    n429 = int(configured.rejections.get("429", 0))
    n529 = int(configured.rejections.get("529", 0))
    burst_429 = int(burst.rejections.get("429", 0))
    if n429 != 0:
        print(f"FAILED:CNF-0011-probe2 configured 429={n429}")
        return 1
    if burst_429 < 1:
        print("FAILED:CNF-0011-probe2 burst produced no 429s; rate cap is inert")
        return 1
    if n529 < 1:
        print("FAILED:CNF-0011-probe2 no 529 observed")
        return 1
    if configured.concurrency_cap_start != configured.concurrency_cap_end:
        print("FAILED:CNF-0011-probe2 concurrency cap changed")
        return 1
    if configured.concurrency_reductions != 0:
        print("FAILED:CNF-0011-probe2 concurrency reductions recorded")
        return 1
    if configured.forbidden_reduce_actions() != 0:
        print("FAILED:CNF-0011-probe2 forbidden reduce action in log")
        return 1
    caps = S.rate_caps(cfg, {j.vendor for j in jobs})
    if not caps:
        print("FAILED:CNF-0011-probe2 rate caps not recorded")
        return 1
    if not ART.is_file():
        print("FAILED:CNF-0011-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    pay = S.artifact_payload(doc)
    run = pay.get("configured_run") or {}
    art_429 = int((run.get("rejections_by_class") or {}).get("429", -1))
    if art_429 != 0:
        print(f"FAILED:CNF-0011-probe2 artifact 429={art_429}")
        return 1
    if not run.get("configured_rate_recorded"):
        print("FAILED:CNF-0011-probe2 artifact did not record the rate")
        return 1
    if not (pay.get("per_vendor_rate_caps") or {}):
        print("FAILED:CNF-0011-probe2 artifact missing per_vendor_rate_caps")
        return 1
    ctrl = pay.get("provider_529_control") or {}
    if ctrl.get("concurrency_reduced") is not False:
        print("FAILED:CNF-0011-probe2 artifact 529 reduced concurrency")
        return 1
    if int(ctrl.get("forbidden_reduce_actions_in_log", -1)) != 0:
        print("FAILED:CNF-0011-probe2 artifact log contains reduce-concurrency")
        return 1
    if int((pay.get("burst_control") or {}).get("rejections_429") or 0) < 1:
        print("FAILED:CNF-0011-probe2 artifact burst control missing 429s")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe2-quota-529",
                "pass": True,
                "configured_429": n429,
                "burst_429": burst_429,
                "observed_529": n529,
                "concurrency_start": configured.concurrency_cap_start,
                "concurrency_end": configured.concurrency_cap_end,
                "rate_caps": caps,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0011-probe2 zero 429 at recorded rate; 529 did not reduce concurrency")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
